#!/usr/bin/env python3
"""
Generate a high-res Oden battle idle sprite via GPT-image-2.

Generates at 1024×1024, then scales down to 512×512 and saves as:
  assets/oden/fight.png

The existing fight.png is backed up as fight_192.png first.
"""
from __future__ import annotations
import base64
import io
import os
import shutil
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
OUT_DIR = BASE / 'assets' / 'oden'
OUT_DIR.mkdir(parents=True, exist_ok=True)

REF_PATHS = [
    BASE / 'CardKnight Concept Art' / 'b7fa6662-0df0-4c3e-a037-3e10fa88bb3b.png',
    BASE / 'assets' / 'oden' / 'idle.png',
    BASE / 'assets' / 'oden' / 'fight.png',
]

client = OpenAI(api_key=API_KEY)

PROMPT = (
    "Pixel art battle idle sprite of Oden: teenage male adventurer, spiky sandy-blonde hair, "
    "bright blue scarf/cloak with gold trim, white shirt under brown leather armour "
    "with gold buckles, red sash, dark navy trousers, heavy brown armoured boots, "
    "sword hilt over right shoulder, card pouch on belt. "
    "JRPG chibi proportions (~5 heads tall). SNES/GBA pixel art — clean black outlines, "
    "limited colour palette, no anti-aliasing, no gradients. "
    "Pose: WIDE-PLANTED combat stance facing RIGHT — feet spread far apart, knees slightly bent, "
    "weight evenly distributed and rooted to the ground, body angled slightly forward in an "
    "aggressive ready position, arms held out slightly from the body as if braced for action, "
    "confident defiant expression. This is a stable power stance — NOT a relaxed walk or "
    "casual stand. Feet should be clearly wider than shoulder-width apart. "
    "Solid bright MAGENTA (#FF00FF) background — do NOT use transparency or checkerboard. "
    "Single frame, centred in the canvas. No borders, no labels, no other characters."
)


def main():
    fight_path = OUT_DIR / 'fight.png'
    backup_path = OUT_DIR / 'fight_192.png'

    # Back up existing sprite
    if fight_path.exists() and not backup_path.exists():
        shutil.copy(fight_path, backup_path)
        print(f'Backed up existing fight.png → fight_192.png')

    ref_handles = [open(p, 'rb') for p in REF_PATHS if p.exists()]
    print(f'Generating Oden battle sprite at 1024×1024…')
    try:
        result = client.images.edit(
            model='gpt-image-2',
            image=ref_handles,
            prompt=PROMPT,
            size='1024x1024',
            quality='high',
            n=1,
        )
    except Exception as e:
        print(f'ERROR: {e}')
        return
    finally:
        for h in ref_handles:
            try: h.close()
            except: pass

    raw = result.data[0].b64_json
    if not raw:
        print('No image data.')
        return

    img_bytes = base64.b64decode(raw)

    # Save full 1024×1024 sheet for reference
    sheet_path = OUT_DIR / 'fight_1024.png'
    sheet_path.write_bytes(img_bytes)
    print(f'Full sheet saved → {sheet_path.name}')

    # Keep 512×512 as Photoshop reference; game sprite is 192×192 to match originals
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    img.resize((512, 512), Image.LANCZOS).save(OUT_DIR / 'fight_512.png')
    img.resize((192, 192), Image.LANCZOS).save(fight_path)
    print(f'Saved fight_512.png (Photoshop reference) and fight.png at 192×192')
    print('Done.')


if __name__ == '__main__':
    main()
