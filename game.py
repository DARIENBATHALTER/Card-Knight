import os
import math
import random
import threading
import subprocess
import pygame
import constants as C
import fonts
import sprite_manager as SM
from battle import Battle
from overworld import Overworld

_BASE = os.path.dirname(os.path.abspath(__file__))


class _AfplayMusic:
    """Looping background music via macOS afplay — no pygame.mixer needed."""

    def __init__(self):
        self._proc   = None
        self._path   = None
        self._active = False
        self._thread = None

    def play(self, path: str, volume: float = 0.75):
        self.stop()
        self._path   = path
        self._active = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        vol_arg = str(round(max(0.0, min(1.0, 1.0)), 2))  # afplay vol is 0-1 via -v
        while self._active and self._path:
            try:
                self._proc = subprocess.Popen(
                    ['afplay', '-v', vol_arg, self._path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._proc.wait()
            except Exception:
                break

    def stop(self):
        self._active = False
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None


_music = _AfplayMusic()

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False

# Bayer 4×4 ordered dithering matrix, normalized to [-0.5, 0.5]
_BAYER = None
if _NUMPY:
    _BAYER = (np.array([
        [ 0,  8,  2, 10],
        [12,  4, 14,  6],
        [ 3, 11,  1,  9],
        [15,  7, 13,  5],
    ], dtype=np.float32) / 16.0) - 0.5

# Cache for pre-computed gradient shapes: (w, h) -> float32 array [0..1]
_GLOW_SHAPES: dict = {}


def _soft_glow(dest: pygame.Surface, cx: int, cy: int,
               w: int, h: int, rgb: tuple, max_alpha: int,
               power: float = 2.0, dither_strength: int = 0) -> None:
    """
    Blit a smooth radial gradient ellipse onto dest, centered at (cx, cy).

    power          — falloff curve (2.0 = quadratic, higher = tighter core)
    dither_strength — alpha jitter range for Bayer dithering (0 = off, 12 = subtle)
    """
    if max_alpha <= 0 or w < 2 or h < 2:
        return

    if _NUMPY:
        key = (w, h)
        if key not in _GLOW_SHAPES:
            yy, xx = np.mgrid[0:h, 0:w]
            dx = (xx - w / 2) / max(1, w / 2)
            dy = (yy - h / 2) / max(1, h / 2)
            dist = np.clip(np.sqrt(dx * dx + dy * dy), 0.0, 1.0)
            _GLOW_SHAPES[key] = (1.0 - dist) ** power
        shape = _GLOW_SHAPES[key]

        alpha_f = shape * max_alpha
        if dither_strength and _BAYER is not None:
            tile = np.tile(_BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
            alpha_f = alpha_f + tile * dither_strength
        alpha = np.clip(alpha_f, 0, 255).astype(np.uint8)

        r, g, b = rgb
        arr = np.empty((h, w, 4), dtype=np.uint8)
        arr[:, :, 0] = r
        arr[:, :, 1] = g
        arr[:, :, 2] = b
        arr[:, :, 3] = alpha

        gsurf = pygame.image.frombuffer(arr.tobytes(), (w, h), 'RGBA').convert_alpha()
    else:
        # Fallback: many thin rings
        gsurf = pygame.Surface((w, h), pygame.SRCALPHA)
        r, g, b = rgb
        steps = 24
        for i in range(steps, 0, -1):
            frac = i / steps
            a = int(max_alpha * (frac ** power))
            rw, rh = max(2, int(w * frac)), max(2, int(h * frac))
            pygame.draw.ellipse(gsurf, (r, g, b, a // steps * 2),
                                ((w - rw) // 2, (h - rh) // 2, rw, rh))

    dest.blit(gsurf, (cx - w // 2, cy - h // 2))


class GameState:
    TITLE     = "title"
    OVERWORLD = "overworld"
    BATTLE    = "battle"


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.state = GameState.TITLE
        self.battle = None
        self.overworld = None
        self.title_timer = 0.0
        # Title screen particles
        self._sparks   = []   # crackling edge sparks
        self._glitter  = []   # drifting upward glitter
        self._spark_t  = 0.0
        self._glitter_t = 0.0
        self._start_title_music()

    def handle_event(self, event):
        if self.state == GameState.TITLE:
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_SPACE, pygame.K_z
            ):
                self._start_overworld()
            return

        if self.state == GameState.OVERWORLD and self.overworld:
            self.overworld.handle_event(event)
            return

        if self.state == GameState.BATTLE and self.battle:
            self.battle.handle_event(event)

    def update(self, dt):
        self.title_timer += dt
        if self.state == GameState.TITLE:
            self._update_title_particles(dt)

        if self.state == GameState.OVERWORLD and self.overworld:
            self.overworld.update(dt)
            if self.overworld.quit_to_title:
                self.overworld = None
                self.state = GameState.TITLE
            elif self.overworld.start_battle:
                self._start_battle_from_overworld()

        elif self.state == GameState.BATTLE and self.battle:
            self.battle.update(dt)
            if self.battle.finished:
                self._return_to_overworld()

    def draw(self):
        if self.state == GameState.TITLE:
            self._draw_title()
        elif self.state == GameState.OVERWORLD and self.overworld:
            self.overworld.draw()
        elif self.state == GameState.BATTLE and self.battle:
            self.battle.draw()

    def _start_title_music(self):
        path = os.path.join(_BASE, 'assets', 'music', 'title.mp3')
        if os.path.exists(path):
            _music.play(path, volume=0.75)
        else:
            print(f"[music] file not found: {path}")

    def _stop_music(self, fade_ms=1200):
        _music.stop()

    def _start_overworld(self):
        self._stop_music()
        self.state = GameState.OVERWORLD
        self.overworld = Overworld(self.screen)

    def _start_battle_from_overworld(self):
        self.state = GameState.BATTLE
        self.battle = Battle(self.screen, folder=self.overworld.folder)
        self.overworld.start_battle = False

    def _return_to_overworld(self):
        won = self.battle.player_won
        self.battle = None
        self.state = GameState.OVERWORLD
        if self.overworld:
            self.overworld.on_battle_end(won)

    def _update_title_particles(self, dt):
        card_surf = SM.get('title_card')
        CW = card_surf.get_width()  if card_surf else 120
        CH = card_surf.get_height() if card_surf else 180
        card_cx = C.SCREEN_W // 2
        card_cy = 220
        bob = math.sin(self.title_timer * 1.1) * 10

        # ── Crackling edge sparks ────────────────────────────────────────────
        self._spark_t -= dt
        if self._spark_t <= 0:
            self._spark_t = random.uniform(0.04, 0.13)
            side = random.choice([0, 1, 2, 3])
            if side == 0:   x, y = card_cx + random.randint(-CW//2, CW//2), int(card_cy + bob - CH//2)
            elif side == 1: x, y = card_cx + random.randint(-CW//2, CW//2), int(card_cy + bob + CH//2)
            elif side == 2: x, y = card_cx - CW//2, int(card_cy + bob + random.randint(-CH//2, CH//2))
            else:           x, y = card_cx + CW//2, int(card_cy + bob + random.randint(-CH//2, CH//2))
            dx, dy = x - card_cx, y - int(card_cy + bob)
            dist   = max(1, math.hypot(dx, dy))
            sp     = random.uniform(35, 110)
            vx     = dx / dist * sp + random.uniform(-18, 18)
            vy     = dy / dist * sp - random.uniform(20, 70)
            col    = random.choice([(195, 165, 65), (130, 90, 255), (80, 160, 255), (255, 245, 180)])
            lt     = random.uniform(0.45, 1.1)
            self._sparks.append([float(x), float(y), vx, vy, lt, lt, col])

        for p in self._sparks:
            p[0] += p[2] * dt;  p[1] += p[3] * dt
            p[3] += 45 * dt;    p[4] -= dt
        self._sparks = [p for p in self._sparks if p[4] > 0]

        # ── Drifting glitter ────────────────────────────────────────────────
        self._glitter_t -= dt
        if self._glitter_t <= 0:
            self._glitter_t = random.uniform(0.06, 0.18)
            x = card_cx + random.randint(-int(CW * 0.8), int(CW * 0.8))
            y = int(card_cy + bob) + random.randint(-CH // 2, CH // 3)
            col = random.choice([(195, 165, 65), (130, 80, 255), (255, 255, 200), (80, 180, 255)])
            lt  = random.uniform(0.9, 1.8)
            self._glitter.append([float(x), float(y),
                                   random.uniform(-8, 8), -random.uniform(18, 40),
                                   lt, lt, col])
        for g in self._glitter:
            g[0] += g[2] * dt;  g[1] += g[3] * dt;  g[4] -= dt
        self._glitter = [g for g in self._glitter if g[4] > 0]

    def _draw_title(self):
        surf = self.screen
        t    = self.title_timer
        cx   = C.SCREEN_W // 2

        # ── Background ────────────────────────────────────────────────────────
        bg = SM.get('title_bg')
        if bg:
            surf.blit(bg, (0, 0))
        else:
            surf.fill((8, 14, 35))

        # ── Card position ─────────────────────────────────────────────────────
        card_cx = cx
        card_cy = 220
        card_surf = SM.get('title_card')
        if card_surf:
            CW = card_surf.get_width()
            CH = card_surf.get_height()
            bob     = math.sin(t * 1.1) * 10
            cos_val = math.cos(t * 0.55)

            # ── Background rune circle (behind everything) ────────────────────
            rune_r   = int(CW * 1.1)
            rune_ang = t * 12
            for rr_scale, rr_alpha in [(1.0, 22), (0.68, 14)]:
                rr = int(rune_r * rr_scale)
                if rr < 2: continue
                rs_size = rr * 2 + 6
                rsc     = rs_size // 2
                rsurf   = pygame.Surface((rs_size, rs_size), pygame.SRCALPHA)
                pygame.draw.circle(rsurf, (110, 75, 230, rr_alpha), (rsc, rsc), rr, 2)
                for i in range(12):
                    ang = math.radians(rune_ang + i * 30)
                    x1 = rsc + int(math.cos(ang) * (rr - 7))
                    y1 = rsc + int(math.sin(ang) * (rr - 7))
                    x2 = rsc + int(math.cos(ang) * rr)
                    y2 = rsc + int(math.sin(ang) * rr)
                    pygame.draw.line(rsurf, (110, 75, 230, rr_alpha), (x1, y1), (x2, y2), 1)
                surf.blit(rsurf, (card_cx - rsc, int(card_cy + bob) - rsc))

            # Dim inner hexagram
            hex_r   = int(CW * 0.72)
            hex_pts = [(card_cx + int(math.cos(math.radians(-rune_ang + i * 60)) * hex_r),
                        int(card_cy + bob) + int(math.sin(math.radians(-rune_ang + i * 60)) * hex_r))
                       for i in range(6)]
            hexsurf = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            if len(hex_pts) >= 3:
                pygame.draw.lines(hexsurf, (100, 65, 210, 18), True, hex_pts, 1)
                for i in range(6):
                    for j in range(i + 2, 6):
                        if not (i == 0 and j == 5):
                            pygame.draw.line(hexsurf, (100, 65, 210, 10), hex_pts[i], hex_pts[j], 1)
            surf.blit(hexsurf, (0, 0))

            # ── Smooth radial glow ────────────────────────────────────────────
            glow_pulse = math.sin(t * 1.8)
            face_frac  = abs(cos_val)      # 1 when card faces viewer, 0 on edge

            # Outer wide blue halo — soft power curve, Bayer dithered
            gw = int(CW * 2.8)
            gh = int(CH * 2.8 * 0.52)
            outer_a = max(0, min(200, int((90 + 35 * glow_pulse) * (0.6 + 0.4 * face_frac))))
            _soft_glow(surf, card_cx, int(card_cy + bob),
                       gw, gh, (40, 90, 255), outer_a,
                       power=1.6, dither_strength=14)

            # Inner tighter blue core — brighter, tighter falloff
            iw = int(CW * 1.4)
            ih = int(CH * 1.4 * 0.52)
            inner_a = max(0, min(255, int((140 + 50 * glow_pulse) * (0.65 + 0.35 * face_frac))))
            _soft_glow(surf, card_cx, int(card_cy + bob),
                       iw, ih, (80, 140, 255), inner_a,
                       power=2.4, dither_strength=8)

            # Gold halo — wraps just outside the card
            gold_a = max(0, min(180, int((70 + 45 * math.sin(t * 2.3)) * (0.55 + 0.45 * face_frac))))
            _soft_glow(surf, card_cx, int(card_cy + bob),
                       CW + 64, CH + 64, (210, 175, 60), gold_a,
                       power=3.5, dither_strength=10)

            # ── Glitter (draw before card so card appears on top) ─────────────
            for g in self._glitter:
                frac = g[4] / g[5]
                cr, cg, cb = g[6]
                gx, gy = int(g[0]), int(g[1])
                r_px   = max(1, int(3 * frac))
                pygame.draw.circle(surf, (min(255, cr + 60), min(255, cg + 60), min(255, cb + 60)),
                                   (gx, gy), r_px)

            # ── Spinning card ─────────────────────────────────────────────────
            draw_w  = max(4, int(abs(cos_val) * CW))
            tilt    = math.sin(t * 0.38) * 7
            scaled  = pygame.transform.scale(card_surf, (draw_w, CH))
            rotated = pygame.transform.rotate(scaled, tilt)
            rw, rh  = rotated.get_size()
            surf.blit(rotated, (card_cx - rw // 2, int(card_cy + bob - rh // 2)))

            # ── Orbiting star particles ───────────────────────────────────────
            for i in range(10):
                angle = t * 0.85 + i * (math.pi / 5)
                px = int(card_cx + math.cos(angle) * CW * 0.85)
                py = int(card_cy + bob + math.sin(angle) * CH * 0.34)
                br = int(160 + 80 * math.sin(t * 2.5 + i))
                r  = 2 if i % 3 == 0 else 1
                pygame.draw.circle(surf, (br, br, 255), (px, py), r)

            for i in range(6):
                angle = -t * 1.7 + i * (math.pi / 3)
                px = int(card_cx + math.cos(angle) * CW * 0.52)
                py = int(card_cy + bob + math.sin(angle) * CH * 0.22)
                br = int(200 + 55 * math.sin(t * 3.2 + i))
                pygame.draw.circle(surf, (br, 220, 255), (px, py), 1)

            # ── Crackling sparks (drawn on top) ───────────────────────────────
            for p in self._sparks:
                frac = p[4] / p[5]
                cr, cg, cb = p[6]
                c = (min(255, cr + int((255 - cr) * (1 - frac) * 0.6)),
                     min(255, cg + int((255 - cg) * (1 - frac) * 0.6)),
                     min(255, cb + int((255 - cb) * (1 - frac) * 0.6)))
                pygame.draw.circle(surf, c, (int(p[0]), int(p[1])), max(1, int(3 * frac)))
