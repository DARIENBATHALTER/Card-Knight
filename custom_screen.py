"""
Custom card selection screen — reference: 2-column layout.
Left column: large card preview with description.
Right column: 2×3 grid of card slots.
Bottom: CODE row (selected codes as colored tiles) + OK button.
Top: player portrait + HP + gauge (same as battle HUD top).
"""
import pygame
import math
import constants as C
import fonts
from chips import can_add_chip, check_program_advance
import sprite_manager as SM
import sfx

# ── Layout constants ──────────────────────────────────────────────────────────
PAD          = 8
PORTRAIT     = 64          # portrait square size
INFO_BOTTOM  = PAD + PORTRAIT + 10   # y where player info block ends

SEP_Y        = INFO_BOTTOM + 4       # gold separator y

CARD_AREA_TOP  = SEP_Y + 8           # card section starts here
CARD_AREA_BOT  = C.SCREEN_H - 72    # CODE row + OK occupy bottom 72px

# Left column (large preview)
PREVIEW_X  = PAD
PREVIEW_W  = 160
PREVIEW_H  = CARD_AREA_BOT - CARD_AREA_TOP

# Right column (card slots grid)
GRID_X_CS  = PREVIEW_X + PREVIEW_W + PAD
GRID_W     = C.CARD_PANEL_W - GRID_X_CS - PAD

# Slot grid: 2 cols × 3 rows (6 slots for 5 chips + 1 empty, fills the height perfectly)
SLOT_COLS  = 2
SLOT_ROWS  = 3
SLOT_GAP   = 4
SLOT_W     = (GRID_W - (SLOT_COLS - 1) * SLOT_GAP) // SLOT_COLS
SLOT_H     = (CARD_AREA_BOT - CARD_AREA_TOP - (SLOT_ROWS - 1) * SLOT_GAP) // SLOT_ROWS

# CODE row
CODE_Y     = CARD_AREA_BOT + PAD
CODE_H     = C.SCREEN_H - CODE_Y - PAD

# OK button
OK_W       = 76
OK_H       = CODE_H - 4
OK_X       = C.CARD_PANEL_W - PAD - OK_W
OK_Y       = CODE_Y + 2

ELEM_BG = {
    C.ELEM_NONE:      ( 40,  36,  68),
    C.ELEM_FIRE:      ( 80,  30,   8),
    C.ELEM_ICE:       (  8,  44,  80),
    C.ELEM_LIGHTNING: ( 72,  64,   8),
    C.ELEM_EARTH:     ( 16,  64,  16),
    C.ELEM_LIGHT:     ( 72,  60,  24),
    C.ELEM_DARK:      ( 36,   8,  60),
}
CLS_COLOR = {
    C.CLS_STANDARD: C.ORANGE,
    C.CLS_MEGA:     (100, 160, 255),
    C.CLS_GIGA:     C.RED,
}
CLS_TILE_COLOR = {
    C.CLS_STANDARD: (160,  80,   0),
    C.CLS_MEGA:     ( 20,  60, 180),
    C.CLS_GIGA:     (160,  20,  20),
}


def _fill_chip_icon(surface, chip, x, y, w, h):
    """Scale chip icon to fill (x, y, w, h) preserving aspect ratio, centered."""
    icons = SM.get('chip_icons') or {}
    icon  = icons.get(chip.name.lower())
    if icon:
        iw, ih = icon.get_size()
        scale  = min(w / max(iw, 1), h / max(ih, 1))
        dw, dh = max(1, int(iw * scale)), max(1, int(ih * scale))
        scaled = pygame.transform.smoothscale(icon, (dw, dh))
        surface.blit(scaled, (x + (w - dw) // 2, y + (h - dh) // 2))
    else:
        _draw_chip_icon_cs(surface, chip, x + w // 2, y + h // 2, min(w, h) * 2 // 3)


def _draw_chip_icon_cs(surface, chip, cx, cy, size=12):
    icons = SM.get('chip_icons') or {}
    icon  = icons.get(chip.name.lower())
    if icon:
        scaled = pygame.transform.smoothscale(icon, (size, size))
        surface.blit(scaled, (cx - size // 2, cy - size // 2))
        return
    # Procedural fallback
    if chip.heals:
        r = max(2, size // 3)
        pygame.draw.circle(surface, (220, 60, 80), (cx - r // 2, cy - 1), r)
        pygame.draw.circle(surface, (220, 60, 80), (cx + r // 2, cy - 1), r)
        pts = [(cx - size//2 + 1, cy + 1), (cx + size//2 - 1, cy + 1), (cx, cy + size//2)]
        pygame.draw.polygon(surface, (220, 60, 80), pts)
    elif chip.damage:
        pygame.draw.line(surface, (210, 200, 170),
                         (cx, cy - size//2), (cx, cy + size//2), 2)
        pygame.draw.line(surface, (210, 200, 170),
                         (cx - size//3, cy - size//6), (cx + size//3, cy - size//6), 2)
    else:
        for angle in range(0, 180, 45):
            rad = math.radians(angle)
            dx = int(math.cos(rad) * (size // 2))
            dy = int(math.sin(rad) * (size // 2))
            pygame.draw.line(surface, (160, 130, 220),
                             (cx - dx, cy - dy), (cx + dx, cy + dy), 2)


class CustomScreen:
    MAX_SELECTABLE = 5

    SLIDE_DURATION = 0.32

    def __init__(self, drawn_chips):
        self.chips = drawn_chips
        self.selected_indices = []
        self.cursor = 0
        self.ok_focused = False   # True when cursor is on the OK button
        self.done   = False
        self.pa_chip = None
        # Slide animation — 0 = fully off-left, 1 = fully open
        self.slide_t = 0.0
        self.closing = False

    # ── Animation update (called by Battle) ──────────────────────────────────

    def update(self, dt):
        target = 0.0 if self.closing else 1.0
        delta  = dt / self.SLIDE_DURATION
        if self.slide_t < target:
            self.slide_t = min(target, self.slide_t + delta)
        elif self.slide_t > target:
            self.slide_t = max(target, self.slide_t - delta)
        if self.closing and self.slide_t <= 0.0:
            self.done = True

    # ── Input ─────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        # Block input while panel is animating in/out
        if self.slide_t < 1.0 or self.closing:
            return
        n = len(self.chips)

        if self.ok_focused:
            # On the OK button — confirm with Z or X, navigate back with arrows
            if event.key in (pygame.K_z, pygame.K_x, pygame.K_RETURN):
                self._confirm()
            elif event.key in (pygame.K_UP, pygame.K_LEFT):
                self.ok_focused = False
                # Return to last-row slot in the appropriate column
                last_row_start = (SLOT_ROWS - 1) * SLOT_COLS
                self.cursor = min(n - 1, last_row_start if event.key == pygame.K_LEFT
                                  else last_row_start + (self.cursor % SLOT_COLS))
                sfx.play('deal')
            elif event.key == pygame.K_RIGHT:
                self.ok_focused = False
                last_row_start = (SLOT_ROWS - 1) * SLOT_COLS
                self.cursor = min(n - 1, last_row_start + 1)
                sfx.play('deal')
            return

        # Normal card-grid navigation
        prev_cursor = self.cursor
        if event.key == pygame.K_LEFT:
            if self.cursor % SLOT_COLS > 0:
                self.cursor -= 1
        elif event.key == pygame.K_RIGHT:
            if self.cursor % SLOT_COLS < SLOT_COLS - 1 and self.cursor + 1 < n:
                self.cursor += 1
        elif event.key == pygame.K_UP:
            new = self.cursor - SLOT_COLS
            if new >= 0:
                self.cursor = new
        elif event.key == pygame.K_DOWN:
            new = self.cursor + SLOT_COLS
            if new < n:
                self.cursor = new
            else:
                self.ok_focused = True   # fall through to OK button
                sfx.play('deal')
                return
        elif event.key in (pygame.K_z, pygame.K_x, pygame.K_RETURN):
            self._try_select(self.cursor)
            return
        if self.cursor != prev_cursor:
            sfx.play('deal')

    def _try_select(self, idx):
        if idx in self.selected_indices:
            if self.selected_indices and self.selected_indices[-1] == idx:
                self.selected_indices.pop()
                self.pa_chip = None
                sfx.play('ui_cancel')
            return
        if len(self.selected_indices) >= self.MAX_SELECTABLE:
            sfx.play('ui_cancel')
            return
        chip = self.chips[idx]
        selected_chips = [self.chips[i] for i in self.selected_indices]
        if can_add_chip(selected_chips, chip):
            self.selected_indices.append(idx)
            sfx.play('card_select')
            self.pa_chip = check_program_advance(
                [self.chips[i] for i in self.selected_indices]
            )
        else:
            sfx.play('ui_cancel')

    def _confirm(self):
        # Start the slide-out animation; `done` will flip when slide_t hits 0.
        sfx.play('shuffle')
        self.closing = True

    def get_selected_chips(self):
        if self.pa_chip:
            return [self.pa_chip]
        return [self.chips[i] for i in self.selected_indices]

    def can_select(self, idx):
        if idx in self.selected_indices:
            return True
        if len(self.selected_indices) >= self.MAX_SELECTABLE:
            return False
        chip = self.chips[idx]
        selected_chips = [self.chips[i] for i in self.selected_indices]
        return can_add_chip(selected_chips, chip)

    # ── Drawing ────────────────────────────────────────────────────────────────

    def draw(self, surface):
        # Right-side fog fades in/out alongside the panel slide
        fog_alpha = int(55 * self.slide_t)
        if fog_alpha > 0:
            fog = pygame.Surface((C.SCREEN_W - C.CARD_PANEL_W, C.SCREEN_H), pygame.SRCALPHA)
            fog.fill((0, 10, 60, fog_alpha))
            surface.blit(fog, (C.CARD_PANEL_W, 0))

        # Build the panel on an offscreen surface, then blit at animated x
        panel = pygame.Surface((C.CARD_PANEL_W, C.SCREEN_H), pygame.SRCALPHA)
        self._render_panel_contents(panel)

        eased = 1.0 - (1.0 - self.slide_t) ** 2     # ease-out quadratic
        x_offset = int(-C.CARD_PANEL_W * (1.0 - eased))
        surface.blit(panel, (x_offset, 0))

    def _render_panel_contents(self, surface):
        """Render the static panel layout to `surface` (CARD_PANEL_W wide).
        The area above SEP_Y is left transparent so the battle HP widget shows
        through; the area below is filled with navy."""
        # Navy backdrop from card area downward
        pygame.draw.rect(surface, C.UI_NAVY,
                         pygame.Rect(0, SEP_Y, C.CARD_PANEL_W, C.SCREEN_H - SEP_Y))

        # ── Gold separator ─────────────────────────────────────────────────────
        pygame.draw.line(surface, C.UI_DARK_GOLD,
                         (PAD, SEP_Y), (C.CARD_PANEL_W - PAD, SEP_Y), 1)
        pygame.draw.line(surface, C.UI_GOLD,
                         (PAD, SEP_Y + 1), (C.CARD_PANEL_W - PAD, SEP_Y + 1), 1)

        # ── Large card preview (left column) ───────────────────────────────────
        if self.chips:
            self._draw_large_preview(surface, self.chips[self.cursor],
                                     PREVIEW_X, CARD_AREA_TOP, PREVIEW_W, PREVIEW_H)

        # ── Card slots (right column) — all positions, empty ones get placeholder
        total_slots = SLOT_COLS * SLOT_ROWS
        for slot_idx in range(total_slots):
            col_idx = slot_idx % SLOT_COLS
            row_idx = slot_idx // SLOT_COLS
            sx = GRID_X_CS + col_idx * (SLOT_W + SLOT_GAP)
            sy = CARD_AREA_TOP + row_idx * (SLOT_H + SLOT_GAP)
            if slot_idx < len(self.chips):
                self._draw_slot(surface, self.chips[slot_idx], slot_idx, sx, sy)
            else:
                pygame.draw.rect(surface, (15, 14, 24),
                                 pygame.Rect(sx, sy, SLOT_W, SLOT_H), border_radius=3)
                pygame.draw.rect(surface, (28, 26, 40),
                                 pygame.Rect(sx, sy, SLOT_W, SLOT_H), 1, border_radius=3)

        # ── Divider above CODE row ─────────────────────────────────────────────
        pygame.draw.line(surface, C.UI_DARK_GOLD,
                         (PAD, CARD_AREA_BOT + 2), (C.CARD_PANEL_W - PAD, CARD_AREA_BOT + 2), 1)
        pygame.draw.line(surface, C.UI_GOLD,
                         (PAD, CARD_AREA_BOT + 3), (C.CARD_PANEL_W - PAD, CARD_AREA_BOT + 3), 1)

        # ── CODE row ──────────────────────────────────────────────────────────
        self._draw_code_row(surface)

        # ── OK button ─────────────────────────────────────────────────────────
        ok_col = (30, 80, 190) if self.selected_indices else (30, 30, 55)
        if self.ok_focused:
            ok_border, border_w = C.WHITE, 3
        elif self.selected_indices:
            ok_border, border_w = C.UI_GOLD, 2
        else:
            ok_border, border_w = C.UI_DARK_GOLD, 1
        pygame.draw.rect(surface, ok_col,
                         pygame.Rect(OK_X, OK_Y, OK_W, OK_H), border_radius=6)
        pygame.draw.rect(surface, ok_border,
                         pygame.Rect(OK_X, OK_Y, OK_W, OK_H), border_w, border_radius=6)
        ok_text = fonts.serif(16, bold=True).render("OK", True,
                                                     C.WHITE if self.selected_indices else (60, 58, 80))
        surface.blit(ok_text,
                     (OK_X + OK_W//2 - ok_text.get_width()//2,
                      OK_Y + OK_H//2 - ok_text.get_height()//2))

    def _draw_large_preview(self, surface, chip, x, y, w, h):
        """Large card detail with art area + description."""
        eb = ELEM_BG.get(chip.element, (40, 36, 68))
        pygame.draw.rect(surface, eb, pygame.Rect(x, y, w, h), border_radius=4)
        # Class stripe
        pygame.draw.rect(surface, CLS_COLOR.get(chip.chip_class, C.WHITE),
                         pygame.Rect(x, y, w, 4), border_radius=4)
        pygame.draw.rect(surface, C.UI_GOLD, pygame.Rect(x, y, w, h), 2, border_radius=4)

        # Code badge (top-right diamond)
        badge_x = x + w - 22
        badge_y = y + 6
        pts = [(badge_x, badge_y - 10), (badge_x + 10, badge_y),
               (badge_x, badge_y + 10), (badge_x - 10, badge_y)]
        pygame.draw.polygon(surface, (30, 90, 200), pts)
        pygame.draw.polygon(surface, C.UI_GOLD, pts, 1)
        cs = fonts.pixel(7, bold=True).render(chip.code, True, C.WHITE)
        surface.blit(cs, (badge_x - cs.get_width()//2, badge_y - cs.get_height()//2))

        # Card name
        ns = fonts.serif(14, bold=True).render(chip.name[:14], True, C.WHITE)
        surface.blit(ns, (x + 6, y + 8))

        # Art area — same height as a card slot for visual harmony
        art_y = y + 30
        art_h = SLOT_H
        art_rect = pygame.Rect(x + 4, art_y, w - 8, art_h)
        art_bg = tuple(min(255, c + 20) for c in eb)
        pygame.draw.rect(surface, art_bg, art_rect, border_radius=3)
        pygame.draw.rect(surface, C.UI_DARK_GOLD, art_rect, 1, border_radius=3)
        # Fill the art rect with the chip icon at its natural 3:4 portrait ratio
        _fill_chip_icon(surface, chip,
                        art_rect.x + 3, art_rect.y + 3,
                        art_rect.w - 6, art_rect.h - 6)

        # Class + damage row
        stat_y = art_y + art_h + 6
        cls_s = fonts.pixel(8, bold=True).render(chip.chip_class, True,
                                                  CLS_COLOR.get(chip.chip_class, C.WHITE))
        surface.blit(cls_s, (x + 6, stat_y))
        _draw_chip_icon_cs(surface, chip, x + 6 + cls_s.get_width() + 10, stat_y + 5, 10)
        if chip.heals:
            dmg_s = fonts.serif(15, bold=True).render(f"+{chip.heals}", True, (80, 220, 80))
        elif chip.damage:
            dmg_s = fonts.serif(15, bold=True).render(str(chip.damage), True, C.WHITE)
        else:
            dmg_s = fonts.serif(13).render("—", True, (120, 115, 140))
        surface.blit(dmg_s, (x + 6, stat_y + 14))

        # Description (word-wrapped lines)
        desc_y = stat_y + 38
        desc = chip.description
        max_chars = max(12, w // 7)
        words = desc.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) <= max_chars:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        for ln in lines[:4]:
            ds = fonts.serif(11).render(ln, True, (160, 150, 190))
            surface.blit(ds, (x + 6, desc_y))
            desc_y += 15

        # ── Lower info section ────────────────────────────────────────────────
        info_y = desc_y + 10
        pygame.draw.line(surface, C.UI_DARK_GOLD, (x + 4, info_y), (x + w - 4, info_y), 1)
        info_y += 8

        # Element affinity
        if chip.element != C.ELEM_NONE:
            en = C.ELEM_NAME.get(chip.element, "")
            ec = C.ELEM_COLOR.get(chip.element, C.WHITE)
            es = fonts.pixel(9).render(f"Element: {en}", True, ec)
            surface.blit(es, (x + 6, info_y))
            info_y += 14
            beaten_by = {v: k for k, v in C.ELEM_BEATS.items()}.get(chip.element)
            if beaten_by:
                bn = C.ELEM_NAME.get(beaten_by, "")
                bs_surf = fonts.pixel(8).render(f"Weak to: {bn}", True, (140, 130, 150))
                surface.blit(bs_surf, (x + 6, info_y))
                info_y += 14
        else:
            ns2 = fonts.pixel(8).render("Element: —", True, (100, 95, 120))
            surface.blit(ns2, (x + 6, info_y))
            info_y += 14

        # Large code letter anchored to bottom of preview — prominent pill
        cc = C.CYAN if chip.code == "*" else C.UI_GOLD
        code_big = fonts.pixel(28, bold=True).render(chip.code, True, cc)
        pill_x = x + w - code_big.get_width() - 20
        pill_y = y + h - code_big.get_height() - 14
        pill_rect = pygame.Rect(pill_x - 5, pill_y - 3,
                                code_big.get_width() + 18, code_big.get_height() + 8)
        pygame.draw.rect(surface, (8, 8, 24), pill_rect, border_radius=5)
        pygame.draw.rect(surface, cc, pill_rect, 2, border_radius=5)
        surface.blit(code_big, (pill_x + 4, pill_y))

    def _draw_slot(self, surface, chip, idx, x, y):
        is_selected = idx in self.selected_indices
        is_cursor   = idx == self.cursor
        can_sel     = self.can_select(idx)

        # Background
        eb = ELEM_BG.get(chip.element, (40, 36, 68))
        if not can_sel:
            eb = (18, 16, 28)
        elif is_selected:
            eb = tuple(min(255, c + 40) for c in eb)
        pygame.draw.rect(surface, eb, pygame.Rect(x, y, SLOT_W, SLOT_H), border_radius=3)

        # Class-colour stripe along the top edge
        stripe = CLS_COLOR.get(chip.chip_class, C.WHITE) if can_sel else (35, 33, 48)
        pygame.draw.rect(surface, stripe, pygame.Rect(x, y, SLOT_W, 3), border_radius=3)

        nc = C.WHITE if can_sel else (55, 52, 70)

        # Card name
        ns = fonts.serif(12, bold=True).render(chip.name[:10], True, nc)
        surface.blit(ns, (x + 5, y + 6))

        # Art area — fills the space between name and bottom strip
        BOTTOM_H = 34
        art_top = y + 22
        art_h_s = SLOT_H - 22 - BOTTOM_H
        art_rect = pygame.Rect(x + 3, art_top, SLOT_W - 6, art_h_s)
        art_bg = tuple(min(255, c + 18) for c in eb) if can_sel else (22, 20, 34)
        pygame.draw.rect(surface, art_bg, art_rect, border_radius=2)
        pygame.draw.rect(surface, C.UI_DARK_GOLD if can_sel else (30, 28, 42),
                         art_rect, 1, border_radius=2)

        # Icon fills art area, aspect-ratio preserved (icons are 3:4 portrait)
        _fill_chip_icon(surface, chip,
                        art_rect.x + 2, art_rect.y + 2,
                        art_rect.w - 4, art_rect.h - 4)

        # ── Bottom strip: prominent code pill + damage value ─────────────────
        strip_y = y + SLOT_H - BOTTOM_H + 3
        cc = C.CYAN if chip.code == "*" else C.UI_GOLD

        # Code letter — prominent pill
        code_s = fonts.pixel(14, bold=True).render(chip.code, True,
                                                    cc if can_sel else (55, 52, 70))
        pill_rect = pygame.Rect(x + 4, strip_y,
                                code_s.get_width() + 10, code_s.get_height() + 4)
        pygame.draw.rect(surface, (10, 10, 26) if can_sel else (10, 10, 18),
                         pill_rect, border_radius=4)
        pygame.draw.rect(surface, cc if can_sel else (40, 38, 55),
                         pill_rect, 1, border_radius=4)
        surface.blit(code_s, (pill_rect.x + 5, pill_rect.y + 2))

        # Damage / heal next to code pill
        val_x = pill_rect.right + 5
        if chip.heals:
            vt, val_c = f"+{chip.heals}", ((80, 240, 80) if can_sel else nc)
        elif chip.damage:
            vt, val_c = str(chip.damage), nc
        else:
            vt, val_c = "", nc
        if vt:
            vs = fonts.serif(13, bold=True).render(vt, True, val_c)
            mid_y = strip_y + (pill_rect.height - vs.get_height()) // 2
            surface.blit(vs, (val_x, mid_y))

        # Selection order badge — right side of bottom strip
        if is_selected:
            order = self.selected_indices.index(idx) + 1
            badge_cx = x + SLOT_W - 11
            badge_cy = strip_y + pill_rect.height // 2
            pygame.draw.circle(surface, C.ORANGE, (badge_cx, badge_cy), 9)
            bs = fonts.pixel(7, bold=True).render(str(order), True, C.WHITE)
            surface.blit(bs, (badge_cx - bs.get_width() // 2,
                              badge_cy - bs.get_height() // 2))

        # Border
        bc = C.WHITE if is_cursor else (C.UI_GOLD if is_selected else C.UI_DARK_GOLD)
        pygame.draw.rect(surface, bc, pygame.Rect(x, y, SLOT_W, SLOT_H),
                         2 if is_cursor else 1, border_radius=3)

    def _draw_code_row(self, surface):
        """Bottom row: 'CODE' label + colored code tiles for each selected card."""
        lbl = fonts.pixel(7, bold=True).render("CODE", True, C.UI_GOLD)
        surface.blit(lbl, (PAD, CODE_Y + (CODE_H - lbl.get_height()) // 2))

        tile_size = CODE_H - 6
        tile_x = PAD + lbl.get_width() + 8
        tile_gap = 4

        if self.pa_chip:
            # Program advance — show PA name instead
            pa_s = fonts.serif(12, bold=True).render(
                f"★ {self.pa_chip.name[:16]} — LIMIT BRK", True, C.YELLOW)
            surface.blit(pa_s, (tile_x, CODE_Y + (CODE_H - pa_s.get_height()) // 2))
            return

        for i in range(self.MAX_SELECTABLE):
            tx = tile_x + i * (tile_size + tile_gap)
            tile_r = pygame.Rect(tx, CODE_Y + 3, tile_size, tile_size)
            if i < len(self.selected_indices):
                chip = self.chips[self.selected_indices[i]]
                bg_col = CLS_TILE_COLOR.get(chip.chip_class, (40, 36, 68))
                pygame.draw.rect(surface, bg_col, tile_r, border_radius=4)
                pygame.draw.rect(surface, C.UI_GOLD, tile_r, 2, border_radius=4)
                cc = C.CYAN if chip.code == "*" else C.WHITE
                code_s = fonts.pixel(9, bold=True).render(chip.code, True, cc)
                surface.blit(code_s,
                             (tile_r.centerx - code_s.get_width()//2,
                              tile_r.centery - code_s.get_height()//2))
            else:
                pygame.draw.rect(surface, (22, 20, 34), tile_r, border_radius=4)
                pygame.draw.rect(surface, C.UI_DARK_GOLD, tile_r, 1, border_radius=4)
