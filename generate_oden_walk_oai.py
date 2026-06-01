#!/usr/bin/env python3
"""
Generate Oden cardinal direction walk animations via GPT-image-2 (images.edit).

Uses the character reference sheet + existing south walk frames as style/character
anchors so GPT-image-2 keeps Oden's look consistent across all directions.

Each direction → 3-frame horizontal spritesheet → sliced into {dir}1/2/3.png.
Ping-pong pattern [1,2,3,2] is already wired in sprite_manager.

Usage:
    python3 generate_oden_walk_oai.py              # all 4 cardinal directions
    python3 generate_oden_walk_oai.py north west   # specific directions
"""
from __future__ import annotations
import base64
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()

API_KEY = os.environ.get('OPENAI_API_KEY', '')
if not API_KEY:
    sys.exit('OPENAI_API_KEY not set in .env')

BASE    = Path(__file__).parent
SPRITES = BASE / 'assets' / 'sprites' / 'characters' / 'oden' / 'movement'

client = OpenAI(api_key=API_KEY)

# ── Reference images ──────────────────────────────────────────────────────────
# images.edit accepts file objects — up to 16 references for gpt-image-2.

REF_PATHS = [
    # Full character sheet: design, colours, equipment
    BASE / 'CardKnight Concept Art' / 'b7fa6662-0df0-4c3e-a037-3e10fa88bb3b.png',
    # Existing south walk frames: exact pixel style to match
    SPRITES / 'south' / 'south1.png',
    SPRITES / 'south' / 'south2.png',
    SPRITES / 'south' / 'south3.png',
]

# ── Prompts ───────────────────────────────────────────────────────────────────

_CHAR = (
    "the pixel art character Oden from the reference images: teenage male adventurer, "
    "spiky sandy-blonde hair, bright blue scarf/cloak with gold trim, white shirt under "
    "brown leather armour with gold buckles, red sash, dark navy trousers, heavy brown "
    "armoured boots, sword hilt over right shoulder, card pouch on belt. "
    "JRPG chibi proportions (~5 heads tall). SNES/GBA pixel art style — clean black "
    "outlines, limited colour palette, no anti-aliasing, no gradients."
)

_LAYOUT = (
    "Output a single image with a TRANSPARENT background. "
    "Arrange exactly THREE sprite frames side by side horizontally with no gaps, no borders, "
    "no labels and no background. Each frame should be the same size as the provided south "
    "walk reference sprites."
)

DIAGONALS = {'northeast', 'northwest', 'southeast', 'southwest'}

# Four foot-instruction variants cycled across copies so each generation
# explicitly describes a different leg posture for frames 1 and 3.
FOOT_VARIANTS = [
    ("RIGHT foot planted forward with knee bent, LEFT heel raised and trailing behind",
     "LEFT foot planted forward with knee bent, RIGHT heel raised and trailing behind"),
    ("LEFT foot planted forward with knee bent, RIGHT heel raised and trailing behind",
     "RIGHT foot planted forward with knee bent, LEFT heel raised and trailing behind"),
    ("weight fully on RIGHT foot — left leg swings forward, left knee lifting",
     "weight fully on LEFT foot — right leg swings forward, right knee lifting"),
    ("left leg extended far back, toe barely touching ground, RIGHT foot bearing all weight",
     "right leg extended far back, toe barely touching ground, LEFT foot bearing all weight"),
]

DIRECTION_PROMPTS: dict[str, str] = {
    'south': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} WALKING SOUTH (facing toward the viewer, "
        "full front view). "
        "Frame 1 (left): LEFT foot forward, body weight shifted left, cape swings left. "
        "Frame 2 (centre): NEUTRAL — feet together, standing upright. "
        "Frame 3 (right): RIGHT foot forward, body weight shifted right, cape swings right. "
        + _LAYOUT
    ),
    'north': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} WALKING NORTH (facing away from the viewer, "
        "back view — showing the back of the blue cloak, sword hilt over right shoulder, "
        "spiky hair visible from behind). "
        "Frame 1 (left): LEFT foot forward. "
        "Frame 2 (centre): NEUTRAL — feet together. "
        "Frame 3 (right): RIGHT foot forward. "
        + _LAYOUT
    ),
    'east': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} WALKING EAST (moving right, right-side "
        "profile — cape streams to the left behind him, sword hilt visible over right shoulder). "
        "Frame 1 (left): back leg (left) pushes off. "
        "Frame 2 (centre): NEUTRAL mid-stride. "
        "Frame 3 (right): front leg (right) lands. "
        + _LAYOUT
    ),
    'west': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} WALKING WEST (moving left, left-side "
        "profile — cape streams to the right behind him, sword hilt visible over left shoulder). "
        "Frame 1 (left): back leg (right) pushes off. "
        "Frame 2 (centre): NEUTRAL mid-stride. "
        "Frame 3 (right): front leg (left) lands. "
        + _LAYOUT
    ),
    # Diagonal base prompts — {F1} and {F3} are filled per-copy with FOOT_VARIANTS
    'southeast': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} moving DOWN and to the RIGHT "
        "(three-quarter front-right view — body faces toward the viewer, angled right, cape sweeping left). "
        "THREE FRAMES side by side. Frame 1 (left): {{F1}}. "
        "Frame 2 (centre): NEUTRAL — both feet flat on ground, standing tall. "
        "Frame 3 (right): {{F3}}. "
        "Frames 1 and 3 MUST show clearly different leg positions. "
        + _LAYOUT
    ),
    'southwest': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} moving DOWN and to the LEFT "
        "(three-quarter front-left view — body faces toward the viewer, angled left, cape sweeping right). "
        "THREE FRAMES side by side. Frame 1 (left): {{F1}}. "
        "Frame 2 (centre): NEUTRAL — both feet flat on ground, standing tall. "
        "Frame 3 (right): {{F3}}. "
        "Frames 1 and 3 MUST show clearly different leg positions. "
        + _LAYOUT
    ),
    'northeast': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} moving UP and to the RIGHT "
        "(three-quarter back-right view — back of cloak faces viewer, right side of face barely visible). "
        "THREE FRAMES side by side. Frame 1 (left): {{F1}}. "
        "Frame 2 (centre): NEUTRAL — both feet flat on ground, standing tall. "
        "Frame 3 (right): {{F3}}. "
        "Frames 1 and 3 MUST show clearly different leg positions. "
        + _LAYOUT
    ),
    'northwest': (
        f"Pixel art walk-cycle spritesheet of {_CHAR} moving UP and to the LEFT "
        "(three-quarter back-left view — back of cloak faces viewer, left side of face barely visible). "
        "THREE FRAMES side by side. Frame 1 (left): {{F1}}. "
        "Frame 2 (centre): NEUTRAL — both feet flat on ground, standing tall. "
        "Frame 3 (right): {{F3}}. "
        "Frames 1 and 3 MUST show clearly different leg positions. "
        + _LAYOUT
    ),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_refs() -> list:
    handles = []
    for p in REF_PATHS:
        if p.exists():
            handles.append(open(p, 'rb'))
        else:
            print(f'  [warn] reference not found: {p}')
    return handles


def _close_refs(handles: list) -> None:
    for h in handles:
        try:
            h.close()
        except Exception:
            pass


def _generate(direction: str, ref_handles: list, f1: str = '', f3: str = '') -> bytes | None:
    prompt = DIRECTION_PROMPTS[direction]
    if f1:
        prompt = prompt.replace('{F1}', f1).replace('{F3}', f3)
    print(f'  → Calling GPT-image-2...', flush=True)
    handles = [open(Path(h.name), 'rb') for h in ref_handles]
    try:
        result = client.images.edit(
            model='gpt-image-2',
            image=handles,
            prompt=prompt,
            size='1536x512',
            quality='high',
            n=1,
        )
    except Exception as e:
        print(f'  ERROR: {e}')
        return None
    finally:
        _close_refs(handles)

    raw = result.data[0].b64_json
    if raw:
        return base64.b64decode(raw)
    print('  No image data in response.')
    return None


def _slice(img_bytes: bytes, direction: str, out_dir: Path) -> None:
    img     = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    w, h    = img.size
    frame_w = w // 3
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        frame    = img.crop((i * frame_w, 0, (i + 1) * frame_w, h))
        out_path = out_dir / f'{direction}{i + 1}.png'
        frame.save(out_path)
        print(f'  Saved {out_path.name}  ({frame_w}×{h}px)')

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    directions = sys.argv[1:] if len(sys.argv) > 1 else list(DIRECTION_PROMPTS)
    invalid    = [d for d in directions if d not in DIRECTION_PROMPTS]
    if invalid:
        sys.exit(f'Unknown direction(s): {invalid}. Choose from: {list(DIRECTION_PROMPTS)}')

    print('Opening reference images...')
    ref_handles = _open_refs()
    print(f'  {len(ref_handles)}/{len(REF_PATHS)} references ready\n')

    for direction in directions:
        out_dir = SPRITES / direction
        out_dir.mkdir(parents=True, exist_ok=True)
        copies = len(FOOT_VARIANTS) if direction in DIAGONALS else 1

        for copy_n in range(copies):
            label = f'[{direction.upper()}{"" if copies == 1 else f" copy {copy_n+1}/{copies}"}]'
            print(label)
            f1, f3 = FOOT_VARIANTS[copy_n] if direction in DIAGONALS else ('', '')
            if f1:
                print(f'  F1: {f1[:60]}...')
                print(f'  F3: {f3[:60]}...')
            img_bytes = _generate(direction, ref_handles, f1, f3)
            if not img_bytes:
                print(f'  FAILED\n')
                continue

            suffix = f'_sheet_{copy_n+1}.png' if copies > 1 else '_sheet.png'
            sheet_path = out_dir / f'{direction}{suffix}'
            sheet_path.write_bytes(img_bytes)
            print(f'  Saved → {sheet_path.name}')
            if direction not in DIAGONALS:
                _slice(img_bytes, direction, out_dir)
            print()

    _close_refs(ref_handles)
    print('Done.')


if __name__ == '__main__':
    main()
