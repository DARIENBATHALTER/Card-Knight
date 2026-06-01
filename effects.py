import pygame
import math
import random
import constants as C
import tile_warp


def _panel_center(col, row):
    return tile_warp.tile_center(col, row)


def _tile_poly(col, row, shrink=0):
    """Integer polygon points for tile (col, row), optionally shrunk toward its center."""
    quad = tile_warp.tile_quad(col, row)
    if shrink:
        cx = sum(p[0] for p in quad) / 4
        cy = sum(p[1] for p in quad) / 4
        shrunk = []
        for x, y in quad:
            dx, dy = x - cx, y - cy
            d = max(1.0, math.hypot(dx, dy))
            f = max(0.0, 1.0 - shrink / d)
            shrunk.append((cx + dx * f, cy + dy * f))
        quad = shrunk
    return [(int(p[0]), int(p[1])) for p in quad]


class Effect:
    alive = True
    # 'floor' = drawn between tiles and entities (highlights, slashes)
    # 'top'   = drawn after entities (projectiles, particles, text — default)
    LAYER = 'top'
    def update(self, dt): pass
    def draw(self, surface): pass


class ProjectileEffect(Effect):
    def __init__(self, start, end, color, radius, trail_color=None):
        self.pos = list(start)
        self.end = list(end)
        self.color = color
        self.trail_color = trail_color or color
        self.radius = radius
        self.alive = True
        self.trail = []
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = max(1, math.hypot(dx, dy))
        speed = 550
        self.vel = [dx / dist * speed, dy / dist * speed]
        self.dist_total = dist
        self.dist_traveled = 0

    def update(self, dt):
        self.trail.append(tuple(self.pos))
        if len(self.trail) > 6:
            self.trail.pop(0)
        move = [v * dt for v in self.vel]
        self.pos[0] += move[0]
        self.pos[1] += move[1]
        self.dist_traveled += math.hypot(*move)
        if self.dist_traveled >= self.dist_total - 2:
            self.alive = False

    def draw(self, surface):
        for i, tp in enumerate(self.trail):
            alpha_frac = (i + 1) / len(self.trail)
            r = max(2, int(self.radius * alpha_frac * 0.6))
            c = tuple(int(ch * alpha_frac * 0.7) for ch in self.trail_color)
            pygame.draw.circle(surface, c, (int(tp[0]), int(tp[1])), r)
        pygame.draw.circle(surface, self.color, (int(self.pos[0]), int(self.pos[1])), self.radius)


class SlashEffect(Effect):
    LAYER = 'floor'
    def __init__(self, panels, color, duration):
        self.panels = panels  # list of (col, row)
        self.color = color
        self.duration = duration
        self.timer = duration
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        alpha = int(255 * (self.timer / self.duration))
        r, g, b = self.color
        for col, row in self.panels:
            if 0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS:
                poly = _tile_poly(col, row, shrink=3)
                overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
                pygame.draw.polygon(overlay, (r, g, b, min(alpha, 180)), poly)
                surface.blit(overlay, (0, 0))
                # Slash diagonals across the warped tile
                pygame.draw.line(surface, self.color, poly[3], poly[1], 3)
                pygame.draw.line(surface, self.color, poly[0], poly[2], 2)


class ExplosionEffect(Effect):
    def __init__(self, pos, color, max_radius, duration):
        self.pos = pos
        self.color = color
        self.max_radius = max_radius
        self.duration = duration
        self.timer = duration
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        frac = 1.0 - (self.timer / self.duration)
        radius = int(self.max_radius * frac)
        alpha = int(255 * (self.timer / self.duration))
        if radius > 0:
            s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            r, g, b = self.color
            pygame.draw.circle(s, (r, g, b, alpha), (radius, radius), radius)
            surface.blit(s, (self.pos[0] - radius, self.pos[1] - radius))


class SpriteExplosionEffect(Effect):
    """Plays a list of pygame Surfaces as a frame-by-frame explosion at pos.
    Each frame is shown for frame_dur seconds; the sprite is centred on pos
    (adjusted by y_offset) and scaled to display_size.
    A brief cross-fade flicker is blended between each frame transition.
    """
    layer = 'ceiling'
    FLICKER_DUR  = 0.040   # tail of each frame that flickers to next (seconds)
    FLICKER_RATE = 0.013   # strobe period — alternates ~3 times per transition

    def __init__(self, pos, frames: list, frame_dur: float = 0.12,
                 display_size: int = 220, y_offset: int = -70):
        self.pos          = pos
        self.frames       = frames
        self.frame_dur    = frame_dur
        self.display_size = display_size
        self.y_offset     = y_offset
        self.timer        = 0.0
        self.alive        = True

    def update(self, dt):
        self.timer += dt
        if self.timer >= self.frame_dur * len(self.frames):
            self.alive = False

    def draw(self, surface):
        if not self.frames:
            return
        sz  = self.display_size
        idx = min(int(self.timer / self.frame_dur), len(self.frames) - 1)
        cx  = int(self.pos[0])
        cy  = int(self.pos[1]) + self.y_offset
        bx  = cx - sz // 2
        by  = cy - sz // 2

        # Strobe flicker during the tail of each frame: alternate current ↔ next
        frame_t  = self.timer % self.frame_dur
        next_idx = min(idx + 1, len(self.frames) - 1)
        tail_t   = frame_t - (self.frame_dur - self.FLICKER_DUR)
        if tail_t > 0 and next_idx != idx:
            tick     = int(tail_t / self.FLICKER_RATE)
            show_idx = next_idx if tick % 2 == 0 else idx
        else:
            show_idx = idx

        scaled = pygame.transform.scale(self.frames[show_idx], (sz, sz))
        surface.blit(scaled, (bx, by))


class RecoveryEffect(Effect):
    def __init__(self, pos, amount):
        self.pos = pos
        self.amount = amount
        self.timer = 0.8
        self.alive = True
        self.particles = [(0, i * 30) for i in range(6)]  # angle, offset

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False
        for i, (a, off) in enumerate(self.particles):
            self.particles[i] = (a + 180 * dt, off)

    def draw(self, surface):
        alpha = int(255 * (self.timer / 0.8))
        for a, off in self.particles:
            rad = math.radians(a)
            x = int(self.pos[0] + math.cos(rad) * (20 + off * 0.3))
            y = int(self.pos[1] + math.sin(rad) * (20 + off * 0.3))
            r, g, b = C.GREEN
            pygame.draw.circle(surface, (r, g, b, min(alpha, 200)), (x, y), 4)


class ElecEffect(Effect):
    def __init__(self, pos):
        self.pos = pos
        self.timer = 0.35
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        import random
        alpha = int(255 * (self.timer / 0.35))
        cx, cy = self.pos
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            length = random.randint(10, 28)
            ex = cx + int(math.cos(angle) * length)
            ey = cy + int(math.sin(angle) * length)
            pygame.draw.line(surface, C.YELLOW, (cx, cy), (ex, ey), 2)


class BombTrajectory(Effect):
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.timer = 0.5
        self.duration = 0.5
        self.alive = True
        self.exploded = False

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0 and not self.exploded:
            self.exploded = True
            self.alive = False

    def draw(self, surface):
        frac = 1.0 - (self.timer / self.duration)
        x = int(self.start[0] + (self.end[0] - self.start[0]) * frac)
        arc_height = -55
        y_base = self.start[1] + (self.end[1] - self.start[1]) * frac
        y = int(y_base + arc_height * math.sin(math.pi * frac))
        # Draw bomb as dark sphere
        pygame.draw.circle(surface, C.DARK_GRAY, (x, y), 10)
        pygame.draw.circle(surface, C.GRAY, (x - 3, y - 3), 4)
        if frac > 0.85:
            # Explosion
            ex_r = int((frac - 0.85) / 0.15 * 40)
            s = pygame.Surface((ex_r * 2 + 1, ex_r * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 180, 30, 180), (ex_r, ex_r), ex_r)
            surface.blit(s, (self.end[0] - ex_r, self.end[1] - ex_r))


class HomingEffect(Effect):
    def __init__(self, start, end):
        self.pos = list(start)
        self.end = list(end)
        self.timer = 0.6
        self.duration = 0.6
        self.alive = True

    def update(self, dt):
        frac = 1.0 - (self.timer / self.duration)
        self.pos[0] = self.end[0] * frac + (self.end[0] - 80) * (1 - frac)
        # Sine-wave path
        t = 1.0 - (self.timer / self.duration)
        self.pos[0] = self._lerp(self.end[0] - 80, self.end[0], t)
        self.pos[1] = self._lerp(self.end[1] - 30, self.end[1], t) + math.sin(t * math.pi * 3) * 20
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def _lerp(self, a, b, t):
        return a + (b - a) * t

    def draw(self, surface):
        pygame.draw.circle(surface, C.RED, (int(self.pos[0]), int(self.pos[1])), 8)
        pygame.draw.circle(surface, C.ORANGE, (int(self.pos[0]), int(self.pos[1])), 5)


class DashEffect(Effect):
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.timer = 0.25
        self.duration = 0.25
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        frac = 1.0 - (self.timer / self.duration)
        # Draw a wide horizontal streak
        x = int(self.start[0] + (self.end[0] - self.start[0]) * frac)
        y = self.start[1]
        for i in range(5):
            offset = i * 12
            alpha = max(0, 200 - i * 40)
            s = pygame.Surface((self.end[0] - self.start[0], 20), pygame.SRCALPHA)
            pygame.draw.rect(s, (255, 255, 255, alpha), s.get_rect())
            surface.blit(s, (self.start[0], y - 10))


class BoomerangEffect(Effect):
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.timer = 0.5
        self.duration = 0.5
        self.going = True
        self.pos = list(start)
        self.alive = True

    def update(self, dt):
        frac = 1.0 - (self.timer / self.duration)
        if frac < 0.5:
            t = frac / 0.5
            self.pos[0] = self.start[0] + (self.end[0] - self.start[0]) * t
            self.pos[1] = self.start[1] + math.sin(t * math.pi * 0.5) * (-25)
        else:
            t = (frac - 0.5) / 0.5
            self.pos[0] = self.end[0] + (self.start[0] - self.end[0]) * t
            self.pos[1] = self.start[1] - 25 + math.sin(t * math.pi * 0.5) * 25
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        # Draw as rotating arc
        frac = 1.0 - (self.timer / self.duration)
        angle = frac * 720
        x, y = int(self.pos[0]), int(self.pos[1])
        pygame.draw.circle(surface, C.BROWN, (x, y), 8)
        pygame.draw.arc(surface, C.ORANGE,
                        pygame.Rect(x - 12, y - 12, 24, 24),
                        math.radians(angle), math.radians(angle + 180), 3)


class TextEffect(Effect):
    def __init__(self, text, pos, color, duration):
        self.text = text
        self.pos = list(pos)
        self.color = color
        self.duration = duration
        self.timer = duration
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        self.pos[1] -= 30 * dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        alpha = int(255 * (self.timer / self.duration))
        try:
            font = pygame.font.SysFont("Arial", 20, bold=True)
        except:
            font = pygame.font.Font(None, 22)
        surf = font.render(self.text, True, self.color)
        surf.set_alpha(alpha)
        surface.blit(surf, (int(self.pos[0]) - surf.get_width() // 2, int(self.pos[1])))


class DamageNumber(Effect):
    def __init__(self, pos, value, color=None):
        self.pos = list(pos)
        self.value = value
        self.color = color or C.WHITE
        self.timer = 0.75
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        self.pos[1] -= 45 * dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        alpha = int(255 * min(1.0, self.timer / 0.5))
        try:
            font = pygame.font.SysFont("Arial", 22, bold=True)
        except:
            font = pygame.font.Font(None, 24)
        surf = font.render(str(self.value), True, self.color)
        surf.set_alpha(alpha)
        surface.blit(surf, (int(self.pos[0]) - surf.get_width() // 2, int(self.pos[1])))


class ScreenFlash(Effect):
    def __init__(self, color, duration=0.12):
        self.color = color
        self.timer = duration
        self.duration = duration
        self.alive = True

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        alpha = int(140 * (self.timer / self.duration))
        s = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        r, g, b = self.color
        s.fill((r, g, b, alpha))
        surface.blit(s, (0, 0))


# ── Panel flash ───────────────────────────────────────────────────────────────

class PanelFlash(Effect):
    LAYER = 'floor'
    """Panel highlight — shows AoE path as attack passes.

    Two modes:
      - Static (wave_speed=None): entire path flashes and fades uniformly.
      - Shockwave (wave_speed=N tiles/sec): only the currently-active tile lights up,
        with a brief fade trail. The effect dies once the wave has cleared the path.
    """

    def __init__(self, panels, color=(255, 215, 40), duration=0.38, wave_speed=None):
        self.panels    = panels   # list of (col, row), order = travel direction
        self.color     = color
        self.duration  = duration
        self.wave_speed = wave_speed   # tiles per second
        self.timer     = duration
        self.elapsed   = 0.0
        self.alive     = True

    def update(self, dt):
        self.elapsed += dt
        if self.wave_speed is not None:
            # Lifetime = time for wave to clear path + short fade tail
            total = len(self.panels) / max(0.1, self.wave_speed) + 0.35
            if self.elapsed >= total:
                self.alive = False
        else:
            self.timer -= dt
            if self.timer <= 0:
                self.alive = False

    def draw(self, surface):
        r, g, b = self.color
        edge_col = (min(255, r + 40), min(255, g + 40), b)

        if self.wave_speed is None:
            # Static whole-path flash
            frac  = max(0.0, self.timer / self.duration)
            alpha = int(190 * frac)
            for col, row in self.panels:
                if 0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS:
                    poly = _tile_poly(col, row, shrink=2)
                    overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.polygon(overlay, (r, g, b, alpha), poly)
                    surface.blit(overlay, (0, 0))
                    pygame.draw.polygon(surface, edge_col, poly, 1)
            return

        # Shockwave mode — peak brightness travels along the path
        head = self.elapsed * self.wave_speed
        for i, (col, row) in enumerate(self.panels):
            if not (0 <= col < C.GRID_COLS and 0 <= row < C.GRID_ROWS):
                continue
            age = head - i               # >0: already passed, <0: not yet reached
            if age < -0.15 or age > 1.4:
                continue
            if age < 0:
                # Anticipation glow just ahead of the wavefront
                alpha = int(70 * (1.0 + age / 0.15))
            else:
                # Active tile + fading trail
                alpha = int(220 * max(0.0, 1.0 - age / 1.4))
            if alpha <= 0:
                continue
            poly = _tile_poly(col, row, shrink=2)
            overlay = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
            pygame.draw.polygon(overlay, (r, g, b, alpha), poly)
            surface.blit(overlay, (0, 0))
            if alpha > 80:
                pygame.draw.polygon(surface, edge_col, poly, 1)


# ── Particle burst ────────────────────────────────────────────────────────────

class ParticleBurst(Effect):
    """General-purpose particle burst — elemental impacts, card hits, etc."""

    def __init__(self, pos, color, count=20, speed=130, gravity=180,
                 life=0.55, color_b=None):
        self.alive = True
        cb = color_b or color
        self.particles = []   # [x, y, vx, vy, life, max_life, radius, color]
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            sp    = random.uniform(speed * 0.35, speed)
            vx    = math.cos(angle) * sp
            vy    = math.sin(angle) * sp - random.uniform(0, speed * 0.4)
            lt    = random.uniform(life * 0.5, life)
            rad   = random.randint(2, 4)
            t     = random.random()
            col   = tuple(int(color[i] + (cb[i] - color[i]) * t) for i in range(3))
            self.particles.append([float(pos[0]), float(pos[1]),
                                   vx, vy, lt, lt, rad, col])

    def update(self, dt):
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 180 * dt   # gravity
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        self.alive = bool(self.particles)

    def draw(self, surface):
        for p in self.particles:
            frac = p[4] / p[5]
            cr, cg, cb = p[7]
            # Brighten toward white as they fade
            c = (min(255, cr + int((255 - cr) * (1 - frac) * 0.5)),
                 min(255, cg + int((255 - cg) * (1 - frac) * 0.5)),
                 min(255, cb + int((255 - cb) * (1 - frac) * 0.5)))
            pygame.draw.circle(surface, c,
                               (int(p[0]), int(p[1])), max(1, int(p[6] * frac)))


# ── Spinning card projectile ─────────────────────────────────────────────────

class CardProjectileEffect(Effect):
    """Oden's buster: a spinning card with a golden comet trail and magic sparkles.

    If `target` is given, damage is applied on impact (pending_damage pattern,
    same as TravelingHit) — caller does NOT call take_damage upfront.
    """
    CW, CH = 22, 32

    # Element → (card bg tint, border color, sparkle color, trail color)
    _ELEM_PALETTE = {
        C.ELEM_FIRE:      ((60, 14,  4,  220), (255, 110,  30, 255), (255, 160,  60, 220), (220, 80,  20)),
        C.ELEM_ICE:       ((4,  24, 60,  220), (140, 220, 255, 255), (180, 240, 255, 220), (80, 180, 240)),
        C.ELEM_LIGHTNING: ((40, 40,  8,  220), (255, 240,  60, 255), (255, 255, 160, 220), (220, 210,  40)),
        C.ELEM_EARTH:     ((24, 16,  4,  220), (160, 110,  50, 255), (200, 170, 100, 220), (140,  90,  30)),
        C.ELEM_LIGHT:     ((50, 50, 30,  220), (255, 250, 180, 255), (255, 255, 220, 220), (220, 210, 140)),
        C.ELEM_DARK:      ((20,  4, 40,  220), (180,  80, 255, 255), (200, 130, 255, 220), (140,  50, 200)),
    }

    def __init__(self, start, end, charged=False,
                 target=None, damage=0, element=0):
        self.pos          = list(start)
        self.end          = list(end)
        self.charged      = charged
        self.alive        = True
        self.angle        = 0.0
        self.trail        = []
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = max(1, math.hypot(dx, dy))
        speed = 1700 if not charged else 1400
        self.vel          = [dx / dist * speed, dy / dist * speed]
        # Perpendicular direction — used to scatter sparkles sideways
        d = max(1.0, math.hypot(*self.vel))
        self._perp = (-self.vel[1] / d, self.vel[0] / d)
        self.dist_total   = dist
        self.dist_traveled = 0
        self.target       = target
        self.damage       = damage
        self.element      = element
        self._palette     = self._ELEM_PALETTE.get(element)
        self._card        = self._build_card()
        self.pending_damage = None   # (dealt, entity) — picked up by Battle._update_effects

        # Magic sparkles: each particle = [x, y, vx, vy, life_remaining, life_total, kind]
        # kind: 0 = round dot, 1 = 4-point star, 2 = small streak
        self.sparkles = []
        self._spark_t = 0.0   # spawn cooldown

    def _build_card(self):
        surf = pygame.Surface((self.CW, self.CH), pygame.SRCALPHA)
        if self._palette:
            bg_col, border_col, star_col, _ = self._palette
        elif self.charged:
            bg_col, border_col, star_col = (10, 16, 65, 230), (220, 180, 255, 255), (200, 160, 255, 220)
        else:
            bg_col, border_col, star_col = (10, 16, 65, 230), (195, 165,  65, 255), (220, 195, 110, 220)
        pygame.draw.rect(surf, bg_col, (0, 0, self.CW, self.CH), border_radius=3)
        pygame.draw.rect(surf, border_col, (0, 0, self.CW, self.CH), 2, border_radius=3)
        cx, cy = self.CW // 2, self.CH // 2
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            pygame.draw.line(surf, star_col,
                             (cx, cy),
                             (cx + int(math.cos(rad) * 7), cy + int(math.sin(rad) * 7)), 1)
        dot_col = (border_col[0], border_col[1], border_col[2], 255)
        pygame.draw.circle(surf, dot_col, (cx, cy), 2)
        return surf

    def update(self, dt):
        self.trail.append(tuple(self.pos))
        if len(self.trail) > 8:
            self.trail.pop(0)
        spin = 800 if not self.charged else 500
        self.angle = (self.angle + spin * dt) % 360
        move = [v * dt for v in self.vel]
        self.pos[0] += move[0]
        self.pos[1] += move[1]
        self.dist_traveled += math.hypot(*move)

        # Spawn magic sparkles along the trail
        self._spark_t -= dt
        while self._spark_t <= 0:
            self._spark_t += 0.012   # ~80 spawns/sec while in flight
            perp_off  = random.uniform(-9, 9)
            spawn_x   = self.pos[0] + self._perp[0] * perp_off
            spawn_y   = self.pos[1] + self._perp[1] * perp_off
            # Sparkle drifts mostly opposite of travel direction (backward), with sideways jitter
            back_speed = random.uniform(40, 130)
            jitter     = random.uniform(-50, 50)
            svx = -self.vel[0] / max(1.0, math.hypot(*self.vel)) * back_speed + self._perp[0] * jitter
            svy = -self.vel[1] / max(1.0, math.hypot(*self.vel)) * back_speed + self._perp[1] * jitter
            life = random.uniform(0.30, 0.55)
            kind = random.choices([0, 1, 2], weights=[6, 3, 2])[0]
            self.sparkles.append([spawn_x, spawn_y, svx, svy, life, life, kind])

        # Age sparkles
        for s in self.sparkles:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] -= dt
        self.sparkles = [s for s in self.sparkles if s[4] > 0]

        if self.dist_traveled >= self.dist_total - 2:
            if self.target is not None and self.target.alive and self.damage > 0:
                dealt = self.target.take_damage(self.damage, self.element)
                if dealt:
                    self.pending_damage = (dealt, self.target)
            self.alive = False

    def draw(self, surface):
        if self._palette:
            _, border, sparkle_base, trail_col = self._palette
        elif self.charged:
            trail_col, sparkle_base = (120, 80, 220), (200, 160, 255)
        else:
            trail_col, sparkle_base = (195, 140, 40), (255, 210, 90)
        for i, tp in enumerate(self.trail):
            frac = (i + 1) / max(1, len(self.trail))
            r_t  = max(1, int(6 * frac))
            c    = tuple(int(ch * frac * 0.65) for ch in trail_col)
            pygame.draw.circle(surface, c, (int(tp[0]), int(tp[1])), r_t)

        # Magic sparkles
        if self._palette:
            r, g, b = sparkle_base[:3]
            sparkle_palette = [(r, g, b), (min(255,r+40), min(255,g+40), min(255,b+40)),
                               (255, 255, 255), (r//2, g//2, b//2)]
        elif self.charged:
            sparkle_palette = [(220, 180, 255), (160, 110, 255), (240, 230, 255), (120, 80, 230)]
        else:
            sparkle_palette = [(255, 230, 130), (255, 200, 80), (255, 250, 200), (200, 140, 50)]
        for sx, sy, _, _, life, life_max, kind in self.sparkles:
            frac  = life / life_max
            alpha = int(255 * (frac ** 0.6))
            base  = sparkle_palette[int((1 - frac) * len(sparkle_palette)) % len(sparkle_palette)]
            col   = (*base, alpha)
            ix, iy = int(sx), int(sy)
            if kind == 0:
                # Soft dot — small surface for alpha blending
                r = max(1, int(2 + 1.5 * frac))
                s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(s, col, (r + 1, r + 1), r)
                surface.blit(s, (ix - r - 1, iy - r - 1))
            elif kind == 1:
                # 4-point star
                size = max(2, int(3 + 3 * frac))
                s = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
                cx, cy = size + 1, size + 1
                pygame.draw.line(s, col, (cx - size, cy), (cx + size, cy), 1)
                pygame.draw.line(s, col, (cx, cy - size), (cx, cy + size), 1)
                pygame.draw.circle(s, col, (cx, cy), 1)
                surface.blit(s, (ix - size - 1, iy - size - 1))
            else:
                # Small streak — short line along travel direction (perpendicular to perp)
                length = int(3 + 4 * frac)
                tx = ix - int(self.vel[0] / max(1.0, math.hypot(*self.vel)) * length)
                ty = iy - int(self.vel[1] / max(1.0, math.hypot(*self.vel)) * length)
                bb_w = abs(ix - tx) + 4
                bb_h = abs(iy - ty) + 4
                s = pygame.Surface((bb_w, bb_h), pygame.SRCALPHA)
                ox, oy = min(ix, tx) - 2, min(iy, ty) - 2
                pygame.draw.line(s, col, (ix - ox, iy - oy), (tx - ox, ty - oy), 2)
                surface.blit(s, (ox, oy))

        rotated = pygame.transform.rotate(self._card, self.angle)
        rw, rh  = rotated.get_size()
        surface.blit(rotated, (int(self.pos[0]) - rw // 2, int(self.pos[1]) - rh // 2))


# ── Magic summoning circle ────────────────────────────────────────────────────

class MagicCircleEffect(Effect):
    """Rotating elemental summoning circle — appears under target, expands, then collapses."""

    _CFG = {
        C.ELEM_FIRE:      {'color': (255, 100, 30),  'sides': 5, 'ticks': 10},
        C.ELEM_ICE:       {'color': (50,  180, 255), 'sides': 6, 'ticks': 12},
        C.ELEM_LIGHTNING: {'color': (255, 230, 50),  'sides': 4, 'ticks': 8},
        C.ELEM_EARTH:     {'color': (60,  220, 80),  'sides': 6, 'ticks': 12},
        C.ELEM_LIGHT:     {'color': (255, 240, 180), 'sides': 8, 'ticks': 10},
        C.ELEM_DARK:      {'color': (160,  60, 220), 'sides': 5, 'ticks': 10},
        C.ELEM_NONE:      {'color': (180, 150, 255), 'sides': 5, 'ticks': 10},
    }

    def __init__(self, pos, element=C.ELEM_NONE, duration=0.85):
        cfg          = self._CFG.get(element, self._CFG[C.ELEM_NONE])
        self.pos     = (int(pos[0]), int(pos[1]))
        self.color   = cfg['color']
        self.sides   = cfg['sides']
        self.ticks   = cfg['ticks']
        self.duration = duration
        self.timer   = duration
        self.alive   = True
        self.rot1    = 0.0   # outer ring
        self.rot2    = 0.0   # inner polygon (counter-rotates)

    def _scale(self):
        frac = self.timer / self.duration
        if frac > 0.72:  return (1.0 - frac) / 0.28   # expand in
        elif frac > 0.18: return 1.0                    # hold
        else:            return frac / 0.18             # collapse

    def update(self, dt):
        self.rot1 = (self.rot1 + 130 * dt) % 360
        self.rot2 = (self.rot2 - 95  * dt) % 360
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False

    def draw(self, surface):
        scale = self._scale()
        frac  = self.timer / self.duration
        alpha = int(230 * min(frac * 4, 1.0))
        cx, cy = self.pos
        r, g, b = self.color

        # ── Outer ring with tick marks ────────────────────────────────────────
        outer_r = int(54 * scale)
        if outer_r > 1:
            sz = outer_r * 2 + 6
            sc = sz // 2
            rs = pygame.Surface((sz, sz), pygame.SRCALPHA)
            pygame.draw.circle(rs, (r, g, b, alpha), (sc, sc), outer_r, 2)
            for i in range(self.ticks):
                ang = math.radians(self.rot1 + i * (360 / self.ticks))
                x1 = sc + int(math.cos(ang) * (outer_r - 6))
                y1 = sc + int(math.sin(ang) * (outer_r - 6))
                x2 = sc + int(math.cos(ang) * outer_r)
                y2 = sc + int(math.sin(ang) * outer_r)
                pygame.draw.line(rs, (r, g, b, alpha), (x1, y1), (x2, y2), 1)
            surface.blit(rs, (cx - sc, cy - sc))

        # ── Middle ring ───────────────────────────────────────────────────────
        mid_r = int(36 * scale)
        if mid_r > 1:
            ms = mid_r * 2 + 4
            mc = ms // 2
            msurf = pygame.Surface((ms, ms), pygame.SRCALPHA)
            pygame.draw.circle(msurf, (r, g, b, alpha // 2), (mc, mc), mid_r, 1)
            surface.blit(msurf, (cx - mc, cy - mc))

        # ── Inner polygon + star diagonals ────────────────────────────────────
        inner_r = int(26 * scale)
        if inner_r > 2 and self.sides >= 3:
            sz2 = inner_r * 2 + 6
            sc2 = sz2 // 2
            ps  = pygame.Surface((sz2, sz2), pygame.SRCALPHA)
            pts = [(sc2 + int(math.cos(math.radians(self.rot2 + i * 360 / self.sides)) * inner_r),
                    sc2 + int(math.sin(math.radians(self.rot2 + i * 360 / self.sides)) * inner_r))
                   for i in range(self.sides)]
            pygame.draw.lines(ps, (r, g, b, alpha), True, pts, 2)
            n = len(pts)
            for i in range(n):
                for j in range(i + 2, n):
                    if not (i == 0 and j == n - 1):
                        pygame.draw.line(ps, (r, g, b, alpha // 2), pts[i], pts[j], 1)
            surface.blit(ps, (cx - sc2, cy - sc2))

        # ── Center glow ───────────────────────────────────────────────────────
        cr = int(5 * scale)
        if cr > 0:
            gs = pygame.Surface((cr * 3, cr * 3), pygame.SRCALPHA)
            pygame.draw.circle(gs, (min(255, r + 60), min(255, g + 60), min(255, b + 60), alpha),
                               (cr, cr), cr)
            surface.blit(gs, (cx - cr, cy - cr))


# ── Traveling projectile (dodgeable) ─────────────────────────────────────────

class TravelingHit(Effect):
    """
    Projectile that travels column-by-column across the grid.
    Damage is deferred: if the target entity has moved off the row by the time
    the orb arrives, the hit misses entirely.  Used for enemy attacks and
    elemental chip orbs.

    Battle._update_effects() watches for pending_damage and spawns
    DamageNumber / ScreenFlash when it is set.
    """
    SPEED = 310   # px/s  ≈ one 96-px panel per 0.31 s

    def __init__(self, src_px, row, col_start, col_end,
                 damage, element, entity, color=(255, 160, 30), radius=8):
        """
        src_px    : (x, y) pixel start (y is overridden to row centre)
        row       : int   — grid row the projectile travels along
        col_start : int   — column it originates from (not checked for collision)
        col_end   : int   — column at which it stops if it never hits
        damage    : int
        element   : element constant
        entity    : Entity to check (player or enemy); None → visual only
        color     : (r,g,b)
        radius    : int
        """
        import tile_warp
        self.y       = float(tile_warp.row_center_y(row))
        self.x       = float(src_px[0])
        self.row     = row
        self.col_end = col_end
        self.damage  = damage
        self.element = element
        self.entity  = entity
        self.color   = color
        self.radius  = radius

        self.vx = -self.SPEED if col_end < col_start else self.SPEED

        self._last_col     = col_start
        self._trail        = []     # [[x, y, frac], ...]
        self.pending_damage = None  # set to (dealt, entity) on a successful hit
        self.alive         = True

    # -- internal -------------------------------------------------------

    def _cur_col(self):
        import tile_warp
        return tile_warp.col_at_x_in_row(self.x, self.row)

    # -- Effect interface -----------------------------------------------

    def update(self, dt):
        # Append trail point
        self._trail.append([self.x, self.y, 1.0])
        # Decay trail
        decay = dt / 0.14
        self._trail = [[x, y, f - decay] for x, y, f in self._trail if f - decay > 0]

        self.x += self.vx * dt
        cur = self._cur_col()

        # Entered a new column — check collision
        if cur != self._last_col:
            self._last_col = cur
            if (self.entity is not None and self.entity.alive
                    and self.entity.col == cur
                    and self.entity.row == self.row):
                dealt = self.entity.take_damage(self.damage, self.element)
                if dealt:
                    self.pending_damage = (dealt, self.entity)
                self.alive = False
                return

        # Termination: gone past the target column or off the grid
        if self.vx < 0 and cur < self.col_end:
            self.alive = False
        elif self.vx > 0 and cur > self.col_end:
            self.alive = False
        elif cur < 0 or cur >= C.GRID_COLS:
            self.alive = False

    def draw(self, surface):
        # Fading trail
        for x, y, frac in self._trail:
            r_px = max(1, int(self.radius * frac * 0.65))
            cr, cg, cb = self.color
            c = (max(0, int(cr * frac * 0.8)),
                 max(0, int(cg * frac * 0.8)),
                 max(0, int(cb * frac * 0.8)))
            pygame.draw.circle(surface, c, (int(x), int(y)), r_px)

        if not self.alive:
            return

        # Soft outer glow
        gr = self.radius + 5
        gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
        cr, cg, cb = self.color
        pygame.draw.circle(gs, (cr, cg, cb, 70), (gr, gr), gr)
        surface.blit(gs, (int(self.x) - gr, int(self.y) - gr))

        # Orb body
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        # Bright core
        core_r = max(1, self.radius // 2)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), core_r)
