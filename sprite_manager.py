"""
Sprite and tile loading for the battle network game.
All images loaded via PIL (since pygame SDL2_image is unavailable on this build).
"""
from __future__ import annotations
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
        _load_oden_sprites()
    except Exception as e:
        print(f"[sprites] oden sprites load failed: {e}")
    try:
        _load_slime_sprites()
    except Exception as e:
        print(f"[sprites] slime sprites load failed: {e}")
    try:
        _load_fx_sprites()
    except Exception as e:
        print(f"[sprites] fx sprites load failed: {e}")
    try:
        _load_oden_poses()
    except Exception as e:
        print(f"[sprites] oden poses load failed: {e}")
    try:
        _load_chip_icons()
    except Exception as e:
        print(f"[sprites] chip icons load failed: {e}")
    try:
        _load_title_assets()
    except Exception as e:
        print(f"[sprites] title assets load failed: {e}")
    try:
        _load_battlefield()
    except Exception as e:
        print(f"[sprites] battlefield load failed: {e}")
    try:
        _load_oden_victory()
    except Exception as e:
        print(f"[sprites] oden victory load failed: {e}")
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
        C.ELEM_NONE:      _CACHE.get('card_gray'),
        C.ELEM_FIRE:      _CACHE.get('card_red'),
        C.ELEM_ICE:       _CACHE.get('card_blue'),
        C.ELEM_LIGHTNING: _CACHE.get('card_yellow'),
        C.ELEM_EARTH:     _CACHE.get('card_green'),
        C.ELEM_LIGHT:     _CACHE.get('card_gray'),
        C.ELEM_DARK:      _CACHE.get('card_dark'),
    }


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


# ── Oden sprites ─────────────────────────────────────────────────────────────

def _load_oden_sprites():
    oden_dir = _path('oden')

    # Battle idle / hurt fallback
    idle_p = os.path.join(oden_dir, 'idle.png')
    if os.path.exists(idle_p):
        img = _pil_to_surf(Image.open(idle_p).convert('RGBA'))
        _CACHE['oden_idle'] = [img]

    # Battle action sprite
    fight_p = os.path.join(oden_dir, 'fight.png')
    if os.path.exists(fight_p):
        _CACHE['oden_battle'] = [_pil_to_surf(Image.open(fight_p).convert('RGBA'))]

    # HUD face portrait
    portrait_p = os.path.join(oden_dir, 'portrait.png')
    if os.path.exists(portrait_p):
        _CACHE['oden_face'] = _pil_to_surf(Image.open(portrait_p).convert('RGBA'))

    # Overworld directional walk — 8 directions, ping-pong [1,2,3,2]
    mv_base = _path('sprites', 'characters', 'oden', 'movement')
    first_idle = None

    def _load_dir(direction: str) -> list:
        """Return [f1,f2,f3] surfaces for a direction, or [] if missing."""
        d_dir = os.path.join(mv_base, direction)
        frames = []
        for n in (1, 2, 3):
            p = os.path.join(d_dir, f'{direction}{n}.png')
            if os.path.exists(p):
                frames.append(_pil_to_surf(Image.open(p).convert('RGBA')))
        return frames if len(frames) == 3 else []

    def _hflip(frames: list) -> list:
        return [pygame.transform.flip(f, True, False) for f in frames]

    def _register(direction: str, frames: list) -> None:
        nonlocal first_idle
        f1, f2, f3 = frames
        _CACHE[f'oden_walk_{direction}'] = [f1, f2, f3, f2]
        _CACHE[f'oden_idle_{direction}'] = [f2]
        if first_idle is None:
            first_idle = f2

    # Cardinals — load directly; east mirrors west if no east frames exist
    for direction in ('south', 'north', 'west'):
        frames = _load_dir(direction)
        if frames:
            _register(direction, frames)
    east_frames = _load_dir('east')
    west_frames = _CACHE.get('oden_walk_west', [])
    if east_frames:
        _register('east', east_frames)
    elif len(west_frames) >= 3:
        _register('east', _hflip(west_frames[:3]))

    # Diagonals — load directly, fall back to mirroring the opposite diagonal
    mirror_pairs = [('southeast', 'southwest'), ('northeast', 'northwest')]
    for a, b in mirror_pairs:
        fa = _load_dir(a)
        fb = _load_dir(b)
        if fa:
            _register(a, fa)
        elif fb:
            _register(a, _hflip(fb))
        if fb:
            _register(b, fb)
        elif fa:
            _register(b, _hflip(fa))

    # Legacy keys used by battle / victory code
    if first_idle:
        _CACHE.setdefault('oden_idle', [first_idle])
    _CACHE.setdefault('oden_run', _CACHE.get('oden_walk_south', []))


# ── Slime enemy sprites ───────────────────────────────────────────────────────

def _load_slime_sprites():
    p = _path('sprites', 'enemies', 'slime_battle.png')
    if not os.path.exists(p):
        return
    img = Image.open(p).convert('RGBA')
    surf = _pil_to_surf(_scale(img, (96, 96)))
    _CACHE['gen_slime_idle'] = [surf]
    _CACHE['gen_slime_hurt'] = [_flash_white(surf)]


def _load_title_assets():
    title_dir = _path('title')
    if not os.path.isdir(title_dir):
        return

    # Title background (text + ornaments baked in; 1672×941 source → 1280×720)
    bg_p = os.path.join(title_dir, 'bg.png')
    if os.path.exists(bg_p):
        bg = Image.open(bg_p).convert('RGB')
        bg = bg.resize((C.SCREEN_W, C.SCREEN_H), Image.LANCZOS)
        _CACHE['title_bg'] = pygame.image.fromstring(
            bg.tobytes(), bg.size, 'RGB').convert()

    # Decorative card art (compass-rose tarot back) — still useful for the
    # save-file panel and other UI flourishes.
    card_p = os.path.join(title_dir, 'card.png')
    if os.path.exists(card_p):
        card = Image.open(card_p).convert('RGBA')
        h = 230
        w = int(card.width * h / card.height)
        _CACHE['title_card'] = _pil_to_surf(card.resize((w, h), Image.LANCZOS))

    # Bridgewalker Studios logo for the cold-open intro
    logo_p = os.path.join(title_dir, 'bridgewalker.png')
    if os.path.exists(logo_p):
        logo = Image.open(logo_p).convert('RGBA')
        # Source is already 1280×720 — fit to screen, preserve aspect just in case
        if logo.size != (C.SCREEN_W, C.SCREEN_H):
            tw = C.SCREEN_W
            th = int(logo.height * tw / logo.width)
            logo = logo.resize((tw, th), Image.LANCZOS)
        _CACHE['bridgewalker_logo'] = pygame.image.fromstring(
            logo.tobytes(), logo.size, 'RGBA').convert_alpha()


def _load_fx_sprites():
    """Load sprite-based FX sheets (explosions, etc.)."""
    fx_dir = _path('fx', 'misdeal_explosion')
    if not os.path.isdir(fx_dir):
        return
    frames = []
    for n in range(1, 10):
        p = os.path.join(fx_dir, f'explosion{n}.png')
        if os.path.exists(p):
            frames.append(_pil_to_surf(Image.open(p).convert('RGBA')))
        else:
            break
    if frames:
        _CACHE['fx_misdeal_explosion'] = frames
        print(f'[sprites] fx_misdeal_explosion: {len(frames)} frames')


def _load_oden_poses():
    """Load battle action poses from assets/oden/poses/, normalised to idle height."""
    poses_dir = _path('oden', 'poses')
    if not os.path.isdir(poses_dir):
        return
    # Target height: match the battle sprite (fight.png), fall back to idle.png
    fight_path = _path('oden', 'fight.png')
    idle_path  = _path('oden', 'idle.png')
    ref_path   = fight_path if os.path.exists(fight_path) else idle_path
    target_h   = Image.open(ref_path).height if os.path.exists(ref_path) else 192
    for pose in ('shoot', 'hurt', 'cast'):
        frames = []
        for n in (1, 2, 3):
            p = os.path.join(poses_dir, f'{pose}{n}.png')
            if os.path.exists(p):
                pil = Image.open(p).convert('RGBA')
                scale = target_h / pil.height
                new_w = max(1, int(pil.width * scale))
                pil   = pil.resize((new_w, target_h), Image.LANCZOS)
                frames.append(_pil_to_surf(pil))
        if frames:
            key = f'oden_pose_{pose}'
            _CACHE[key] = frames
            print(f'[sprites] {key}: {len(frames)} frames ({frames[0].get_size()})')

    # Charge poses: charge1.png (yellow phase), charge2.png (full-charge blue phase)
    for charge_name, cache_key in (('charge1', 'oden_pose_charge1'), ('charge2', 'oden_pose_charge2')):
        p = os.path.join(poses_dir, f'{charge_name}.png')
        if not os.path.exists(p) and charge_name == 'charge1':
            p = os.path.join(poses_dir, 'charge.png')   # fallback
        if os.path.exists(p):
            pil   = Image.open(p).convert('RGBA')
            scale = target_h / pil.height
            new_w = max(1, int(pil.width * scale))
            pil   = pil.resize((new_w, target_h), Image.LANCZOS)
            _CACHE[cache_key] = [_pil_to_surf(pil)]
            print(f'[sprites] {cache_key}: 1 frame ({new_w}×{target_h})')


def _load_chip_icons():
    """Load per-chip pixel art icons from assets/chips/icons/."""
    icons_dir = _path('chips', 'icons')
    if not os.path.isdir(icons_dir):
        return
    icons = {}
    for f in os.listdir(icons_dir):
        if f.endswith('.png') and not f.startswith('_'):
            name = f[:-4]   # strip .png
            surf = _pil_to_surf(Image.open(os.path.join(icons_dir, f)).convert('RGBA'))
            icons[name] = surf
    if icons:
        _CACHE['chip_icons'] = icons
        print(f'[sprites] chip_icons: {len(icons)} loaded')


def _load_oden_victory():
    """Full-body Oden victory pose for the end-of-battle screen."""
    p = _path('oden', 'fullbody.png')
    if not os.path.exists(p):
        return
    img = Image.open(p).convert('RGBA')
    # Scale to 560 px tall, preserving aspect (420×733 → 320×560)
    target_h = 560
    target_w = int(img.width * target_h / img.height)
    img = img.resize((target_w, target_h), Image.LANCZOS)
    _CACHE['oden_victory'] = pygame.image.fromstring(
        img.tobytes(), img.size, 'RGBA').convert_alpha()



# ── Battlefield: backgrounds, platform, and warped per-tile sprites ───────────

def _load_battlefield():
    import tile_warp
    bf_dir = _path('battlefields')
    if not os.path.isdir(bf_dir):
        return

    # Full-screen backgrounds (1280×720)
    for name in ('crystalcave', 'forest', 'temple', 'dojo'):
        p = os.path.join(bf_dir, f'{name}.png')
        if os.path.exists(p):
            bg = Image.open(p).convert('RGB')
            if bg.size != (C.SCREEN_W, C.SCREEN_H):
                bg = bg.resize((C.SCREEN_W, C.SCREEN_H), Image.LANCZOS)
            _CACHE[f'bf_bg_{name}'] = pygame.image.fromstring(
                bg.tobytes(), bg.size, 'RGB').convert()

    # Platform stone-block frame (RGBA, 1280×720, sits between bg and tiles)
    plat_p = os.path.join(bf_dir, 'platform.png')
    if os.path.exists(plat_p):
        plat = Image.open(plat_p).convert('RGBA')
        if plat.size != (C.SCREEN_W, C.SCREEN_H):
            plat = plat.resize((C.SCREEN_W, C.SCREEN_H), Image.LANCZOS)
        _CACHE['bf_platform'] = pygame.image.fromstring(
            plat.tobytes(), plat.size, 'RGBA').convert_alpha()

    # Pre-bake 32 warped tile surfaces per owner (player/enemy).
    # Keyed by (col, row, owner) → (surface, anchor_xy).
    tile_p_path = os.path.join(bf_dir, 'tilesprite_player.png')
    tile_e_path = os.path.join(bf_dir, 'tilesprite_enemy.png')
    if not (os.path.exists(tile_p_path) and os.path.exists(tile_e_path)):
        return
    tile_player_src = Image.open(tile_p_path).convert('RGBA')
    tile_enemy_src  = Image.open(tile_e_path).convert('RGBA')

    warped: dict = {}
    for owner_id, src_img in ((C.OWN_PLAYER, tile_player_src),
                              (C.OWN_ENEMY,  tile_enemy_src)):
        for row in range(C.GRID_ROWS):
            for col in range(C.GRID_COLS):
                quad = tile_warp.tile_quad(col, row)
                surf, anchor = tile_warp.bake_quad(src_img, quad)
                warped[(col, row, owner_id)] = (surf, anchor)
    _CACHE['bf_tiles'] = warped

