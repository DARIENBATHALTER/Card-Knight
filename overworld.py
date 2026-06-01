"""
Isometric tile-based overworld — multi-map, smooth 8-directional movement.
Maps defined in map_defs.py. Exit tiles trigger seamless map transitions.
"""
from __future__ import annotations
import math
import pygame
import constants as C
import fonts
import sprite_manager as SM
import sfx
import gamepad
import story
import map_defs
from chips import make_sample_folder

# ── Render constants ──────────────────────────────────────────────────────────

RENDER_SCALE         = 2       # multiply map_defs tile_w/h/wall_h by this
PLAYER_SPEED         = 4.2     # tiles per second (matches ~180 px/s at tile_h=48)
CHAR_H               = 88      # sprite render height in pixels
TALK_DIST_TILES      = 1.8     # show TALK prompt within this tile distance
ENCOUNTER_DIST_TILES = 1.4     # battle triggers within this distance
EXIT_TRIGGER_DIST    = 0.75    # exit fires when player is this close (tiles)

# Set of map names that are interiors (for door rendering + sound)
_INTERIOR_MAPS = frozenset({'home', 'courier', 'store', 'edric', 'dojo', 'inn'})

# Target on-screen render height (px) for generated decorative objects.
_OBJECT_H = {
    'oak': 156, 'pine_large': 150, 'pine_small': 112, 'dead_tree': 150,
    'bush_plain': 52, 'bush_berry': 52, 'bush_flower': 52, 'bush_flower2': 52,
    'rock_small': 42, 'rock_cluster': 58, 'boulder': 82, 'rock_mossy': 70,
    'stump': 48, 'flowers_blue': 34, 'flowers_purple': 34,
    'crystal_blue': 70, 'crystal_purple': 70,
    'signpost': 92, 'sign_flat': 68, 'fence': 56, 'fence_post': 60,
    'lamp_post': 120, 'lantern_hanging': 72, 'market_stall': 120,
    'chest_wood': 56, 'chest_gold': 60, 'barrel': 60, 'crate': 60,
    'shrine': 100, 'shrine_ruined': 100,
}

# NPC display name → generated sprite base (NW/SW poses; NE/SE via flip).
_NPC_SPRITE = {
    'Mira': 'mira', 'Courier Master': 'courier', "Oden's Mother": 'mother',
    'Shopkeeper': 'shopkeeper', 'Edric': 'edric', 'Sage Hanzo': 'hanzo',
    'Townsfolk': 'townsfolk', 'Dojo Apprentice': 'apprentice',
    'Tired Traveler': 'traveler',
}

# ── Tile colour palettes ──────────────────────────────────────────────────────

# Border/structural walls (stone, gray)
_WALL_TOP   = (112, 105,  95)
_WALL_LEFT  = ( 80,  74,  66)
_WALL_RIGHT = ( 96,  90,  80)

# Building walls (warm tan — detected by having at least one non-wall neighbor)
_BLDG_TOP   = (198, 172, 138)
_BLDG_LEFT  = (158, 132, 100)
_BLDG_RIGHT = (178, 152, 118)

_TILE_TOP = {
    map_defs.TILE_GRASS: ( 72, 120,  55),
    map_defs.TILE_WALL:  _WALL_TOP,
    map_defs.TILE_WATER: ( 50, 120, 180),
    map_defs.TILE_PATH:  (160, 148, 110),
    map_defs.TILE_DIRT:  (140, 115,  80),
}
_TILE_LEFT = {
    map_defs.TILE_GRASS: ( 55,  95,  42),
    map_defs.TILE_WALL:  _WALL_LEFT,
    map_defs.TILE_WATER: ( 38,  95, 150),
    map_defs.TILE_PATH:  (130, 118,  85),
    map_defs.TILE_DIRT:  (112,  90,  62),
}
_TILE_RIGHT = {
    map_defs.TILE_GRASS: ( 62, 108,  48),
    map_defs.TILE_WALL:  _WALL_RIGHT,
    map_defs.TILE_WATER: ( 44, 108, 165),
    map_defs.TILE_PATH:  (145, 132,  98),
    map_defs.TILE_DIRT:  (126, 102,  70),
}

# ── Iso helper ────────────────────────────────────────────────────────────────

def _iso(col, row, hw, hh, ox, oy):
    return ((col - row) * hw + ox, (col + row) * hh + oy)


# ── State enum ────────────────────────────────────────────────────────────────

class OWState:
    WALK    = "walk"
    DIALOG  = "dialog"
    PAUSE   = "pause"
    LIBRARY = "library"


# ── Entity records ────────────────────────────────────────────────────────────

class OWEnemy:
    def __init__(self, waypoints, interval=1.1):
        self.waypoints = [(float(c), float(r)) for c, r in waypoints]
        self.col, self.row = self.waypoints[0]
        self.alive    = True
        self._wp_idx  = 0
        self._timer   = 0.0
        self.interval = interval

    def update(self, dt):
        if not self.alive:
            return
        self._timer -= dt
        if self._timer <= 0:
            self._timer  = self.interval
            self._wp_idx = (self._wp_idx + 1) % len(self.waypoints)
            self.col, self.row = self.waypoints[self._wp_idx]


class OWNPC:
    def __init__(self, col, row, name, color, dialog_fn):
        self.col       = float(col)
        self.row       = float(row)
        self.name      = name
        self.color     = color
        self.dialog_fn = dialog_fn

    def lines(self):
        return self.dialog_fn()


# ── Main class ────────────────────────────────────────────────────────────────

class Overworld:
    def __init__(self, screen, folder=None, map_name='cardhollow', spawn_key='default'):
        self.screen = screen
        self.folder = folder if folder is not None else make_sample_folder()

        self.state          = OWState.WALK
        self.start_battle   = False
        self.quit_to_title  = False
        self.map_transition = None

        self._pause_opts    = ["Resume", "Chip Library", "Quit to Title", "Quit Game"]
        self._pause_cursor  = 0
        self._lib_scroll    = 0
        self._LIB_ROWS      = 8
        self._timer         = 0.0
        self._moving        = False
        self._direction     = 'south'
        self._grace_timer   = 0.0
        self._active_npc    = None
        self._dialog_npc_name = ''
        self._dialog_page   = 0
        self._battle_enemy  = None
        self._block_msg     = ''
        self._block_timer   = 0.0

        # Pixel coords for smooth movement on screen (derived from tile pos + camera)
        # Actual logical position is (player_col, player_row) in tile space (floats).
        self.player_col = 0.0
        self.player_row = 0.0

        self.load_map(map_name, spawn_key)

    # ── Map loading ───────────────────────────────────────────────────────────

    def load_map(self, map_name: str, spawn_key: str = 'default'):
        self.map_transition = None
        self.start_battle   = False
        self.state          = OWState.WALK
        self._grace_timer   = 0.6
        self._battle_enemy  = None
        self._active_npc    = None
        self._dialog_page   = 0

        mdef = map_defs.MAPS[map_name]
        self._map_name = map_name
        self._grid     = mdef['grid']
        self._rows     = len(self._grid)
        self._cols     = max((len(r) for r in self._grid), default=0)

        # Scale tile dims from map_defs values
        rs             = RENDER_SCALE
        self._tile_w   = mdef['tile_w'] * rs
        self._tile_h   = mdef['tile_h'] * rs
        self._wall_h   = mdef['wall_h'] * rs
        self._half_w   = self._tile_w // 2
        self._half_h   = self._tile_h // 2

        spawn = mdef['spawns'].get(spawn_key) or mdef['spawns'].get('default', (1, 1))
        self.player_col = float(spawn[0])
        self.player_row = float(spawn[1])

        self.npcs    = []
        self.enemies = []

        for nd in mdef.get('npcs', []):
            self.npcs.append(OWNPC(
                nd['tile'][0], nd['tile'][1],
                nd['name'], nd['color'], nd['dialog'],
            ))

        for ed in mdef.get('enemies', []):
            if ed.get('story_trigger'):
                if not (story.get('package_accepted') and not story.get('misdeal_road_beaten')):
                    continue
            self.enemies.append(OWEnemy(ed['waypoints'], ed.get('interval', 1.1)))

        self._exits        = mdef.get('exits', [])
        self._props        = mdef.get('props', [])
        self._blocking_msg = mdef.get('blocking_msg', {})

        # Classify wall tiles: BUILDINGS (warm tan, tall, solid roofs) vs terrain
        # (gray border / forest, short). A wall is "terrain" if it connects to the
        # map edge through other walls; isolated wall clusters surrounded by floor
        # are buildings. Flood-filling from the border catches the whole footprint,
        # including interior tiles, so building roofs render solid (no holes).
        terrain: set[tuple[int, int]] = set()
        stack = []
        for r in range(self._rows):
            row = self._grid[r]
            for c in range(len(row)):
                if row[c] == map_defs.TILE_WALL and \
                   (r == 0 or r == self._rows - 1 or c == 0 or c == len(row) - 1):
                    stack.append((c, r))
        while stack:
            c, r = stack.pop()
            if (c, r) in terrain or not self._is_wall(c, r):
                continue
            terrain.add((c, r))
            stack.extend([(c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)])

        self._building_walls: set[tuple[int, int]] = set()
        for r in range(self._rows):
            row = self._grid[r]
            for c in range(len(row)):
                if row[c] == map_defs.TILE_WALL and (c, r) not in terrain:
                    self._building_walls.add((c, r))

        # Buildings rise taller than terrain walls so they read as structures.
        self._building_h = int(self._wall_h * 2.6)

        # Which exit tiles lead to interior maps (the doorway floor tiles)
        self._door_tiles: set[tuple[int, int]] = {
            ex['tile'] for ex in self._exits if ex['dest'] in _INTERIOR_MAPS
        }

        # For each interior doorway, mark the nearest building-wall tile and which
        # visible face ('sw'/'se') points toward the doorway, so we can paint a flat
        # black door on that face. (Doors render as a black tile-face, swappable for
        # a real door sprite later.)
        self._door_panels: dict[tuple[int, int], str] = {}
        for ex in self._exits:
            if ex['dest'] not in _INTERIOR_MAPS:
                continue
            dc, dr = ex['tile']
            best, best_d = None, 99
            for bc, br in self._building_walls:
                d = abs(bc - dc) + abs(br - dr)
                if d < best_d and d <= 3:
                    best, best_d = (bc, br), d
            if best:
                bc, br = best
                # Face whose outward direction points toward the door floor tile.
                face = 'se' if (dc - bc) >= (dr - br) else 'sw'
                if dr > br and dc == bc:
                    face = 'sw'
                elif dc > bc and dr == br:
                    face = 'se'
                self._door_panels[best] = face

        # Objects (decorative billboards: trees, rocks, lamps, signs, chests…)
        self._objects = mdef.get('objects', [])

        # Terrain-wall palette: forest maps get green foliage blocks; towns/interiors
        # keep gray stone for their border/perimeter walls.
        if map_name == 'briar_road':
            self._terr_top, self._terr_left, self._terr_right = \
                (52, 92, 44), (34, 64, 30), (43, 78, 37)
        else:
            self._terr_top, self._terr_left, self._terr_right = \
                _WALL_TOP, _WALL_LEFT, _WALL_RIGHT

        # Pre-scale generated ground-tile art to the tile footprint, once per map.
        self._is_interior = map_name in _INTERIOR_MAPS
        self._tile_imgs = self._build_tile_imgs()
        self._obj_cache: dict = {}   # asset name -> scaled Surface

    # ── Generated-art helpers ───────────────────────────────────────────────────

    @staticmethod
    def _scale_to_w(surf, w):
        sw, sh = surf.get_size()
        h = max(1, round(sh * w / sw))
        return pygame.transform.smoothscale(surf, (int(w), h))

    def _build_tile_imgs(self):
        """Map each tile type → list of scaled generated-tile Surfaces (variants)."""
        if self._is_interior:
            names = {
                map_defs.TILE_PATH:  ['wood_floor1', 'wood_floor2'],
                map_defs.TILE_GRASS: ['tatami_floor'],
                map_defs.TILE_DIRT:  ['stone_floor'],
                map_defs.TILE_WATER: ['water'],
            }
        else:
            names = {
                map_defs.TILE_GRASS: ['grass1', 'grass2', 'grass3'],
                map_defs.TILE_PATH:  ['cobblestone', 'dirt_path'],
                map_defs.TILE_DIRT:  ['packed_earth'],
                map_defs.TILE_WATER: ['water'],
            }
        out = {}
        for ttype, keys in names.items():
            surfs = []
            for k in keys:
                s = SM.get(f'env_tiles_{k}')
                if s:
                    surfs.append(self._scale_to_w(s, self._tile_w))
            if surfs:
                out[ttype] = surfs
        return out

    def _obj_surf(self, asset, target_h):
        """Scaled generated object/NPC sprite, cached by (asset, height)."""
        key = (asset, target_h)
        if key in self._obj_cache:
            return self._obj_cache[key]
        raw = SM.get(f'env_objects_{asset}') or SM.get(f'env_npcs_{asset}')
        surf = None
        if raw:
            sw, sh = raw.get_size()
            w = max(1, round(sw * target_h / sh))
            surf = pygame.transform.smoothscale(raw, (w, int(target_h)))
        self._obj_cache[key] = surf
        return surf

    # ── Camera ────────────────────────────────────────────────────────────────

    def _get_origin(self):
        px_sx = (self.player_col - self.player_row) * self._half_w
        px_sy = (self.player_col + self.player_row) * self._half_h
        return C.SCREEN_W // 2 - int(px_sx), C.SCREEN_H // 2 - int(px_sy)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        self._timer      += dt
        self._grace_timer = max(0.0, self._grace_timer - dt)
        self._block_timer = max(0.0, self._block_timer - dt)

        if self.state == OWState.WALK:
            self._update_movement(dt)
            if self.map_transition is None:
                self._check_exits()
            for e in self.enemies:
                e.update(dt)
            self._check_battle()

    def _passable(self, col: int, row: int) -> bool:
        if row < 0 or row >= self._rows:
            return False
        grid_row = self._grid[row]
        if col < 0 or col >= len(grid_row):
            return False
        return grid_row[col] not in (map_defs.TILE_WALL, map_defs.TILE_WATER)

    def _passable_float(self, col: float, row: float, radius: float = 0.32) -> bool:
        for dc, dr in ((-radius, -radius), (radius, -radius),
                       (-radius,  radius), (radius,  radius)):
            if not self._passable(int(round(col + dc)), int(round(row + dr))):
                return False
        return True

    def _update_movement(self, dt):
        keys = pygame.key.get_pressed()
        joy  = gamepad.active()

        up    = keys[pygame.K_UP]    or 'up'    in joy
        down  = keys[pygame.K_DOWN]  or 'down'  in joy
        left  = keys[pygame.K_LEFT]  or 'left'  in joy
        right = keys[pygame.K_RIGHT] or 'right' in joy

        # Raw tile-space deltas (each key contributes -1/+1 to col and row)
        raw_dc = (-1 if up else 0) + (1 if down else 0) + \
                 (-1 if left else 0) + (1 if right else 0)
        raw_dr = (-1 if up else 0) + (1 if down else 0) + \
                 (1 if left else 0) + (-1 if right else 0)

        if raw_dc == 0 and raw_dr == 0:
            self._moving = False
            return

        self._moving = True

        # 8-directional facing based on screen-space projection
        sx_dir = raw_dc - raw_dr   # positive = screen-east
        sy_dir = raw_dc + raw_dr   # positive = screen-south

        if sx_dir > 0:
            if sy_dir < 0:   self._direction = 'northeast'
            elif sy_dir > 0: self._direction = 'southeast'
            else:            self._direction = 'east'
        elif sx_dir < 0:
            if sy_dir < 0:   self._direction = 'northwest'
            elif sy_dir > 0: self._direction = 'southwest'
            else:            self._direction = 'west'
        else:
            if sy_dir < 0:   self._direction = 'north'
            else:            self._direction = 'south'

        # Normalize and scale by speed
        length = math.hypot(raw_dc, raw_dr) or 1.0
        dc = (raw_dc / length) * PLAYER_SPEED * dt
        dr = (raw_dr / length) * PLAYER_SPEED * dt

        nc = self.player_col + dc
        nr = self.player_row + dr

        # Slide collision: try full move, then axis-only
        if self._passable_float(nc, nr):
            self.player_col, self.player_row = nc, nr
        elif self._passable_float(nc, self.player_row):
            self.player_col = nc
        elif self._passable_float(self.player_col, nr):
            self.player_row = nr

    def _check_exits(self):
        """Fire a transition when the player walks close to an exit tile."""
        if self._grace_timer > 0:
            return
        for ex in self._exits:
            ec, er = ex['tile']
            dist = math.hypot(self.player_col - ec, self.player_row - er)
            if dist < EXIT_TRIGGER_DIST:
                req = ex.get('req_flag')
                if req and not story.get(req):
                    key = ex['dest']
                    self._block_msg = (
                        self._blocking_msg.get(key) or
                        self._blocking_msg.get('from_' + key.split('_')[0]) or
                        "I can't go that way yet."
                    )
                    self._block_timer = 2.5
                    return
                self.map_transition = (ex['dest'], ex['spawn'])
                return

    def _check_battle(self):
        if self._grace_timer > 0:
            return
        for e in self.enemies:
            if not e.alive:
                continue
            dist = math.hypot(self.player_col - e.col, self.player_row - e.row)
            if dist <= ENCOUNTER_DIST_TILES:
                self._battle_enemy = e
                self.start_battle  = True
                return

    def on_battle_end(self, player_won):
        self.start_battle = False
        self._grace_timer = 2.2
        if player_won and self._battle_enemy:
            if self._map_name == 'briar_road':
                self._battle_enemy.alive = False
                story.set_flag('misdeal_road_beaten')
        self._battle_enemy = None

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        k = event.key

        if self.state == OWState.WALK:
            if k == pygame.K_ESCAPE:
                self.state = OWState.PAUSE
                self._pause_cursor = 0
                sfx.play('ui_dialog_open')
            elif k in (pygame.K_z, pygame.K_RETURN):
                self._try_talk()

        elif self.state == OWState.DIALOG:
            if k in (pygame.K_z, pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                lines = self._active_npc.lines() if self._active_npc else []
                self._dialog_page += 1
                if self._dialog_page >= len(lines):
                    self._on_dialog_end(self._dialog_npc_name)
                    self.state        = OWState.WALK
                    self._dialog_page = 0
                    self._active_npc  = None
                    sfx.play('ui_cancel')
                else:
                    sfx.play('ui_confirm')

        elif self.state == OWState.PAUSE:
            if k == pygame.K_UP:
                prev = self._pause_cursor
                self._pause_cursor = max(0, self._pause_cursor - 1)
                if self._pause_cursor != prev:
                    sfx.play('ui_cursor')
            elif k == pygame.K_DOWN:
                prev = self._pause_cursor
                self._pause_cursor = min(len(self._pause_opts) - 1, self._pause_cursor + 1)
                if self._pause_cursor != prev:
                    sfx.play('ui_cursor')
            elif k in (pygame.K_z, pygame.K_RETURN):
                sfx.play('ui_confirm')
                self._select_pause()
            elif k == pygame.K_ESCAPE:
                self.state = OWState.WALK
                sfx.play('ui_cancel')

        elif self.state == OWState.LIBRARY:
            if k == pygame.K_UP:
                prev = self._lib_scroll
                self._lib_scroll = max(0, self._lib_scroll - 1)
                if self._lib_scroll != prev:
                    sfx.play('ui_cursor')
            elif k == pygame.K_DOWN:
                cap  = max(0, len(self.folder) - self._LIB_ROWS)
                prev = self._lib_scroll
                self._lib_scroll = min(cap, self._lib_scroll + 1)
                if self._lib_scroll != prev:
                    sfx.play('ui_cursor')
            elif k in (pygame.K_ESCAPE, pygame.K_x, pygame.K_z):
                self.state = OWState.PAUSE
                sfx.play('ui_cancel')

    def _try_talk(self):
        best, best_d = None, TALK_DIST_TILES + 1
        for npc in self.npcs:
            d = math.hypot(self.player_col - npc.col, self.player_row - npc.row)
            if d < best_d:
                best_d, best = d, npc
        if best is not None:
            self._active_npc      = best
            self._dialog_npc_name = best.name
            self._dialog_page     = 0
            self.state = OWState.DIALOG
            sfx.play('ui_dialog_open')

    def _on_dialog_end(self, name: str):
        """Set story flags after finishing NPC dialogue."""
        if name == 'Courier Master' and not story.get('package_accepted'):
            story.set_flag('package_accepted')
        elif name == 'Edric':
            if not story.get('met_edric'):
                story.set_flag('met_edric')
            if not story.get('received_deck'):
                story.set_flag('received_deck')

    def _select_pause(self):
        if self._pause_cursor == 0:
            self.state = OWState.WALK
        elif self._pause_cursor == 1:
            self.state       = OWState.LIBRARY
            self._lib_scroll = 0
        elif self._pause_cursor == 2:
            self.quit_to_title = True
        elif self._pause_cursor == 3:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        surf = self.screen
        surf.fill((22, 20, 32))

        ox, oy = self._get_origin()
        hw, hh, wh = self._half_w, self._half_h, self._wall_h

        cull_x0 = -hw * 5
        cull_x1 = C.SCREEN_W + hw * 5
        cull_y0 = -hh * 8
        cull_y1 = C.SCREEN_H + self._building_h + wh * 6

        # ── Pass 1: GROUND tiles only (flat floor types) ──────────────────────
        # Drawn first, in depth (col+row) order so generated tile art with a
        # thick base lip overlaps back-to-front, and ground never clips over a
        # character. Walls/buildings + entities depth-sort in pass 2.
        floor = []
        for r in range(self._rows):
            row = self._grid[r]
            for c in range(len(row)):
                if row[c] != map_defs.TILE_WALL:
                    floor.append((c + r, c, r, row[c]))
        floor.sort(key=lambda d: d[0])
        for depth, c, r, ttype in floor:
            sx = int((c - r) * hw + ox)
            sy = int((c + r) * hh + oy)
            if cull_x0 < sx < cull_x1 and cull_y0 < sy < cull_y1:
                self._draw_floor(surf, sx, sy, ttype, hw, hh, c, r)

        # ── Pass 2: WALLS + props + objects + entities + player, depth-sorted ──
        drawables = []
        for r in range(self._rows):
            row = self._grid[r]
            for c in range(len(row)):
                if row[c] == map_defs.TILE_WALL:
                    drawables.append((c + r, 'tile', c, r, row[c]))

        for prop in self._props:
            pc, pr = prop['tile']
            drawables.append((pc + pr + 0.4, 'prop', pc, pr, prop['type']))

        for obj in self._objects:
            oc, orr = obj['tile']
            drawables.append((oc + orr + 0.45, 'object', oc, orr, obj['asset']))

        for npc in self.npcs:
            drawables.append((npc.col + npc.row + 0.5, 'npc', npc.col, npc.row, npc))

        for e in self.enemies:
            if e.alive:
                drawables.append((e.col + e.row + 0.5, 'enemy', e.col, e.row, e))

        drawables.append((self.player_col + self.player_row + 0.5,
                          'player', self.player_col, self.player_row, None))

        drawables.sort(key=lambda d: d[0])

        for depth, kind, c, r, data in drawables:
            sx = int((c - r) * hw + ox)
            sy = int((c + r) * hh + oy)
            if kind == 'tile':
                if cull_x0 < sx < cull_x1 and cull_y0 < sy < cull_y1:
                    self._draw_tile(surf, sx, sy, data, hw, hh, wh, int(c), int(r))
            elif kind == 'prop':
                self._draw_prop(surf, sx, sy, data)
            elif kind == 'object':
                self._draw_object(surf, sx, sy, data)
            elif kind == 'npc':
                self._draw_npc(surf, sx, sy, data)
            elif kind == 'enemy':
                self._draw_enemy(surf, sx, sy, data)
            elif kind == 'player':
                self._draw_player(surf, sx, sy)

        # HUD
        if self.state == OWState.WALK:
            self._draw_hints(surf)
            if self._block_timer > 0 and self._block_msg:
                self._draw_block_msg(surf)
        elif self.state == OWState.DIALOG:
            self._draw_dialog(surf)
        elif self.state == OWState.PAUSE:
            self._draw_pause(surf)
        elif self.state == OWState.LIBRARY:
            self._draw_library(surf)

    # ── Tile rendering ────────────────────────────────────────────────────────

    def _is_wall(self, c, r):
        if r < 0 or r >= self._rows:
            return False
        row = self._grid[r]
        if c < 0 or c >= len(row):
            return False
        return row[c] == map_defs.TILE_WALL

    def _draw_tile(self, surf, sx, sy, tile_type, hw, hh, wh, col, row):
        is_building = (col, row) in self._building_walls
        door_face   = self._door_panels.get((col, row))

        if tile_type == map_defs.TILE_WALL:
            # Blocks extrude UPWARD: the roof sits at (sy - H) and the visible
            # south faces drop from the roof down to the ground diamond. Drawing
            # upward (rather than down) is what makes a building correctly OCCLUDE
            # a character standing behind it once tiles depth-sort by (col+row).
            H  = self._building_h if is_building else wh
            tc = _BLDG_TOP   if is_building else self._terr_top
            lc = _BLDG_LEFT  if is_building else self._terr_left
            rc = _BLDG_RIGHT if is_building else self._terr_right

            # Only draw a side face when the neighbour sharing it is NOT also a wall,
            # so a solid building reads as one structure with no internal seams.
            show_sw = not self._is_wall(col, row + 1)   # face toward screen down-left
            show_se = not self._is_wall(col + 1, row)   # face toward screen down-right

            # SW (lower-left) face
            if show_sw:
                col_sw = (8, 6, 10) if door_face == 'sw' else lc
                pygame.draw.polygon(surf, col_sw, [
                    (sx - hw, sy),
                    (sx,      sy + hh),
                    (sx,      sy + hh - H),
                    (sx - hw, sy      - H),
                ])
                if door_face == 'sw':
                    pygame.draw.polygon(surf, (90, 62, 34), [
                        (sx - hw, sy), (sx, sy + hh),
                        (sx, sy + hh - H), (sx - hw, sy - H)], 2)
            # SE (lower-right) face
            if show_se:
                col_se = (8, 6, 10) if door_face == 'se' else rc
                pygame.draw.polygon(surf, col_se, [
                    (sx,      sy + hh),
                    (sx + hw, sy),
                    (sx + hw, sy      - H),
                    (sx,      sy + hh - H),
                ])
                if door_face == 'se':
                    pygame.draw.polygon(surf, (90, 62, 34), [
                        (sx, sy + hh), (sx + hw, sy),
                        (sx + hw, sy - H), (sx, sy + hh - H)], 2)

            # Roof (top diamond) raised by H
            roof = [(sx, sy - hh - H), (sx + hw, sy - H),
                    (sx, sy + hh - H), (sx - hw, sy - H)]
            pygame.draw.polygon(surf, tc, roof)
            pygame.draw.polygon(surf, (0, 0, 0), roof, 1)

        else:
            tc = _TILE_TOP.get(tile_type, (100, 100, 100))
            top = [(sx, sy - hh), (sx + hw, sy), (sx, sy + hh), (sx - hw, sy)]
            pygame.draw.polygon(surf, tc, top)

            if tile_type == map_defs.TILE_WATER:
                shimmer = int(25 + 20 * abs(
                    math.sin(self._timer * 2.2 + col * 0.4 + row * 0.3)))
                hl = tuple(min(255, x + shimmer) for x in tc)
                pygame.draw.polygon(surf, hl, [
                    (sx,           sy - hh),
                    (sx + hw // 2, sy - hh // 2),
                    (sx,           sy),
                    (sx - hw // 2, sy - hh // 2),
                ])

            pygame.draw.polygon(surf, (0, 0, 0), top, 1)

    def _draw_floor(self, surf, sx, sy, ttype, hw, hh, c, r):
        """Draw a ground tile — generated art if available, else flat polygon."""
        variants = self._tile_imgs.get(ttype)
        if variants:
            img = variants[(c * 7 + r * 13) % len(variants)]
            # Generated tiles are scaled to width=tile_w; place the diamond top
            # at (sx, sy-hh) so they tessellate, base lip overlapping forward.
            surf.blit(img, (sx - hw, sy - hh))
            return
        tc  = _TILE_TOP.get(ttype, (100, 100, 100))
        top = [(sx, sy - hh), (sx + hw, sy), (sx, sy + hh), (sx - hw, sy)]
        pygame.draw.polygon(surf, tc, top)
        if ttype == map_defs.TILE_WATER:
            shimmer = int(25 + 20 * abs(math.sin(self._timer * 2.2 + c * 0.4 + r * 0.3)))
            hl = tuple(min(255, x + shimmer) for x in tc)
            pygame.draw.polygon(surf, hl, [
                (sx, sy - hh), (sx + hw // 2, sy - hh // 2),
                (sx, sy), (sx - hw // 2, sy - hh // 2)])
        pygame.draw.polygon(surf, (0, 0, 0), top, 1)

    def _draw_object(self, surf, sx, sy, asset):
        target_h = _OBJECT_H.get(asset, int(self._tile_h * 1.8))
        img = self._obj_surf(asset, target_h)
        if not img:
            return
        ow_ = img.get_width()
        # Soft contact shadow
        ssw = max(8, int(ow_ * 0.55))
        shp = pygame.Surface((ssw, max(4, ssw // 3)), pygame.SRCALPHA)
        pygame.draw.ellipse(shp, (0, 0, 0, 70), shp.get_rect())
        surf.blit(shp, (sx - ssw // 2, sy - shp.get_height() // 2))
        surf.blit(img, (sx - ow_ // 2, sy - img.get_height()))

    def _draw_prop(self, surf, sx, sy, prop_type):
        if   prop_type == 'shrine':        self._draw_shrine(surf, sx, sy, False)
        elif prop_type == 'shrine_ruined': self._draw_shrine(surf, sx, sy, True)

    def _draw_shrine(self, surf, cx, cy, ruined):
        col = (75, 70, 65)   if ruined else (100, 95, 90)
        cap = (100, 95, 90)  if ruined else (128, 122, 115)
        pygame.draw.rect(surf, col, (cx - 14, cy - 34, 28, 26))
        pts = [(cx - 16, cy - 34), (cx + 16, cy - 34), (cx, cy - 54)]
        pygame.draw.polygon(surf, cap, pts)
        pygame.draw.polygon(surf, (0, 0, 0), pts, 1)
        if not ruined:
            r = int(5 + math.sin(self._timer * 3.2) * 2)
            pygame.draw.circle(surf, (55, 130, 255), (cx, cy - 46), r)
            pygame.draw.circle(surf, (200, 225, 255), (cx, cy - 46), max(1, r - 2))

    # ── Entity drawing ────────────────────────────────────────────────────────

    _DIAGONALS = frozenset({'northeast', 'northwest', 'southeast', 'southwest'})

    def _sprite_at(self, surf, sx, sy, frames, scale_mul=1.0):
        if not frames:
            return
        frame = frames[int(self._timer * 6) % len(frames)] if isinstance(frames, list) else frames
        fw, fh = frame.get_size()
        th     = int(CHAR_H * scale_mul)
        dw     = int(fw * th / fh)
        surf.blit(pygame.transform.scale(frame, (dw, th)), (sx - dw // 2, sy - th))

    def _draw_player(self, surf, sx, sy):
        d  = self._direction
        sm = 0.95 if d in self._DIAGONALS else 1.0
        # Flat contact shadow centred exactly under the feet anchor (sx, sy) in
        # every direction. Normalised sprites put the feet at (sx, sy), so a
        # simple centred ellipse stays planted as Oden turns.
        sw = int(40 * sm)
        sh = int(16 * sm)
        shadow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 85), shadow.get_rect())
        surf.blit(shadow, (sx - sw // 2, sy - sh // 2))
        frames = (SM.get(f'oden_walk_{d}') or SM.get('oden_run')) if self._moving \
            else (SM.get(f'oden_idle_{d}') or SM.get('oden_idle'))
        if frames:
            self._sprite_at(surf, sx, sy, frames, sm)
        else:
            pygame.draw.ellipse(surf, (0, 0, 0),  (sx - 10, sy - 4, 20, 8))
            pygame.draw.rect(   surf, C.BLUE,      (sx - 7,  sy - 30, 14, 20), border_radius=3)
            pygame.draw.circle( surf, C.BLUE,      (sx, sy - 38), 9)
            pygame.draw.circle( surf, C.WHITE,     (sx, sy - 38), 9, 2)

    def _draw_npc(self, surf, sx, sy, npc):
        sprite = _NPC_SPRITE.get(npc.name)
        img = self._obj_surf(f'{sprite}_sw', int(CHAR_H * 0.92)) if sprite else None
        if img:
            iw = img.get_width()
            ssw = max(10, int(iw * 0.7))
            shp = pygame.Surface((ssw, max(4, ssw // 3)), pygame.SRCALPHA)
            pygame.draw.ellipse(shp, (0, 0, 0, 80), shp.get_rect())
            surf.blit(shp, (sx - ssw // 2, sy - shp.get_height() // 2))
            surf.blit(img, (sx - iw // 2, sy - img.get_height()))
        else:
            bob  = int(math.sin(self._timer * 2.2) * 2)
            col  = npc.color
            lite = tuple(min(255, c + 50) for c in col)
            pygame.draw.ellipse(surf, (0, 0, 0), (sx - 9, sy - 4, 18, 8))
            pygame.draw.rect(surf, col,  (sx - 8, sy - 28 + bob, 16, 20), border_radius=3)
            pygame.draw.circle(surf, col,  (sx, sy - 34 + bob), 9)
            pygame.draw.circle(surf, lite, (sx, sy - 34 + bob), 9, 1)
        dist = math.hypot(self.player_col - npc.col, self.player_row - npc.row)
        if dist <= TALK_DIST_TILES:
            lf  = fonts.serif(13, bold=True)
            lbl = lf.render("TALK", True, C.UI_GOLD)
            px, py = 7, 2
            cw     = lbl.get_width() + px * 2
            ch     = lbl.get_height() + py * 2
            chip   = pygame.Surface((cw, ch), pygame.SRCALPHA)
            chip.fill((10, 14, 38, 215))
            pygame.draw.rect(chip, C.UI_DARK_GOLD, chip.get_rect(), 2, border_radius=3)
            chip.blit(lbl, (px, py))
            surf.blit(chip, (sx - cw // 2, sy - CHAR_H))

    def _draw_enemy(self, surf, sx, sy, enemy):
        bob    = 1 if int(self._timer * 4) % 2 else 0
        frames = SM.get('gen_slime_idle')
        if frames:
            idx   = int(self._timer * 6) % len(frames)
            frame = frames[idx]
            fw, fh = frame.get_size()
            eh    = int(CHAR_H * 0.72)
            ew    = int(fw * eh / fh)
            surf.blit(pygame.transform.scale(frame, (ew, eh)), (sx - ew // 2, sy - eh - bob))
        else:
            pygame.draw.ellipse(surf, (0, 0, 0),    (sx - 11, sy - 4,  22, 8))
            pygame.draw.ellipse(surf, (30, 140, 40), (sx - 12, sy - 22 + bob, 24, 20))
            pygame.draw.ellipse(surf, (55, 190, 65), (sx - 8,  sy - 24 + bob, 16, 14))
        dist = math.hypot(self.player_col - enemy.col, self.player_row - enemy.row)
        if dist <= ENCOUNTER_DIST_TILES * 3.5:
            pulse = int(self._timer * 5) % 2 == 0
            wf    = fonts.serif(28, bold=True)
            ws    = wf.render("!", True, C.RED if pulse else C.YELLOW)
            ss    = wf.render("!", True, (10, 4, 4))
            bobb  = int(math.sin(self._timer * 6) * 2)
            wx, wy = sx - ws.get_width() // 2, sy - CHAR_H - 16 + bobb
            surf.blit(ss, (wx + 1, wy + 1))
            surf.blit(ws, (wx, wy))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hints(self, surf):
        hint = fonts.pixel(6).render(
            "Arrows:Move  Z:Talk  Esc:Pause", True, (70, 65, 100))
        surf.blit(hint, (4, C.SCREEN_H - 11))

    def _draw_block_msg(self, surf):
        f   = fonts.serif(16)
        s   = f.render(self._block_msg, True, C.UI_GOLD)
        bx  = C.SCREEN_W // 2 - s.get_width() // 2 - 12
        by  = C.SCREEN_H - 90
        box = pygame.Surface((s.get_width() + 24, s.get_height() + 12), pygame.SRCALPHA)
        box.fill((10, 14, 38, 215))
        pygame.draw.rect(box, C.UI_DARK_GOLD, box.get_rect(), 2, border_radius=4)
        surf.blit(box, (bx, by))
        surf.blit(s, (bx + 12, by + 6))

    def _draw_dialog(self, surf):
        if self._active_npc is None:
            return
        lines = self._active_npc.lines()
        if not lines or self._dialog_page >= len(lines):
            return

        bw, bh = 1100, 200
        bx = (C.SCREEN_W - bw) // 2
        by = C.SCREEN_H - bh - 32

        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        box.fill((10, 14, 38, 245))
        pygame.draw.rect(box, (24, 30, 70, 80),
                         pygame.Rect(8, 8, bw - 16, bh - 16), border_radius=6)
        pygame.draw.rect(box, C.UI_DARK_GOLD, box.get_rect(), 4, border_radius=8)
        pygame.draw.rect(box, C.UI_GOLD, box.get_rect().inflate(-4, -4), 1, border_radius=6)
        surf.blit(box, (bx, by))

        for cx, cy in ((bx + 22, by + 22), (bx + bw - 22, by + 22),
                       (bx + 22, by + bh - 22), (bx + bw - 22, by + bh - 22)):
            pygame.draw.polygon(surf, C.UI_GOLD,
                                [(cx, cy - 11), (cx + 11, cy), (cx, cy + 11), (cx - 11, cy)])
            pygame.draw.polygon(surf, (10, 14, 38),
                                [(cx + 4, cy - 4), (cx + 4, cy + 4),
                                 (cx - 4, cy + 4), (cx - 4, cy - 4)])
            pygame.draw.circle(surf, C.UI_DARK_GOLD, (cx, cy), 2)

        surf.blit(fonts.serif(24, bold=True).render(self._active_npc.name, True, C.UI_GOLD),
                  (bx + 36, by + 18))

        pg_s = fonts.serif(13).render(
            f"{self._dialog_page + 1} / {len(lines)}", True, (180, 165, 210))
        surf.blit(pg_s, (bx + bw - pg_s.get_width() - 36, by + 26))

        ry  = by + 56
        rx0, rx1 = bx + 32, bx + bw - 32
        pygame.draw.line(surf, C.UI_DARK_GOLD, (rx0, ry + 1), (rx1, ry + 1), 1)
        pygame.draw.line(surf, C.UI_GOLD,      (rx0, ry),     (rx1, ry),     1)
        for dx in (rx0, (rx0 + rx1) // 2, rx1):
            pygame.draw.polygon(surf, C.UI_GOLD,
                                [(dx, ry - 4), (dx + 4, ry), (dx, ry + 4), (dx - 4, ry)])

        bf    = fonts.serif(19)
        rows  = self._wrap_text_px(lines[self._dialog_page], bf, bw - 72)
        ty    = ry + 16
        for i, row_text in enumerate(rows[:4]):
            surf.blit(bf.render(row_text, True, C.WHITE), (bx + 36, ty + i * 24))

        if int(self._timer * 3) % 2 == 0:
            ax, ay = bx + bw - 44, by + bh - 32
            pygame.draw.polygon(surf, C.UI_GOLD,
                                [(ax, ay - 7), (ax + 14, ay - 7), (ax + 7, ay + 3)])

    @staticmethod
    def _wrap_text_px(text, font, max_width):
        words, rows, cur = text.split(), [], ""
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
        mx = C.SCREEN_W // 2 - mw // 2
        my = C.SCREEN_H // 2 - mh // 2
        pygame.draw.rect(surf, C.UI_NAVY, (mx, my, mw, mh), border_radius=6)
        pygame.draw.rect(surf, C.UI_GOLD, (mx, my, mw, mh), 2, border_radius=6)
        ts = fonts.pixel(8, bold=True).render("PAUSE", True, C.UI_GOLD)
        surf.blit(ts, (mx + mw // 2 - ts.get_width() // 2, my + 7))
        pygame.draw.line(surf, C.UI_DARK_GOLD, (mx + 4, my + 22), (mx + mw - 4, my + 22))
        for i, opt in enumerate(self._pause_opts):
            oy  = my + 28 + i * 26
            sel = i == self._pause_cursor
            if sel:
                pygame.draw.rect(surf, C.UI_ACCENT, (mx + 4, oy - 1, mw - 8, 22), border_radius=3)
            col = C.WHITE if sel else (90, 85, 120)
            surf.blit(fonts.pixel(8).render(opt, True, col), (mx + 14, oy + 3))

    def _draw_library(self, surf):
        surf.fill(C.UI_NAVY)
        pygame.draw.rect(surf, C.UI_GOLD, (4, 4, C.SCREEN_W - 8, C.SCREEN_H - 8), 2, border_radius=4)
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
            surf.blit(fonts.mono(13).render(dmg,       True, C.WHITE),                (172, ry + 6))
            surf.blit(fonts.mono(13).render(en,        True, ec),                     (216, ry + 6))
            surf.blit(fonts.pixel(7).render(chip.code, True, cc),                     (282, ry + 7))
        n = len(self.folder)
        if n > self._LIB_ROWS:
            bar_h = self._LIB_ROWS * 28
            pct   = self._lib_scroll / max(1, n - self._LIB_ROWS)
            bar_y = 42 + int(pct * (bar_h - 16))
            pygame.draw.rect(surf, C.UI_DARK_GOLD, (C.SCREEN_W - 10, 42, 6, bar_h))
            pygame.draw.rect(surf, C.UI_GOLD,      (C.SCREEN_W - 10, bar_y, 6, 16))
        hint = fonts.pixel(6).render("Z/Esc — back", True, (70, 65, 100))
        surf.blit(hint, (C.SCREEN_W // 2 - hint.get_width() // 2, C.SCREEN_H - 12))
