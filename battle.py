import pygame
import random
import math
import constants as C
import fonts
from grid import Grid
from entities import Player, Slime
import sprite_manager as SM
from chips import CHIP_EFFECTS, make_sample_folder
from custom_screen import CustomScreen
import effects as FX


def _panel_center(col, row):
    return (
        C.GRID_X + col * C.PANEL_W + C.PANEL_W // 2,
        C.GRID_Y + row * C.PANEL_H + C.PANEL_H // 2,
    )


def _draw_chip_icon(surface, chip, cx, cy, size=14):
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
        pygame.draw.circle(surface, (140, 130, 100), (cx, cy + size//3), 2)
    else:
        for angle in range(0, 180, 45):
            rad = math.radians(angle)
            dx = int(math.cos(rad) * (size // 2))
            dy = int(math.sin(rad) * (size // 2))
            pygame.draw.line(surface, (160, 130, 220),
                             (cx - dx, cy - dy), (cx + dx, cy + dy), 2)


class BattleState:
    OPENING   = "opening"
    CUSTOM    = "custom"
    BATTLE    = "battle"
    CHIP_USE  = "chip_use"
    VICTORY   = "victory"
    DEFEAT    = "defeat"


class Battle:
    def __init__(self, screen, folder=None):
        self.screen = screen
        self.state = BattleState.OPENING
        self.opening_timer = 1.2

        # Outcome flags — read by game.py to decide next state
        self.finished   = False
        self.player_won = False

        # Grid
        self.grid = Grid()

        # Player
        self.player = Player()

        # Enemies (initial wave — enemy side is cols 4-7, rows 0-3)
        self.enemies = [
            Slime(5, 0),
            Slime(6, 2),
            Slime(7, 1),
        ]

        # Effects list
        self.effects = []

        # Folder and chip management
        self.folder = list(folder) if folder is not None else make_sample_folder()
        random.shuffle(self.folder)
        self.folder_idx = 0
        self.chip_queue = []     # chips player has queued for this battle phase
        self.current_chip_idx = 0

        # Custom gauge
        self.custom_gauge = 0.0  # 0.0 → 1.0
        self.gauge_flash = 0.0   # flash when full

        # Custom screen
        self.custom_screen_obj = None

        # Movement rate limiting
        self.move_timer = 0.0
        self.move_cool = 0.14
        self._keys_down = set()

        # Chip use lock
        self.chip_lock_timer = 0.0

        # ZetaCannon PA state
        self._pa_cannon_timer = 0.0
        self._pa_cannon_interval = 0.2
        self._pa_cannon_count = 0

        # Background
        self.bg_timer = 0.0

        # Kick off with custom screen
        self._open_custom_screen()

    # ──────────────────────────────────────────────────────────────────────────
    # Custom screen helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_chips(self, n=5):
        drawn = []
        for _ in range(n):
            if self.folder_idx < len(self.folder):
                drawn.append(self.folder[self.folder_idx])
                self.folder_idx += 1
        return drawn

    def _open_custom_screen(self):
        drawn = self._draw_chips(5)
        if not drawn:
            # Reshuffle and try again
            self.folder = make_sample_folder()
            random.shuffle(self.folder)
            self.folder_idx = 0
            drawn = self._draw_chips(5)
        self.custom_screen_obj = CustomScreen(drawn)
        self.state = BattleState.CUSTOM
        self.custom_gauge = 0.0
        self.gauge_flash = 0.0

    def _close_custom_screen(self):
        selected = self.custom_screen_obj.get_selected_chips()
        self.chip_queue.extend(selected)  # append new chips to existing queue
        self.custom_screen_obj = None
        self.state = BattleState.BATTLE

    # ──────────────────────────────────────────────────────────────────────────
    # Event handling
    # ──────────────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if self.state == BattleState.CUSTOM:
            self.custom_screen_obj.handle_event(event)
            if self.custom_screen_obj.done:
                self._close_custom_screen()
            return

        if self.state == BattleState.VICTORY or self.state == BattleState.DEFEAT:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
                self.player_won = self.state == BattleState.VICTORY
                self.finished   = True
            return

        if self.state != BattleState.BATTLE:
            return

        if event.type == pygame.KEYDOWN:
            self._keys_down.add(event.key)

            # Open custom screen when gauge full
            if event.key in (pygame.K_SPACE, pygame.K_l):
                if self.custom_gauge >= 1.0:
                    self._open_custom_screen()

            # Use chip / buster
            elif event.key == pygame.K_z:
                if self.chip_lock_timer <= 0:
                    self._use_chip_or_buster()

        elif event.type == pygame.KEYUP:
            self._keys_down.discard(event.key)
            # Release X → fire charged if charged enough
            if event.key == pygame.K_x:
                if self.player.charge_held >= C.CHARGE_TIME and self.player.buster_cooldown <= 0:
                    self._fire_buster(charged=True)
                self.player.charge_held = 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # Gameplay actions
    # ──────────────────────────────────────────────────────────────────────────

    def _use_chip_or_buster(self):
        if self.current_chip_idx < len(self.chip_queue):
            chip = self.chip_queue[self.current_chip_idx]
            self.current_chip_idx += 1
            resolver = CHIP_EFFECTS.get(chip.effect_key)
            if resolver:
                resolver(chip, self.player, self.grid, self.enemies, self.effects)
            # Magic circle on nearest enemy in player's row (or any enemy)
            targets_row = [e for e in self.enemies if e.row == self.player.row and e.alive]
            target = targets_row[0] if targets_row else (self.enemies[0] if self.enemies else None)
            if target and target.alive:
                self.effects.insert(0, FX.MagicCircleEffect(
                    target.pixel_center(), chip.element))
            self._post_chip_damage_numbers()
            self.chip_lock_timer = C.CHIP_LOCK_TIME
        else:
            # Buster shot
            if self.player.buster_cooldown <= 0:
                self._fire_buster(charged=False)

    def _fire_buster(self, charged=False):
        dmg = C.CHARGED_DMG if charged else C.BUSTER_DMG
        row = self.player.row

        self.player.buster_cooldown = C.BUSTER_COOL
        if charged:
            self.player.charge_held = 0.0
            self.effects.append(FX.ScreenFlash(C.LIGHT_BLUE, 0.08))

        hit = False
        hit_col = C.GRID_COLS - 1
        for col in range(self.player.col + 1, C.GRID_COLS):
            targets = [e for e in self.enemies if e.col == col and e.row == row and e.alive]
            if targets:
                dealt = targets[0].take_damage(dmg, C.ELEM_NONE)
                if dealt:
                    self.effects.append(FX.DamageNumber(targets[0].pixel_center(), dealt, C.WHITE))
                hit_col = col
                hit = True
                break

        # Panel highlight along the shot path
        path = [(c, row) for c in range(self.player.col + 1, hit_col + 1)]
        if path:
            self.effects.insert(0, FX.PanelFlash(path))

        # Spinning card projectile
        src = _panel_center(self.player.col, row)
        dst = _panel_center(hit_col, row)
        self.effects.append(FX.CardProjectileEffect(src, dst, charged=charged))

        # Impact burst at landing point
        burst_col = (C.LIGHT_BLUE if charged else C.CYAN,
                     (200, 220, 255) if charged else (180, 240, 255))
        self.effects.append(FX.ParticleBurst(
            dst, burst_col[0], count=18, speed=110, color_b=burst_col[1]))

    def _post_chip_damage_numbers(self):
        """Add damage number effects for enemies that were just hit."""
        for e in self.enemies:
            if not e.alive and e.flash_timer > 0:
                # Just died - show defeat sparkle
                self.effects.append(FX.ExplosionEffect(e.pixel_center(), C.YELLOW, 50, 0.4))

    def _zeta_cannon_fire(self):
        """Fire one auto-cannon burst for ZetaCannon PA."""
        row = random.randint(0, C.GRID_ROWS - 1)
        dmg = 200
        for col in range(self.player.col + 1, C.GRID_COLS):
            targets = [e for e in self.enemies if e.col == col and e.row == row and e.alive]
            if targets:
                targets[0].take_damage(dmg, C.ELEM_NONE)
                self.effects.append(FX.ProjectileEffect(
                    _panel_center(self.player.col, row),
                    _panel_center(col, row),
                    C.YELLOW, 10))
                break

    # ──────────────────────────────────────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────────────────────────────────────

    def update(self, dt):
        self.bg_timer += dt

        if self.state == BattleState.OPENING:
            self.opening_timer -= dt
            if self.opening_timer <= 0:
                self.state = BattleState.CUSTOM
                self._open_custom_screen()
            return

        if self.state == BattleState.CUSTOM:
            # Custom screen handles its own input
            return

        if self.state in (BattleState.VICTORY, BattleState.DEFEAT):
            self._update_effects(dt)
            return

        if self.state != BattleState.BATTLE:
            return

        # Custom gauge
        if self.custom_gauge < 1.0:
            self.custom_gauge = min(1.0, self.custom_gauge + dt / C.CUSTOM_GAUGE_TIME)
            if self.custom_gauge >= 1.0:
                self.gauge_flash = 0.5
        if self.gauge_flash > 0:
            self.gauge_flash -= dt

        # Chip lock
        if self.chip_lock_timer > 0:
            self.chip_lock_timer -= dt

        # Player movement
        self._update_player_movement(dt)

        # Charge buster
        keys = pygame.key.get_pressed()
        if keys[pygame.K_x]:
            self.player.charge_held += dt
        else:
            # Release handled in events; reset if not pressed
            pass

        # ZetaCannon PA auto-fire
        if self.player.pa_timer > 0 and self.player.pa_effect == "ZetaCannon":
            self._pa_cannon_timer -= dt
            if self._pa_cannon_timer <= 0:
                self._zeta_cannon_fire()
                self._pa_cannon_timer = self._pa_cannon_interval

        # Player update
        self.player.update(dt)

        # Grid update
        self.grid.update(dt)

        # Enemy updates
        for e in self.enemies:
            if e.alive:
                e.update(dt, self.player, self.grid, self.effects)

        # Effects update
        self._update_effects(dt)

        # Check lava damage for player
        p = self.grid.get(self.player.col, self.player.row)
        if p and p.type == C.PNL_LAVA:
            p.effect_timer += dt
            if p.effect_timer >= 0.5:
                p.effect_timer = 0
                self.player.take_damage(30, C.ELEM_FIRE)

        # Check victory / defeat
        if not any(e.alive for e in self.enemies):
            self.state = BattleState.VICTORY
            self.effects.append(FX.ScreenFlash(C.WHITE, 0.3))
        if not self.player.alive:
            self.state = BattleState.DEFEAT
            self.effects.append(FX.ScreenFlash(C.RED, 0.5))

    def _update_player_movement(self, dt):
        if self.move_timer > 0:
            self.move_timer -= dt
            return
        keys = pygame.key.get_pressed()
        moved = False

        def _try_move(dc, dr):
            nc, nr = self.player.col + dc, self.player.row + dr
            new_p = self.grid.get(nc, nr)
            if new_p and new_p.is_passable() and new_p.owner == C.OWN_PLAYER:
                old = self.grid.get(self.player.col, self.player.row)
                if old:
                    old.on_step_off()
                self.player.phase_move(nc, nr)
                return True
            return False

        if keys[pygame.K_LEFT]:
            moved = _try_move(-1, 0)
        elif keys[pygame.K_RIGHT]:
            moved = _try_move(1, 0)
        elif keys[pygame.K_UP]:
            moved = _try_move(0, -1)
        elif keys[pygame.K_DOWN]:
            moved = _try_move(0, 1)

        if moved:
            self.move_timer = self.move_cool

    def _update_effects(self, dt):
        new_fx = []
        for eff in self.effects:
            eff.update(dt)
            pd = getattr(eff, 'pending_damage', None)
            if pd is not None:
                eff.pending_damage = None
                dealt, entity = pd
                if dealt > 0:
                    is_player = (entity is self.player)
                    color = C.RED if is_player else C.WHITE
                    new_fx.append(FX.DamageNumber(entity.pixel_center(), dealt, color))
                    if is_player:
                        new_fx.append(FX.ScreenFlash(C.RED))
                    elif not entity.alive:
                        new_fx.append(FX.ExplosionEffect(entity.pixel_center(), C.YELLOW, 50, 0.4))
        self.effects = [e for e in self.effects if e.alive] + new_fx

    def _restart(self):
        self.__init__(self.screen)

    # ──────────────────────────────────────────────────────────────────────────
    # Draw
    # ──────────────────────────────────────────────────────────────────────────

    def draw(self):
        surface = self.screen

        # Background gradient
        self._draw_background(surface)

        # Grid
        highlight = set()
        if self.state == BattleState.BATTLE:
            # Highlight chip target panels based on current chip
            pass
        self.grid.draw(surface, highlight)

        # Entities
        if self.player.alive or self.state != BattleState.DEFEAT:
            self.player.draw(surface)
        for e in self.enemies:
            if e.alive:
                e.draw(surface)

        # Effects
        for eff in self.effects:
            eff.draw(surface)

        # HUD
        self._draw_hud(surface)

        # State overlays
        if self.state == BattleState.CUSTOM and self.custom_screen_obj:
            self.custom_screen_obj.draw(surface)

        elif self.state == BattleState.VICTORY:
            self._draw_end_screen(surface, "VIRUS BUSTED!", C.CYAN)

        elif self.state == BattleState.DEFEAT:
            self._draw_end_screen(surface, "JACKED OUT...", C.RED)

        elif self.state == BattleState.OPENING:
            self._draw_opening(surface)

    def _draw_background(self, surface):
        surface.fill(C.HUD_BG)
        # Slow-moving star field
        t = self.bg_timer
        rng = __import__('random').Random(42)
        for _ in range(60):
            sx = rng.randint(0, C.SCREEN_W - 1)
            sy = rng.randint(0, C.SCREEN_H - 1)
            phase = rng.random() * 6.28
            bright = int(80 + 60 * math.sin(t * 1.4 + phase))
            pygame.draw.rect(surface, (bright, bright, bright + 20), (sx, sy, 1, 1))
        # Subtle horizontal scan lines
        for y in range(0, C.SCREEN_H, 3):
            s = pygame.Surface((C.SCREEN_W, 1), pygame.SRCALPHA)
            s.fill((0, 0, 30, 35))
            surface.blit(s, (0, y))

    # ── Decorative helpers ────────────────────────────────────────────────────

    def _draw_gold_rule(self, surface, y):
        """Gold ruled line with small diamond ornaments."""
        pygame.draw.line(surface, C.UI_DARK_GOLD, (0, y + 1), (C.SCREEN_W, y + 1), 1)
        pygame.draw.line(surface, C.UI_GOLD,      (0, y),     (C.SCREEN_W, y),     1)
        for dx in (4, C.SCREEN_W // 2, C.SCREEN_W - 4):
            pts = [(dx, y - 3), (dx + 3, y), (dx, y + 3), (dx - 3, y)]
            pygame.draw.polygon(surface, C.UI_GOLD, pts)

    def _draw_panel_box(self, surface, rect, title=None):
        """Framed navy box with gold border — FF menu style."""
        pygame.draw.rect(surface, C.UI_NAVY,  rect, border_radius=2)
        pygame.draw.rect(surface, C.UI_DARK_GOLD, rect, 2, border_radius=2)
        pygame.draw.rect(surface, C.UI_GOLD,  rect, 1, border_radius=2)
        if title:
            tf = fonts.pixel(7, bold=True)
            ts = tf.render(title, True, C.UI_GOLD)
            surface.blit(ts, (rect.x + 4, rect.y + 2))

    # ── HUD ───────────────────────────────────────────────────────────────────

    # Info section constants
    _PAD = 8
    _PORTRAIT = 64
    _INFO_BOTTOM = _PAD + _PORTRAIT + 10   # y where player info ends → separator

    def _draw_hud(self, surface):
        # ── Left panel (full height) ──────────────────────────────────────────
        pygame.draw.rect(surface, C.UI_NAVY, pygame.Rect(0, 0, C.CARD_PANEL_W, C.SCREEN_H))
        pygame.draw.line(surface, C.UI_DARK_GOLD,
                         (C.CARD_PANEL_W, 0), (C.CARD_PANEL_W, C.SCREEN_H), 1)
        pygame.draw.line(surface, C.UI_GOLD,
                         (C.CARD_PANEL_W - 1, 0), (C.CARD_PANEL_W - 1, C.SCREEN_H), 1)

        # ── Player portrait ───────────────────────────────────────────────────
        p_rect = pygame.Rect(self._PAD, self._PAD, self._PORTRAIT, self._PORTRAIT)
        pygame.draw.rect(surface, (16, 12, 40), p_rect, border_radius=4)
        pygame.draw.rect(surface, C.UI_GOLD, p_rect, 2, border_radius=4)
        face = SM.get('oden_face')
        if face:
            p_scaled = pygame.transform.scale(face, (self._PORTRAIT, self._PORTRAIT))
            surface.blit(p_scaled, (self._PAD, self._PAD))
        else:
            p_surf = SM.get('oden_idle')
            if p_surf:
                if isinstance(p_surf, list):
                    p_surf = p_surf[0]
                p_scaled = pygame.transform.scale(p_surf, (self._PORTRAIT, self._PORTRAIT))
                surface.blit(p_scaled, (self._PAD, self._PAD))

        # Name + HP + gauge (right of portrait)
        ix = self._PAD + self._PORTRAIT + 6
        iw = C.CARD_PANEL_W - ix - self._PAD
        surface.blit(fonts.serif(15, bold=True).render("Oden", True, C.UI_GOLD),
                     (ix, self._PAD + 2))
        self._draw_hp_bar(surface, "HP", self.player.hp, self.player.max_hp,
                          ix, self._PAD + 22, iw, 24, bar_offset=12, font_size=8)
        self._draw_gauge_inline(surface, ix, self._PAD + 52, iw)

        # Separator below info
        sy = self._INFO_BOTTOM
        self._draw_gold_rule(surface, sy)

        # ── Chip queue / active card ──────────────────────────────────────────
        if self.state == BattleState.BATTLE or self.state == BattleState.CHIP_USE:
            self._draw_chip_queue(surface, sy + 8)

        if self.state == BattleState.BATTLE:
            self._draw_controls_hint(surface)

        # ── Right area: portrait strip (y=0 to GRID_Y) ───────────────────────
        rx = C.CARD_PANEL_W + 2
        pygame.draw.rect(surface, C.UI_NAVY,
                         pygame.Rect(rx, 0, C.SCREEN_W - rx, C.GRID_Y))
        pygame.draw.line(surface, C.UI_GOLD,
                         (rx, C.GRID_Y - 1), (C.SCREEN_W, C.GRID_Y - 1), 1)
        pygame.draw.line(surface, C.UI_DARK_GOLD,
                         (rx, C.GRID_Y), (C.SCREEN_W, C.GRID_Y), 1)
        self._draw_portrait_strip(surface, rx)

        # ── Below-grid strip ─────────────────────────────────────────────────
        bot_y = C.GRID_Y + C.GRID_ROWS * C.PANEL_H
        if bot_y < C.SCREEN_H:
            bot_rect = pygame.Rect(rx, bot_y, C.SCREEN_W - rx, C.SCREEN_H - bot_y)
            pygame.draw.rect(surface, C.UI_NAVY, bot_rect)
            pygame.draw.line(surface, C.UI_DARK_GOLD, (rx, bot_y), (C.SCREEN_W, bot_y), 1)
            pygame.draw.line(surface, C.UI_GOLD,      (rx, bot_y + 1), (C.SCREEN_W, bot_y + 1), 1)
            self._draw_battle_info(surface, rx, bot_y + 2)

    def _draw_hp_bar(self, surface, name, hp, max_hp, x, y, w, h,
                     dimmed=False, bar_offset=12, font_size=9, use_serif=False):
        col = C.WHITE if not dimmed else (60, 60, 80)
        nf  = fonts.serif(font_size, bold=True) if use_serif else fonts.pixel(font_size, bold=True)
        ns  = nf.render(name, True, col)
        surface.blit(ns, (x, y))

        bar_y = y + bar_offset
        bar_h = max(4, h - bar_offset)

        pygame.draw.rect(surface, (20, 20, 40), pygame.Rect(x, bar_y, w, bar_h))

        frac    = max(0.0, hp / max_hp)
        fill_w  = int(w * frac)
        bar_col = C.HP_GREEN if frac > 0.5 else (C.HP_YELLOW if frac > 0.25 else C.HP_RED)
        if dimmed:
            bar_col = (40, 40, 50)
        if fill_w > 0:
            seg = max(2, fill_w // 10)
            for sx in range(0, fill_w, seg + 1):
                sw = min(seg, fill_w - sx)
                pygame.draw.rect(surface, bar_col, (x + sx, bar_y, sw, bar_h))

        pygame.draw.rect(surface, C.UI_DARK_GOLD, pygame.Rect(x, bar_y, w, bar_h), 1)

        hp_text = f"{hp}/{max_hp}"
        hf = fonts.serif(max(10, font_size - 2)) if use_serif else fonts.pixel(max(6, font_size - 1))
        ht = hf.render(hp_text, True, col)
        surface.blit(ht, (x + w - ht.get_width() - 2, bar_y + 1))

    def _draw_gauge_inline(self, surface, x, y, w):
        """Compact gauge used in left panel below HP bar."""
        lbl = fonts.pixel(6).render("Custom Gauge", True, (110, 100, 155))
        if self.custom_gauge >= 1.0:
            press = fonts.pixel(6, bold=True).render("SPACE", True, C.UI_GOLD)
            surface.blit(press, (x + w - press.get_width(), y))
        surface.blit(lbl, (x, y))
        gy = y + 11
        gh = 10
        bg = pygame.Rect(x, gy, w, gh)
        pygame.draw.rect(surface, (20, 20, 40), bg)
        fw = int(w * self.custom_gauge)
        if fw > 0:
            gc = C.WHITE if (self.custom_gauge >= 1.0 and int(self.gauge_flash * 8) % 2 == 0) \
                 else (70, 120, 220)
            pygame.draw.rect(surface, gc, pygame.Rect(x, gy, fw, gh))
        pygame.draw.rect(surface, C.UI_DARK_GOLD, bg, 1)

    def _draw_portrait_strip(self, surface, rx):
        """Right-side top strip: custom gauge centered."""
        strip_h = C.GRID_Y
        strip_w = C.SCREEN_W - rx

        gauge_w = min(340, strip_w - 32)
        cx = rx + strip_w // 2
        right_start = cx - gauge_w // 2

        gh = 12
        lbl_h = 14
        total_h = lbl_h + 3 + gh
        gy_base = (strip_h - total_h) // 2

        lbl = fonts.serif(11, bold=True).render("CUSTOM GAUGE", True, C.UI_GOLD)
        surface.blit(lbl, (cx - lbl.get_width() // 2, gy_base))
        gy = gy_base + lbl_h + 3
        bg = pygame.Rect(right_start, gy, gauge_w, gh)
        pygame.draw.rect(surface, (20, 20, 40), bg)
        fw = int(gauge_w * self.custom_gauge)
        if fw > 0:
            gc = C.WHITE if (self.custom_gauge >= 1.0 and int(self.gauge_flash * 8) % 2 == 0) \
                 else (70, 120, 220)
            pygame.draw.rect(surface, gc, pygame.Rect(right_start, gy, fw, gh))
        pygame.draw.rect(surface, C.UI_DARK_GOLD, bg, 1)
        if self.custom_gauge >= 1.0:
            hs = fonts.pixel(7, bold=True).render("SPACE", True, C.UI_GOLD)
            surface.blit(hs, (right_start + gauge_w - hs.get_width(), gy_base))

    _ELEM_BG = {
        C.ELEM_NONE: ( 40,  36,  68),
        C.ELEM_FIRE: ( 80,  30,   8),
        C.ELEM_AQUA: (  8,  44,  80),
        C.ELEM_ELEC: ( 72,  64,   8),
        C.ELEM_WOOD: ( 16,  64,  16),
    }
    _CLS_COLOR = {
        C.CLS_STANDARD: C.ORANGE,
        C.CLS_MEGA:     (100, 160, 255),
        C.CLS_GIGA:     C.RED,
    }

    def _draw_large_card(self, surface, chip, x, y, w, h, dim=False):
        eb = self._ELEM_BG.get(chip.element, (40, 36, 68))
        if dim:
            eb = tuple(max(0, c - 30) for c in eb)
        pygame.draw.rect(surface, eb, pygame.Rect(x, y, w, h), border_radius=3)
        pygame.draw.rect(surface, self._CLS_COLOR.get(chip.chip_class, C.WHITE),
                         pygame.Rect(x, y, w, 4), border_radius=3)
        nc = (90, 86, 110) if dim else C.WHITE
        _draw_chip_icon(surface, chip, x + w - 18, y + 16, 14)
        ns = fonts.serif(14, bold=True).render(chip.name[:14], True, nc)
        surface.blit(ns, (x + 6, y + 8))
        en = C.ELEM_NAME.get(chip.element, "") or "None"
        ec = C.ELEM_COLOR.get(chip.element, C.WHITE) if not dim else (70, 70, 80)
        surface.blit(fonts.pixel(8).render(en, True, ec), (x + 6, y + 28))
        if chip.heals:
            vs = fonts.serif(13, bold=True).render(f"+{chip.heals} HP", True,
                                                    (80, 220, 80) if not dim else nc)
        elif chip.damage:
            vs = fonts.serif(13, bold=True).render(f"{chip.damage} dmg", True, nc)
        else:
            vs = fonts.serif(12).render("utility", True, (140, 135, 160) if not dim else nc)
        surface.blit(vs, (x + 6, y + 44))
        cc = (60, 58, 80) if dim else (C.CYAN if chip.code == "*" else C.UI_GOLD)
        code_s = fonts.pixel(18, bold=True).render(chip.code, True, cc)
        surface.blit(code_s, (x + w - code_s.get_width() - 8, y + h - code_s.get_height() - 6))
        border_c = (50, 48, 68) if dim else C.UI_GOLD
        pygame.draw.rect(surface, border_c, pygame.Rect(x, y, w, h), 1, border_radius=3)

    def _draw_chip_queue(self, surface, start_y=None):
        ix = C.CHIP_QUEUE_X
        iy = start_y if start_y is not None else (self._INFO_BOTTOM + 8)
        pw = C.CARD_PANEL_W - ix * 2

        surface.blit(fonts.serif(16, bold=True).render("Actions", True, C.UI_GOLD), (ix, iy))
        iy += 22

        remaining = self.chip_queue[self.current_chip_idx:]
        if not remaining:
            surface.blit(fonts.serif(13).render("— no cards —", True, (50, 48, 68)), (ix, iy))
            return

        # Active card (large preview)
        active = remaining[0]
        self._draw_large_card(surface, active, ix, iy, pw, 120)
        iy += 126

        # Queued cards (small row)
        if len(remaining) > 1:
            card_w = min(42, (pw - (len(remaining) - 2) * 4) // max(1, len(remaining) - 1))
            for j, chip in enumerate(remaining[1:]):
                cx2 = ix + j * (card_w + 4)
                if cx2 + card_w > C.CARD_PANEL_W - 4:
                    break
                cr = pygame.Rect(cx2, iy, card_w, 30)
                bg = {C.CLS_STANDARD: (55, 42, 10),
                      C.CLS_MEGA:     (10, 28, 72),
                      C.CLS_GIGA:     (55,  8,  8)}.get(chip.chip_class, (30, 30, 40))
                pygame.draw.rect(surface, bg, cr, border_radius=2)
                pygame.draw.rect(surface, C.UI_DARK_GOLD, cr, 1, border_radius=2)
                ns = fonts.pixel(7, bold=True).render(chip.name[:5], True, C.WHITE)
                surface.blit(ns, (cr.centerx - ns.get_width() // 2, iy + 3))
                vt = (f"+{chip.heals}" if chip.heals
                      else str(chip.damage) if chip.damage else chip.code)
                vs = fonts.pixel(7).render(vt, True, (180, 175, 200))
                surface.blit(vs, (cr.centerx - vs.get_width() // 2, iy + 17))

    def _draw_controls_hint(self, surface):
        hints = [
            ("Arrows", "Move"),
            ("Z",      "Use card / buster"),
            ("X",      "Hold: charge shot"),
            ("Space",  "CUSTOM!" if self.custom_gauge >= 1.0 else "Custom (gauge full)"),
        ]
        bf = fonts.pixel(8, bold=True)
        nf = fonts.pixel(7)
        y = C.SCREEN_H - 62
        for key, desc in hints:
            ks = bf.render(key, True, C.UI_GOLD if "CUSTOM" in desc else C.UI_DARK_GOLD)
            ds = nf.render(f": {desc}", True, (80, 75, 100))
            surface.blit(ks, (8, y))
            surface.blit(ds, (8 + ks.get_width(), y))
            y += 14

    def _draw_battle_info(self, surface, rx, y):
        """Info panel below the battlefield grid."""
        pad = 12
        area_w = C.SCREEN_W - rx
        area_h = C.SCREEN_H - y

        # Objective box (left half)
        box_w = area_w // 2 - pad
        box_h = min(80, area_h - pad)
        box_rect = pygame.Rect(rx + pad, y + pad, box_w, box_h)
        self._draw_panel_box(surface, box_rect, "Objective")
        alive_count = sum(1 for e in self.enemies if e.alive)
        total_count = len(self.enemies)
        obj_s = fonts.serif(12).render(
            f"Defeat all enemies ({alive_count}/{total_count} remain)", True,
            C.UI_GOLD if alive_count > 0 else C.HP_GREEN
        )
        surface.blit(obj_s, (box_rect.x + 6, box_rect.y + 18))

        # Enemy roster box (right half)
        ex = rx + pad + box_w + pad
        ew = area_w - box_w - pad * 3
        ew = max(60, ew)
        er = pygame.Rect(ex, y + pad, ew, box_h)
        self._draw_panel_box(surface, er, "Enemies")
        ey = er.y + 18
        for e in self.enemies:
            col = (55, 52, 70) if not e.alive else C.WHITE
            ns = fonts.serif(11).render(
                f"{'✓' if not e.alive else '►'} {e.name}", True, col
            )
            if ey + ns.get_height() <= er.bottom - 2:
                surface.blit(ns, (er.x + 6, ey))
                ey += 14

    def _draw_end_screen(self, surface, message, color):
        overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))

        font = fonts.pixel(26, bold=True)
        text   = font.render(message, True, color)
        shadow = font.render(message, True, C.BLACK)
        cx = C.SCREEN_W // 2 - text.get_width() // 2
        cy = C.SCREEN_H // 2 - text.get_height() // 2
        surface.blit(shadow, (cx + 2, cy + 2))
        surface.blit(text,   (cx, cy))

        sub_font = fonts.pixel(10)
        sub = sub_font.render("Press Z to play again", True, C.WHITE)
        surface.blit(sub, (C.SCREEN_W // 2 - sub.get_width() // 2, cy + 36))

    def _draw_opening(self, surface):
        font = fonts.pixel(20, bold=True)
        t = font.render("BATTLE START!", True, C.UI_GOLD)
        shadow = font.render("BATTLE START!", True, C.UI_DARK_GOLD)
        cx = C.SCREEN_W // 2 - t.get_width() // 2
        cy = C.SCREEN_H // 2 - t.get_height() // 2
        surface.blit(shadow, (cx + 2, cy + 2))
        surface.blit(t, (cx, cy))
