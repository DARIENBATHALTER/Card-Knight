import os
import math
import random
import pygame
import constants as C
import fonts
import sprite_manager as SM
from battle import Battle
from overworld import Overworld
from music import music as _music, track_path

_BASE = os.path.dirname(os.path.abspath(__file__))

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
    INTRO       = "intro"        # Bridgewalker logo cold-open
    TITLE       = "title"
    LOADING     = "loading"      # Faux "loading save" screen
    OVERWORLD   = "overworld"
    TRANSITION  = "transition"   # FF-style zoom+flash into battle
    BATTLE      = "battle"


class LoadingScreen:
    """Faux save-load screen: dark backdrop + ornate loading bar that fills
    over ~1.1s. Played between the title and the overworld so the moment of
    'pressing load' has a beat of dramatic pause."""
    DURATION = 1.1

    def __init__(self):
        self.t    = 0.0
        self.done = False

    def update(self, dt):
        self.t += dt
        if self.t >= self.DURATION:
            self.done = True

    def draw(self, screen):
        # Backdrop — fade in from black to a very dark navy for a hint of color
        bg_t = min(1.0, self.t / 0.25)
        bgr = int(2 * bg_t)
        bgg = int(4 * bg_t)
        bgb = int(12 * bg_t)
        screen.fill((bgr, bgg, bgb))

        cx = C.SCREEN_W // 2
        cy = C.SCREEN_H // 2

        # Decorative compass-rose mark above the bar
        ornament_a = int(180 * min(1.0, self.t / 0.4))
        if ornament_a > 0:
            star_r = 18
            star_pts = [(cx, cy - 70 - star_r),
                        (cx + star_r, cy - 70),
                        (cx, cy - 70 + star_r),
                        (cx - star_r, cy - 70)]
            star = pygame.Surface((star_r * 4, star_r * 4), pygame.SRCALPHA)
            # Offset polygon into the star surface
            ox, oy = star.get_width() // 2 - cx, star.get_height() // 2 - (cy - 70)
            pygame.draw.polygon(star, (*C.UI_GOLD, ornament_a),
                                [(p[0] + ox, p[1] + oy) for p in star_pts])
            screen.blit(star, (cx - star.get_width() // 2,
                               (cy - 70) - star.get_height() // 2))

        # Loading bar
        bar_w, bar_h = 440, 14
        bx = cx - bar_w // 2
        by = cy
        # Outer dark frame
        pygame.draw.rect(screen, (8, 10, 28),
                         pygame.Rect(bx - 4, by - 4, bar_w + 8, bar_h + 8),
                         border_radius=5)
        # Trough
        pygame.draw.rect(screen, (14, 18, 40),
                         pygame.Rect(bx, by, bar_w, bar_h),
                         border_radius=2)

        # Fill — ease-out so it rushes at the start, settles at the end
        frac  = min(1.0, self.t / (self.DURATION * 0.95))
        eased = 1 - (1 - frac) ** 2
        fill_w = int(bar_w * eased)
        if fill_w > 0:
            pygame.draw.rect(screen, C.UI_DARK_GOLD,
                             pygame.Rect(bx, by, fill_w, bar_h),
                             border_radius=2)
            # Bright highlight strip on top of the gold fill
            hl_h = max(2, bar_h // 3)
            pygame.draw.rect(screen, C.UI_GOLD,
                             pygame.Rect(bx, by, fill_w, hl_h),
                             border_radius=2)
            # Leading edge glint
            glint_x = bx + fill_w - 2
            pygame.draw.rect(screen, (255, 245, 200),
                             pygame.Rect(glint_x, by, 2, bar_h))

        # Outer gold border on the trough
        pygame.draw.rect(screen, C.UI_GOLD,
                         pygame.Rect(bx, by, bar_w, bar_h), 1, border_radius=2)
        # End-cap diamonds
        for dx in (bx, bx + bar_w):
            pts = [(dx, by - 5), (dx + 5, by + bar_h // 2),
                   (dx, by + bar_h + 5), (dx - 5, by + bar_h // 2)]
            pygame.draw.polygon(screen, C.UI_GOLD, pts)

        # "Loading…" label
        try:
            import fonts as _fonts
            lbl_font = _fonts.serif(13)
        except Exception:
            lbl_font = pygame.font.Font(None, 18)
        lbl = lbl_font.render("Loading…", True, (190, 180, 220))
        screen.blit(lbl, (cx - lbl.get_width() // 2, by + bar_h + 18))


class TitleSubstate:
    PROMPT = "prompt"   # baked "Press Z to Start" + spinning card visible
    SAVE   = "save"     # Z pressed → save/continue panel (with open animation)


class IntroSequence:
    """Bridgewalker Studios cold-open: black → fade in logo → hold → fade out → black."""
    # Stage cumulative end-times (seconds)
    BLACK_IN_END   = 0.4
    FADE_IN_END    = 1.4
    HOLD_END       = 3.2
    FADE_OUT_END   = 4.1
    BLACK_OUT_END  = 4.5

    def __init__(self):
        self.t    = 0.0
        self.done = False

    def update(self, dt):
        self.t += dt
        if self.t >= self.BLACK_OUT_END:
            self.done = True

    def skip(self):
        # Snap to the last stage so the closing fade still plays briefly,
        # then `done` flips on the next tick.
        self.t = max(self.t, self.FADE_OUT_END)

    def draw(self, screen, logo):
        screen.fill((0, 0, 0))
        if logo is None:
            return

        t = self.t
        if t <= self.BLACK_IN_END:
            alpha = 0
        elif t <= self.FADE_IN_END:
            p = (t - self.BLACK_IN_END) / (self.FADE_IN_END - self.BLACK_IN_END)
            alpha = int(255 * p)
        elif t <= self.HOLD_END:
            alpha = 255
        elif t <= self.FADE_OUT_END:
            p = (t - self.HOLD_END) / (self.FADE_OUT_END - self.HOLD_END)
            alpha = int(255 * (1.0 - p))
        else:
            alpha = 0

        if alpha > 0:
            logo_copy = logo.copy()
            logo_copy.set_alpha(alpha)
            lw, lh = logo_copy.get_size()
            x = (C.SCREEN_W - lw) // 2
            y = (C.SCREEN_H - lh) // 2
            screen.blit(logo_copy, (x, y))


class BattleTransition:
    """FF-style transition into a battle: snapshot the overworld, then progressively
    zoom + rotate + white-flash the captured frame until the screen is overwhelmed.
    When `done` flips true, the caller starts the actual battle."""
    DURATION = 0.75

    def __init__(self, snapshot: pygame.Surface):
        self.snapshot = snapshot.copy()
        self.t   = 0.0
        self.done = False

    def update(self, dt):
        self.t += dt
        if self.t >= self.DURATION:
            self.done = True

    def draw(self, screen):
        frac = min(1.0, self.t / self.DURATION)
        # Ease-in (square) so motion accelerates
        eased = frac * frac
        zoom  = 1.0 + eased * 1.8       # 1.0 → 2.8x
        angle = eased * 22              # 0 → 22°

        # Build a quick chromatic shimmer by offsetting blits of the snapshot.
        try:
            zoomed = pygame.transform.rotozoom(self.snapshot, angle, zoom)
        except (pygame.error, MemoryError):
            zoomed = self.snapshot

        zw, zh = zoomed.get_size()
        cx, cy = C.SCREEN_W // 2, C.SCREEN_H // 2
        screen.fill((0, 0, 0))
        screen.blit(zoomed, (cx - zw // 2, cy - zh // 2))

        # Chromatic split — offset red/blue copies that grow with frac
        if frac > 0.15:
            split_d = int(eased * 14)
            # Tinted copies of the zoomed image
            for tint, ox in ((( 60, 200, 255), -split_d), ((255,  80, 110), split_d)):
                tinted = zoomed.copy()
                overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
                overlay.fill((*tint, 90))
                tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                tinted.set_alpha(110)
                screen.blit(tinted, (cx - zw // 2 + ox, cy - zh // 2))

        # White flash builds toward the end
        flash_alpha = int(255 * (frac ** 3) * 1.2)
        flash_alpha = max(0, min(255, flash_alpha))
        if flash_alpha > 0:
            flash = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            flash.fill((255, 245, 220, flash_alpha))
            screen.blit(flash, (0, 0))


class Game:
    TITLE_FADE_IN_SEC = 1.0
    SAVE_OPEN_SEC     = 0.32   # save panel open animation duration

    def __init__(self, screen):
        self.screen = screen
        self.state = GameState.INTRO
        self.battle = None
        self.overworld = None
        self.transition = None

        # Intro
        self.intro = IntroSequence()

        # Title screen
        self.title_timer    = 0.0
        self.title_alpha_t  = 0.0    # 0 → 1.0 fade-in after intro completes
        self.title_substate = TitleSubstate.PROMPT
        self.save_open_t    = 0.0    # 0 → 1.0 — save panel open animation
        # Title-card animation particles
        self._tc_sparks  = []
        self._tc_glitter = []
        self._tc_spark_t = 0.0
        self._tc_glit_t  = 0.0

        # Loading screen (Z on save → loading bar → overworld)
        self.loading = None

    def handle_event(self, event):
        if self.state == GameState.INTRO:
            if event.type == pygame.KEYDOWN:
                self.intro.skip()
            return

        if self.state == GameState.TITLE:
            self._handle_title_event(event)
            return

        if self.state == GameState.OVERWORLD and self.overworld:
            self.overworld.handle_event(event)
            return

        if self.state == GameState.BATTLE and self.battle:
            self.battle.handle_event(event)

    def _handle_title_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        # Suppress input until the title is mostly faded in
        if self.title_alpha_t < 0.4:
            return

        if self.title_substate == TitleSubstate.PROMPT:
            # The title says "Press Z to Start" — Z opens the save/continue panel.
            if event.key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                self.title_substate = TitleSubstate.SAVE
                self.save_open_t    = 0.0
            return

        if self.title_substate == TitleSubstate.SAVE:
            # Block input while the panel is still animating in
            if self.save_open_t < 0.6:
                return
            if event.key in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE):
                self._begin_loading_to_overworld()
            elif event.key in (pygame.K_x, pygame.K_ESCAPE):
                self.title_substate = TitleSubstate.PROMPT
                self.save_open_t    = 0.0
            return

    def update(self, dt):
        if self.state == GameState.INTRO:
            self.intro.update(dt)
            if self.intro.done:
                self.state = GameState.TITLE
                self.title_timer    = 0.0
                self.title_alpha_t  = 0.0
                self.title_substate = TitleSubstate.PROMPT
                self.save_open_t    = 0.0
                self._start_title_music()
            return

        self.title_timer += dt
        if self.state == GameState.TITLE:
            if self.title_alpha_t < 1.0:
                self.title_alpha_t = min(1.0, self.title_alpha_t + dt / self.TITLE_FADE_IN_SEC)
            self._update_title_card_particles(dt)
            if self.title_substate == TitleSubstate.SAVE and self.save_open_t < 1.0:
                self.save_open_t = min(1.0, self.save_open_t + dt / self.SAVE_OPEN_SEC)

        if self.state == GameState.LOADING and self.loading:
            self.loading.update(dt)
            if self.loading.done:
                self._start_overworld()
            return

        if self.state == GameState.OVERWORLD and self.overworld:
            self.overworld.update(dt)
            if self.overworld.quit_to_title:
                self.overworld = None
                self.state = GameState.TITLE
            elif self.overworld.start_battle:
                self._begin_transition_to_battle()

        elif self.state == GameState.TRANSITION and self.transition:
            self.transition.update(dt)
            if self.transition.done:
                self._start_battle_from_overworld()

        elif self.state == GameState.BATTLE and self.battle:
            self.battle.update(dt)
            if self.battle.finished:
                self._handle_battle_finished()

    def draw(self):
        if self.state == GameState.INTRO:
            self.intro.draw(self.screen, SM.get('bridgewalker_logo'))
        elif self.state == GameState.TITLE:
            self._draw_title()
        elif self.state == GameState.LOADING and self.loading:
            self.loading.draw(self.screen)
        elif self.state == GameState.OVERWORLD and self.overworld:
            self.overworld.draw()
        elif self.state == GameState.TRANSITION and self.transition:
            self.transition.draw(self.screen)
        elif self.state == GameState.BATTLE and self.battle:
            self.battle.draw()

    def _start_title_music(self):
        _music.play(track_path('title'), volume=0.75)

    def _start_dojo_music(self):
        _music.play(track_path('dojo'), volume=0.70)

    def _start_battle_music(self):
        _music.play(track_path('battle'), volume=0.80)

    def _stop_music(self, fade_ms=600):
        _music.stop(fade_ms=fade_ms)

    def _begin_loading_to_overworld(self):
        """Cut music, show the loading bar, then enter the overworld when it fills."""
        self._stop_music(fade_ms=120)
        self.loading = LoadingScreen()
        self.state   = GameState.LOADING

    def _start_overworld(self):
        self.loading = None
        self.state = GameState.OVERWORLD
        self.overworld = Overworld(self.screen)
        self._start_dojo_music()

    def _start_battle_direct(self):
        """Skip overworld entirely — title → battle for the current dev focus."""
        self.state = GameState.BATTLE
        self.battle = Battle(self.screen)
        self._start_battle_music()

    def _begin_transition_to_battle(self):
        """Snapshot the overworld and start the FF-style transition."""
        # Fade out the dojo music as the transition begins.
        self._stop_music(fade_ms=500)
        # Make sure the overworld has rendered its current frame to the screen.
        self.overworld.draw()
        self.transition = BattleTransition(self.screen)
        self.state = GameState.TRANSITION
        # Don't reset overworld.start_battle yet — _start_battle_from_overworld does it
        # once the transition finishes.

    def _start_battle_from_overworld(self):
        self.state = GameState.BATTLE
        self.battle = Battle(self.screen, folder=self.overworld.folder)
        self.overworld.start_battle = False
        self.transition = None
        self._start_battle_music()

    def _handle_battle_finished(self):
        """Battle ended — `next_action` on the Battle tells us what to do."""
        action = getattr(self.battle, 'next_action', 'overworld')
        if action == 'restart':
            # Fresh battle on the same enemy — overworld stays alive in the background.
            if self.overworld is not None:
                self.overworld.start_battle = False
            self.state = GameState.BATTLE
            self.battle = Battle(
                self.screen,
                folder=self.overworld.folder if self.overworld else None,
            )
            self._start_battle_music()
        elif action == 'overworld' and self.overworld is not None:
            self._return_to_overworld()
        else:
            # No overworld for some reason — fall back to title.
            self.battle = None
            self.state = GameState.TITLE
            self._start_title_music()

    def _return_to_overworld(self):
        won = self.battle.player_won
        self.battle = None
        self.state = GameState.OVERWORLD
        if self.overworld:
            self.overworld.on_battle_end(won)
        self._start_dojo_music()

    # ──────────────────────────────────────────────────────────────────────────
    # Title screen
    # ──────────────────────────────────────────────────────────────────────────

    # Menu geometry — positioned over the "Press Z to Start" baked text
    _MENU_ITEM_W   = 360
    _MENU_ITEM_H   = 52
    _MENU_GAP      = 10
    _MENU_CENTER_Y = 622   # y-center of the original "Press Z to Start" line
    # Y-extent of the baked "Press Z to Start" frame — used to ensure our menu
    # backing fully covers it.
    _BAKED_TEXT_Y_TOP    = 588
    _BAKED_TEXT_Y_BOTTOM = 678

    # Spinning card position on the title screen (above the baked CARD KNIGHT text)
    _TC_CX = C.SCREEN_W // 2
    _TC_CY = 210
    _TC_H  = 215

    def _draw_title_sunflare(self, surf, cx, cy, CW, CH, t):
        """Radial sunburst rays behind the title card. Two layered passes:
        - Long thin gold rays (slow rotation)
        - Shorter warm rays (faster counter-rotation)
        Each pass renders to its own surface with a per-pass radial alpha mask
        so rays fade to zero precisely at their tips (no hard cutoff)."""
        max_size = max(CW, CH)
        long_r   = int(max_size * 2.4)
        short_r  = int(max_size * 1.4)

        # Pass 1 — long thin gold rays
        long_flare = self._make_ray_pass(
            ray_count=16, rotation_deg=t * 6, ray_extent=long_r,
            half_angle_frac=0.10, color=(255, 230, 140),
            alpha=int(48 + 16 * math.sin(t * 1.4)),
        )
        surf.blit(long_flare, (cx - long_flare.get_width() // 2,
                               cy - long_flare.get_height() // 2))

        # Pass 2 — shorter warmer rays, counter-rotating
        short_flare = self._make_ray_pass(
            ray_count=12, rotation_deg=-t * 9 + 7.5, ray_extent=short_r,
            half_angle_frac=0.18, color=(255, 195, 105),
            alpha=int(38 + 12 * math.sin(t * 2.1 + 1.0)),
        )
        surf.blit(short_flare, (cx - short_flare.get_width() // 2,
                                cy - short_flare.get_height() // 2))

    def _make_ray_pass(self, ray_count, rotation_deg, ray_extent,
                       half_angle_frac, color, alpha):
        """Build a single ray pass on its own surface. The radial alpha mask
        is normalized to `ray_extent`, so falloff hits 0 exactly at ray tips."""
        # Small padding so the falloff has room to reach 0 cleanly
        bbox = ray_extent * 2 + 6
        flare = pygame.Surface((bbox, bbox), pygame.SRCALPHA)
        fcx = fcy = bbox // 2

        step = 360.0 / ray_count
        half = math.radians(step * half_angle_frac)

        for i in range(ray_count):
            ang = math.radians(rotation_deg + i * step)
            x2 = fcx + math.cos(ang - half) * ray_extent
            y2 = fcy + math.sin(ang - half) * ray_extent
            x3 = fcx + math.cos(ang + half) * ray_extent
            y3 = fcy + math.sin(ang + half) * ray_extent
            pygame.draw.polygon(flare, (*color, alpha),
                                [(fcx, fcy), (x2, y2), (x3, y3)])

        # Radial alpha mask — normalized so dist = 1.0 at ray_extent.
        # falloff = (1 - dist)^p hits 0 exactly at the tip.
        try:
            import numpy as np
            arr = pygame.surfarray.pixels_alpha(flare)
            size = arr.shape[0]
            yy, xx = np.mgrid[0:size, 0:size]
            dy = (yy - fcy) / float(ray_extent)
            dx = (xx - fcx) / float(ray_extent)
            dist = np.clip(np.sqrt(dx * dx + dy * dy), 0.0, 1.0)
            falloff = (1.0 - dist) ** 1.5
            arr[:, :] = (arr.astype(np.float32) * falloff).astype(np.uint8)
            del arr   # release lock
        except Exception:
            pass

        return flare

    def _update_title_card_particles(self, dt):
        card_surf = SM.get('title_card')
        CW = int(card_surf.get_width() * self._TC_H / card_surf.get_height()) if card_surf else 100
        CH = self._TC_H
        cx, cy = self._TC_CX, self._TC_CY
        bob = math.sin(self.title_timer * 1.1) * 6

        # Edge sparks
        self._tc_spark_t -= dt
        if self._tc_spark_t <= 0:
            self._tc_spark_t = random.uniform(0.10, 0.22)
            side = random.choice([0, 1, 2, 3])
            if side == 0:   x, y = cx + random.randint(-CW//2, CW//2), int(cy + bob - CH//2)
            elif side == 1: x, y = cx + random.randint(-CW//2, CW//2), int(cy + bob + CH//2)
            elif side == 2: x, y = cx - CW//2, int(cy + bob + random.randint(-CH//2, CH//2))
            else:           x, y = cx + CW//2, int(cy + bob + random.randint(-CH//2, CH//2))
            dx, dy = x - cx, y - int(cy + bob)
            dist   = max(1, math.hypot(dx, dy))
            sp     = random.uniform(25, 80)
            vx     = dx / dist * sp + random.uniform(-12, 12)
            vy     = dy / dist * sp - random.uniform(14, 46)
            col    = random.choice([(195, 165, 65), (130, 90, 255), (255, 245, 180)])
            lt     = random.uniform(0.35, 0.95)
            self._tc_sparks.append([float(x), float(y), vx, vy, lt, lt, col])

        for p in self._tc_sparks:
            p[0] += p[2] * dt; p[1] += p[3] * dt
            p[3] += 35 * dt;   p[4] -= dt
        self._tc_sparks = [p for p in self._tc_sparks if p[4] > 0]

        # Drifting glitter
        self._tc_glit_t -= dt
        if self._tc_glit_t <= 0:
            self._tc_glit_t = random.uniform(0.10, 0.24)
            x = cx + random.randint(-int(CW * 0.7), int(CW * 0.7))
            y = int(cy + bob) + random.randint(-CH // 2, CH // 3)
            col = random.choice([(195, 165, 65), (255, 255, 200), (140, 110, 255)])
            lt  = random.uniform(0.8, 1.6)
            self._tc_glitter.append([float(x), float(y),
                                     random.uniform(-6, 6), -random.uniform(14, 30),
                                     lt, lt, col])
        for g in self._tc_glitter:
            g[0] += g[2] * dt; g[1] += g[3] * dt; g[4] -= dt
        self._tc_glitter = [g for g in self._tc_glitter if g[4] > 0]

    def _draw_title_card_anim(self, surf, t):
        """Smaller spinning title-card with sunflare, subtle glow + particles."""
        card_surf = SM.get('title_card')
        if not card_surf:
            return

        # Source aspect → fit to _TC_H
        src_w, src_h = card_surf.get_size()
        CW = int(src_w * self._TC_H / src_h)
        CH = self._TC_H

        cx, cy = self._TC_CX, self._TC_CY
        bob     = math.sin(t * 1.1) * 6
        cos_val = math.cos(t * 0.55)
        face_frac  = abs(cos_val)
        glow_pulse = math.sin(t * 1.8)

        # Sunflare rays — drawn FIRST, behind everything else
        self._draw_title_sunflare(surf, cx, int(cy + bob), CW, CH, t)

        # Outer blue halo
        gw = int(CW * 2.4)
        gh = int(CH * 2.4 * 0.55)
        outer_a = max(0, min(170, int((60 + 25 * glow_pulse) * (0.55 + 0.45 * face_frac))))
        _soft_glow(surf, cx, int(cy + bob), gw, gh,
                   (50, 100, 235), outer_a, power=1.7, dither_strength=12)

        # Inner core glow
        iw = int(CW * 1.3)
        ih = int(CH * 1.3 * 0.55)
        inner_a = max(0, min(220, int((110 + 40 * glow_pulse) * (0.6 + 0.4 * face_frac))))
        _soft_glow(surf, cx, int(cy + bob), iw, ih,
                   (90, 150, 255), inner_a, power=2.4, dither_strength=8)

        # Gold halo just outside card
        gold_a = max(0, min(160, int((55 + 35 * math.sin(t * 2.3)) * (0.55 + 0.45 * face_frac))))
        _soft_glow(surf, cx, int(cy + bob), CW + 40, CH + 40,
                   (210, 175, 60), gold_a, power=3.0, dither_strength=10)

        # Glitter (under card)
        for g in self._tc_glitter:
            frac = g[4] / g[5]
            cr, cg, cb = g[6]
            gx, gy = int(g[0]), int(g[1])
            r_px   = max(1, int(2 * frac))
            pygame.draw.circle(surf,
                               (min(255, cr + 60), min(255, cg + 60), min(255, cb + 60)),
                               (gx, gy), r_px)

        # The card itself — flat spin via x-scale = |cos|
        draw_w  = max(4, int(face_frac * CW))
        tilt    = math.sin(t * 0.38) * 4
        scaled  = pygame.transform.smoothscale(card_surf, (draw_w, CH))
        rotated = pygame.transform.rotate(scaled, tilt)
        rw, rh  = rotated.get_size()
        surf.blit(rotated, (cx - rw // 2, int(cy + bob - rh // 2)))

        # Orbiting micro-stars
        for i in range(8):
            angle = t * 0.85 + i * (math.pi / 4)
            px = int(cx + math.cos(angle) * CW * 0.75)
            py = int(cy + bob + math.sin(angle) * CH * 0.32)
            br = int(160 + 80 * math.sin(t * 2.5 + i))
            pygame.draw.circle(surf, (br, br, 255), (px, py), 1)

        # Sparks (on top)
        for p in self._tc_sparks:
            frac = p[4] / p[5]
            cr, cg, cb = p[6]
            c = (min(255, cr + int((255 - cr) * (1 - frac) * 0.6)),
                 min(255, cg + int((255 - cg) * (1 - frac) * 0.6)),
                 min(255, cb + int((255 - cb) * (1 - frac) * 0.6)))
            pygame.draw.circle(surf, c, (int(p[0]), int(p[1])), max(1, int(2 * frac)))

    def _draw_title(self):
        surf = self.screen
        t    = self.title_timer

        # Background (title text + ornaments baked in)
        bg = SM.get('title_bg')
        if bg:
            surf.blit(bg, (0, 0))
        else:
            surf.fill((8, 14, 35))

        # Spinning card animation up top (drawn before the panel so the panel sits on top)
        self._draw_title_card_anim(surf, t)

        # SAVE: animated continue panel. PROMPT: nothing extra — baked "Press Z to Start" shows through.
        if self.title_substate == TitleSubstate.SAVE:
            self._draw_save_panel(surf, t)

        # Global fade-in alpha (after intro)
        if self.title_alpha_t < 1.0:
            fade = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, int(255 * (1.0 - self.title_alpha_t))))
            surf.blit(fade, (0, 0))

    # ── Title sub-panel: NEW GAME / CONTINUE menu ────────────────────────────

    def _draw_title_menu(self, surf, t):
        """Two-item vertical menu, positioned to cover the baked 'Press Z to
        Start' text. Ornate gold/navy chrome with a pulsing cursor."""
        items = self.TITLE_MENU_ITEMS
        n = len(items)
        total_h = n * self._MENU_ITEM_H + (n - 1) * self._MENU_GAP
        # Center the stack vertically over the original prompt area
        baked_cy = (self._BAKED_TEXT_Y_TOP + self._BAKED_TEXT_Y_BOTTOM) // 2
        top_y    = baked_cy - total_h // 2

        # Solid wash that fully obscures the baked "PRESS Z TO START" gold
        # text AND the ornament frame around it. Bigger than the menu so the
        # entire prompt graphic disappears.
        WASH_W = max(self._MENU_ITEM_W + 220, 620)
        WASH_H = (self._BAKED_TEXT_Y_BOTTOM - self._BAKED_TEXT_Y_TOP) + 110
        wash = pygame.Surface((WASH_W, WASH_H), pygame.SRCALPHA)
        wash.fill((8, 12, 30, 250))
        # Subtle outer vignette so the wash blends into the bg parchment
        for i in range(10):
            pygame.draw.rect(wash, (8, 12, 30, max(0, 32 - i * 3)),
                             pygame.Rect(i, i, WASH_W - 2 * i, WASH_H - 2 * i),
                             1, border_radius=6)
        surf.blit(wash, ((C.SCREEN_W - WASH_W) // 2,
                         self._BAKED_TEXT_Y_TOP - 55))

        # Decorative ornament line above the menu
        rule_y = top_y - 18
        rule_left  = C.SCREEN_W // 2 - self._MENU_ITEM_W // 2 + 30
        rule_right = C.SCREEN_W // 2 + self._MENU_ITEM_W // 2 - 30
        self._draw_gold_rule(surf, rule_left, rule_right, rule_y)

        # Draw each menu item
        for i, (label, _) in enumerate(items):
            y = top_y + i * (self._MENU_ITEM_H + self._MENU_GAP)
            x = (C.SCREEN_W - self._MENU_ITEM_W) // 2
            selected = (i == self.title_cursor)
            self._draw_menu_item(surf, x, y, self._MENU_ITEM_W, self._MENU_ITEM_H,
                                 label, selected, t)

        # Hint line under the menu
        hint_y = top_y + total_h + 12
        hint_font = fonts.serif(11)
        hint = hint_font.render("↑ ↓  navigate     Z  select", True, (180, 165, 210))
        surf.blit(hint, ((C.SCREEN_W - hint.get_width()) // 2, hint_y))

    def _draw_menu_item(self, surf, x, y, w, h, label, selected, t):
        # Base panel
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        bg = (16, 20, 56, 240) if selected else (10, 14, 38, 220)
        panel.fill(bg)
        # Border — gold (selected, with pulse) or dark gold
        if selected:
            pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t * 3.4))
            border = (
                int(C.UI_GOLD[0] * pulse + 255 * (1 - pulse)),
                int(C.UI_GOLD[1] * pulse + 200 * (1 - pulse)),
                int(C.UI_GOLD[2] * pulse + 120 * (1 - pulse)),
            )
        else:
            border = C.UI_DARK_GOLD
        pygame.draw.rect(panel, border, panel.get_rect(), 2, border_radius=5)
        pygame.draw.rect(panel, (255, 230, 170, 35) if selected else (0, 0, 0, 0),
                         panel.get_rect().inflate(-4, -4), 1, border_radius=4)
        surf.blit(panel, (x, y))

        # Label
        text_col = C.UI_GOLD if selected else (200, 192, 230)
        label_font = fonts.serif(24, bold=True)
        ts = label_font.render(label, True, text_col)
        shadow = label_font.render(label, True, (8, 6, 16))
        tx = x + (w - ts.get_width()) // 2
        ty = y + (h - ts.get_height()) // 2 - 1
        surf.blit(shadow, (tx + 1, ty + 1))
        surf.blit(ts,     (tx, ty))

        # Cursor indicators (diamond points) on the selected row
        if selected:
            cy = y + h // 2
            for cx_off, sign in ((-w // 2 + 12, 1), (w // 2 - 12, -1)):
                cx = x + w // 2 + cx_off
                pts = [(cx, cy - 6), (cx + 8 * sign, cy), (cx, cy + 6)]
                pygame.draw.polygon(surf, C.UI_GOLD, pts)

    # ── Title sub-panel: faux save-file Continue view ────────────────────────

    def _draw_save_panel(self, surf, t):
        """Save/Continue panel — opens with a scale + alpha animation driven by
        self.save_open_t. The dim overlay fades in alongside."""
        frac = max(0.0, min(1.0, self.save_open_t))
        # Ease-out cubic — fast at start, settles smoothly
        eased = 1.0 - (1.0 - frac) ** 3

        # Dim — fades in ahead of the panel so the title behind dims first
        dim_a = int(225 * min(1.0, frac * 1.6))
        if dim_a > 0:
            dim = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            dim.fill((4, 6, 14, dim_a))
            surf.blit(dim, (0, 0))

        # Render panel contents at native size, then scale/alpha
        PW, PH = 860, 460
        ps = pygame.Surface((PW, PH), pygame.SRCALPHA)
        self._render_save_panel_contents(ps, t)

        # Animation: scale 0.55 → 1.0, alpha 0 → 255 (alpha finishes earlier)
        scale = 0.55 + 0.45 * eased
        alpha = int(255 * min(1.0, frac * 1.6))
        ps.set_alpha(alpha)
        dw = max(2, int(PW * scale))
        dh = max(2, int(PH * scale))
        scaled = pygame.transform.smoothscale(ps, (dw, dh))
        surf.blit(scaled, ((C.SCREEN_W - dw) // 2, (C.SCREEN_H - dh) // 2))

    def _render_save_panel_contents(self, ps, t):
        """Render the save panel contents on the offscreen surface `ps`.
        All coordinates here are LOCAL to ps (0..PW, 0..PH)."""
        PW, PH = ps.get_size()

        # ── Backing ──────────────────────────────────────────────────────────
        ps.fill((10, 14, 38, 245))
        pygame.draw.rect(ps, (24, 30, 70, 80),
                         pygame.Rect(8, 8, PW - 16, PH - 16), border_radius=6)
        pygame.draw.rect(ps, C.UI_DARK_GOLD, ps.get_rect(), 4, border_radius=8)
        pygame.draw.rect(ps, C.UI_GOLD,      ps.get_rect().inflate(-4, -4),
                         1, border_radius=6)

        # Corner compass-rose ornaments
        for (cx, cy) in ((22, 22), (PW - 22, 22),
                         (22, PH - 22), (PW - 22, PH - 22)):
            self._draw_corner_star(ps, cx, cy, 11)

        # Title bar
        title_font = fonts.serif(28, bold=True)
        ts = title_font.render("CONTINUE", True, C.UI_GOLD)
        ps.blit(ts, ((PW - ts.get_width()) // 2, 18))
        self._draw_gold_rule(ps, 40, PW - 40, 60)

        # ── Save slot ────────────────────────────────────────────────────────
        SX = 28
        SY = 80
        SW = PW - 56
        SH = PH - 80 - 60
        slot = pygame.Surface((SW, SH), pygame.SRCALPHA)
        slot.fill((22, 26, 56, 220))
        pygame.draw.rect(slot, C.UI_DARK_GOLD, slot.get_rect(), 2, border_radius=4)
        pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t * 2.6))
        glow_col = (int(C.UI_GOLD[0] * pulse),
                    int(C.UI_GOLD[1] * pulse),
                    int(C.UI_GOLD[2] * pulse))
        pygame.draw.rect(slot, glow_col, slot.get_rect().inflate(-4, -4),
                         1, border_radius=3)
        ps.blit(slot, (SX, SY))

        # FILE 1 chip
        fnum = fonts.pixel(9, bold=True).render("FILE 1", True, C.UI_GOLD)
        ps.blit(fnum, (SX + 14, SY + 10))

        # ── Portrait (Oden) ──────────────────────────────────────────────────
        portrait = SM.get('oden_face') or SM.get('oden_idle')
        if isinstance(portrait, list):
            portrait = portrait[0]
        PSIZE = 140
        PX_p = SX + 20
        PY_p = SY + 36
        pygame.draw.rect(ps, (8, 12, 30),
                         pygame.Rect(PX_p - 3, PY_p - 3, PSIZE + 6, PSIZE + 6),
                         border_radius=4)
        if portrait:
            p_scaled = pygame.transform.smoothscale(portrait, (PSIZE, PSIZE))
            ps.blit(p_scaled, (PX_p, PY_p))
        else:
            pygame.draw.rect(ps, (50, 50, 80),
                             pygame.Rect(PX_p, PY_p, PSIZE, PSIZE))
        pygame.draw.rect(ps, C.UI_GOLD,
                         pygame.Rect(PX_p, PY_p, PSIZE, PSIZE), 2, border_radius=3)
        pygame.draw.rect(ps, C.UI_DARK_GOLD,
                         pygame.Rect(PX_p - 3, PY_p - 3, PSIZE + 6, PSIZE + 6),
                         2, border_radius=4)

        # ── Stats column ─────────────────────────────────────────────────────
        STX = PX_p + PSIZE + 28
        STY = SY + 38
        name_font  = fonts.serif(26, bold=True)
        class_font = fonts.serif(14)
        ns = name_font.render("Oden", True, C.UI_GOLD)
        ps.blit(ns, (STX, STY))
        cs = class_font.render("Cardknight", True, (200, 195, 230))
        ps.blit(cs, (STX + ns.get_width() + 10, STY + 12))

        rule_y = STY + ns.get_height() + 4
        self._draw_gold_rule(ps, STX, STX + 320, rule_y)

        stat_font  = fonts.serif(15, bold=True)
        label_font = fonts.serif(13)
        rows = [
            ("LV",       "1"),
            ("HP",       "5000 / 5000"),
            ("LOCATION", "The Dueling Hall"),
            ("PLAYTIME", "00:00:14"),
        ]
        ry = rule_y + 12
        for lbl, val in rows:
            ls = label_font.render(lbl, True, (160, 150, 200))
            vs = stat_font.render(val, True, C.WHITE)
            ps.blit(ls, (STX, ry))
            ps.blit(vs, (STX + 110, ry - 2))
            ry += 26

        # ── Footer ───────────────────────────────────────────────────────────
        footer_y = PH - 38
        self._draw_gold_rule(ps, 40, PW - 40, footer_y - 12)

        key_font = fonts.serif(14, bold=True)

        def key_chip(letter):
            ks = key_font.render(letter, True, C.UI_GOLD)
            pad_x, pad_y = 7, 2
            w = ks.get_width() + pad_x * 2
            h = ks.get_height() + pad_y * 2
            chip = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(chip, (12, 16, 40, 220), chip.get_rect(), border_radius=4)
            pygame.draw.rect(chip, C.UI_GOLD,           chip.get_rect(), 1, border_radius=4)
            chip.blit(ks, (pad_x, pad_y))
            return chip

        z_chip = key_chip("Z")
        z_lbl  = key_font.render("Load", True, C.WHITE)
        x_chip = key_chip("X")
        x_lbl  = key_font.render("Back", True, C.WHITE)
        gap_inner = 6
        gap_outer = 32
        total_w = (z_chip.get_width() + gap_inner + z_lbl.get_width()
                   + gap_outer +
                   x_chip.get_width() + gap_inner + x_lbl.get_width())
        sx = (PW - total_w) // 2
        ps.blit(z_chip, (sx, footer_y))
        ps.blit(z_lbl,  (sx + z_chip.get_width() + gap_inner,
                         footer_y + (z_chip.get_height() - z_lbl.get_height()) // 2))
        sx += z_chip.get_width() + gap_inner + z_lbl.get_width() + gap_outer
        ps.blit(x_chip, (sx, footer_y))
        ps.blit(x_lbl,  (sx + x_chip.get_width() + gap_inner,
                         footer_y + (x_chip.get_height() - x_lbl.get_height()) // 2))

    # ── Shared ornament helpers ──────────────────────────────────────────────

    def _draw_gold_rule(self, surf, x0, x1, y):
        """Gold rule line with diamond ornaments at endpoints and midpoint."""
        pygame.draw.line(surf, C.UI_DARK_GOLD, (x0, y + 1), (x1, y + 1), 1)
        pygame.draw.line(surf, C.UI_GOLD,      (x0, y),     (x1, y),     1)
        for dx in (x0, (x0 + x1) // 2, x1):
            pts = [(dx, y - 4), (dx + 4, y), (dx, y + 4), (dx - 4, y)]
            pygame.draw.polygon(surf, C.UI_GOLD, pts)

    def _draw_corner_star(self, surf, cx, cy, r):
        """Small compass-rose star ornament for panel corners."""
        outer = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        inner = [(cx + int(r * 0.36), cy - int(r * 0.36)),
                 (cx + int(r * 0.36), cy + int(r * 0.36)),
                 (cx - int(r * 0.36), cy + int(r * 0.36)),
                 (cx - int(r * 0.36), cy - int(r * 0.36))]
        pygame.draw.polygon(surf, C.UI_GOLD, outer)
        pygame.draw.polygon(surf, (12, 16, 40), inner)
        pygame.draw.circle(surf, C.UI_DARK_GOLD, (cx, cy), 2)
