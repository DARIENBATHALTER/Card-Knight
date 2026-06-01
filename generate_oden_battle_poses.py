#!/usr/bin/env python3
"""
Generate Oden battle-pose spritesheets via GPT-image-2.

Poses generated:
  shoot  — 2 frames: card-cocked wind-up → arm-extended release
  hurt   — 2 frames: initial impact stagger → further recoil
  cast   — 3 frames: card raised overhead → glowing → burst

Each pose is saved as a horizontal sheet (frames side by side) and then
sliced into individual PNGs under assets/oden/poses/.
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
OUT_DIR = BASE / 'assets' / 'oden' / 'poses'
OUT_DIR.mkdir(parents=True, exist_ok=True)

REF_PATHS = [
    BASE / 'CardKnight Concept Art' / 'b7fa6662-0df0-4c3e-a037-3e10fa88bb3b.png',
    BASE / 'assets' / 'oden' / 'idle.png',
    BASE / 'assets' / 'oden' / 'fight.png',
]

client = OpenAI(api_key=API_KEY)

_CHAR = (
    "the pixel art character Oden: teenage male adventurer, spiky sandy-blonde hair, "
    "bright blue scarf/cloak with gold trim, white shirt under brown leather armour "
    "with gold buckles, red sash, dark navy trousers, heavy brown armoured boots, "
    "sword hilt over right shoulder, card pouch on belt. "
    "JRPG chibi proportions (~5 heads tall). SNES/GBA pixel art — clean black outlines, "
    "limited colour palette, no anti-aliasing, no gradients. "
    "SOLID BRIGHT MAGENTA (#FF00FF) background — do NOT use transparency, alpha channel, "
    "or checkerboard pattern. Each frame same size as the reference battle idle sprite."
)

_LAYOUT_2 = (
    "Output a SINGLE 1024×1024 image split into TWO equal frames side by side (each 512×1024), "
    "no gap, no border, no label. Solid bright MAGENTA (#FF00FF) background."
)
_LAYOUT_3 = (
    "Output a SINGLE image: exactly THREE frames side by side, no gap, no border, no label. "
    "Solid bright MAGENTA (#FF00FF) background."
)

POSES = {
    'shoot': {
        'frames': 2,
        'size': '1024x1024',
        'prompt': (
            f"Pixel art battle spritesheet of {_CHAR} performing a card-throw attack. "
            "Facing RIGHT (toward enemies). "
            "Frame 1 (left): WIND-UP — weight on back foot, right arm drawn back holding a "
            "glowing playing card, body coiled, eyes focused. "
            "Frame 2 (right): RELEASE — body lunging forward, right arm fully extended and "
            "pointing right, card just left the fingers (card visible at fingertips or just "
            "beyond), dynamic forward lean, cape streaming behind. "
            + _LAYOUT_2
        ),
    },
    'hurt': {
        'frames': 2,
        'size': '1024x1024',
        'prompt': (
            f"Pixel art battle spritesheet of {_CHAR} taking damage. "
            "Facing RIGHT. "
            "Frame 1 (left): IMPACT — body snapping backwards from a hit, arms flung out "
            "wide, legs buckling, eyes wincing shut, cape whipping forward from the impact. "
            "Frame 2 (right): RECOIL — stumbling back, one knee slightly bent, one arm "
            "raised to shield face, grimacing in pain, body leaning far backwards. "
            + _LAYOUT_2
        ),
    },
    'cast': {
        'frames': 3,
        'size': '1536x512',
        'prompt': (
            f"Pixel art battle spritesheet of {_CHAR} casting a magic card. "
            "Facing RIGHT. "
            "Frame 1 (left): RAISE — both feet planted wide, right arm thrust upward holding "
            "a glowing card high overhead, left arm out for balance, determined expression. "
            "Frame 2 (centre): CHARGE — card blazing with intense magical light above his "
            "head, bright aura/sparkles radiating from it, body slightly crouching under the "
            "power, face lit from above by the glow. "
            "Frame 3 (right): BURST — card explodes in a starburst of light, Oden's arm "
            "snapping forward releasing the energy, magic particles and light rays streaming "
            "outward from his outstretched hand, triumphant pose. "
            + _LAYOUT_3
        ),
    },
}


def _open_refs() -> list:
    handles = []
    for p in REF_PATHS:
        if p.exists():
            handles.append(open(p, 'rb'))
        else:
            print(f'  [warn] ref not found: {p}')
    return handles


def _generate(pose: str, cfg: dict) -> bytes | None:
    handles = _open_refs()
    print(f'  → Calling GPT-image-2 ({cfg["size"]})…', flush=True)
    try:
        result = client.images.edit(
            model='gpt-image-2',
            image=handles,
            prompt=cfg['prompt'],
            size=cfg['size'],
            quality='high',
            n=1,
        )
    except Exception as e:
        print(f'  ERROR: {e}')
        return None
    finally:
        for h in handles:
            try: h.close()
            except: pass
    raw = result.data[0].b64_json
    return base64.b64decode(raw) if raw else None


def _slice(img_bytes: bytes, pose: str, n_frames: int) -> None:
    img     = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    w, h    = img.size
    fw      = w // n_frames
    for i in range(n_frames):
        frame    = img.crop((i * fw, 0, (i + 1) * fw, h))
        out_path = OUT_DIR / f'{pose}{i + 1}.png'
        frame.save(out_path)
        print(f'  Saved {out_path.name}  ({fw}×{h}px)')


def main():
    poses = sys.argv[1:] if sys.argv[1:] else list(POSES)
    invalid = [p for p in poses if p not in POSES]
    if invalid:
        sys.exit(f'Unknown pose(s): {invalid}. Choose from: {list(POSES)}')

    for pose in poses:
        cfg = POSES[pose]
        print(f'\n[{pose.upper()}] ({cfg["frames"]} frames)')
        img_bytes = _generate(pose, cfg)
        if not img_bytes:
            print('  FAILED')
            continue
        sheet_path = OUT_DIR / f'{pose}_sheet.png'
        sheet_path.write_bytes(img_bytes)
        print(f'  Sheet → {sheet_path.name}')
        _slice(img_bytes, pose, cfg['frames'])

    print('\nDone.')


if __name__ == '__main__':
    main()
