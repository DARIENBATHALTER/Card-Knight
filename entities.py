import pygame
import math
import random
import constants as C
import effects as FX
import sprite_manager as SM


def _flash_white_surf(surf: pygame.Surface) -> pygame.Surface:
    t = surf.copy()
    white = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    white.fill((255, 255, 255, 170))
    t.blit(white, (0, 0))
    return t


def _panel_center(col, row):
    x = C.GRID_X + col * C.PANEL_W + C.PANEL_W // 2
    y = C.GRID_Y + (row + 1) * C.PANEL_H   # bottom of tile = ground level
    return (x, y)


class Entity:
    def __init__(self, col, row, hp, element=C.ELEM_NONE):
        self.col = col
        self.row = row
        self.hp = hp
        self.max_hp = hp
        self.element = element
        self.alive = True
        self.iframe_timer = 0.0
        self.anim_timer = 0.0

    def take_damage(self, amount, attacker_element=C.ELEM_NONE):
        if not self.alive or self.iframe_timer > 0:
            return 0
        mult = 1.0
        if attacker_element != C.ELEM_NONE:
            if C.ELEM_BEATS.get(attacker_element) == self.element:
                mult = 2.0
        dmg = max(1, int(amount * mult))
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def pixel_center(self):
        return _panel_center(self.col, self.row)

    def update(self, dt):
        self.anim_timer += dt
        if self.iframe_timer > 0:
            self.iframe_timer -= dt


# ──────────────────────────────────────────────────────────────────────────────
# Player
# ──────────────────────────────────────────────────────────────────────────────

class Player(Entity):
    PHASE_DURATION = 0.13   # total seconds for the phase-in/out effect

    def __init__(self):
        super().__init__(1, 1, 5000, C.ELEM_NONE)
        self.col = 1
        self.row = 1
        self.chip_queue = []
        self.charge_held = 0.0
        self.buster_cooldown = 0.0
        self.guarding = False
        self.guard_timer = 0.0
        self.pa_timer = 0.0
        self.pa_effect = None
        self.flash_timer = 0.0
        self.move_dir = [0, 0]
        # Phase movement
        self._phase_t    = 1.0   # 1.0 = not phasing
        self._phase_src  = (1, 1)
        self._phase_dst  = (1, 1)

    def take_damage(self, amount, attacker_element=C.ELEM_NONE):
        if self.guarding:
            return 0
        dmg = super().take_damage(amount, attacker_element)
        if dmg:
            self.iframe_timer = C.PLAYER_IFRAMES
            self.flash_timer = 0.1
        return dmg

    def phase_move(self, new_col, new_row):
        """Trigger the phase effect and teleport to new tile."""
        self._phase_src = (self.col, self.row)
        self._phase_dst = (new_col, new_row)
        self._phase_t   = 0.0
        self.col = new_col
        self.row = new_row

    def update(self, dt):
        super().update(dt)
        if self._phase_t < 1.0:
            self._phase_t = min(1.0, self._phase_t + dt / self.PHASE_DURATION)
        if self.buster_cooldown > 0:
            self.buster_cooldown -= dt
        if self.guard_timer > 0:
            self.guard_timer -= dt
            if self.guard_timer <= 0:
                self.guarding = False
        if self.pa_timer > 0:
            self.pa_timer -= dt
        if self.flash_timer > 0:
            self.flash_timer -= dt

    def draw(self, surface):
        cx, cy = self.pixel_center()

        if self.iframe_timer > 0 and int(self.iframe_timer * 12) % 2 == 0:
            return

        # Pick frame
        if self.flash_timer > 0:
            frames = SM.get('oden_hurt') or SM.get('player_hurt_flash')
        else:
            frames = SM.get('oden_battle') or SM.get('oden_idle') or SM.get('player_idle')

        if frames:
            idx = int(self.anim_timer * 6) % len(frames)
            base_frame = frames[idx]
        else:
            base_frame = None

        fw = base_frame.get_width()  if base_frame else 36
        fh = base_frame.get_height() if base_frame else 46

        # Phase effect: t < 1 means we're mid-phase
        if self._phase_t < 1.0:
            t = self._phase_t
            # First half: depart from src — squish + lift + fade out
            # Second half: arrive at dst — unsquish + drop + fade in
            if t < 0.5:
                progress = t / 0.5                 # 0→1 during depart
                draw_cx, draw_cy = _panel_center(*self._phase_src)
                scale_x = 1.0 - progress * 0.4    # compress to 60% width
                scale_y = 1.0 - progress * 0.7    # compress to 30% height
                lift    = int(progress * fh * 0.5) # lift upward
                alpha   = int((1.0 - progress) * 255)
            else:
                progress = (t - 0.5) / 0.5        # 0→1 during arrive
                draw_cx, draw_cy = cx, cy
                scale_x = 0.6 + progress * 0.4    # expand back to 100%
                scale_y = 0.3 + progress * 0.7
                lift    = int((1.0 - progress) * fh * 0.5)
                alpha   = int(progress * 255)

            if base_frame:
                new_w = max(2, int(fw * scale_x))
                new_h = max(2, int(fh * scale_y))
                scaled = pygame.transform.scale(base_frame, (new_w, new_h))
                scaled.set_alpha(alpha)
                surface.blit(scaled, (draw_cx - new_w // 2, draw_cy - new_h - lift))
            return

        # Normal draw — feet at ground
        if base_frame:
            surface.blit(base_frame, (cx - fw // 2, cy - fh))
        else:
            body_color = C.BLUE if not self.guarding else C.LIGHT_BLUE
            pygame.draw.rect(surface, body_color,
                             pygame.Rect(cx - fw//2, cy - fh, fw, fh), border_radius=4)

        # Guard indicator
        if self.guarding:
            pygame.draw.rect(surface, C.WHITE,
                             pygame.Rect(cx - fw//2 - 4, cy - fh - 4, fw + 8, fh + 8),
                             3, border_radius=4)

        # PA glow
        if self.pa_timer > 0:
            glow = pygame.Surface((fw + 20, fh + 20), pygame.SRCALPHA)
            glow.fill((200, 200, 50, 80))
            surface.blit(glow, (cx - fw//2 - 10, cy - fh - 10))

        # Charge indicator
        if self.charge_held > 0.5:
            frac = min(1.0, self.charge_held / C.CHARGE_TIME)
            charge_color = C.YELLOW if frac < 1.0 else C.WHITE
            radius = int(6 + frac * 12)
            glow = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*charge_color, 160), (radius + 2, radius + 2), radius)
            surface.blit(glow, (cx + fw//2 - radius + 6, cy - fh // 2 - radius))


# ──────────────────────────────────────────────────────────────────────────────
# Enemies
# ──────────────────────────────────────────────────────────────────────────────

class Enemy(Entity):
    name = "Enemy"
    HP = 60
    ELEM = C.ELEM_NONE
    COLOR = C.RED

    def __init__(self, col, row):
        super().__init__(col, row, self.HP, self.ELEM)
        self.ai_state = "idle"
        self.ai_timer = 0.0
        self.flash_timer = 0.0

    def take_damage(self, amount, attacker_element=C.ELEM_NONE):
        dmg = super().take_damage(amount, attacker_element)
        if dmg:
            self.flash_timer = 0.15
        return dmg

    def update(self, dt, player, grid, eff_list):
        super().update(dt)
        if self.flash_timer > 0:
            self.flash_timer -= dt
        self._ai(dt, player, grid, eff_list)

    def _ai(self, dt, player, grid, eff_list):
        pass

    def _fire_projectile(self, player, eff_list, dmg, color, radius):
        """Fire a traveling projectile toward the player — player can dodge by changing row."""
        row = self.row
        src_x = C.GRID_X + self.col * C.PANEL_W + C.PANEL_W // 2

        # Panel flash: warn all cols between player's side and enemy (longer duration for travel time)
        path = [(c, row) for c in range(0, self.col)]
        if path:
            eff_list.insert(0, FX.PanelFlash(path, duration=0.72))

        # TravelingHit: damage deferred — applied only if player is still on this row
        eff_list.append(FX.TravelingHit(
            (src_x, 0), row, self.col, 0,
            dmg, self.element, player, color, radius
        ))

    def _try_move(self, dcol, drow, grid):
        nc = self.col + dcol
        nr = self.row + drow
        if 4 <= nc < C.GRID_COLS and 0 <= nr < C.GRID_ROWS:
            p = grid.get(nc, nr)
            if p and p.is_passable():
                old_panel = grid.get(self.col, self.row)
                if old_panel:
                    old_panel.on_step_off()
                self.col = nc
                self.row = nr
                return True
        return False

    def sprite_key(self):
        return None

    def draw(self, surface):
        cx, cy = self.pixel_center()
        key = self.sprite_key()
        frames = SM.get(key) if key else None
        if frames:
            if isinstance(frames, list):
                idx = int(self.anim_timer * 6) % len(frames)
                frame = frames[idx]
            else:
                frame = frames
            if self.flash_timer > 0:
                frame = _flash_white_surf(frame)
            fw, fh = frame.get_size()
            surface.blit(frame, (cx - fw // 2, cy - fh))   # feet at ground
            self._draw_float_hp(surface, cx, cy - fh - 4, fw)
        else:
            color = C.WHITE if self.flash_timer > 0 else self.COLOR
            self._draw_body(surface, cx, cy, color)
            self._draw_float_hp(surface, cx, cy - 52, 40)

    def _draw_float_hp(self, surface, cx, top_y, sprite_w):
        """Draw a small floating HP bar and number above the sprite."""
        bar_w = max(40, sprite_w)
        bar_h = 5
        bx = cx - bar_w // 2
        by = top_y - bar_h - 2
        pygame.draw.rect(surface, (20, 20, 40), pygame.Rect(bx, by, bar_w, bar_h))
        frac = max(0.0, self.hp / self.max_hp)
        fw = int(bar_w * frac)
        if fw > 0:
            bar_c = C.HP_GREEN if frac > 0.5 else (C.HP_YELLOW if frac > 0.25 else C.HP_RED)
            pygame.draw.rect(surface, bar_c, pygame.Rect(bx, by, fw, bar_h))
        pygame.draw.rect(surface, C.UI_DARK_GOLD, pygame.Rect(bx, by, bar_w, bar_h), 1)
        import fonts as _fonts
        hp_s = _fonts.pixel(8).render(str(self.hp), True, C.WHITE)
        surface.blit(hp_s, (cx - hp_s.get_width() // 2, by - hp_s.get_height() - 1))

    def _draw_body(self, surface, cx, cy, color):
        pygame.draw.rect(surface, color,
                         pygame.Rect(cx - 18, cy - 44, 36, 44), border_radius=4)


# ── Mettaur ──────────────────────────────────────────────────────────────────

class Mettaur(Enemy):
    name = "Mettaur"
    HP = 40
    ELEM = C.ELEM_NONE
    COLOR = (200, 190, 30)

    # AI states: hiding → popping → exposed → shooting → hiding
    HIDE_TIME    = 3.6
    POP_TIME     = 0.6
    EXPOSED_TIME = 1.2
    SHOOT_TIME   = 0.5

    def __init__(self, col, row):
        super().__init__(col, row)
        self.ai_state = "hiding"
        self.ai_timer = self.HIDE_TIME
        self.hiding = True  # invincible flag

    def sprite_key(self):
        state_map = {
            "hiding":   "mettaur_hiding",
            "popping":  "mettaur_pop",
            "exposed":  "mettaur_exposed",
            "shooting": "mettaur_shoot",
        }
        return state_map.get(self.ai_state, "mettaur_hiding")

    def take_damage(self, amount, attacker_element=C.ELEM_NONE):
        if self.hiding:
            return 0
        return super().take_damage(amount, attacker_element)

    def _ai(self, dt, player, grid, eff_list):
        self.ai_timer -= dt
        if self.ai_state == "hiding":
            self.hiding = True
            if self.ai_timer <= 0:
                self.ai_state = "popping"
                self.ai_timer = self.POP_TIME

        elif self.ai_state == "popping":
            self.hiding = False
            if self.ai_timer <= 0:
                self.ai_state = "exposed"
                self.ai_timer = self.EXPOSED_TIME

        elif self.ai_state == "exposed":
            if self.ai_timer <= 0:
                self.ai_state = "shooting"
                self.ai_timer = self.SHOOT_TIME

        elif self.ai_state == "shooting":
            if self.ai_timer <= 0:
                self._fire_projectile(player, eff_list, 30, C.YELLOW, 6)
                self.ai_state = "hiding"
                self.ai_timer = self.HIDE_TIME

    def _draw_body(self, surface, cx, cy, color):
        helmet_color = color
        # Draw helmet (triangle on top of rectangular head)
        helmet_pts = [
            (cx, cy - 38),
            (cx - 20, cy - 14),
            (cx + 20, cy - 14),
        ]
        pygame.draw.polygon(surface, helmet_color, helmet_pts)
        pygame.draw.polygon(surface, C.DARK_GRAY, helmet_pts, 2)

        if not self.hiding:
            # Body under helmet
            pygame.draw.rect(surface, color,
                             pygame.Rect(cx - 14, cy - 14, 28, 28), border_radius=3)
            # Eyes
            pygame.draw.circle(surface, C.BLACK, (cx - 6, cy - 4), 4)
            pygame.draw.circle(surface, C.BLACK, (cx + 6, cy - 4), 4)
            pygame.draw.circle(surface, C.WHITE, (cx - 5, cy - 5), 2)
            pygame.draw.circle(surface, C.WHITE, (cx + 7, cy - 5), 2)
        else:
            # Only helmet + tiny eyes peeking
            pygame.draw.circle(surface, C.BLACK, (cx - 5, cy - 6), 3)
            pygame.draw.circle(surface, C.BLACK, (cx + 5, cy - 6), 3)


# ── Spikey ───────────────────────────────────────────────────────────────────

class Spikey(Enemy):
    name = "Spikey"
    HP = 60
    ELEM = C.ELEM_FIRE
    COLOR = (210, 80, 30)

    IDLE_TIME  = 2.4
    SHOOT_TIME = 0.7

    def __init__(self, col, row):
        super().__init__(col, row)
        self.ai_state = "idle"
        self.ai_timer = self.IDLE_TIME

    def sprite_key(self):
        return "spikey_shoot" if self.ai_state == "shooting" else "spikey_idle"

    def _ai(self, dt, player, grid, eff_list):
        self.ai_timer -= dt
        if self.ai_state == "idle":
            if self.ai_timer <= 0:
                # Randomly move to adjacent row
                dr = random.choice([-1, 0, 1])
                self._try_move(0, dr, grid)
                self.ai_state = "shooting"
                self.ai_timer = self.SHOOT_TIME

        elif self.ai_state == "shooting":
            if self.ai_timer <= 0:
                self._fire_projectile(player, eff_list, 40, C.ORANGE, 8)
                self.ai_state = "idle"
                self.ai_timer = self.IDLE_TIME

    def _draw_body(self, surface, cx, cy, color):
        # Body
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 16, cy - 14, 32, 28))
        # Spikes on top
        for i, x_off in enumerate([-12, -4, 4, 12]):
            pts = [
                (cx + x_off, cy - 14),
                (cx + x_off - 4, cy - 28),
                (cx + x_off + 4, cy - 28),
            ]
            pygame.draw.polygon(surface, color, pts)
        # Eyes
        pygame.draw.circle(surface, C.YELLOW, (cx - 7, cy - 4), 5)
        pygame.draw.circle(surface, C.YELLOW, (cx + 7, cy - 4), 5)
        pygame.draw.circle(surface, C.BLACK, (cx - 7, cy - 4), 3)
        pygame.draw.circle(surface, C.BLACK, (cx + 7, cy - 4), 3)


# ── Bunny ─────────────────────────────────────────────────────────────────────

class Bunny(Enemy):
    name = "Bunny"
    HP = 30
    ELEM = C.ELEM_ELEC
    COLOR = (230, 230, 230)

    HOP_TIME   = 1.2
    SHOOT_TIME = 0.8

    def __init__(self, col, row):
        super().__init__(col, row)
        self.ai_state = "hop"
        self.ai_timer = self.HOP_TIME
        self.hop_count = 0

    def sprite_key(self):
        return "bunny_shoot" if self.ai_state == "shooting" else "bunny_hop"

    def _ai(self, dt, player, grid, eff_list):
        self.ai_timer -= dt
        if self.ai_state == "hop":
            if self.ai_timer <= 0:
                # Hop toward player (left = lower col)
                moved = self._try_move(-1, 0, grid)
                if not moved:
                    # At leftmost enemy column, retreat
                    self._try_move(1, 0, grid)
                self.hop_count += 1
                if self.hop_count >= 2:
                    self.hop_count = 0
                    self.ai_state = "shooting"
                    self.ai_timer = self.SHOOT_TIME
                else:
                    self.ai_timer = self.HOP_TIME

        elif self.ai_state == "shooting":
            if self.ai_timer <= 0:
                self._fire_projectile(player, eff_list, 20, C.YELLOW, 7)
                self.ai_state = "hop"
                self.ai_timer = self.HOP_TIME

    def _draw_body(self, surface, cx, cy, color):
        # Body
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 14, cy - 10, 28, 26))
        # Head
        pygame.draw.circle(surface, color, (cx, cy - 18), 14)
        # Ears
        pygame.draw.ellipse(surface, color, pygame.Rect(cx - 14, cy - 40, 8, 22))
        pygame.draw.ellipse(surface, C.PINK, pygame.Rect(cx - 12, cy - 38, 4, 18))
        pygame.draw.ellipse(surface, color, pygame.Rect(cx + 6, cy - 40, 8, 22))
        pygame.draw.ellipse(surface, C.PINK, pygame.Rect(cx + 8, cy - 38, 4, 18))
        # Eyes
        pygame.draw.circle(surface, C.RED, (cx - 5, cy - 20), 3)
        pygame.draw.circle(surface, C.RED, (cx + 5, cy - 20), 3)


# ── Canodumb ─────────────────────────────────────────────────────────────────

class Canodumb(Enemy):
    name = "Canodumb"
    HP = 80
    ELEM = C.ELEM_NONE
    COLOR = (100, 100, 130)

    IDLE_TIME  = 4.0
    SHOOT_TIME = 0.6

    def __init__(self, col, row):
        super().__init__(col, row)
        self.ai_state = "idle"
        self.ai_timer = self.IDLE_TIME

    def sprite_key(self):
        return "canodumb_shoot" if self.ai_state == "shooting" else "canodumb_idle"

    def _ai(self, dt, player, grid, eff_list):
        self.ai_timer -= dt
        if self.ai_state == "idle":
            if self.ai_timer <= 0:
                self.ai_state = "shooting"
                self.ai_timer = self.SHOOT_TIME

        elif self.ai_state == "shooting":
            if self.ai_timer <= 0:
                # Fires at player's row
                self._fire_projectile(player, eff_list, 60, C.GRAY, 9)
                self.ai_state = "idle"
                self.ai_timer = self.IDLE_TIME

    def _draw_body(self, surface, cx, cy, color):
        # Base / treads
        pygame.draw.rect(surface, C.DARK_GRAY,
                         pygame.Rect(cx - 20, cy + 4, 40, 14), border_radius=4)
        # Body box
        pygame.draw.rect(surface, color,
                         pygame.Rect(cx - 18, cy - 16, 36, 24), border_radius=3)
        # Cannon barrel pointing left
        pygame.draw.rect(surface, C.DARK_GRAY,
                         pygame.Rect(cx - 30, cy - 6, 20, 10), border_radius=3)
        pygame.draw.rect(surface, C.GRAY,
                         pygame.Rect(cx - 32, cy - 4, 6, 6), border_radius=2)
        # Eye/sensor
        pygame.draw.circle(surface, C.RED, (cx + 6, cy - 6), 5)
        pygame.draw.circle(surface, C.ORANGE, (cx + 6, cy - 6), 3)


# ── Slime ─────────────────────────────────────────────────────────────────────

class Slime(Enemy):
    name = "Slime"
    HP = 60
    ELEM = C.ELEM_WOOD
    COLOR = (50, 200, 50)

    IDLE_TIME   = 1.8
    MOVE_TIME   = 0.4
    ATTACK_TIME = 0.5

    def __init__(self, col, row):
        super().__init__(col, row)
        self.ai_state = "idle"
        self.ai_timer = self.IDLE_TIME

    def sprite_key(self):
        if self.flash_timer > 0:
            return 'gen_slime_hurt'
        return 'gen_slime_idle'

    def draw(self, surface):
        cx, cy = self.pixel_center()
        key = self.sprite_key()
        frames = SM.get(key)
        if frames:
            idx = int(self.anim_timer * 6) % len(frames)
            frame = frames[idx]
            if self.flash_timer > 0:
                frame = _flash_white_surf(frame)
            fw, fh = frame.get_size()
            surface.blit(frame, (cx - fw // 2, cy - fh))
            self._draw_float_hp(surface, cx, cy - fh - 4, fw)
        else:
            color = C.WHITE if self.flash_timer > 0 else self.COLOR
            self._draw_body(surface, cx, cy, color)
            self._draw_float_hp(surface, cx, cy - 32, 40)

    def _ai(self, dt, player, grid, eff_list):
        self.ai_timer -= dt
        if self.ai_state == "idle":
            if self.ai_timer <= 0:
                if abs(self.row - player.row) <= 1:
                    self.ai_state = "attacking"
                    self.ai_timer = self.ATTACK_TIME
                else:
                    self._try_move(0, 1 if player.row > self.row else -1, grid)
                    self.ai_timer = self.MOVE_TIME

        elif self.ai_state == "attacking":
            if self.ai_timer <= 0:
                self._fire_projectile(player, eff_list, 30, (50, 200, 80), 6)
                self.ai_state = "idle"
                self.ai_timer = self.IDLE_TIME

    def _draw_body(self, surface, cx, cy, color):
        pygame.draw.ellipse(surface, color,
                            pygame.Rect(cx - 16, cy - 10, 32, 22))
        pygame.draw.ellipse(surface, (30, 140, 30),
                            pygame.Rect(cx - 16, cy - 10, 32, 22), 2)
        pygame.draw.circle(surface, C.BLACK, (cx - 5, cy - 4), 3)
        pygame.draw.circle(surface, C.BLACK, (cx + 5, cy - 4), 3)
