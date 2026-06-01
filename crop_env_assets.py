#!/usr/bin/env python3
"""
Crop generated asset sheets into individual sprites.

- Keys out the magenta background (-> transparent).
- Finds each sprite as a connected blob (detection on a 4x-downsampled mask for
  speed), then CROPS the full-resolution image to that blob's tight alpha bbox.
- NEVER resizes/scales — crop only. (User refines in Photoshop as needed.)
- Names sprites by reading order, zipped against the known per-sheet layout.

Usage: python3 crop_env_assets.py
"""
from __future__ import annotations
import os
from pathlib import Path
import numpy as np
from PIL import Image

BASE = Path(__file__).parent
SRC  = BASE / 'assets' / 'generated_env'
OUT  = BASE / 'assets' / 'env'

DOWN = 4          # detection downsample factor
MIN_AREA = 40     # min component area in downsampled px

# Expected sprite names in reading order (top→bottom rows, left→right within row).
LAYOUTS: dict[str, dict] = {
    'objects_nature': {'folder': 'objects', 'names': [
        'pine_small', 'pine_large', 'oak', 'dead_tree',
        'bush_plain', 'bush_berry', 'bush_flower', 'bush_flower2',
        'rock_small', 'rock_cluster', 'boulder', 'rock_mossy',
        'stump', 'flowers_blue', 'flowers_purple', 'crystal_blue', 'crystal_purple']},
    'objects_props': {'folder': 'objects', 'names': [
        'signpost', 'sign_flat', 'fence', 'fence_post',
        'lamp_post', 'lantern_hanging', 'chest_wood', 'chest_gold',
        'barrel', 'crate', 'shrine', 'shrine_ruined', 'market_stall']},
    'tiles_overworld': {'folder': 'tiles', 'names': [
        'grass1', 'grass2', 'grass3',
        'dirt_path', 'cobblestone', 'packed_earth',
        'water', 'stone1', 'stone2']},
    'tiles_interior': {'folder': 'tiles', 'names': [
        'wood_floor1', 'wood_floor2', 'crest_floor', 'stone_floor', 'tatami_floor',
        'wall1', 'wall2', 'wall_crest', 'wall3', 'wall4']},
    'npcs_cardhollow': {'folder': 'npcs', 'names': [
        'mira_nw', 'mira_sw', 'courier_nw', 'courier_sw',
        'mother_nw', 'mother_sw', 'shopkeeper_nw', 'shopkeeper_sw']},
    'npcs_veilgate': {'folder': 'npcs', 'names': [
        'edric_nw', 'edric_sw', 'hanzo_nw', 'hanzo_sw',
        'townsfolk_nw', 'townsfolk_sw', 'apprentice_nw', 'apprentice_sw',
        'traveler_nw', 'traveler_sw']},
    'buildings_cardhollow': {'folder': 'buildings', 'names': [
        'cottage', 'courier_post', 'general_store', 'cottage2']},
    'buildings_veilgate': {'folder': 'buildings', 'names': [
        'scholar_house', 'dojo_hall', 'inn', 'shop']},
}


def _magenta_mask(arr: np.ndarray) -> np.ndarray:
    """True where pixel is the magenta key background (used for blob detection)."""
    r, g, b = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    return (r > 170) & (b > 170) & (g < 110)


def _dilate(mask: np.ndarray, iters: int = 1) -> np.ndarray:
    m = mask.copy()
    for _ in range(iters):
        d = m.copy()
        d[:-1, :] |= m[1:, :]; d[1:, :] |= m[:-1, :]
        d[:, :-1] |= m[:, 1:]; d[:, 1:] |= m[:, :-1]
        m = d
    return m


def _dekey(arr: np.ndarray) -> np.ndarray:
    """Remove magenta background AND the pink anti-aliased halo.

    1. Hard-key the (near-pure) magenta background -> transparent.
    2. Dilate that mask into a 2px edge RING, then on the ring neutralise the
       magenta cast: strongly-magenta fringe pixels go fully transparent, mild
       ones get their R/B pulled down to G (despill). Interior purples are
       untouched because they're not adjacent to the keyed background.
    """
    a = arr.copy()
    R = a[..., 0].astype(np.int16)
    G = a[..., 1].astype(np.int16)
    B = a[..., 2].astype(np.int16)
    cast = np.minimum(R, B) - G               # how magenta a pixel is

    bg = (R > 200) & (B > 200) & (G < 70)      # near-pure background
    a[bg, 3] = 0

    ring = _dilate(bg, 2) & (~bg) & (a[..., 3] > 0)
    pink = ring & (R > G + 8) & (B > G + 8)

    # Strong halo -> transparent; mild halo -> despill (pull R,B toward G)
    drop = pink & (cast > 38)
    desp = pink & (cast <= 38)
    a[drop, 3] = 0
    a[..., 0] = np.where(desp, np.minimum(R, G + 6), a[..., 0]).astype(np.uint8)
    a[..., 2] = np.where(desp, np.minimum(B, G + 6), a[..., 2]).astype(np.uint8)
    return a


def _label(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """8-connectivity connected components via stack flood fill (numpy mask)."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    cur = 0
    nbrs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for sy in range(h):
        for sx in range(w):
            if mask[sy, sx] and labels[sy, sx] == 0:
                cur += 1
                stack = [(sy, sx)]
                labels[sy, sx] = cur
                while stack:
                    y, x = stack.pop()
                    for dy, dx in nbrs:
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = cur
                            stack.append((ny, nx))
    return labels, cur


def _reading_order(boxes: list) -> list:
    """Sort (x0,y0,x1,y1) blobs top→bottom in row bands, then left→right."""
    if not boxes:
        return boxes
    heights = [b[3] - b[1] for b in boxes]
    band = max(8, int(np.median(heights) * 0.5))
    boxes = sorted(boxes, key=lambda b: b[1])           # by top
    rows, cur, cur_y = [], [], None
    for b in boxes:
        if cur_y is None or b[1] - cur_y <= band:
            cur.append(b); cur_y = b[1] if cur_y is None else cur_y
        else:
            rows.append(cur); cur = [b]; cur_y = b[1]
    if cur:
        rows.append(cur)
    out = []
    for row in rows:
        out.extend(sorted(row, key=lambda b: b[0]))
    return out


def process(sheet: str, info: dict):
    path = SRC / f'{sheet}.png'
    if not path.exists():
        print(f'  [skip] {sheet} (missing)'); return
    img = Image.open(path).convert('RGBA')
    arr = np.array(img)
    mag = _magenta_mask(arr)
    fg  = ~mag

    # Detection on a downsampled mask
    small = fg[::DOWN, ::DOWN]
    labels, n = _label(small)

    boxes = []
    for i in range(1, n + 1):
        ys, xs = np.where(labels == i)
        if len(ys) < MIN_AREA:
            continue
        # back to full-res coords (with a small margin)
        x0 = max(0, xs.min() * DOWN - DOWN)
        y0 = max(0, ys.min() * DOWN - DOWN)
        x1 = min(arr.shape[1], (xs.max() + 1) * DOWN + DOWN)
        y1 = min(arr.shape[0], (ys.max() + 1) * DOWN + DOWN)
        boxes.append((x0, y0, x1, y1))

    boxes = _reading_order(boxes)

    # Build a transparent (magenta-keyed + de-fringed) full image once
    keyed_img = Image.fromarray(_dekey(arr), 'RGBA')

    out_dir = OUT / info['folder']
    out_dir.mkdir(parents=True, exist_ok=True)
    names = info['names']

    print(f'  {sheet}: {len(boxes)} blobs (expected {len(names)})')
    saved = 0
    for idx, (x0, y0, x1, y1) in enumerate(boxes):
        crop = keyed_img.crop((x0, y0, x1, y1))
        # Tight-trim to exact alpha bbox (crop only, no resize)
        bbox = crop.getbbox()
        if bbox:
            crop = crop.crop(bbox)
        name = names[idx] if idx < len(names) else f'{sheet}_{idx:02d}'
        crop.save(out_dir / f'{name}.png')
        saved += 1
    print(f'    -> saved {saved} to {out_dir}')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for sheet, info in LAYOUTS.items():
        process(sheet, info)
    print('Done.')


if __name__ == '__main__':
    main()
