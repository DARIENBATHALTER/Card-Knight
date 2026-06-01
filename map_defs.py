"""
Map definitions for Card Knight: Astral Arcana.

Tile types:
  0 = GRASS  — open ground, passable
  1 = WALL   — stone block, impassable (3D extruded in iso)
  2 = WATER  — animated shimmer, impassable
  3 = PATH   — cobblestone, passable
  4 = DIRT   — rough earth, passable (used on route)

Exit/building entries are defined per-map as (col, row) tile triggers — not tile types.
Props (shrine, tree, etc.) are decorative overlays on passable tiles.

Map coordinate system:
  col increases to the right-and-down (screen east)
  row increases to the left-and-down (screen west)
  iso screen x = (col - row) * (TILE_W // 2)  + origin_x
  iso screen y = (col + row) * (TILE_H // 2)  + origin_y
"""

import story

TILE_GRASS = 0
TILE_WALL  = 1
TILE_WATER = 2
TILE_PATH  = 3
TILE_DIRT  = 4

# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────

def _row(s):
    """Compact row notation: '.' grass, '#' wall, '~' water, '=' path, '-' dirt."""
    m = {'.': 0, '#': 1, '~': 2, '=': 3, '-': 4}
    return [m[c] for c in s if c in m]


# ──────────────────────────────────────────────────────────────────────────────
# CARDHOLLOW  22×22
# Layout: wall border with west gap (rows 9-11) for exit.
#   Top half: Oden's house (NW), Courier Post (NE)
#   Center: Card Shrine prop, crossing path
#   Bottom half: General Store (SW), Neighbor's house (SE)
# ──────────────────────────────────────────────────────────────────────────────
_CH = [
    _row('######################'),  # 0
    _row('#....................#'),  # 1
    _row('#.###.......####.....#'),  # 2  Oden's house cols 2-4 (solid), Courier cols 12-15 (solid)
    _row('#.###.......####.....#'),  # 3
    _row('#.###.......####.....#'),  # 4
    _row('#....................#'),  # 5  door floor tiles south of each building
    _row('#....................#'),  # 6
    _row('#....................#'),  # 7  (shrine now free-standing — no enclosure)
    _row('#....................#'),  # 8
    _row('.====================.'),  # 9  EXIT west — clear east-west path
    _row('.====================.'),  #10  EXIT west — clear east-west path
    _row('#....................#'),  #11
    _row('#....................#'),  #12
    _row('#..###.........###...#'),  #13  Store cols 3-5 (solid), Neighbor cols 15-17 (solid)
    _row('#..###.........###...#'),  #14
    _row('#..###.........###...#'),  #15
    _row('#....................#'),  #16  door floor tiles south of each building
    _row('#....................#'),  #17
    _row('#....................#'),  #18
    _row('#....................#'),  #19
    _row('#....................#'),  #20
    _row('######################'),  #21
]

# ──────────────────────────────────────────────────────────────────────────────
# THE BRIAR ROAD  48 wide × 22 tall
# Long winding route. Cardhollow sits at the EAST end (high col); Veilgate at the
# WEST end (low col). Travel = DECREASING col, which renders as screen NW (up-left)
# — so the road visibly heads NW from Cardhollow toward Veilgate, matching the
# direction the player walks out of Cardhollow's west gate.
#
# The path is a winding horizontal band: for each column we open a small set of
# rows whose centre meanders up and down. Forest (wall) fills the rest.
# ──────────────────────────────────────────────────────────────────────────────
_BR_W, _BR_H = 48, 22

import math as _math

# Centre row of the path at each column — a meander built from gentle sine waves.
def _path_center(col: int) -> int:
    base = _BR_H / 2
    wob  = 3.4 * _math.sin(col * 0.32) + 1.8 * _math.sin(col * 0.11 + 1.0)
    return int(round(base + wob))

# Per-column open rows (path band), and which columns are clearings (wider).
_CLEARING_COLS = set(range(22, 27))   # mid-route clearing (ruined shrine sits here)

_PATH_ROWS = {}   # col -> set of open rows
for _c in range(_BR_W):
    cen   = _path_center(_c)
    half  = 3 if _c in _CLEARING_COLS else 1   # clearing is wider
    rows  = set(range(cen - half, cen + half + 1))
    rows  = {r for r in rows if 1 <= r <= _BR_H - 2}
    _PATH_ROWS[_c] = rows

_ROAD = []
for _r in range(_BR_H):
    row = []
    for _c in range(_BR_W):
        if _r == 0 or _r == _BR_H - 1:
            row.append(TILE_WALL)                       # north/south forest edge
        elif _r in _PATH_ROWS[_c]:
            row.append(TILE_PATH)                       # walkable road
        elif _c in _CLEARING_COLS and abs(_r - _path_center(_c)) <= 4:
            row.append(TILE_GRASS)                       # grassy clearing shoulder
        else:
            row.append(TILE_WALL)                        # dense forest (impassable)
    _ROAD.append(row)

# Resolve the centre rows at the two ends for spawn/exit placement.
_BR_EAST_CEN = _path_center(_BR_W - 2)   # Cardhollow side (high col)
_BR_WEST_CEN = _path_center(1)           # Veilgate side  (low col)
_BR_MID      = _BR_W // 2                 # mid-route column (clearing)
_BR_MID_CEN  = _path_center(_BR_MID)

# Edge-column path rows become the transition tiles on each end.
_BR_EXITS_TO_CARDHOLLOW = [
    {'tile': (_BR_W - 1, r), 'dest': 'cardhollow', 'spawn': 'from_briar', 'req_flag': None}
    for r in sorted(_PATH_ROWS[_BR_W - 1])
]
_BR_EXITS_TO_VEILGATE = [
    {'tile': (0, r), 'dest': 'veilgate', 'spawn': 'from_briar', 'req_flag': None}
    for r in sorted(_PATH_ROWS[0])
]

# ──────────────────────────────────────────────────────────────────────────────
# VEILGATE  24×22
# Older, more weathered than Cardhollow. Stone streets. East exit.
# Edric's house (NW), Dojo (center-N), Inn + Store (NE)
# Card shrine (left of center), canal water feature (south)
# ──────────────────────────────────────────────────────────────────────────────
_VG = [
    _row('########################'),  # 0
    _row('#......................#'),  # 1
    _row('#.####...######........#'),  # 2  Edric cols 2-5 (solid), Dojo cols 9-14 (solid)
    _row('#.####...######........#'),  # 3
    _row('#.####...######........#'),  # 4
    _row('#.####...######........#'),  # 5
    _row('#......................#'),  # 6  door floor tiles south of each building
    _row('#......................#'),  # 7
    _row('#....===.===.===.......#'),  # 8  cobbled square (decorative path)
    _row('#....===.===.===.......#'),  # 9  shrine now free-standing — no enclosure
    _row('#....===.===.===.......#'),  #10
    _row('#=====================..'),  #11  Main east-west path — EAST EXIT (cols 22-23 open)
    _row('#=====================..'),  #12
    _row('#......................#'),  #13
    _row('#.~~~~.................#'),  #14  canal water (left bank)
    _row('#.~~~~.................#'),  #15
    _row('#.~~~~.................#'),  #16
    _row('#......................#'),  #17
    _row('#..####...........####.#'),  #18  Inn cols 3-6 (solid), Store cols 18-21 (solid)
    _row('#..####...........####.#'),  #19
    _row('#..####...........####.#'),  #20
    _row('#......................#'),  #21
    _row('#......................#'),  #22
    _row('########################'),  #23
]

# ──────────────────────────────────────────────────────────────────────────────
# INTERIORS (all 14×10)
# ──────────────────────────────────────────────────────────────────────────────

def _interior_base(w=14, h=10):
    """Empty room: wall border, path floor, south-center door."""
    grid = []
    for r in range(h):
        if r == 0 or r == h - 1:
            grid.append([TILE_WALL] * w)
        else:
            row = [TILE_WALL] + [TILE_PATH] * (w - 2) + [TILE_WALL]
            grid.append(row)
    # Door at south-center (bottom wall, gap of 2)
    dc = w // 2
    grid[h - 1][dc - 1] = TILE_PATH
    grid[h - 1][dc]     = TILE_PATH
    return grid


# Oden's house — simple cottage, warm
_HOME = _interior_base(14, 10)
# Furniture: table (impassable wall) at (6,3), bed at (2,3)-(3,3)
_HOME[3][6] = TILE_WALL   # table
_HOME[3][2] = TILE_WALL   # bed head
_HOME[3][3] = TILE_WALL   # bed body
_HOME[4][6] = TILE_WALL   # chair

# Courier Post — small office with counter
_COURIER = _interior_base(14, 10)
# Counter across cols 3-10 at row 4
for c in range(3, 11): _COURIER[4][c] = TILE_WALL
# Mailboxes on back wall (row 1)
for c in range(2, 12, 2): _COURIER[1][c] = TILE_WALL

# Edric's Study — books, desk, warmth
_EDRIC = _interior_base(14, 10)
# Bookshelves: cols 1 and 12, rows 1-3
for r in range(1, 4):
    _EDRIC[r][1]  = TILE_WALL
    _EDRIC[r][12] = TILE_WALL
# Desk at center-back
for c in range(5, 9): _EDRIC[2][c] = TILE_WALL
# Chair
_EDRIC[3][6] = TILE_WALL

# Dojo interior — open sparring floor with observation benches
_DOJO = _interior_base(16, 12)
# Benches on sides rows 2-9
for r in range(2, 10):
    _DOJO[r][1]  = TILE_WALL
    _DOJO[r][14] = TILE_WALL
# Raised platform (just wall tiles) at back rows 1-3, cols 5-10
for c in range(5, 11):
    _DOJO[1][c] = TILE_PATH  # already path but marking it


# ──────────────────────────────────────────────────────────────────────────────
# MASTER MAP REGISTRY
# ──────────────────────────────────────────────────────────────────────────────

def _dialog(static):
    """Wrap static string list in a callable."""
    return lambda: static


MAPS = {

    'cardhollow': {
        'grid':   _CH,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {
            'default':       (11, 8),   # center of town (just north of the path)
            'from_briar':    (2,  9),   # arrives from west road (clear of the exit tile)
            'from_home':     (3,  6),   # in front of Oden's house, clear of its door
            'from_courier':  (13, 6),   # in front of Courier Post
            'from_store':    (4,  17),  # in front of Store
        },
        'exits': [
            # West exits → Briar Road (require package first)
            {'tile': (0, 9),  'dest': 'briar_road', 'spawn': 'from_cardhollow',
             'req_flag': 'package_accepted'},
            {'tile': (0, 10), 'dest': 'briar_road', 'spawn': 'from_cardhollow',
             'req_flag': 'package_accepted'},
            # Building doors — trigger tiles are the floor squares in front of each
            # solid building; the black door panel renders on the building face behind.
            {'tile': (3, 5),  'dest': 'home',    'spawn': 'default', 'req_flag': None},
            {'tile': (13, 5), 'dest': 'courier', 'spawn': 'default', 'req_flag': None},
            {'tile': (4, 16), 'dest': 'store',   'spawn': 'default', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (8, 7),
                'name': 'Mira',
                'color': (200, 160, 120),
                'dialog': _dialog([
                    "Morning, Oden.",
                    "The shrine's been making that low noise again. Third time this week. Nobody knows why.",
                ]),
            },
        ],
        'enemies': [],
        'props': [
            {'tile': (10, 7), 'type': 'shrine'},   # free-standing, no enclosure
        ],
        # Solid wall footprints (collision) rendered as whole building sprites.
        'buildings': [
            {'sprite': 'cottage',       'origin': (2, 2),   'w': 3, 'h': 3},
            {'sprite': 'courier_post',  'origin': (12, 2),  'w': 4, 'h': 3},
            {'sprite': 'general_store', 'origin': (3, 13),  'w': 3, 'h': 3},
            {'sprite': 'cottage2',      'origin': (15, 13), 'w': 3, 'h': 3},
        ],
        'objects': [
            # Trees lining the village
            {'tile': (1, 1),  'asset': 'oak'},        {'tile': (7, 1),  'asset': 'pine_large'},
            {'tile': (19, 1), 'asset': 'pine_large'}, {'tile': (1, 6),  'asset': 'pine_small'},
            {'tile': (18, 6), 'asset': 'oak'},        {'tile': (1, 12), 'asset': 'pine_large'},
            {'tile': (10, 12),'asset': 'oak'},        {'tile': (19, 12),'asset': 'pine_small'},
            {'tile': (1, 20), 'asset': 'pine_large'}, {'tile': (10, 20),'asset': 'oak'},
            {'tile': (19, 20),'asset': 'pine_large'}, {'tile': (7, 18), 'asset': 'pine_small'},
            {'tile': (13, 18),'asset': 'oak'},
            # Bushes & flowers
            {'tile': (5, 6),  'asset': 'bush_flower'}, {'tile': (9, 6),  'asset': 'bush_plain'},
            {'tile': (17, 7), 'asset': 'bush_berry'},  {'tile': (3, 11), 'asset': 'bush_flower2'},
            {'tile': (18, 11),'asset': 'bush_plain'},  {'tile': (6, 16), 'asset': 'bush_flower'},
            {'tile': (15, 6), 'asset': 'flowers_blue'},{'tile': (8, 12), 'asset': 'flowers_purple'},
            # Furnishings
            {'tile': (2, 8),  'asset': 'signpost'},    {'tile': (14, 6), 'asset': 'lamp_post'},
            {'tile': (6, 8),  'asset': 'lamp_post'},    {'tile': (18, 19),'asset': 'chest_wood'},
            {'tile': (16, 16),'asset': 'barrel'},
        ],
        'blocking_msg': {
            # Message shown when player tries to exit west without the package
            'from_briar': "I should pick up that delivery first.",
        },
    },

    'briar_road': {
        'grid':   _ROAD,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 36,
        'music':  'dojo',
        'spawns': {
            # East end = Cardhollow side (high col); West end = Veilgate side (low col).
            'from_cardhollow': (_BR_W - 2, _BR_EAST_CEN),
            'from_veilgate':   (1,         _BR_WEST_CEN),
        },
        'exits': _BR_EXITS_TO_CARDHOLLOW + _BR_EXITS_TO_VEILGATE,
        'npcs': [
            {
                'tile': (_BR_W - 14, _path_center(_BR_W - 14)),
                'name': 'Tired Traveler',
                'color': (170, 150, 130),
                'dialog': _dialog([
                    "I swear I passed the same broken pillar three times heading west.",
                    "Roads have been strange lately. Watch yourself.",
                ]),
            },
        ],
        'enemies': [
            {
                # Tutorial road encounter — mid-route, gated by story flags.
                'waypoints': [(_BR_MID, _BR_MID_CEN), (_BR_MID - 1, _BR_MID_CEN),
                              (_BR_MID - 1, _BR_MID_CEN + 1), (_BR_MID, _BR_MID_CEN + 1)],
                'interval': 1.8,
                'story_trigger': True,   # only active if package_accepted & not misdeal_road_beaten
            },
        ],
        'props': [
            {'tile': (_BR_MID + 1, max(2, _BR_MID_CEN - 3)), 'type': 'shrine_ruined'},
        ],
        'objects': [
            # Signposts at each end of the route
            {'tile': (_BR_W - 3, _BR_EAST_CEN), 'asset': 'signpost'},
            {'tile': (3,          _BR_WEST_CEN), 'asset': 'signpost'},
            # Trees & brush dressing the mid-route clearing shoulders
            {'tile': (_BR_MID - 2, max(2, _BR_MID_CEN - 4)), 'asset': 'pine_large'},
            {'tile': (_BR_MID + 2, max(2, _BR_MID_CEN - 4)), 'asset': 'dead_tree'},
            {'tile': (_BR_MID - 1, min(_BR_H - 2, _BR_MID_CEN + 4)), 'asset': 'bush_flower'},
            {'tile': (_BR_MID + 2, min(_BR_H - 2, _BR_MID_CEN + 4)), 'asset': 'rock_mossy'},
            {'tile': (_BR_MID,     max(2, _BR_MID_CEN - 4)), 'asset': 'flowers_blue'},
        ],
        'blocking_msg': {},
    },

    'veilgate': {
        'grid':   _VG,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {
            'default':    (18, 11),  # east entrance, arrived from Briar (clear of exit)
            'from_briar': (18, 11),
            'from_edric': (3, 7),    # in front of Edric's, clear of its door
            'from_dojo':  (11, 7),   # in front of the Dojo
            'from_inn':   (4, 22),   # in front of the Inn
            'from_store': (19, 22),  # in front of the Store
        },
        'exits': [
            # East exits → Briar Road  (rows 11/12, in-bounds)
            {'tile': (22, 11), 'dest': 'briar_road', 'spawn': 'from_veilgate', 'req_flag': None},
            {'tile': (22, 12), 'dest': 'briar_road', 'spawn': 'from_veilgate', 'req_flag': None},
            # Building doors — trigger tiles are the floor squares in front of each
            # solid building; the black door panel renders on the building face behind.
            {'tile': (3, 6),  'dest': 'edric', 'spawn': 'default', 'req_flag': None},
            {'tile': (11, 6), 'dest': 'dojo',  'spawn': 'default', 'req_flag': None},
            {'tile': (4, 21), 'dest': 'inn',   'spawn': 'default', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (7, 7),
                'name': 'Townsfolk',
                'color': (160, 140, 190),
                'dialog': _dialog([
                    "Welcome to Veilgate, stranger.",
                    "Old Edric hasn't left his study in weeks. Something's got him stirred up.",
                ]),
            },
            {
                'tile': (16, 7),
                'name': 'Dojo Apprentice',
                'color': (140, 170, 150),
                'dialog': _dialog([
                    "The Dojo's open to challengers, if you've got a deck.",
                    "Master Hanzo doesn't go easy on anyone. Fair warning.",
                ]),
            },
        ],
        'enemies': [
            {
                'waypoints': [(16, 9), (17, 9), (17, 10), (16, 10)],
                'interval': 1.5,
                'story_trigger': False,  # always active (dojo training)
            },
        ],
        'props': [
            {'tile': (10, 9), 'type': 'shrine'},   # free-standing in the square
        ],
        'objects': [
            # Trees framing the old town
            {'tile': (1, 1),  'asset': 'pine_large'}, {'tile': (8, 1),  'asset': 'oak'},
            {'tile': (16, 1), 'asset': 'pine_large'}, {'tile': (20, 1), 'asset': 'pine_small'},
            {'tile': (1, 7),  'asset': 'oak'},        {'tile': (20, 7), 'asset': 'pine_large'},
            {'tile': (1, 21), 'asset': 'pine_large'}, {'tile': (20, 22),'asset': 'oak'},
            # Lamps around the cobbled square + market stall
            {'tile': (5, 8),  'asset': 'lamp_post'},  {'tile': (15, 8), 'asset': 'lamp_post'},
            {'tile': (5, 10), 'asset': 'lamp_post'},  {'tile': (15, 10),'asset': 'lamp_post'},
            {'tile': (8, 7),  'asset': 'market_stall'},
            # Bushes / flowers
            {'tile': (2, 7),  'asset': 'bush_flower'}, {'tile': (19, 13),'asset': 'bush_berry'},
            {'tile': (7, 13), 'asset': 'flowers_purple'},
            # Store goods + signpost at the east gate
            {'tile': (16, 19),'asset': 'crate'},      {'tile': (16, 20),'asset': 'barrel'},
            {'tile': (20, 11),'asset': 'signpost'},
        ],
        'blocking_msg': {},
    },

    # ── Interiors ────────────────────────────────────────────────────────────

    'home': {
        'grid':   _HOME,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {'default': (7, 7)},
        'exits': [
            {'tile': (6, 9), 'dest': 'cardhollow', 'spawn': 'from_home', 'req_flag': None},
            {'tile': (7, 9), 'dest': 'cardhollow', 'spawn': 'from_home', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (3, 5),
                'name': 'Oden\'s Mother',
                'color': (200, 160, 140),
                'dialog': _dialog([
                    "Be careful on the Briar Road, Oden.",
                    "And come back before dark. I mean it.",
                ]),
            },
        ],
        'enemies': [], 'props': [], 'blocking_msg': {},
    },

    'courier': {
        'grid':   _COURIER,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {'default': (7, 7)},
        'exits': [
            {'tile': (6, 9), 'dest': 'cardhollow', 'spawn': 'from_courier', 'req_flag': None},
            {'tile': (7, 9), 'dest': 'cardhollow', 'spawn': 'from_courier', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (7, 3),
                'name': 'Courier Master',
                'color': (140, 165, 205),
                'dialog': lambda: [
                    "Ah, Oden. Sealed delivery for Veilgate. Someone out west, near the old quarter.",
                    "Don't open it. Don't read the seal. Don't drop it. Take the Briar Road.",
                    "And be back before dark. I mean it this time.",
                ] if not story.get('package_accepted') else (
                    ["Safe delivery. Well done."] if story.get('received_deck')
                    else ["Well? That package won't walk itself to Veilgate."]
                ),
            },
        ],
        'enemies': [], 'props': [], 'blocking_msg': {},
    },

    'store': {
        'grid':   _interior_base(14, 10),
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {'default': (7, 7)},
        'exits': [
            {'tile': (6, 9), 'dest': 'cardhollow', 'spawn': 'from_store', 'req_flag': None},
            {'tile': (7, 9), 'dest': 'cardhollow', 'spawn': 'from_store', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (7, 3),
                'name': 'Shopkeeper',
                'color': (160, 180, 120),
                'dialog': _dialog(["Not much in stock, I'm afraid. Roads have been unreliable."]),
            },
        ],
        'enemies': [], 'props': [], 'blocking_msg': {},
    },

    'edric': {
        'grid':   _EDRIC,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {'default': (7, 7)},
        'exits': [
            {'tile': (6, 9), 'dest': 'veilgate', 'spawn': 'from_edric', 'req_flag': None},
            {'tile': (7, 9), 'dest': 'veilgate', 'spawn': 'from_edric', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (7, 3),
                'name': 'Edric',
                'color': (180, 170, 210),
                'dialog': lambda: [
                    "You're the courier. I can tell by the look — young, road-worn, slightly alarmed.",
                    "And you opened the package. That's all right. The cards chose to be opened.",
                    "Sit down. I'll explain what they are. Or — more accurately — what you are.",
                    "The blank card you found. Don't pretend you didn't find it. I've been waiting for someone to pick that thing up for eleven years.",
                ] if not story.get('received_deck') else (
                    ["I've said what needed saying. The rest is yours to learn."]
                    if not story.get('saw_smoke') else
                    ["Go. Something is wrong at home. I can feel it in the cards."]
                ),
            },
        ],
        'enemies': [], 'props': [], 'blocking_msg': {},
    },

    'dojo': {
        'grid':   _DOJO,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {'default': (8, 9)},
        'exits': [
            {'tile': (7, 11), 'dest': 'veilgate', 'spawn': 'from_dojo', 'req_flag': None},
            {'tile': (8, 11), 'dest': 'veilgate', 'spawn': 'from_dojo', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (8, 2),
                'name': 'Sage Hanzo',
                'color': (180, 140, 220),
                'dialog': _dialog([
                    "Welcome to the Dueling Hall, Oden. Step onto the mat when you're ready.",
                    "Defeat the training Misdeal and your deck will be sharper for it.",
                ]),
            },
        ],
        'enemies': [
            {'waypoints': [(8, 6), (9, 6)], 'interval': 1.0, 'story_trigger': False},
        ],
        'props': [], 'blocking_msg': {},
    },

    'inn': {
        'grid':   _interior_base(14, 10),
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {'default': (7, 7)},
        'exits': [
            {'tile': (6, 9), 'dest': 'veilgate', 'spawn': 'from_inn', 'req_flag': None},
            {'tile': (7, 9), 'dest': 'veilgate', 'spawn': 'from_inn', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (7, 3),
                'name': 'Innkeeper',
                'color': (190, 155, 120),
                'dialog': _dialog(["Room and board if you need it. Cards accepted."]),
            },
        ],
        'enemies': [], 'props': [], 'blocking_msg': {},
    },
}
