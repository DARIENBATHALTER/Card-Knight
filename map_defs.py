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
    _row('#.###.......####..###'),  # 2  Oden's house cols 2-4, Courier cols 12-15
    _row('#.#.#.......#..#..#.#'),  # 3
    _row('#.#.#.......#..#..#.#'),  # 4
    _row('#....................#'),  # 5
    _row('#....................#'),  # 6
    _row('#........###.........#'),  # 7  Shrine enclosure (decorative only, passable inside)
    _row('#........#.#.........#'),  # 8
    _row('.===.====.#.====.====.'),  # 9  EXIT west (col 0 is open) — main path
    _row('.===.====.###====.===='),  #10  EXIT west continues
    _row('#....................#'),  #11
    _row('#....................#'),  #12
    _row('#..###.............##'),  #13  Store cols 3-5, Neighbor cols 18-19
    _row('#..#.#.............#.'),  #14
    _row('#..#.#.............#.'),  #15
    _row('#....................#'),  #16
    _row('#....................#'),  #17
    _row('#....................#'),  #18
    _row('#....................#'),  #19
    _row('#....................#'),  #20
    _row('######################'),  #21
]

# ──────────────────────────────────────────────────────────────────────────────
# THE BRIAR ROAD  22×48
# Long winding route, Cardhollow (south) → Veilgate (north).
# Path snakes from bottom-center to top-center with bends.
# Ruined shrine prop mid-route. Dense forest either side.
# ──────────────────────────────────────────────────────────────────────────────
def _road_row(path_cols, width=22):
    """Build a route row: wall border, dense bush (#) except on path cols."""
    row = []
    for c in range(width):
        if c == 0 or c == width - 1:
            row.append(TILE_WALL)
        elif c in path_cols:
            row.append(TILE_PATH)
        else:
            row.append(TILE_WALL)  # dense forest (impassable)
    return row


def _open_row(path_cols, width=22):
    """Like road_row but uses GRASS for non-path cells (clearing zones)."""
    row = []
    for c in range(width):
        if c == 0 or c == width - 1:
            row.append(TILE_WALL)
        elif c in path_cols:
            row.append(TILE_PATH)
        else:
            row.append(TILE_GRASS)
    return row


# path column sets at each row (snakes from bottom to top)
_P = {r: set() for r in range(48)}
# Bottom approach — wide entry from Cardhollow (south exit)
for r in range(44, 48): _P[r] = {9, 10, 11}
# Path body
for r in range(38, 44): _P[r] = {10, 11, 12}
for r in range(33, 38): _P[r] = {11, 12, 13}
# First bend westward
for r in range(29, 33): _P[r] = {10, 11, 12}
for r in range(25, 29): _P[r] = {8, 9, 10}
# Clearing (ruined shrine area)
for r in range(22, 25): _P[r] = {7, 8, 9, 10, 11}
# Continue northwest
for r in range(18, 22): _P[r] = {9, 10, 11}
for r in range(14, 18): _P[r] = {10, 11, 12}
# Final bend east toward Veilgate
for r in range(10, 14): _P[r] = {11, 12, 13}
for r in range(5, 10):  _P[r] = {10, 11, 12}
# Top approach
for r in range(0, 5):   _P[r] = {9, 10, 11}

_ROAD = []
for r in range(48):
    if r in (22, 23, 24):  # clearing around shrine
        _ROAD.append(_open_row(_P[r]))
    elif r == 0 or r == 47:
        row = [TILE_WALL] * 22
        for c in _P[r]: row[c] = TILE_PATH
        _ROAD.append(row)
    else:
        _ROAD.append(_road_row(_P[r]))

# ──────────────────────────────────────────────────────────────────────────────
# VEILGATE  24×22
# Older, more weathered than Cardhollow. Stone streets. East exit.
# Edric's house (NW), Dojo (center-N), Inn + Store (NE)
# Card shrine (left of center), canal water feature (south)
# ──────────────────────────────────────────────────────────────────────────────
_VG = [
    _row('########################'),  # 0
    _row('#......................#'),  # 1
    _row('#.####.......######..##'),  # 2  Edric cols 2-5, Dojo cols 9-14
    _row('#.#..#.......#....#..##'),  # 3
    _row('#.#..#.......#....#..##'),  # 4
    _row('#.#..#.......#....#..##'),  # 5
    _row('#......................#'),  # 6
    _row('#......................#'),  # 7
    _row('#....===.===.===.......#'),  # 8  Cobbled square
    _row('#....===.###.===.......#'),  # 9  Shrine in center of square
    _row('#....===.===.===.......#'),  #10
    _row('#====.====.====.======.'),  #11  Main east-west path — EAST EXIT (col 23 open)
    _row('#====.====.====.======.'),  #12
    _row('#......................#'),  #13
    _row('#.~~~~...............##'),  #14  Canal water (left bank)
    _row('#.~~~~...............##'),  #15
    _row('#.~~~~...............##'),  #16
    _row('#......................#'),  #17
    _row('#..####...........####.'),  #18  Inn cols 3-6, Store cols 18-21
    _row('#..#..#...........#..#.'),  #19
    _row('#..#..#...........#..#.'),  #20
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
            'default':       (11, 9),   # center of town
            'from_briar':    (1,  9),   # arrives from west road
            'from_home':     (3,  5),   # exiting Oden's house
            'from_courier':  (13, 5),   # exiting Courier Post
            'from_store':    (4,  16),  # exiting Store
            'from_neighbor': (18, 16),  # exiting Neighbor
        },
        'exits': [
            # West exits → Briar Road (require package first)
            {'tile': (0, 9),  'dest': 'briar_road', 'spawn': 'from_cardhollow',
             'req_flag': 'package_accepted'},
            {'tile': (0, 10), 'dest': 'briar_road', 'spawn': 'from_cardhollow',
             'req_flag': 'package_accepted'},
            # Building entries
            {'tile': (3, 4),  'dest': 'home',    'spawn': 'default', 'req_flag': None},
            {'tile': (13, 4), 'dest': 'courier', 'spawn': 'default', 'req_flag': None},
            {'tile': (4, 15), 'dest': 'store',   'spawn': 'default', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (7, 6),
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
            {'tile': (10, 9), 'type': 'shrine'},
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
            'from_cardhollow': (10, 45),  # enters from south
            'from_veilgate':   (10, 2),   # enters from north
        },
        'exits': [
            # North exit → Veilgate
            {'tile': (9, 0),  'dest': 'veilgate', 'spawn': 'from_briar', 'req_flag': None},
            {'tile': (10, 0), 'dest': 'veilgate', 'spawn': 'from_briar', 'req_flag': None},
            {'tile': (11, 0), 'dest': 'veilgate', 'spawn': 'from_briar', 'req_flag': None},
            # South exit → Cardhollow
            {'tile': (9, 47),  'dest': 'cardhollow', 'spawn': 'from_briar', 'req_flag': None},
            {'tile': (10, 47), 'dest': 'cardhollow', 'spawn': 'from_briar', 'req_flag': None},
            {'tile': (11, 47), 'dest': 'cardhollow', 'spawn': 'from_briar', 'req_flag': None},
        ],
        'npcs': [
            {
                'tile': (8, 30),
                'name': 'Tired Traveler',
                'color': (170, 150, 130),
                'dialog': _dialog([
                    "I swear I passed the same broken pillar three times heading east.",
                    "Roads have been strange lately. Watch yourself.",
                ]),
            },
        ],
        'enemies': [
            {
                # Tutorial road encounter — gated by story flags in overworld logic
                'waypoints': [(10, 25), (11, 25), (11, 26), (10, 26)],
                'interval': 1.8,
                'story_trigger': True,   # only active if package_accepted & not misdeal_road_beaten
            },
        ],
        'props': [
            {'tile': (8, 23), 'type': 'shrine_ruined'},
        ],
        'blocking_msg': {},
    },

    'veilgate': {
        'grid':   _VG,
        'tile_w': 48, 'tile_h': 24, 'wall_h': 30,
        'music':  'dojo',
        'spawns': {
            'default':    (21, 11),  # east entrance, arrived from Briar
            'from_briar': (21, 11),
            'from_edric': (4, 7),
            'from_dojo':  (12, 7),
            'from_inn':   (4, 22),
            'from_store': (19, 22),
        },
        'exits': [
            # East exits → Briar Road
            {'tile': (23, 11), 'dest': 'briar_road', 'spawn': 'from_veilgate', 'req_flag': None},
            {'tile': (23, 12), 'dest': 'briar_road', 'spawn': 'from_veilgate', 'req_flag': None},
            # Building entries
            {'tile': (4, 6),  'dest': 'edric', 'spawn': 'default', 'req_flag': None},
            {'tile': (12, 6), 'dest': 'dojo',  'spawn': 'default', 'req_flag': None},
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
                'tile': (18, 7),
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
                'waypoints': [(16, 8), (17, 8), (17, 9), (16, 9)],
                'interval': 1.5,
                'story_trigger': False,  # always active (dojo training)
            },
        ],
        'props': [
            {'tile': (9, 9), 'type': 'shrine'},
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
