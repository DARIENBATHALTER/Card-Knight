#!/usr/bin/env python3
"""
Generate a 6-frame Misdeal defeat explosion spritesheet via GPT-image-2.

Layout: 1536x1024 → 3×2 grid, each frame 512×512px.
Saved to assets/fx/misdeal_explosion/ as explosion1-6.png.
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
OUT_DIR = BASE / 'assets' / 'fx' / 'misdeal_explosion'
OUT_DIR.mkdir(parents=True, exist_ok=True)

REF_PATHS = [
    BASE / 'CardKnight Concept Art' / 'b7fa6662-0df0-4c3e-a037-3e10fa88bb3b.png',
]

client = OpenAI(api_key=API_KEY)

PROMPT = """\
Pixel art EXPLOSION ANIMATION SPRITESHEET — 6 frames arranged in a 3-column × 2-row grid
(each cell exactly 512×512 pixels). Solid bright MAGENTA (#FF00FF) background throughout —
do NOT use transparency, alpha channel, or checkerboard pattern. No borders, no labels.

Style: SNES/GBA pixel art — clean black outlines, limited bright palette, no anti-aliasing.
Theme: a magical playing-card enemy (Misdeal) being defeated — an explosion of glowing \
playing cards, magical energy, sparkles, and colourful light.

Frame 1 (top-left):     FLASH — small tight burst of white-gold light, just starting
Frame 2 (top-centre):   EXPAND — ring of blue-gold energy expands outward, card suits \
(♠ ♥ ♦ ♣) visible in the burst, bright centre
Frame 3 (top-right):    PEAK — maximum size explosion, playing cards and card fragments \
flying outward in all directions, rainbow sparks at the edges, very dramatic
Frame 4 (bottom-left):  DISSIPATE — explosion shrinking, card fragments tumbling and fading, \
smoke wisps, dimming colours
Frame 5 (bottom-centre):EMBERS — only sparks and tiny card fragments remain, fading out, \
scattered glowing dots on magenta
Frame 6 (bottom-right): BLANK — solid MAGENTA (#FF00FF) only, no explosion content

Each frame should be centred in its 512×512 cell. The explosion grows from frame 1 to 3, \
then shrinks and fades from 4 to 6. Make it feel satisfying and magical.
"""


def main():
    ref_handles = [open(p, 'rb') for p in REF_PATHS if p.exists()]
    print(f'Generating 6-frame Misdeal explosion sheet…')
    try:
        result = client.images.edit(
            model='gpt-image-2',
            image=ref_handles,
            prompt=PROMPT,
            size='1536x1024',
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
    sheet_path = OUT_DIR / 'explosion_sheet.png'
    sheet_path.write_bytes(img_bytes)
    print(f'Sheet saved → {sheet_path.name}')

    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    w, h = img.size   # 1536 × 1024
    fw, fh = w // 3, h // 2

    for frame_idx in range(6):
        col_i = frame_idx % 3
        row_i = frame_idx // 3
        region = img.crop((col_i * fw, row_i * fh, (col_i + 1) * fw, (row_i + 1) * fh))
        out = OUT_DIR / f'explosion{frame_idx + 1}.png'
        region.save(out)
        print(f'  explosion{frame_idx + 1}.png  ({fw}×{fh}px)')

    print('Done.')


if __name__ == '__main__':
    main()
