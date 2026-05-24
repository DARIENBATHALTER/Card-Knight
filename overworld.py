"""
Flat overworld — large scrollable world built on a single background image.
Rocks, trees, and other props will be placed on top later.
"""
import math
import os
import pygame
import constants as C
import fonts
import sprite_manager as SM
from chips import make_sample_folder

_BASE    = os.path.dirname(os.path.abspath(__file__))
_BG_PATH = os.path.join(_BASE, 'assets', 'overworld',
                         '5d23aef3-1e97-42dd-b491-c591dedcf679.png')

# ── World constants ────────────────────────────────────────────────────────────
WORLD_SCALE    = 1.8    # source image scaled up by this factor
PLAYER_SPEED   = 230    # world px / second
CHAR_H         = 64     # target character render height (world px)
ENCOUNTER_DIST = 55     # world px — battle triggers inside this radius
TALK_DIST      = 70     # world px — TALK prompt visible inside this radius

# ── Cached scaled background (avoids re-scaling on every overworld init) ──────
_bg_surf:  pygame.Surface | None = None
_bg_scale: float = 0.0


def _get_bg() -> pygame.Surface | None:
    global _bg_surf, _bg_scale
    if _bg_surf is not None and _bg_scale == WORLD_SCALE:
        return _bg_surf
    try:
        from PIL import Image as PILImage
        import io
        pil = PILImage.open(_BG_PATH).convert('RGB')
        iw, ih = pil.size
        tw, th = int(iw * WORLD_SCALE), int(ih * WORLD_SCALE)
        pil    = pil.resize((tw, th), PILImage.LANCZOS)
        raw    = pygame.image.frombytes(pil.tobytes(), (tw, th), 'RGB').convert()
        _bg_surf  = raw
        _bg_scale = WORLD_SCALE
    except Exception as e:
        print(f"[overworld] bg load failed: {e}")
        _bg_surf = None
    return _bg_surf


# ── Entity records ─────────────────────────────────────────────────────────────

class OWEnemy:
    """Overworld enemy that steps between waypoints."""
    def __init__(self, waypoints, interval=1.1):
        self.waypoints = [(float(x), float(y)) for x, y in waypoints]
        self.x, self.y = self.waypoints[0]
        self.alive     = True
        self._wp_idx   = 0
        self._timer    = 0.0
        self.interval  = interval

    def update(self, dt):
        if not self.alive:
            return
        self._timer -= dt
        if self._timer <= 0:
            self._timer    = self.interval
            self._wp_idx   = (self._wp_idx + 1) % len(self.waypoints)
            self.x, self.y = self.waypoints[self._wp_idx]


class OWNPC:
    def __init__(self, x, y, name, color, dialog):
        self.x      = float(x)
        self.y      = float(y)
        self.name   = name
        self.color  = color
        self.dialog = dialog


class OWState:
    WALK    = "walk"
    DIALOG  = "dialog"
    PAUSE   = "pause"
    LIBRARY = "library"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def _w(ix, iy):
    """Convert image-space coordinates to world-space at WORLD_SCALE."""
    return (ix * WORLD_SCALE, iy * WORLD_SCALE)


# ── Main class ────────────────────────────────────────────────────────────────

class Overworld:
    def __init__(self, screen, folder=None):
        self.screen = screen
        self.folder = folder if folder is not None else make_sample_folder()

        # Background
        bg = _get_bg()
        self.world_w = bg.get_width()  if bg else C.SCREEN_W * 3
        self.world_h = bg.get_height() if bg else C.SCREEN_H * 3

        # Player position (world pixels)
        cx, cy = _w(836, 720)   # near bottom-centre of the grass diamond
        self.player_x = float(cx)
        self.player_y = float(cy)

        # ── NPCs ──────────────────────────────────────────────────────────────
        self.npcs = [
            OWNPC(*_w(570, 370), "Elder Voss", (180, 120, 220),
                  ["Welcome to Ashenveil, traveler.",
                   "Our village has been plagued by slimes",
                   "creeping up from the Crystal Wilds.",
                   "We need a hero. That hero may be you."]),
            OWNPC(*_w(1070, 360), "Serin", (220, 165, 50),
                  ["Wares! Chips! Rare codes for the bold!",
                   "...Well, I would sell you some, but",
                   "those slimes cleared me out yesterday.",
                   "Defeat them and maybe I'll restock."]),
            OWNPC(*_w(836, 175), "Sage Orlan", (60, 210, 120),
                  ["You've reached the Crystal Shrine.",
                   "Monsters guard every path here.",
                   "Keep your chips close — and your",
                   "Limit Breaks even closer. Be well."]),
        ]
        self._active_npc = 0
        self._dialog_page = 0

        # ── Enemies ───────────────────────────────────────────────────────────
        self.enemies = [
            OWEnemy([_w(480, 500), _w(510, 540), _w(490, 560)], interval=1.0),
            OWEnemy([_w(920, 440), _w(960, 410), _w(950, 460)], interval=1.1),
            OWEnemy([_w(700, 610), _w(750, 580), _w(730, 640)], interval=1.2),
            OWEnemy([_w(1050, 530), _w(1090, 490), _w(1060, 560)], interval=0.95),
        ]
        self._battle_enemy_idx = 0

        # State
        self.state         = OWState.WALK
        self.start_battle  = False
        self.quit_to_title = False

        # Pause
        self._pause_opts   = ["Resume", "Chip Library", "Quit to Title"]
        self._pause_cursor = 0

        # Library
        self._lib_scroll = 0
        self._LIB_ROWS   = 8

        # Animation
        self._timer       = 0.0
        self._moving      = False
        self._facing_left = False

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self._timer += dt
        if self.state == OWState.WALK:
            self._update_movement(dt)
            for e in self.enemies:
                e.update(dt)
            self._check_battle()

    def _update_movement(self, dt):
        keys = pygame.key.get_pressed()
        dx, dy = 0.0, 0.0
        if keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_RIGHT]: dx += 1

        self._moving = (dx != 0 or dy != 0)
        if dx > 0:  self._facing_left = True
        elif dx < 0: self._facing_left = False

        if not self._moving:
            return

        length = math.hypot(dx, dy) or 1.0
        dx = dx / length * PLAYER_SPEED * dt
        dy = dy / length * PLAYER_SPEED * dt

        margin = CHAR_H // 2
        self.player_x = max(margin, min(self.world_w - margin, self.player_x + dx))
        self.player_y = max(margin, min(self.world_h - margin, self.player_y + dy))

    def _check_battle(self):
        for i, e in enumerate(self.enemies):
            if e.alive and _dist(self.player_x, self.player_y, e.x, e.y) <= ENCOUNTER_DIST:
                self._battle_enemy_idx = i
                self.start_battle = True
                return

    def on_battle_end(self, player_won):
        self.start_battle = False
        if player_won:
            idx = self._battle_enemy_idx
            if 0 <= idx < len(self.enemies):
                self.enemies[idx].alive = False

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        k = event.key

        if self.state == OWState.WALK:
            if k == pygame.K_ESCAPE:
                self.state = OWState.PAUSE
                self._pause_cursor = 0
            elif k in (pygame.K_z, pygame.K_RETURN):
                self._try_talk()

        elif self.state == OWState.DIALOG:
            if k in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self._dialog_page += 1
                if self._dialog_page >= len(self.npcs[self._active_npc].dialog):
                    self.state = OWState.WALK
                    self._dialog_page = 0

        elif self.state == OWState.PAUSE:
            if k == pygame.K_UP:
                self._pause_cursor = max(0, self._pause_cursor - 1)
            elif k == pygame.K_DOWN:
                self._pause_cursor = min(len(self._pause_opts) - 1, self._pause_cursor + 1)
            elif k in (pygame.K_z, pygame.K_RETURN):
                self._select_pause()
            elif k == pygame.K_ESCAPE:
                self.state = OWState.WALK

        elif self.state == OWState.LIBRARY:
            if k == pygame.K_UP:
                self._lib_scroll = max(0, self._lib_scroll - 1)
            elif k == pygame.K_DOWN:
                cap = max(0, len(self.folder) - self._LIB_ROWS)
                self._lib_scroll = min(cap, self._lib_scroll + 1)
            elif k in (pygame.K_ESCAPE, pygame.K_x, pygame.K_z):
                self.state = OWState.PAUSE

    def _try_talk(self):
        best, best_d = -1, TALK_DIST + 1
        for i, npc in enumerate(self.npcs):
            d = _dist(self.player_x, self.player_y, npc.x, npc.y)
            if d < best_d:
                best_d, best = d, i
        if best >= 0:
            self._active_npc  = best
            self._dialog_page = 0
            self.state = OWState.DIALOG

    def _select_pause(self):
        if self._pause_cursor == 0:
            self.state = OWState.WALK
        elif self._pause_cursor == 1:
            self.state = OWState.LIBRARY
            self._lib_scroll = 0
        elif self._pause_cursor == 2:
            self.quit_to_title = True

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        surf = self.screen

        # ── Camera ────────────────────────────────────────────────────────────
        cam_x = int(max(0, min(self.world_w - C.SCREEN_W,
                               self.player_x - C.SCREEN_W / 2)))
        cam_y = int(max(0, min(self.world_h - C.SCREEN_H,
                               self.player_y - C.SCREEN_H / 2)))

        # ── Background ────────────────────────────────────────────────────────
        bg = _get_bg()
        if bg:
            surf.blit(bg, (-cam_x, -cam_y))
        else:
            surf.fill((45, 90, 40))

        # ── Entities (painter's order: sort by y so closer = on top) ──────────
        def _sy(obj):
            return obj[1]   # sort by world-y

        drawables = []
        for npc in self.npcs:
            drawables.append(('npc', npc.x, npc.y, npc))
        for e in self.enemies:
            if e.alive:
                drawables.append(('enemy', e.x, e.y, e))
        drawables.append(('player', self.player_x, self.player_y, None))
        drawables.sort(key=lambda d: d[2])   # painter's order by world-y

        for kind, wx, wy, obj in drawables:
            sx = int(wx - cam_x)
            sy = int(wy - cam_y)
            if -CHAR_H * 2 <= sx <= C.SCREEN_W + CHAR_H * 2 and \
               -CHAR_H * 2 <= sy <= C.SCREEN_H + CHAR_H * 2:
                if kind == 'player':
                    self._draw_player(surf, sx, sy)
                elif kind == 'npc':
                    self._draw_npc(surf, sx, sy, obj, cam_x, cam_y)
                elif kind == 'enemy':
                    self._draw_enemy(surf, sx, sy, obj)

        # ── HUD overlays ──────────────────────────────────────────────────────
        if self.state == OWState.WALK:
            self._draw_hints(surf)
        elif self.state == OWState.DIALOG:
            self._draw_dialog(surf)
        elif self.state == OWState.PAUSE:
            self._draw_pause(surf)
        elif self.state == OWState.LIBRARY:
            self._draw_library(surf)

    # ── Entity drawing ────────────────────────────────────────────────────────

    def _sprite_at(self, surf, sx, sy, frames, flip=False):
        """Blit a sprite list (or single surface) centred at (sx, sy) feet."""
        if not frames:
            return
        if isinstance(frames, list):
            idx   = int(self._timer * 8) % len(frames)
            frame = frames[idx]
        else:
            frame = frames
        fw, fh = frame.get_size()
        # Scale to CHAR_H keeping aspect ratio
        scale_f = CHAR_H / fh
        dw, dh  = int(fw * scale_f), CHAR_H
        frame   = pygame.transform.scale(frame, (dw, dh))
        if flip:
            frame = pygame.transform.flip(frame, True, False)
        surf.blit(frame, (sx - dw // 2, sy - dh))

    def _draw_player(self, surf, sx, sy):
        run_f  = SM.get('oden_run') if self._moving else None
        idle_f = SM.get('oden_idle')
        frames = run_f or idle_f
        if frames:
            self._sprite_at(surf, sx, sy, frames, flip=self._facing_left)
        else:
            # Placeholder
            pygame.draw.ellipse(surf, (0, 0, 0), (sx - 12, sy - 3, 24, 8))
            pygame.draw.rect(surf, C.BLUE, (sx - 7, sy - 30, 14, 20), border_radius=2)
            pygame.draw.circle(surf, C.BLUE, (sx, sy - 38), 9)
            pygame.draw.circle(surf, C.WHITE, (sx, sy - 38), 9, 2)

    def _draw_npc(self, surf, sx, sy, npc, cam_x, cam_y):
        # Robe-style placeholder (slightly wider body, no run frames)
        bob  = int(math.sin(self._timer * 2.2) * 2)
        col  = npc.color
        lite = tuple(min(255, c + 50) for c in col)
        pygame.draw.ellipse(surf, (0, 0, 0), (sx - 11, sy - 3, 22, 8))
        pygame.draw.rect(surf, col, (sx - 9, sy - 30 + bob, 18, 22), border_radius=3)
        pygame.draw.rect(surf, lite, (sx - 9, sy - 30 + bob, 18, 22), 1, border_radius=3)
        pygame.draw.circle(surf, col, (sx, sy - 39 + bob), 10)
        pygame.draw.circle(surf, lite, (sx, sy - 39 + bob), 10, 2)
        # Face dots
        pygame.draw.circle(surf, (255, 255, 255), (sx - 3, sy - 40 + bob), 2)
        pygame.draw.circle(surf, (255, 255, 255), (sx + 3, sy - 40 + bob), 2)
        # TALK prompt
        if _dist(self.player_x, self.player_y, npc.x, npc.y) <= TALK_DIST:
            lbl = fonts.pixel(6, bold=True).render("TALK", True, C.UI_GOLD)
            lx  = sx - lbl.get_width() // 2
            ly  = sy - CHAR_H - 8
            pygame.draw.rect(surf, C.UI_NAVY,
                             (lx - 2, ly - 1, lbl.get_width() + 4, lbl.get_height() + 2),
                             border_radius=2)
            surf.blit(lbl, (lx, ly))

    def _draw_enemy(self, surf, sx, sy, enemy):
        bob = 1 if int(self._timer * 4) % 2 else 0
        frames = SM.get('gen_slime_idle')
        if frames:
            idx   = int(self._timer * 6) % len(frames)
            frame = frames[idx]
            fw, fh = frame.get_size()
            eh    = int(CHAR_H * 0.75)
            ew    = int(fw * eh / fh)
            frame = pygame.transform.scale(frame, (ew, eh))
            surf.blit(frame, (sx - ew // 2, sy - eh - bob))
        else:
            # Blob fallback
            b = bob
            pygame.draw.ellipse(surf, (0, 0, 0), (sx - 12, sy - 3, 24, 8))
            pygame.draw.ellipse(surf, (30, 140, 40), (sx - 13, sy - 26 + b, 26, 22))
            pygame.draw.ellipse(surf, (55, 190, 65), (sx - 10, sy - 28 + b, 20, 16))
            pygame.draw.circle(surf, (255, 255, 255), (sx - 5, sy - 22 + b), 3)
            pygame.draw.circle(surf, (255, 255, 255), (sx + 5, sy - 22 + b), 3)
        # Warning exclamation
        if _dist(self.player_x, self.player_y, enemy.x, enemy.y) <= ENCOUNTER_DIST * 3.5:
            pulse    = int(self._timer * 5) % 2 == 0
            warn_col = C.RED if pulse else C.YELLOW
            warn     = fonts.pixel(8, bold=True).render("!", True, warn_col)
            surf.blit(warn, (sx - warn.get_width() // 2, sy - CHAR_H - 10))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hints(self, surf):
        hint = fonts.pixel(6).render(
            "Arrows:Move  Z:Talk  Esc:Pause", True, (70, 65, 100))
        surf.blit(hint, (4, C.SCREEN_H - 11))

    def _draw_dialog(self, surf):
        npc  = self.npcs[self._active_npc]
        bw, bh = C.SCREEN_W - 16, 76
        bx, by = 8, C.SCREEN_H - bh - 4
        pygame.draw.rect(surf, C.UI_NAVY, (bx, by, bw, bh), border_radius=4)
        pygame.draw.rect(surf, npc.color,  (bx, by, bw, bh), 2, border_radius=4)

        surf.blit(fonts.pixel(7, bold=True).render(npc.name, True, npc.color),
                  (bx + 8, by + 5))
        pg_txt = fonts.pixel(6).render(
            f"{self._dialog_page + 1}/{len(npc.dialog)}", True, C.UI_DARK_GOLD)
        surf.blit(pg_txt, (bx + bw - pg_txt.get_width() - 8, by + 6))
        pygame.draw.line(surf, C.UI_DARK_GOLD,
                         (bx + 4, by + 18), (bx + bw - 4, by + 18))

        line  = npc.dialog[self._dialog_page]
        words = line.split()
        rows, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if len(test) <= 50:
                cur = test
            else:
                rows.append(cur); cur = w
        if cur:
            rows.append(cur)
        for i, r in enumerate(rows[:3]):
            surf.blit(fonts.mono(13).render(r, True, C.WHITE),
                      (bx + 8, by + 22 + i * 15))

        if int(self._timer * 3) % 2 == 0:
            ax, ay = bx + bw - 12, by + bh - 8
            pygame.draw.polygon(surf, C.UI_GOLD,
                                [(ax, ay - 5), (ax + 8, ay - 5), (ax + 4, ay)])

    def _draw_pause(self, surf):
        ov = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        surf.blit(ov, (0, 0))
        mw = 170
        mh = 28 + len(self._pause_opts) * 26 + 8
        mx, my = C.SCREEN_W // 2 - mw // 2, C.SCREEN_H // 2 - mh // 2
        pygame.draw.rect(surf, C.UI_NAVY, (mx, my, mw, mh), border_radius=6)
        pygame.draw.rect(surf, C.UI_GOLD, (mx, my, mw, mh), 2, border_radius=6)
        ts = fonts.pixel(8, bold=True).render("PAUSE", True, C.UI_GOLD)
        surf.blit(ts, (mx + mw // 2 - ts.get_width() // 2, my + 7))
        pygame.draw.line(surf, C.UI_DARK_GOLD, (mx + 4, my + 22), (mx + mw - 4, my + 22))
        for i, opt in enumerate(self._pause_opts):
            oy  = my + 28 + i * 26
            sel = i == self._pause_cursor
            if sel:
                pygame.draw.rect(surf, C.UI_ACCENT,
                                 (mx + 4, oy - 1, mw - 8, 22), border_radius=3)
            col = C.WHITE if sel else (90, 85, 120)
            surf.blit(fonts.pixel(8).render(opt, True, col), (mx + 14, oy + 3))

    def _draw_library(self, surf):
        surf.fill(C.UI_NAVY)
        pygame.draw.rect(surf, C.UI_GOLD,
                         (4, 4, C.SCREEN_W - 8, C.SCREEN_H - 8), 2, border_radius=4)
        ts = fonts.pixel(8, bold=True).render("CHIP LIBRARY", True, C.UI_GOLD)
        surf.blit(ts, (C.SCREEN_W // 2 - ts.get_width() // 2, 10))
        pygame.draw.line(surf, C.UI_DARK_GOLD, (8, 24), (C.SCREEN_W - 8, 24))
        hf = fonts.pixel(6, bold=True)
        surf.blit(hf.render("NAME", True, C.UI_DARK_GOLD), (12,  28))
        surf.blit(hf.render("DMG",  True, C.UI_DARK_GOLD), (172, 28))
        surf.blit(hf.render("ELEM", True, C.UI_DARK_GOLD), (216, 28))
        surf.blit(hf.render("CODE", True, C.UI_DARK_GOLD), (282, 28))
        pygame.draw.line(surf, C.UI_DARK_GOLD, (8, 38), (C.SCREEN_W - 8, 38))
        visible = self.folder[self._lib_scroll: self._lib_scroll + self._LIB_ROWS]
        for i, chip in enumerate(visible):
            ry = 42 + i * 28
            if i % 2 == 0:
                pygame.draw.rect(surf, (14, 18, 52), (8, ry, C.SCREEN_W - 16, 26))
            ec  = C.ELEM_COLOR.get(chip.element, C.WHITE)
            en  = C.ELEM_NAME.get(chip.element, "") or "—"
            dmg = str(chip.damage) if chip.damage else (f"+{chip.heals}" if chip.heals else "—")
            cc  = C.CYAN if chip.code == "*" else C.UI_GOLD
            surf.blit(fonts.pixel(7, bold=True).render(chip.name[:12], True, C.WHITE), (12,  ry + 7))
            surf.blit(fonts.mono(13).render(dmg,        True, C.WHITE),                (172, ry + 6))
            surf.blit(fonts.mono(13).render(en,         True, ec),                     (216, ry + 6))
            surf.blit(fonts.pixel(7).render(chip.code,  True, cc),                     (282, ry + 7))
        n = len(self.folder)
        if n > self._LIB_ROWS:
            bar_h = self._LIB_ROWS * 28
            pct   = self._lib_scroll / max(1, n - self._LIB_ROWS)
            bar_y = 42 + int(pct * (bar_h - 16))
            pygame.draw.rect(surf, C.UI_DARK_GOLD, (C.SCREEN_W - 10, 42, 6, bar_h))
            pygame.draw.rect(surf, C.UI_GOLD,      (C.SCREEN_W - 10, bar_y, 6, 16))
        hint = fonts.pixel(6).render("Z/Esc — back", True, (70, 65, 100))
        surf.blit(hint, (C.SCREEN_W // 2 - hint.get_width() // 2, C.SCREEN_H - 12))
