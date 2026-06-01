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
import tile_warp
import sfx
import gamepad
from music import music as _music, track_path


def _panel_center(col, row):
    """Center of tile (col, row) — used as VFX source/target."""
    return tile_warp.tile_center(col, row)


def _draw_chip_icon(surface, chip, cx, cy, size=14):
    icons = SM.get('chip_icons') or {}
    icon  = icons.get(chip.name.lower())
    if icon:
        scaled = pygame.transform.scale(icon, (size, size))
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
    def __init__(self, screen, folder=None, skip_opening=False):
        self.screen = screen

        if skip_opening:
            self.state = BattleState.BATTLE
            self.opening_timer    = 0.0
            self._opening_elapsed = 0.0
            self._sfx_events      = []
            self._sfx_idx         = 0
        else:
            self.state = BattleState.OPENING
            self.opening_timer = 2.2
            self._opening_elapsed = 0.0
            self._sfx_events = [(0.05, 'shuffle', 0.85)]
            deal_t = 0.50
            for _ in range(6):
                self._sfx_events.append((deal_t, 'deal', 0.65))
                deal_t += random.uniform(0.10, 0.16)
            self._sfx_idx = 0

        # Outcome flags — read by game.py to decide next state
        self.finished    = False
        self.player_won  = False
        self.next_action = None   # 'restart' | 'overworld' — set when player chooses

        # Fanfare follow-up after victory SFX (None = not pending, >0 = countdown)
        self._fanfare_timer = None

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

        # Battle starts in OPENING state — the SHUFFLE / DEAL / DRAW! title
        # sequence runs over `opening_timer` seconds while the battlefield is
        # visible behind it. When the timer expires, custom screen opens.

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
        sfx.play('custom_open')

    def _close_custom_screen(self):
        selected = self.custom_screen_obj.get_selected_chips()
        self.chip_queue.extend(selected)  # append new chips to existing queue
        self.custom_screen_obj = None
        self.state = BattleState.BATTLE
        sfx.play('custom_close')

    # ──────────────────────────────────────────────────────────────────────────
    # Event handling
    # ──────────────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if self.state == BattleState.CUSTOM:
            self.custom_screen_obj.handle_event(event)
            # _close_custom_screen is now driven by update() once the slide-out
            # finishes; no need to check done here.
            return

        if self.state == BattleState.VICTORY or self.state == BattleState.DEFEAT:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_z:
                    self.player_won  = self.state == BattleState.VICTORY
                    self.next_action = 'restart'
                    self.finished    = True
                elif event.key == pygame.K_x:
                    self.player_won  = self.state == BattleState.VICTORY
                    self.next_action = 'overworld'
                    self.finished    = True
            return

        if self.state != BattleState.BATTLE:
            return

        if event.type == pygame.KEYDOWN:
            self._keys_down.add(event.key)

            # Open custom screen when gauge full
            if event.key in (pygame.K_SPACE, pygame.K_l):
                if self.custom_gauge >= 1.0:
                    self._open_custom_screen()

            # Use a queued card (no buster fallback — buster lives on X)
            elif event.key == pygame.K_z:
                if self.chip_lock_timer <= 0:
                    self._use_chip()

        elif event.type == pygame.KEYUP:
            self._keys_down.discard(event.key)
            # Release X → fire buster.  Held past CHARGE_TIME → charged shot,
            # otherwise a quick tap fires the uncharged buster.
            if event.key == pygame.K_x:
                if self.player.buster_cooldown <= 0:
                    charged = self.player.charge_held >= C.CHARGE_TIME
                    self._fire_buster(charged=charged)
                self.player.charge_held = 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # Gameplay actions
    # ──────────────────────────────────────────────────────────────────────────

    def _use_chip(self):
        """Z: fire the next queued card. No fallback to buster — buster is on X."""
        if self.current_chip_idx >= len(self.chip_queue):
            return
        chip = self.chip_queue[self.current_chip_idx]
        self.current_chip_idx += 1
        resolver = CHIP_EFFECTS.get(chip.effect_key)
        if resolver:
            resolver(chip, self.player, self.grid, self.enemies, self.effects)
        sfx.play(chip.name.lower())
        targets_row = [e for e in self.enemies if e.row == self.player.row and e.alive]
        target = targets_row[0] if targets_row else (self.enemies[0] if self.enemies else None)
        if target and target.alive:
            self.effects.insert(0, FX.MagicCircleEffect(
                target.pixel_center(), chip.element))
        self._post_chip_damage_numbers()
        self.chip_lock_timer = C.CHIP_LOCK_TIME
        # Trigger attack pose — 'shoot' for damaging cards, 'cast' for utility/heal
        self.player.set_pose('shoot' if chip.damage > 0 else 'cast')

    def _fire_buster(self, charged=False):
        dmg = C.CHARGED_DMG if charged else C.BUSTER_DMG
        row = self.player.row

        self.player.buster_cooldown = C.BUSTER_COOL
        self.player.set_pose('shoot')
        sfx.play('buster_charged' if charged else 'buster_shoot')
        if charged:
            self.player.charge_held = 0.0
            self.effects.append(FX.ScreenFlash(C.LIGHT_BLUE, 0.08))

        # Find first enemy in the row from player forward (target for deferred damage)
        target = None
        hit_col = C.GRID_COLS - 1
        for col in range(self.player.col + 1, C.GRID_COLS):
            candidates = [e for e in self.enemies if e.col == col and e.row == row and e.alive]
            if candidates:
                target = candidates[0]
                hit_col = col
                break

        # Shockwave panel highlight along the shot path
        path = [(c, row) for c in range(self.player.col + 1, hit_col + 1)]
        if path:
            # Card travels at ~1700 px/s; tile avg width ~112px → ~15 tiles/sec
            self.effects.insert(0, FX.PanelFlash(path, wave_speed=15.0))

        # Spinning card projectile — spawns from Oden's throwing hand
        src = self.player.shoot_origin()
        dst = _panel_center(hit_col, row)
        self.effects.append(FX.CardProjectileEffect(
            src, dst, charged=charged,
            target=target, damage=dmg, element=C.ELEM_NONE,
        ))

        # Impact burst at landing point — keep the visual but pull it slightly later
        # so it lands when the card arrives. Burst is a particle effect that lives
        # for its own duration; spawning it now means it appears at the destination
        # immediately, which still reads as anticipation. Acceptable for now.
        pass  # particle burst now spawned on card arrival via _update_effects pending_damage

    def _post_chip_damage_numbers(self):
        """Add death explosion for enemies just killed by a chip."""
        for e in self.enemies:
            if not e.alive and e.flash_timer > 0:
                pos = e.pixel_center()
                explosion_frames = SM.get('fx_misdeal_explosion')
                if explosion_frames:
                    self.effects.append(FX.SpriteExplosionEffect(pos, explosion_frames))
                else:
                    self.effects.append(FX.ExplosionEffect(pos, C.YELLOW, 50, 0.4))

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
            self._opening_elapsed += dt
            # Drain any due SFX events
            while self._sfx_idx < len(self._sfx_events):
                when, name, vol = self._sfx_events[self._sfx_idx]
                if self._opening_elapsed >= when:
                    sfx.play(name, vol)
                    self._sfx_idx += 1
                else:
                    break
            if self.opening_timer <= 0:
                self.state = BattleState.CUSTOM
                self._open_custom_screen()
            return

        if self.state == BattleState.CUSTOM:
            # Tick the slide animation and close once the slide-out finishes
            if self.custom_screen_obj is not None:
                self.custom_screen_obj.update(dt)
                if self.custom_screen_obj.done:
                    self._close_custom_screen()
            return

        if self.state in (BattleState.VICTORY, BattleState.DEFEAT):
            self._update_effects(dt)
            if self._fanfare_timer is not None:
                self._fanfare_timer -= dt
                if self._fanfare_timer <= 0:
                    _music.play(track_path('fanfare'), volume=0.8, loop=False)
                    self._fanfare_timer = None
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
        if keys[pygame.K_x] or 1 in gamepad.buttons_held:
            prev_charge = self.player.charge_held
            self.player.charge_held += dt
            if prev_charge == 0.0:
                sfx.play('buster_charge_start')
            elif prev_charge < C.CHARGE_TIME <= self.player.charge_held:
                sfx.play('buster_charge_full')
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
            sfx.play('victory', 0.9)
            # Cut battle music immediately so the victory chime lands in silence,
            # then the fanfare kicks in after a brief beat.
            _music.stop()
            self._fanfare_timer = 0.7
        if not self.player.alive:
            self.state = BattleState.DEFEAT
            self.effects.append(FX.ScreenFlash(C.RED, 0.5))

    def _update_player_movement(self, dt):
        if self.move_timer > 0:
            self.move_timer -= dt
            return
        keys = pygame.key.get_pressed()
        joy  = gamepad.active()
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

        if keys[pygame.K_LEFT]  or 'left'  in joy:
            moved = _try_move(-1, 0)
        elif keys[pygame.K_RIGHT] or 'right' in joy:
            moved = _try_move(1, 0)
        elif keys[pygame.K_UP]    or 'up'    in joy:
            moved = _try_move(0, -1)
        elif keys[pygame.K_DOWN]  or 'down'  in joy:
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
                    else:
                        # Particle burst on impact (deferred to card arrival)
                        elem = getattr(eff, 'element', 0)
                        charged = getattr(eff, 'charged', False)
                        bc = C.ELEM_COLOR.get(elem, C.LIGHT_BLUE if charged else C.CYAN)
                        new_fx.append(FX.ParticleBurst(entity.pixel_center(), bc, count=14, speed=100))
                        if not entity.alive:
                            frames = SM.get('fx_misdeal_explosion')
                            if frames:
                                new_fx.append(FX.SpriteExplosionEffect(entity.pixel_center(), frames))
                            else:
                                new_fx.append(FX.ExplosionEffect(entity.pixel_center(), C.YELLOW, 50, 0.4))
        self.effects = [e for e in self.effects if e.alive] + new_fx

    def _restart(self):
        self.__init__(self.screen)

    # ──────────────────────────────────────────────────────────────────────────
    # Draw
    # ──────────────────────────────────────────────────────────────────────────

    def draw(self, target=None):
        surface = target if target is not None else self.screen

        # Background gradient
        self._draw_background(surface)

        # Grid
        highlight = set()
        if self.state == BattleState.BATTLE:
            # Highlight chip target panels based on current chip
            pass
        self.grid.draw(surface, highlight)

        # Floor effects (panel highlights, slash overlays) — drawn on the tiles
        # but UNDER the entity sprites
        for eff in self.effects:
            if getattr(eff, 'LAYER', 'top') == 'floor':
                eff.draw(surface)

        # Entities
        if self.player.alive or self.state != BattleState.DEFEAT:
            self.player.draw(surface)
        for e in self.enemies:
            if e.alive:
                e.draw(surface)

        # Top effects (projectiles, particles, text)
        for eff in self.effects:
            if getattr(eff, 'LAYER', 'top') != 'floor':
                eff.draw(surface)

        # HUD
        self._draw_hud(surface)

        # State overlays
        if self.state == BattleState.CUSTOM and self.custom_screen_obj:
            self.custom_screen_obj.draw(surface)

        elif self.state == BattleState.VICTORY:
            self._draw_victory_screen(surface)

        elif self.state == BattleState.DEFEAT:
            self._draw_end_screen(surface, "Defeated", C.RED, victory=False)

        elif self.state == BattleState.OPENING:
            self._draw_opening(surface)

    # Battlefield to use for this battle (cycled via assets/battlefields/*)
    BATTLEFIELD = 'dojo'   # 'dojo' | 'forest' | 'crystalcave' | 'temple'

    def _draw_background(self, surface):
        # Layer 1: battlefield background
        bg = SM.get(f'bf_bg_{self.BATTLEFIELD}')
        if bg:
            surface.blit(bg, (0, 0))
        else:
            surface.fill(C.HUD_BG)

        # Layer 2: stone platform frame (sits between bg and tiles)
        plat = SM.get('bf_platform')
        if plat:
            surface.blit(plat, (0, 0))

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
        """Floating-widgets-only HUD. The HP widget stays visible during the
        custom screen (player needs to see their HP while picking cards).
        Victory/defeat/opening overlays own the screen themselves."""
        if self.state in (BattleState.VICTORY, BattleState.DEFEAT, BattleState.OPENING):
            return

        # HP widget always visible during play (CUSTOM screen leaves its top
        # area clear so the widget shows through unobstructed).
        self._draw_hp_widget(surface)

        if self.state == BattleState.CUSTOM:
            return

        self._draw_gauge_widget(surface)
        if self.state in (BattleState.BATTLE, BattleState.CHIP_USE):
            self._draw_card_queue_widget(surface)

    # ── Floating widgets ──────────────────────────────────────────────────────

    def _draw_hp_widget(self, surface):
        """Top-left HP widget: portrait + name + HP bar."""
        pad = 12
        x, y = pad, pad
        portrait = 52
        bar_w = 180
        bar_h = 12
        widget_w = portrait + 8 + bar_w + 10
        widget_h = portrait + 8

        panel = pygame.Surface((widget_w, widget_h), pygame.SRCALPHA)
        panel.fill((6, 10, 30, 215))
        pygame.draw.rect(panel, C.UI_DARK_GOLD, panel.get_rect(), 2, border_radius=4)
        pygame.draw.rect(panel, C.UI_GOLD,      panel.get_rect(), 1, border_radius=4)
        surface.blit(panel, (x, y))

        # Portrait
        face = SM.get('oden_face')
        if face is None:
            face = SM.get('oden_idle')
            if isinstance(face, list):
                face = face[0]
        if face:
            p_scaled = pygame.transform.scale(face, (portrait, portrait))
            surface.blit(p_scaled, (x + 4, y + 4))
        else:
            pygame.draw.rect(surface, (40, 40, 60),
                             pygame.Rect(x + 4, y + 4, portrait, portrait))

        # Name + HP bar
        info_x = x + 4 + portrait + 8
        info_y = y + 4
        surface.blit(fonts.serif(13, bold=True).render("Oden", True, C.UI_GOLD),
                     (info_x, info_y))
        # HP bar
        bar_y = info_y + 20
        bg = pygame.Rect(info_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(surface, (18, 18, 36), bg)
        frac = max(0.0, self.player.hp / self.player.max_hp)
        fill_w = int(bar_w * frac)
        col = C.HP_GREEN if frac > 0.5 else (C.HP_YELLOW if frac > 0.25 else C.HP_RED)
        if fill_w > 0:
            pygame.draw.rect(surface, col, pygame.Rect(info_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(surface, C.UI_DARK_GOLD, bg, 1)
        # HP text
        hp_text = f"{self.player.hp}/{self.player.max_hp}"
        ts = fonts.pixel(8, bold=True).render(hp_text, True, C.WHITE)
        surface.blit(ts, (info_x + bar_w - ts.get_width() - 3, bar_y + 1))

    def _draw_gauge_widget(self, surface):
        """Centered custom-gauge widget along the top of the screen."""
        gauge_w = 360
        gauge_h = 14
        pad = 6
        widget_w = gauge_w + pad * 2
        widget_h = gauge_h + 22
        x = (C.SCREEN_W - widget_w) // 2
        y = 14

        panel = pygame.Surface((widget_w, widget_h), pygame.SRCALPHA)
        panel.fill((6, 10, 30, 215))
        pygame.draw.rect(panel, C.UI_DARK_GOLD, panel.get_rect(), 2, border_radius=4)
        pygame.draw.rect(panel, C.UI_GOLD,      panel.get_rect(), 1, border_radius=4)
        surface.blit(panel, (x, y))

        lbl = fonts.serif(10, bold=True).render("CUSTOM GAUGE", True, C.UI_GOLD)
        surface.blit(lbl, (x + (widget_w - lbl.get_width()) // 2, y + 3))

        gx, gy = x + pad, y + 18
        bg = pygame.Rect(gx, gy, gauge_w, gauge_h)
        pygame.draw.rect(surface, (18, 18, 36), bg)
        fw = int(gauge_w * self.custom_gauge)
        if fw > 0:
            col = C.WHITE if (self.custom_gauge >= 1.0 and int(self.gauge_flash * 8) % 2 == 0) \
                  else (90, 150, 240)
            pygame.draw.rect(surface, col, pygame.Rect(gx, gy, fw, gauge_h))
        pygame.draw.rect(surface, C.UI_DARK_GOLD, bg, 1)
        if self.custom_gauge >= 1.0:
            press = fonts.pixel(8, bold=True).render("SPACE", True, C.UI_GOLD)
            surface.blit(press, (gx + gauge_w - press.get_width() - 4, gy - 1))

    def _draw_card_queue_widget(self, surface):
        """Card queue floating at the bottom of the screen."""
        remaining = self.chip_queue[self.current_chip_idx:]
        if not remaining:
            return

        card_w = 64
        card_h = 86
        gap = 6
        n = min(len(remaining), 7)
        total_w = n * card_w + (n - 1) * gap
        x0 = (C.SCREEN_W - total_w) // 2
        y0 = C.SCREEN_H - card_h - 22

        # Backing panel — softer alpha so it floats over the platform
        pad = 10
        panel_rect = pygame.Rect(x0 - pad, y0 - pad, total_w + pad * 2, card_h + pad * 2)
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((6, 10, 30, 170))
        pygame.draw.rect(panel, C.UI_DARK_GOLD, panel.get_rect(), 2, border_radius=5)
        pygame.draw.rect(panel, C.UI_GOLD,      panel.get_rect(), 1, border_radius=5)
        surface.blit(panel, panel_rect.topleft)

        for i, chip in enumerate(remaining[:n]):
            x = x0 + i * (card_w + gap)
            is_active = (i == 0)
            self._draw_small_card(surface, chip, x, y0, card_w, card_h, active=is_active)

    def _draw_small_card(self, surface, chip, x, y, w, h, active=False):
        eb = self._ELEM_BG.get(chip.element, (40, 36, 68))
        if not active:
            eb = tuple(max(0, c - 25) for c in eb)
        pygame.draw.rect(surface, eb, pygame.Rect(x, y, w, h), border_radius=3)
        pygame.draw.rect(surface, self._CLS_COLOR.get(chip.chip_class, C.WHITE),
                         pygame.Rect(x, y, w, 3), border_radius=3)
        # Name
        nf = fonts.pixel(7, bold=True)
        ns = nf.render(chip.name[:9], True, C.WHITE if active else (180, 175, 200))
        surface.blit(ns, (x + (w - ns.get_width()) // 2, y + 6))
        # Big damage/heal number
        if chip.heals:
            vs = fonts.serif(15, bold=True).render(f"+{chip.heals}", True,
                                                    (80, 220, 80) if active else (60, 140, 60))
        elif chip.damage:
            vs = fonts.serif(15, bold=True).render(str(chip.damage), True,
                                                    C.WHITE if active else (150, 150, 170))
        else:
            vs = fonts.pixel(8).render("util", True, (180, 175, 200))
        surface.blit(vs, (x + (w - vs.get_width()) // 2, y + 20))
        # Code letter bottom-right
        cc = (C.CYAN if chip.code == "*" else C.UI_GOLD) if active else (90, 88, 110)
        code_s = fonts.pixel(11, bold=True).render(chip.code, True, cc)
        surface.blit(code_s, (x + w - code_s.get_width() - 4, y + h - code_s.get_height() - 3))
        border_c = C.UI_GOLD if active else (60, 58, 80)
        pygame.draw.rect(surface, border_c, pygame.Rect(x, y, w, h), 1 if not active else 2,
                         border_radius=3)

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
        C.ELEM_NONE:      ( 40,  36,  68),
        C.ELEM_FIRE:      ( 80,  30,   8),
        C.ELEM_ICE:       (  8,  44,  80),
        C.ELEM_LIGHTNING: ( 72,  64,   8),
        C.ELEM_EARTH:     ( 16,  64,  16),
        C.ELEM_LIGHT:     ( 72,  60,  24),
        C.ELEM_DARK:      ( 36,   8,  60),
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

    def _draw_end_screen(self, surface, message, color, victory=True):
        """Simple text-only end screen used for defeat (and as a fallback)."""
        overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        surface.blit(overlay, (0, 0))

        font = fonts.serif(54, bold=True)
        text   = font.render(message, True, color)
        shadow = font.render(message, True, C.BLACK)
        cx = C.SCREEN_W // 2 - text.get_width() // 2
        cy = C.SCREEN_H // 2 - text.get_height() // 2 - 20
        surface.blit(shadow, (cx + 2, cy + 2))
        surface.blit(text,   (cx, cy))

        self._draw_endscreen_prompt(surface, cy + text.get_height() + 30)

    # ── Victory screen ────────────────────────────────────────────────────────

    def _draw_victory_screen(self, surface):
        """Ornate victory: dimmed battlefield + radial gold glow + Oden pose +
        large serif 'Victory!' headline + gold ornament rules + Z/X prompt."""
        # Soft dim — keep battlefield slightly visible behind
        overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        oden = SM.get('oden_victory')
        oden_x = oden_y = None
        if oden:
            ow, oh = oden.get_size()
            # Place on the right side so the headline has room on the left
            oden_x = int(C.SCREEN_W * 0.62) - ow // 4
            oden_y = (C.SCREEN_H - oh) // 2 + 20

            # Radial gold glow behind him
            self._draw_radial_glow(
                surface,
                cx=oden_x + ow // 2,
                cy=oden_y + int(oh * 0.42),
                radius=int(oh * 0.55),
                color=(255, 215, 110),
                max_alpha=130,
            )

            surface.blit(oden, (oden_x, oden_y))

        # ── Headline ────────────────────────────────────────────────────────
        headline_font = fonts.serif(86, bold=True)
        head = headline_font.render("Victory!", True, C.UI_GOLD)
        head_shadow = headline_font.render("Victory!", True, (40, 25, 4))

        # Left-aligned next to Oden, or centered if no sprite
        if oden:
            hx = int(C.SCREEN_W * 0.10)
        else:
            hx = C.SCREEN_W // 2 - head.get_width() // 2
        hy = int(C.SCREEN_H * 0.30)

        surface.blit(head_shadow, (hx + 3, hy + 3))
        surface.blit(head,        (hx, hy))

        # Subtitle / flavor
        sub_font = fonts.serif(20)
        sub = sub_font.render("The cards favored you.", True, (220, 210, 180))
        surface.blit(sub, (hx + 4, hy + head.get_height() + 4))

        # Gold rule with diamond ornaments under the subtitle
        rule_y = hy + head.get_height() + 38
        rule_x0 = hx
        rule_x1 = hx + max(head.get_width(), sub.get_width()) + 30
        self._draw_gold_rule_range(surface, rule_x0, rule_x1, rule_y)

        # ── Bottom prompt ───────────────────────────────────────────────────
        self._draw_endscreen_prompt(surface, C.SCREEN_H - 60)

    def _draw_endscreen_prompt(self, surface, y):
        """Shared 'Z Fight again    X Overworld' bottom prompt."""
        prompt_font = fonts.serif(15, bold=True)
        key_box_font = fonts.serif(15, bold=True)

        def key_chip(letter):
            ks = key_box_font.render(letter, True, C.UI_GOLD)
            pad_x, pad_y = 8, 3
            w = ks.get_width() + pad_x * 2
            h = ks.get_height() + pad_y * 2
            chip = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(chip, (12, 16, 40, 220), chip.get_rect(), border_radius=4)
            pygame.draw.rect(chip, C.UI_GOLD,           chip.get_rect(), 1, border_radius=4)
            chip.blit(ks, (pad_x, pad_y))
            return chip

        z_chip = key_chip("Z")
        z_lbl  = prompt_font.render("Fight again", True, C.WHITE)
        x_chip = key_chip("X")
        x_lbl  = prompt_font.render("Overworld",   True, C.WHITE)

        gap_inner = 8     # chip → label
        gap_outer = 40    # between the two pairs

        total_w = (z_chip.get_width() + gap_inner + z_lbl.get_width()
                   + gap_outer +
                   x_chip.get_width() + gap_inner + x_lbl.get_width())
        sx = C.SCREEN_W // 2 - total_w // 2
        ky = y

        surface.blit(z_chip, (sx, ky))
        surface.blit(z_lbl,  (sx + z_chip.get_width() + gap_inner,
                              ky + (z_chip.get_height() - z_lbl.get_height()) // 2))
        sx += z_chip.get_width() + gap_inner + z_lbl.get_width() + gap_outer
        surface.blit(x_chip, (sx, ky))
        surface.blit(x_lbl,  (sx + x_chip.get_width() + gap_inner,
                              ky + (x_chip.get_height() - x_lbl.get_height()) // 2))

    def _draw_gold_rule_range(self, surface, x0, x1, y):
        """Gold rule line from x0→x1 with diamond ornaments at each end and midpoint."""
        pygame.draw.line(surface, C.UI_DARK_GOLD, (x0, y + 1), (x1, y + 1), 1)
        pygame.draw.line(surface, C.UI_GOLD,      (x0, y),     (x1, y),     1)
        for dx in (x0, (x0 + x1) // 2, x1):
            pts = [(dx, y - 4), (dx + 4, y), (dx, y + 4), (dx - 4, y)]
            pygame.draw.polygon(surface, C.UI_GOLD, pts)

    def _draw_radial_glow(self, surface, cx, cy, radius, color, max_alpha=120):
        """Soft circular gradient glow centered at (cx, cy)."""
        try:
            import numpy as np
            yy, xx = np.mgrid[0:radius * 2, 0:radius * 2]
            dx = (xx - radius) / max(1, radius)
            dy = (yy - radius) / max(1, radius)
            dist = np.clip(np.sqrt(dx * dx + dy * dy), 0.0, 1.0)
            falloff = (1.0 - dist) ** 2
            alpha = (falloff * max_alpha).astype(np.uint8)
            r, g, b = color
            arr = np.empty((radius * 2, radius * 2, 4), dtype=np.uint8)
            arr[:, :, 0] = r
            arr[:, :, 1] = g
            arr[:, :, 2] = b
            arr[:, :, 3] = alpha
            glow = pygame.image.frombuffer(arr.tobytes(), (radius * 2, radius * 2),
                                            'RGBA').convert_alpha()
            surface.blit(glow, (cx - radius, cy - radius))
        except ImportError:
            # Fallback — concentric circles
            for i in range(radius, 0, -8):
                a = int(max_alpha * (1 - i / radius) ** 2)
                if a <= 0:
                    continue
                s = pygame.Surface((i * 2, i * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (*color, a), (i, i), i)
                surface.blit(s, (cx - i, cy - i))

    # Intro title-card sequence.
    # Each tuple: (text, enter_time_sec, font_size, base_angle_deg, (cx, cy))
    _OPENING_CARDS = [
        ("SHUFFLE",  0.05,  60, -10, (-220, -120)),
        ("DEAL",     0.55,  92,   7,   (-30,  -25)),
        ("DRAW!",    1.05, 140,  -5,  (180,  100)),
    ]
    _CARD_ENTER_DURATION = 0.22

    def _draw_opening(self, surface):
        """Battlefield is already drawn behind this. Stack SHUFFLE / DEAL / DRAW!
        title cards as they slap onto the screen with scale-bounce + slight rotation."""
        elapsed = self._opening_elapsed
        scx = C.SCREEN_W // 2
        scy = C.SCREEN_H // 2

        # Subtle vignette for legibility — only fades in for the first 0.4s
        if elapsed < 0.45:
            a = int(80 * min(1.0, elapsed / 0.2))
            vig = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            vig.fill((0, 0, 0, a))
            surface.blit(vig, (0, 0))

        for text, enter_t, size, angle, (ox, oy) in self._OPENING_CARDS:
            local = elapsed - enter_t
            if local < 0:
                continue
            # Scale-bounce: starts at 2.0, springs to 1.0 with mild overshoot
            if local < self._CARD_ENTER_DURATION:
                p = local / self._CARD_ENTER_DURATION         # 0 → 1
                # Ease-out with slight settle: start 2.0, end 1.0 (overshoot 0.9 then back)
                scale = 1.0 + (2.0 - 1.0) * (1 - p) ** 2
                alpha = int(255 * min(1.0, p * 1.8))
            else:
                scale = 1.0
                alpha = 255

            # Render at base size, then scale up for the bounce
            font = fonts.serif(size, bold=True)
            shadow_s = font.render(text, True, (12, 8, 4))
            text_s   = font.render(text, True, C.UI_GOLD)
            tw, th = text_s.get_size()
            sw, sh = int(tw * scale), int(th * scale)
            if sw < 1 or sh < 1:
                continue
            shadow_scaled = pygame.transform.smoothscale(shadow_s, (sw, sh))
            text_scaled   = pygame.transform.smoothscale(text_s,   (sw, sh))

            # Rotate
            shadow_rot = pygame.transform.rotate(shadow_scaled, angle)
            text_rot   = pygame.transform.rotate(text_scaled,   angle)
            text_rot.set_alpha(alpha)
            shadow_rot.set_alpha(alpha)

            rw, rh = text_rot.get_size()
            dx = scx + ox - rw // 2
            dy = scy + oy - rh // 2
            surface.blit(shadow_rot, (dx + 5, dy + 5))
            surface.blit(text_rot,   (dx, dy))
