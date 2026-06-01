#!/usr/bin/env python3
"""
Generate Oden cardinal direction walk animations via Nano Banana Pro
(gemini-3-pro-image-preview).

Each direction produces a horizontal 3-frame spritesheet which is sliced into
{dir}1.png / {dir}2.png / {dir}3.png — matching the ping-pong pattern already
wired in sprite_manager: [1, 2, 3, 2].

Usage:
    python3 generate_oden_walk.py              # all 4 directions
    python3 generate_oden_walk.py south north  # specific directions
"""
from __future__ import annotations
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types

load_dotenv()

API_KEY = os.environ.get('GOOGLE_IMAGE_API_KEY', '')
if not API_KEY:
    sys.exit('GOOGLE_IMAGE_API_KEY not set in .env')

BASE    = Path(__file__).parent
SPRITES = BASE / 'assets' / 'sprites' / 'characters' / 'oden' / 'movement'
MODEL   = 'gemini-3-pro-image-preview'

client = genai.Client(api_key=API_KEY)

# ── Reference images ──────────────────────────────────────────────────────────

REF_PATHS = [
    BASE / 'CardKnight Concept Art' / 'b7fa6662-0df0-4c3e-a037-3e10fa88bb3b.png',
    Path('/Users/darien/Desktop/Screenshots/Screenshot 2026-05-24 at 10.28.58 PM.png'),
    SPRITES / 'south' / 'south1.png',
    SPRITES / 'south' / 'south2.png',
    SPRITES / 'south' / 'south3.png',
]

# ── Prompts ───────────────────────────────────────────────────────────────────

_CHAR = (
    "a teenage male pixel art adventurer named Oden: spiky sandy-blonde hair, "
    "bright blue scarf/cloak with gold trim flowing behind him, white shirt under "
    "brown leather armour with gold buckles, red sash at waist, dark navy trousers, "
    "heavy brown armoured boots, sword hilt over right shoulder, card pouch on belt. "
    "JRPG chibi proportions (~5 heads tall). SNES/GBA pixel art style: clean black "
    "outlines, limited palette, no anti-aliasing."
)

_SHEET = (
    "Output a single PNG image with a TRANSPARENT background containing exactly THREE "
    "frames arranged side by side horizontally (no gaps, no labels, no grid lines). "
    "Match the pixel size of the provided south walk reference frames exactly."
)

DIRECTION_PROMPTS: dict[str, str] = {
    'south': (
        f"Pixel art walk cycle spritesheet of {_CHAR} WALKING SOUTH (facing toward the viewer, "
        "full front view). "
        "Frame 1: LEFT foot forward, weight shifted left, cape swings left. "
        "Frame 2: NEUTRAL — feet together, standing tall. "
        "Frame 3: RIGHT foot forward, weight shifted right, cape swings right. "
        + _SHEET
    ),
    'north': (
        f"Pixel art walk cycle spritesheet of {_CHAR} WALKING NORTH (facing away from viewer, "
        "showing back of cloak, sword hilt over right shoulder, hair from behind). "
        "Frame 1: LEFT foot forward. "
        "Frame 2: NEUTRAL — feet together. "
        "Frame 3: RIGHT foot forward. "
        + _SHEET
    ),
    'east': (
        f"Pixel art walk cycle spritesheet of {_CHAR} WALKING EAST (moving right, right-side "
        "profile, cape flowing left behind character). "
        "Frame 1: back leg (left) lifts off ground. "
        "Frame 2: NEUTRAL mid-stride. "
        "Frame 3: front leg (right) plants on ground. "
        + _SHEET
    ),
    'west': (
        f"Pixel art walk cycle spritesheet of {_CHAR} WALKING WEST (moving left, left-side "
        "profile, cape flowing right behind character). "
        "Frame 1: back leg (right) lifts off ground. "
        "Frame 2: NEUTRAL mid-stride. "
        "Frame 3: front leg (left) plants on ground. "
        + _SHEET
    ),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_refs() -> list:
    parts = []
    for p in REF_PATHS:
        if p.exists():
            parts.append(Image.open(p).convert('RGBA'))
        else:
            print(f'  [warn] reference not found: {p}')
    return parts


def _generate(direction: str, refs: list) -> bytes | None:
    contents = [DIRECTION_PROMPTS[direction]] + refs
    print(f'  → Calling Nano Banana Pro...', flush=True)
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
            ),
        )
    except Exception as e:
        print(f'  ERROR: {e}')
        return None

    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            return part.inline_data.data
    # Sometimes the model returns text with a refusal/explanation
    for part in resp.candidates[0].content.parts:
        if part.text:
            print(f'  Model response (no image): {part.text[:300]}')
    return None


def _slice(img_bytes: bytes, direction: str, out_dir: Path) -> bool:
    img     = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    w, h    = img.size
    frame_w = w // 3
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        frame    = img.crop((i * frame_w, 0, (i + 1) * frame_w, h))
        out_path = out_dir / f'{direction}{i + 1}.png'
        frame.save(out_path)
        print(f'  Saved {out_path.name}  ({frame_w}×{h}px)')
    return True

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    directions = sys.argv[1:] if len(sys.argv) > 1 else list(DIRECTION_PROMPTS)
    invalid    = [d for d in directions if d not in DIRECTION_PROMPTS]
    if invalid:
        sys.exit(f'Unknown direction(s): {invalid}. Choose from: {list(DIRECTION_PROMPTS)}')

    print('Loading reference images...')
    refs = _load_refs()
    print(f'  {len(refs)}/{len(REF_PATHS)} references loaded\n')

    for direction in directions:
        out_dir = SPRITES / direction
        print(f'[{direction.upper()}]')
        img_bytes = _generate(direction, refs)
        if not img_bytes:
            print(f'  FAILED — skipping {direction}\n')
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        sheet_path = out_dir / f'{direction}_sheet.png'
        sheet_path.write_bytes(img_bytes)
        print(f'  Spritesheet → {sheet_path.name}')
        _slice(img_bytes, direction, out_dir)
        print()

    print('Done.')


if __name__ == '__main__':
    main()
