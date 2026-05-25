import pygame
import constants as C
import sprite_manager as SM
import tile_warp


class Panel:
    def __init__(self, col, row, owner):
        self.col = col
        self.row = row
        self.owner = owner         # OWN_PLAYER or OWN_ENEMY
        self.type = C.PNL_NORMAL
        self.crack_timer = 0.0     # for cracked panels
        self.broken_timer = 0.0    # regeneration countdown when broken
        self.effect_timer = 0.0    # general timer for effects (lava damage etc.)

    def pixel_rect(self):
        """Bounding rect of the warped tile (for highlight/overlay purposes)."""
        quad = tile_warp.tile_quad(self.col, self.row)
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        return pygame.Rect(int(min(xs)), int(min(ys)),
                           int(max(xs) - min(xs)), int(max(ys) - min(ys)))

    def pixel_center(self):
        return tile_warp.tile_center(self.col, self.row)

    def update(self, dt):
        if self.type == C.PNL_BROKEN:
            self.broken_timer -= dt
            if self.broken_timer <= 0:
                self.type = C.PNL_NORMAL

    def crack(self):
        """Crack a normal panel; broken panels become holes-ish."""
        if self.type == C.PNL_NORMAL:
            self.type = C.PNL_CRACKED
        elif self.type == C.PNL_CRACKED:
            self.type = C.PNL_BROKEN
            self.broken_timer = 5.0
        elif self.type == C.PNL_GRASS:
            self.type = C.PNL_CRACKED
        elif self.type == C.PNL_ICE:
            self.type = C.PNL_CRACKED

    def on_step_off(self):
        """Called when an entity steps off this panel."""
        if self.type == C.PNL_CRACKED:
            self.type = C.PNL_BROKEN
            self.broken_timer = 5.0

    def is_passable(self):
        return self.type not in (C.PNL_BROKEN, C.PNL_HOLE)

    def base_color(self):
        """Return the base fill color for this panel based on owner."""
        if self.owner == C.OWN_PLAYER:
            return C.PLAYER_PANEL
        return C.ENEMY_PANEL

    def light_color(self):
        if self.owner == C.OWN_PLAYER:
            return C.PLAYER_LIGHT
        return C.ENEMY_LIGHT


class Grid:
    def __init__(self):
        self.panels = []
        for row in range(C.GRID_ROWS):
            for col in range(C.GRID_COLS):
                owner = C.OWN_PLAYER if col < 4 else C.OWN_ENEMY
                self.panels.append(Panel(col, row, owner))

    def get(self, col, row):
        if 0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS:
            return self.panels[row * C.GRID_COLS + col]
        return None

    def update(self, dt):
        for p in self.panels:
            p.update(dt)

    def crack_panel(self, col, row):
        p = self.get(col, row)
        if p:
            p.crack()

    def area_grab(self, num_cols=1):
        """Steal num_cols columns from enemy side, shifting enemy panels to the right."""
        for row in range(C.GRID_ROWS):
            for c_off in range(num_cols):
                target_col = 4 - num_cols + c_off
                src_col = 4 + c_off
                t = self.get(target_col, row)
                s = self.get(src_col, row)
                if t:
                    t.owner = C.OWN_PLAYER
                if s:
                    s.owner = C.OWN_PLAYER

    def draw(self, surface, highlighted_panels=None):
        if highlighted_panels is None:
            highlighted_panels = set()

        # Iterate back-to-front so depth-sorting is natural.
        tiles_cache = SM.get('bf_tiles')

        for row in range(C.GRID_ROWS):
            for col in range(C.GRID_COLS):
                p = self.get(col, row)
                if p is None:
                    continue

                # Broken / hole panels render dark
                if p.type in (C.PNL_BROKEN, C.PNL_HOLE):
                    quad = tile_warp.tile_quad(col, row)
                    pygame.draw.polygon(surface, (15, 15, 25),
                                        [(int(x), int(y)) for x, y in quad])
                    continue

                # Baked perspective tile sprite for this (col, row, owner)
                if tiles_cache and (col, row, p.owner) in tiles_cache:
                    surf, anchor = tiles_cache[(col, row, p.owner)]
                    surface.blit(surf, anchor)
                else:
                    # Fallback: solid trapezoid polygon
                    quad = tile_warp.tile_quad(col, row)
                    pygame.draw.polygon(surface, p.base_color(),
                                        [(int(x), int(y)) for x, y in quad])

                # Highlight overlay (target preview, etc.)
                if (col, row) in highlighted_panels:
                    quad = tile_warp.tile_quad(col, row)
                    poly = [(int(x), int(y)) for x, y in quad]
                    overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.polygon(overlay, (255, 240, 120, 90), poly)
                    surface.blit(overlay, (0, 0))
