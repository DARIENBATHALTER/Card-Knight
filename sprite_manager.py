"""
Sprite and tile loading for the battle network game.
All images loaded via PIL (since pygame SDL2_image is unavailable on this build).
"""
import os
import numpy as np
from PIL import Image
import pygame
import constants as C

_BASE = os.path.dirname(os.path.abspath(__file__))
_CACHE: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _path(*parts):
    return os.path.join(_BASE, 'assets', *parts)


def _pil_to_surf(pil_img: Image.Image) -> pygame.Surface:
    pil_img = pil_img.convert('RGBA')
    return pygame.image.fromstring(pil_img.tobytes(), pil_img.size, 'RGBA')


def _load_pil(rel: str) -> Image.Image:
    return Image.open(_path(rel)).convert('RGBA')


def _scale(img: Image.Image, size: tuple) -> Image.Image:
    return img.resize(size, Image.NEAREST)


def _remove_colorkey(img: Image.Image, tolerance: int = 35) -> Image.Image:
    """Make the background colour (top-left pixel) transparent using numpy."""
    arr = np.array(img.convert('RGBA'), dtype=np.int32)
    bg = arr[0, 0, :3]
    diff = np.abs(arr[:, :, :3] - bg)
    mask = (diff < tolerance).all(axis=2)
    arr[mask, 3] = 0
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def _extract(img: Image.Image, x, y, w, h, scale=None) -> pygame.Surface:
    region = img.crop((x, y, x + w, y + h))
    if scale:
        region = _scale(region, scale)
    return _pil_to_surf(region)


def _tint(surf: pygame.Surface, rgb: tuple, alpha: int = 150) -> pygame.Surface:
    """Return a copy of surf with a colour overlay blended in."""
    t = surf.copy()
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((*rgb, alpha))
    t.blit(overlay, (0, 0))
    return t


def _flash_white(surf: pygame.Surface) -> pygame.Surface:
    t = surf.copy()
    white = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    white.fill((255, 255, 255, 170))
    t.blit(white, (0, 0))
    return t


# ── Public API ────────────────────────────────────────────────────────────────

def init():
    """Load and cache every game sprite/tile. Call once after pygame.init()."""
    _CACHE.clear()
    try:
        _load_player_sprites()
    except Exception as e:
        print(f"[sprites] player load failed: {e}")
    try:
        _load_enemy_sprites()
    except Exception as e:
        print(f"[sprites] enemy load failed: {e}")
    try:
        _load_panel_tiles()
    except Exception as e:
        print(f"[sprites] tile load failed: {e}")
    try:
        _load_card_sprites()
    except Exception as e:
        print(f"[sprites] card load failed: {e}")
    try:
        _load_bg()
    except Exception as e:
        print(f"[sprites] bg load failed: {e}")
    try:
        _load_generated_cards()
    except Exception as e:
        print(f"[sprites] generated cards load failed: {e}")
    try:
        _load_generated_backgrounds()
    except Exception as e:
        print(f"[sprites] generated backgrounds load failed: {e}")
    try:
        _load_generated_player()
    except Exception as e:
        print(f"[sprites] generated player load failed: {e}")
    try:
        _load_generated_slime()
    except Exception as e:
        print(f"[sprites] generated slime load failed: {e}")
    try:
        _load_title_assets()
    except Exception as e:
        print(f"[sprites] title assets load failed: {e}")
    print("[sprites] init complete — loaded:", list(_CACHE.keys()))


def get(key: str, default=None):
    return _CACHE.get(key, default)


def get_frame(key: str, timer: float, fps: float = 6) -> pygame.Surface | None:
    """Return the current animation frame for key, cycling at fps."""
    frames = _CACHE.get(key)
    if not frames:
        return None
    idx = int(timer * fps) % len(frames)
    return frames[idx]


# ── Player (gumbot.png — 256×224, 32×32 cells, pink colorkey) ────────────────

def _load_player_sprites():
    raw = _remove_colorkey(_load_pil('sprites/gumbot.png'), tolerance=35)
    S = (76, 76)

    def f(col, row):
        return _extract(raw, (col + 1) * 32, (row + 1) * 32, 32, 32, S)

    _CACHE['player_idle']   = [f(0, 0), f(1, 0)]
    _CACHE['player_walk']   = [f(0, 0), f(1, 0), f(2, 0), f(3, 0)]
    _CACHE['player_attack'] = [f(0, 1), f(1, 1), f(0, 1)]
    _CACHE['player_hurt']   = [f(0, 2)]
    _CACHE['player_hurt_flash'] = [_flash_white(fr) for fr in _CACHE['player_idle']]


# ── Enemies ───────────────────────────────────────────────────────────────────

def _load_enemy_sprites():
    # ── robot_8dir.png: 210×255, 3×3 grid at 70×85 per frame ──────────────────
    r8 = _load_pil('sprites/robot_8dir.png')
    FW, FH = 70, 85

    def r8f(col, row, sc=(40, 40)):
        return _extract(r8, col * FW, row * FH, FW, FH, sc)

    MS = (80, 80)
    _CACHE['mettaur_hiding']  = [r8f(1, 0, MS)]
    _CACHE['mettaur_pop']     = [r8f(0, 1, MS), r8f(1, 1, MS)]
    _CACHE['mettaur_exposed'] = [r8f(1, 2, MS), r8f(0, 2, MS)]
    _CACHE['mettaur_shoot']   = [r8f(2, 2, MS)]

    # Spikey: orange-tinted version of the dome robot
    for state in ('hiding', 'pop', 'exposed', 'shoot'):
        src = _CACHE[f'mettaur_{state}']
        _CACHE[f'spikey_{state}'] = [_tint(fr, (255, 110, 20), 160) for fr in src]
    _CACHE['spikey_idle'] = _CACHE['spikey_exposed']

    # Bunny: gumbot with white-blue tint + long ear silhouette overlay
    gum = _remove_colorkey(_load_pil('sprites/gumbot.png'), tolerance=35)
    BS = (64, 64)

    def gf(col, row):
        return _extract(gum, col * 32, row * 32, 32, 32, BS)

    raw_hop = [gf(c, 0) for c in range(3)]
    _CACHE['bunny_hop']   = [_tint(fr, (240, 240, 255), 90) for fr in raw_hop]
    _CACHE['bunny_idle']  = _CACHE['bunny_hop']
    _CACHE['bunny_shoot'] = [_tint(gf(0, 1), (240, 240, 255), 90)]

    cannon = _load_pil('sprites/cannons.png')
    CANO_S = (108, 84)
    cano_frame = _extract(cannon, 0, 0, 143, 148, CANO_S)
    _CACHE['canodumb_idle']  = [cano_frame]
    _CACHE['canodumb_shoot'] = [cano_frame]


# ── Panel tiles (scifi_32x32.png — 1120×736, 32×32 tiles) ────────────────────

def _load_panel_tiles():
    tile_img = _load_pil('tiles/scifi_32x32.png')
    PW, PH = C.PANEL_W, C.PANEL_H

    def get_tile(tx: int, ty: int) -> pygame.Surface:
        t = tile_img.crop((tx * 32, ty * 32, (tx + 1) * 32, (ty + 1) * 32))
        t = _scale(t, (PW, PH))
        return _pil_to_surf(t)

    # Row 0, col 0 is dark (brightness≈53, variance≈139) — good base for tech panels
    base = get_tile(0, 0)
    # Row 5 col 0 has a slightly textured dark tile too (variance≈113)
    base_b = get_tile(0, 5)

    def make(surf, rgb, alpha):
        return _tint(surf, rgb, alpha)

    _CACHE['tile_player_normal']  = make(base,   ( 60, 100, 230), 130)
    _CACHE['tile_enemy_normal']   = make(base,   (230,  60,  60), 130)
    _CACHE['tile_player_cracked'] = make(base_b, ( 60, 100, 230),  70)
    _CACHE['tile_enemy_cracked']  = make(base_b, (230,  60,  60),  70)

    dark = pygame.Surface((PW, PH)); dark.fill((15, 15, 15))
    _CACHE['tile_broken'] = dark

    _CACHE['tile_grass']  = make(base, ( 30, 200,  50), 170)
    _CACHE['tile_ice']    = make(base, (150, 230, 255), 170)
    _CACHE['tile_lava']   = make(base, (255,  70,  10), 190)
    _CACHE['tile_poison'] = make(base, (180,  20, 210), 190)
    _CACHE['tile_metal']  = make(base, (190, 190, 200),  60)


# ── Card sprites (pixelcards.png — 720×613) ───────────────────────────────────
# Measured card x-starts: [14, 133, 250, 366, 479, 610]  width≈100  height≈130

def _load_card_sprites():
    cards_img = _load_pil('ui/pixelcards.png')
    # Card positions found by alpha boundary scan
    xs    = [14, 133, 250, 366, 479, 610]
    names = ['blue', 'red', 'gray', 'green', 'yellow', 'dark']
    CARD_S = (80, 98)

    for name, x in zip(names, xs):
        card = cards_img.crop((x, 0, x + 100, 130))
        card = _scale(card, CARD_S)
        _CACHE[f'card_{name}'] = _pil_to_surf(card)

    _CACHE['card_elem'] = {
        C.ELEM_NONE: _CACHE.get('card_gray'),
        C.ELEM_FIRE: _CACHE.get('card_red'),
        C.ELEM_AQUA: _CACHE.get('card_blue'),
        C.ELEM_ELEC: _CACHE.get('card_yellow'),
        C.ELEM_WOOD: _CACHE.get('card_green'),
    }


_GEN = os.path.join(_BASE, 'assets', 'generated')


def _gen_path(*parts):
    return os.path.join(_GEN, *parts)


# ── Background (scifi_bg.jpg) ─────────────────────────────────────────────────

def _load_bg():
    bg = Image.open(_path('tiles/scifi_bg.jpg')).convert('RGB')
    grid_w = C.GRID_COLS * C.PANEL_W
    grid_h = C.GRID_ROWS * C.PANEL_H
    bg = bg.resize((grid_w, grid_h), Image.LANCZOS)
    raw = bg.tobytes()
    surf = pygame.image.fromstring(raw, bg.size, 'RGB').convert()
    # Darken slightly so panels stand out
    dark = pygame.Surface(surf.get_size())
    dark.fill((0, 0, 0))
    dark.set_alpha(80)
    surf.blit(dark, (0, 0))
    _CACHE['bg_grid'] = surf


# ── Generated card art ────────────────────────────────────────────────────────

def _load_generated_cards():
    cards_dir = _gen_path('cards')
    if not os.path.isdir(cards_dir):
        return
    CARD_S = (80, 98)
    for fname in os.listdir(cards_dir):
        if not fname.endswith('.png'):
            continue
        name = fname[:-4]
        img = Image.open(os.path.join(cards_dir, fname)).convert('RGBA')
        img = _scale(img, CARD_S)
        _CACHE[f'gen_card_{name}'] = _pil_to_surf(img)


# ── Generated battle backgrounds ──────────────────────────────────────────────

def _load_generated_backgrounds():
    bg_dir = _gen_path('backgrounds')
    if not os.path.isdir(bg_dir):
        return
    grid_w = C.GRID_COLS * C.PANEL_W
    grid_h = C.GRID_ROWS * C.PANEL_H
    for fname in os.listdir(bg_dir):
        if not (fname.endswith('.jpg') or fname.endswith('.png')):
            continue
        name = fname.rsplit('.', 1)[0]
        bg = Image.open(os.path.join(bg_dir, fname)).convert('RGB')
        bg = bg.resize((grid_w, grid_h), Image.LANCZOS)
        surf = pygame.image.fromstring(bg.tobytes(), bg.size, 'RGB').convert()
        dark = pygame.Surface(surf.get_size())
        dark.fill((0, 0, 0))
        dark.set_alpha(60)
        surf.blit(dark, (0, 0))
        _CACHE[f'bg_{name}'] = surf


# ── Generated player sprite animations ───────────────────────────────────────

def _load_generated_player():
    anim_dir = _gen_path('player_anims')
    if not os.path.isdir(anim_dir):
        return
    anim_names = ('idle', 'walk', 'attack_buster', 'attack_sword', 'cast_magic', 'hurt')
    for anim in anim_names:
        frames = []
        for i in range(4):
            p = os.path.join(anim_dir, f'{anim}_f{i}.png')
            if os.path.exists(p):
                img = Image.open(p).convert('RGBA')
                frames.append(_pil_to_surf(img))   # full native size
        if frames:
            _CACHE[f'gen_player_{anim}'] = frames

    # Portrait — load at 96×96 for HUD display
    portrait_p = _gen_path('portraits', 'oden_portrait.png')
    if os.path.exists(portrait_p):
        portrait = Image.open(portrait_p).convert('RGBA')
        portrait = _scale(portrait, (96, 96))
        _CACHE['gen_portrait_player'] = _pil_to_surf(portrait)

    # Oden battle/overworld sprite — load from oden/ subfolder at native size
    oden_dir = _gen_path('oden')
    if os.path.isdir(oden_dir):
        ODEN_S = (130, 130)
        idle_p = os.path.join(oden_dir, 'idle.png')
        if os.path.exists(idle_p):
            img = _scale(Image.open(idle_p).convert('RGBA'), ODEN_S)
            _CACHE['oden_idle'] = [_pil_to_surf(img)]
            _CACHE['oden_hurt'] = [_pil_to_surf(img)]

        run_frames = []
        for i in (0, 2):
            p = os.path.join(oden_dir, f'run_f{i}.png')
            if os.path.exists(p):
                run_frames.append(_pil_to_surf(_scale(Image.open(p).convert('RGBA'), ODEN_S)))
        if run_frames:
            _CACHE['oden_run'] = run_frames   # f0 ↔ f2
            if 'oden_idle' not in _CACHE:
                _CACHE['oden_idle'] = [run_frames[0]]

        fight_p = os.path.join(oden_dir, 'fight.png')
        if os.path.exists(fight_p):
            img = _scale(Image.open(fight_p).convert('RGBA'), ODEN_S)
            _CACHE['oden_battle'] = [_pil_to_surf(img)]

        # Face portrait for battle HUD top strip — loaded at native size
        portrait_p2 = os.path.join(oden_dir, 'portrait.png')
        if os.path.exists(portrait_p2):
            _CACHE['oden_face'] = _pil_to_surf(Image.open(portrait_p2).convert('RGBA'))


# ── Generated slime enemy animations ─────────────────────────────────────────

def _load_title_assets():
    title_dir = _gen_path('title')
    if not os.path.isdir(title_dir):
        return
    bg_p = os.path.join(title_dir, 'bg.png')
    if os.path.exists(bg_p):
        bg = Image.open(bg_p).convert('RGB')
        bg = _scale(bg, (C.SCREEN_W, C.SCREEN_H))
        raw = bg.tobytes()
        _CACHE['title_bg'] = pygame.image.fromstring(raw, bg.size, 'RGB').convert()
    card_p = os.path.join(title_dir, 'card.png')
    if os.path.exists(card_p):
        card = Image.open(card_p).convert('RGBA')
        h = 230
        w = int(card.width * h / card.height)
        _CACHE['title_card'] = _pil_to_surf(_scale(card, (w, h)))


def _load_generated_slime():
    anim_dir = _gen_path('slime_anims')
    if not os.path.isdir(anim_dir):
        return
    S = (80, 80)
    for anim in ('idle', 'hurt'):
        frames = []
        for i in range(4):
            p = os.path.join(anim_dir, f'{anim}_f{i}.png')
            if os.path.exists(p):
                img = _remove_colorkey(Image.open(p).convert('RGBA'))
                frames.append(_pil_to_surf(_scale(img, S)))
        if frames:
            _CACHE[f'gen_slime_{anim}'] = frames
