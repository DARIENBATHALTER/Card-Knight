import pygame
import constants as C
import sprite_manager as SM


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
        x = C.GRID_X + self.col * C.PANEL_W
        y = C.GRID_Y + self.row * C.PANEL_H
        return pygame.Rect(x, y, C.PANEL_W, C.PANEL_H)

    def pixel_center(self):
        r = self.pixel_rect()
        return (r.centerx, r.centery)

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

        for p in self.panels:
            rect = p.pixel_rect()
            owner_str = "player" if p.owner == C.OWN_PLAYER else "enemy"

            # Determine tile sprite key
            if p.type in (C.PNL_BROKEN, C.PNL_HOLE):
                tile = SM.get('tile_broken')
                if tile:
                    surface.blit(tile, rect.topleft)
                else:
                    pygame.draw.rect(surface, (10, 10, 10), rect)
                pygame.draw.rect(surface, C.PANEL_LINE, rect, 1)
                continue

            if p.type == C.PNL_GRASS:
                tile_key = 'tile_grass'
            elif p.type == C.PNL_ICE:
                tile_key = 'tile_ice'
            elif p.type == C.PNL_LAVA:
                tile_key = 'tile_lava'
            elif p.type == C.PNL_POISON:
                tile_key = 'tile_poison'
            elif p.type == C.PNL_METAL:
                tile_key = 'tile_metal'
            elif p.type == C.PNL_CRACKED:
                tile_key = f'tile_{owner_str}_cracked'
            else:
                tile_key = f'tile_{owner_str}_normal'

            tile = SM.get(tile_key)
            if tile:
                surface.blit(tile, rect.topleft)
            else:
                pygame.draw.rect(surface, p.base_color(), rect)

            # Row-depth shading — back rows get a dark overlay, front rows clear
            shade = C.ROW_SHADE[p.row]
            if shade < 1.0:
                darkness = int((1.0 - shade) * 200)
                dark_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                dark_surf.fill((0, 0, 0, darkness))
                surface.blit(dark_surf, rect.topleft)

            # Crack overlay
            if p.type == C.PNL_CRACKED:
                pcx, pcy = rect.centerx, rect.centery
                pygame.draw.line(surface, C.DARK_GRAY, (pcx, rect.top+4), (pcx-8, rect.bottom-4), 2)
                pygame.draw.line(surface, C.DARK_GRAY, (pcx-8, pcy), (rect.right-4, pcy+10), 2)

            # Highlight
            if (p.col, p.row) in highlighted_panels:
                s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                s.fill((255, 255, 100, 80))
                surface.blit(s, rect.topleft)

            pygame.draw.rect(surface, C.PANEL_LINE, rect, 1)

        # Center divider
        mid_x = C.GRID_X + 4 * C.PANEL_W
        pygame.draw.line(surface, C.WHITE, (mid_x, C.GRID_Y), (mid_x, C.GRID_BOTTOM), 3)
