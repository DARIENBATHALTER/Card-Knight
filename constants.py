# ── Render / window ──────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720   # native window — no render surface scaling
FPS   = 60
TITLE = "Card Knight: Astral Arcana"

# ── Grid layout ───────────────────────────────────────────────────────────────
CARD_PANEL_W = 420   # left HUD / card panel width
PANEL_W   = 96
PANEL_H   = 64
GRID_COLS = 8        # 4 player cols + 4 enemy cols
GRID_ROWS = 4
GRID_X    = 436      # left panel (420) + 16px gap
GRID_Y    = 70       # thin top bar, then grid fills most of screen

# ── Colors ────────────────────────────────────────────────────────────────────
BLACK      = (  0,   0,   0)
WHITE      = (255, 255, 255)
GRAY       = (128, 128, 128)
DARK_GRAY  = ( 50,  50,  50)
RED        = (220,  50,  50)
DARK_RED   = (120,  20,  20)
BLUE       = ( 50, 100, 220)
DARK_BLUE  = ( 20,  60, 140)
GREEN      = ( 50, 200,  50)
DARK_GREEN = ( 20, 130,  20)
YELLOW     = (220, 200,  50)
ORANGE     = (230, 130,  20)
CYAN       = ( 50, 210, 230)
LIGHT_BLUE = (150, 200, 255)
PURPLE     = (160,  60, 230)
PINK       = (255, 140, 190)
BROWN      = (130,  80,  30)
ICE_BLUE   = (180, 230, 255)

# FF-style UI accent colors
UI_GOLD      = (195, 165,  65)
UI_DARK_GOLD = (110,  88,  28)
UI_NAVY      = (  8,  12,  40)
UI_FRAME     = ( 30,  22,  60)
UI_ACCENT    = ( 80,  55, 140)

# ── Panel owner colors ────────────────────────────────────────────────────────
PLAYER_PANEL = ( 32,  58, 148)
PLAYER_LIGHT = ( 50,  80, 180)
ENEMY_PANEL  = (148,  32,  32)
ENEMY_LIGHT  = (180,  52,  52)
PANEL_LINE   = ( 18,  18,  30)

# ── Elements ──────────────────────────────────────────────────────────────────
ELEM_NONE = 0
ELEM_FIRE = 1
ELEM_AQUA = 2
ELEM_ELEC = 3
ELEM_WOOD = 4

ELEM_COLOR = {
    ELEM_NONE: WHITE,
    ELEM_FIRE: ORANGE,
    ELEM_AQUA: CYAN,
    ELEM_ELEC: YELLOW,
    ELEM_WOOD: GREEN,
}
ELEM_NAME = {
    ELEM_NONE: "",
    ELEM_FIRE: "Fire",
    ELEM_AQUA: "Aqua",
    ELEM_ELEC: "Elec",
    ELEM_WOOD: "Wood",
}
ELEM_BEATS = {
    ELEM_FIRE: ELEM_WOOD,
    ELEM_AQUA: ELEM_FIRE,
    ELEM_ELEC: ELEM_AQUA,
    ELEM_WOOD: ELEM_ELEC,
}

# ── Panel types ───────────────────────────────────────────────────────────────
PNL_NORMAL  = "normal"
PNL_CRACKED = "cracked"
PNL_BROKEN  = "broken"
PNL_GRASS   = "grass"
PNL_ICE     = "ice"
PNL_LAVA    = "lava"
PNL_POISON  = "poison"
PNL_METAL   = "metal"
PNL_HOLE    = "hole"

# ── Panel owner ───────────────────────────────────────────────────────────────
OWN_PLAYER = 0
OWN_ENEMY  = 1

# ── Chip class ────────────────────────────────────────────────────────────────
CLS_STANDARD = "S"
CLS_MEGA     = "M"
CLS_GIGA     = "G"

# ── Battle timing ─────────────────────────────────────────────────────────────
CUSTOM_GAUGE_TIME = 9.0
BUSTER_DMG        = 9999   # DEV: one-hit kill
CHARGED_DMG       = 9999   # DEV: one-hit kill
CHARGE_TIME       = 1.5
BUSTER_COOL       = 0.5
CHIP_LOCK_TIME    = 0.10
PLAYER_IFRAMES    = 1.5

# ── Derived grid geometry ─────────────────────────────────────────────────────
GRID_BOTTOM = GRID_Y + GRID_ROWS * PANEL_H

# Row depth shading — row 0 (back) is darkest, row 3 (front) is full brightness
ROW_SHADE = [0.55, 0.70, 0.85, 1.00]

# ── HUD layout ───────────────────────────────────────────────────────────────
HUD_TOP_H    = 104   # top strip height
GAUGE_X      = 16
GAUGE_Y      = 80
GAUGE_W      = 326
GAUGE_H      = 16
CHIP_QUEUE_X = 16
CHIP_QUEUE_Y = 116

# ── HUD colors ────────────────────────────────────────────────────────────────
HP_GREEN  = ( 50, 210,  50)
HP_YELLOW = (220, 210,  30)
HP_RED    = (220,  50,  50)
GAUGE_CLR = (200, 160,  40)
HUD_BG    = (  8,  12,  40)
