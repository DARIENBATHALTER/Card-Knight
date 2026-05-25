"""
Flat overworld — large scrollable world built on a single background image.
Rocks, trees, and other props will be placed on top later.
"""
from __future__ import annotations
import math
import os
import pygame
import constants as C
import fonts
import sprite_manager as SM
from chips import make_sample_folder

_BASE    = os.path.dirname(os.path.abspath(__file__))
_BG_PATH = os.path.join(_BASE, 'assets', 'overworld', 'dojo.png')

# ── World constants ────────────────────────────────────────────────────────────
WORLD_SCALE    = 1.0    # dojo.png is already 1280×720 — no upscaling
PLAYER_SPEED   = 180    # world px / second
CHAR_H         = 88     # target character render height (taller — single-screen scene)
ENCOUNTER_DIST = 70     # world px — battle triggers inside this radius
TALK_DIST      = 90     # world px — TALK prompt visible inside this radius

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

        # ── Dojo layout ──────────────────────────────────────────────────────
        # Image is 1280×720 — coordinates are direct screen-space.
        # The duel mat (light tile area) center is at roughly (640, 420).
        # Player spawns just south of the central enemy.
        self.player_x, self.player_y = _w(640, 540)

        # ── NPCs ──────────────────────────────────────────────────────────────
        self.npcs = [
            OWNPC(*_w(1020, 410), "Sage Hanzo", (180, 140, 220),
                  ["Welcome to the Dueling Hall, Oden.",
                   "Step onto the mat when you're ready.",
                   "Defeat the training Misdeal and your",
                   "deck will be sharper for it."]),
        ]
        self._active_npc = 0
        self._dialog_page = 0

        # ── Enemies ───────────────────────────────────────────────────────────
        # One stationary enemy on the center of the dueling mat.
        self.enemies = [
            OWEnemy([_w(640, 420)], interval=1.0),
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
        # Keep the dojo enemy alive — it's a training Misdeal, the player can
        # walk back into it for repeated practice battles.
        self.start_battle = False
        # Return Oden to his spawn so the encounter doesn't immediately re-fire.
        self.player_x, self.player_y = _w(640, 540)
        self._moving = False

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
        # TALK prompt — serif chip in matching gold/navy style, just above the head
        if _dist(self.player_x, self.player_y, npc.x, npc.y) <= TALK_DIST:
            lbl_font = fonts.serif(14, bold=True)
            lbl = lbl_font.render("TALK", True, C.UI_GOLD)
            pad_x, pad_y = 9, 3
            cw, ch = lbl.get_width() + pad_x * 2, lbl.get_height() + pad_y * 2
            lx = sx - cw // 2
            ly = sy - CHAR_H + 4   # lower than before — sits just above head
            chip = pygame.Surface((cw, ch), pygame.SRCALPHA)
            chip.fill((10, 14, 38, 235))
            pygame.draw.rect(chip, C.UI_DARK_GOLD, chip.get_rect(),
                             2, border_radius=4)
            pygame.draw.rect(chip, C.UI_GOLD, chip.get_rect().inflate(-2, -2),
                             1, border_radius=3)
            chip.blit(lbl, (pad_x, pad_y))
            surf.blit(chip, (lx, ly))

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
        # Warning exclamation — large serif "!" with bobbing motion + alert pulse
        if _dist(self.player_x, self.player_y, enemy.x, enemy.y) <= ENCOUNTER_DIST * 3.5:
            pulse    = int(self._timer * 5) % 2 == 0
            warn_col = C.RED if pulse else C.YELLOW
            warn_font = fonts.serif(36, bold=True)
            shadow_s = warn_font.render("!", True, (10, 4, 4))
            warn_s   = warn_font.render("!", True, warn_col)
            bob = int(math.sin(self._timer * 6) * 2)
            wx = sx - warn_s.get_width() // 2
            wy = sy - CHAR_H - 28 + bob
            surf.blit(shadow_s, (wx + 2, wy + 2))
            surf.blit(warn_s,   (wx, wy))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hints(self, surf):
        hint = fonts.pixel(6).render(
            "Arrows:Move  Z:Talk  Esc:Pause", True, (70, 65, 100))
        surf.blit(hint, (4, C.SCREEN_H - 11))

    def _draw_dialog(self, surf):
        npc = self.npcs[self._active_npc]

        # Box geometry — wide, tall, centered horizontally near the bottom
        bw, bh = 1100, 168
        bx = (C.SCREEN_W - bw) // 2
        by = C.SCREEN_H - bh - 32

        # Backing — same recipe as the loading / save / victory chrome
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        box.fill((10, 14, 38, 245))
        pygame.draw.rect(box, (24, 30, 70, 80),
                         pygame.Rect(8, 8, bw - 16, bh - 16), border_radius=6)
        pygame.draw.rect(box, C.UI_DARK_GOLD, box.get_rect(), 4, border_radius=8)
        pygame.draw.rect(box, C.UI_GOLD,      box.get_rect().inflate(-4, -4),
                         1, border_radius=6)
        surf.blit(box, (bx, by))

        # Corner compass-rose ornaments
        for (cx, cy) in ((bx + 22, by + 22), (bx + bw - 22, by + 22),
                         (bx + 22, by + bh - 22), (bx + bw - 22, by + bh - 22)):
            outer = [(cx, cy - 11), (cx + 11, cy), (cx, cy + 11), (cx - 11, cy)]
            inner = [(cx + 4, cy - 4), (cx + 4, cy + 4),
                     (cx - 4, cy + 4), (cx - 4, cy - 4)]
            pygame.draw.polygon(surf, C.UI_GOLD, outer)
            pygame.draw.polygon(surf, (10, 14, 38), inner)
            pygame.draw.circle(surf, C.UI_DARK_GOLD, (cx, cy), 2)

        # Name — serif gold, large
        name_font = fonts.serif(24, bold=True)
        name_s = name_font.render(npc.name, True, C.UI_GOLD)
        surf.blit(name_s, (bx + 36, by + 18))

        # Page indicator (top-right)
        pg_font = fonts.serif(13)
        pg_s = pg_font.render(f"{self._dialog_page + 1} / {len(npc.dialog)}",
                              True, (180, 165, 210))
        surf.blit(pg_s, (bx + bw - pg_s.get_width() - 36, by + 26))

        # Gold rule with diamond endpoints + midpoint
        rule_y = by + 56
        rx0, rx1 = bx + 32, bx + bw - 32
        pygame.draw.line(surf, C.UI_DARK_GOLD, (rx0, rule_y + 1), (rx1, rule_y + 1), 1)
        pygame.draw.line(surf, C.UI_GOLD,      (rx0, rule_y),     (rx1, rule_y),     1)
        for dx in (rx0, (rx0 + rx1) // 2, rx1):
            pygame.draw.polygon(surf, C.UI_GOLD,
                                [(dx, rule_y - 4), (dx + 4, rule_y),
                                 (dx, rule_y + 4), (dx - 4, rule_y)])

        # Body text — serif, larger, pixel-width wrap
        body_font = fonts.serif(19)
        line  = npc.dialog[self._dialog_page]
        avail = bw - 72
        rows  = self._wrap_text_px(line, body_font, avail)
        text_y = rule_y + 16
        for i, r in enumerate(rows[:3]):
            ts = body_font.render(r, True, C.WHITE)
            surf.blit(ts, (bx + 36, text_y + i * 26))

        # Continue indicator — pulsing gold triangle in bottom-right
        if int(self._timer * 3) % 2 == 0:
            ax, ay = bx + bw - 44, by + bh - 32
            pygame.draw.polygon(surf, C.UI_GOLD,
                                [(ax, ay - 7), (ax + 14, ay - 7), (ax + 7, ay + 3)])

    @staticmethod
    def _wrap_text_px(text, font, max_width):
        words = text.split()
        rows  = []
        cur   = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                if cur:
                    rows.append(cur)
                cur = w
        if cur:
            rows.append(cur)
        return rows

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
