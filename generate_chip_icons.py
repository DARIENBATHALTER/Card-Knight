#!/usr/bin/env python3
"""
Generate pixel art chip icons via GPT-image-2.

Each unique chip name gets its own 64×64 icon saved to assets/chips/icons/.
Icons are generated 8-up on a 1536×512 sheet (two rows of 4 at ~192×256 each),
then sliced and scaled down to 64×64.

Usage:
    python3 generate_chip_icons.py           # all batches
    python3 generate_chip_icons.py weapons   # specific batch name
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
OUT_DIR = BASE / 'assets' / 'chips' / 'icons'
OUT_DIR.mkdir(parents=True, exist_ok=True)

REF_PATHS = [
    BASE / 'CardKnight Concept Art' / 'b7fa6662-0df0-4c3e-a037-3e10fa88bb3b.png',
]

client = OpenAI(api_key=API_KEY)

_STYLE = (
    "SNES/GBA pixel art icon style. Clean black 1-2px outline, limited bright colour palette, "
    "flat shading with 2-3 highlight colours, no anti-aliasing, no gradients. "
    "Each icon square, centred, NO card frame, NO decorative border around any icon — raw artwork only. "
    "Each icon may have its own thematic background colour (e.g. dark for shadow cards, fiery red for fire). "
    "Output a SINGLE image — a horizontal strip of exactly {n} icons side by side, "
    "no gaps, no labels, no dividers between icons."
)

# Each batch: (batch_name, [(chip_name, description), ...])
# Descriptions tell GPT what to draw for each icon.
BATCHES: list[tuple[str, list[tuple[str, str]]]] = [
    ('weapons', [
        ('Sword',     'a short straight sword with a simple crossguard, gleaming silver blade'),
        ('WideBlade', 'a wide broadsword blade so broad it fills the frame, double-edged'),
        ('Partisan',  'a long pole-lance with a leaf-shaped blade tip, wooden shaft'),
        ('Excalibur', 'a holy golden longsword with radiant light rays emanating from the blade'),
        ('Shortbow',  'a small recurve bow with an arrow nocked, simple wood construction'),
        ('Longbow',   'a tall longbow taller than the icon frame, arrow glowing blue at the tip'),
        ('Ignite',    'a small orange-red flame, single tongue of fire on a black background'),
        ('Scorch',    'three tongues of bright red-orange flame, larger and more intense than ignite'),
    ]),
    ('fire', [
        ('Immolate',    'a roaring pillar of fire filling the frame, intense crimson and gold flames, very dramatic'),
        ('Freeze',      'a pale blue ice shard / icicle crystal, sharp pointed tip'),
        ('Icicle',      'a cluster of three blue-white ice spikes arranged like a crown'),
        ('Blizzard',    'a swirling blizzard vortex of white and ice-blue snowflakes and wind'),
        ('Jolt',        'a single bright yellow lightning bolt zigzag'),
        ('Shock',       'two crossing yellow lightning bolts with a bright flash at the centre'),
        ('Electrocute', 'a storm cloud with multiple lightning bolts striking downward, very dramatic'),
        ('Gust',        'two curved wind streaks in pale teal/white, like a stylised gust'),
    ]),
    ('wind_earth', [
        ('Gale',        'a powerful horizontal wind burst with three strong streaks and leaf debris'),
        ('Tempest',     'a dark storm vortex with swirling winds and lightning, very dramatic'),
        ('Crack',       'a brown boulder with a crack splitting it, earth element'),
        ('Quake',       'a fissure crack in the ground with rocks flying upward, earth burst'),
        ('Landslide',   'a massive avalanche of brown rocks tumbling downward, very dramatic'),
        ('Sanctify',    'a golden sunburst cross / radiant holy light symbol'),
        ('Exorcise',    'a blazing white-gold star with rays of holy light on a dark background'),
        ('Absolution',  'two golden wings spread wide with a bright holy light at the centre, very dramatic'),
    ]),
    ('dark_heal', [
        ('Hex',       'a purple-black eye with a hex symbol, malevolent glow'),
        ('Curse',     'a dark purple skull with a cursed aura and swirling dark energy'),
        ('Oblivion',  'a void — deep black circle consuming everything, with dark purple wisps at the edge'),
        ('Heal',      'a small red cross / plus symbol with a green glow, simple first-aid'),
        ('Cure',      'a red cross with sparkle particles around it, slightly larger than Heal'),
        ('Recover',   'a large bright red cross with a golden glow and multiple sparkle stars'),
        ('Rejuvenate','a radiant golden-green heart surrounded by sparkles and leaf shapes, very powerful'),
        ('Antidote',  'a blue bottle / flask with a green leaf, potion icon'),
    ]),
    ('status_clear', [
        ('Voice',      'a musical note with a golden glow, clearing silence'),
        ('Wake',       'a bright sun / alarm bell icon with radiating light, waking up'),
        ('Stonebreak', 'a cracked grey stone shattering into pieces'),
        ('Return',     'a white dove silhouette flying upward with a small light aura'),
        ('Raise',      'a hand reaching upward from below with a green glow'),
        ('Revive',     'a golden phoenix silhouette rising with flame wings'),
        ('Resurrect',  'a brilliant golden phoenix fully spread, blazing — largest and most dramatic revival'),
        ('Toxin',      'a small green droplet / skull-and-crossbones minimal icon, mild poison'),
    ]),
    ('status', [
        ('Poison',    'a dark green bubbling vial overflowing with poison, more intense than toxin'),
        ('Mute',      'a musical note with a red X through it, small and grey'),
        ('Silence',   'an open mouth with a sound wave and a large red X through it'),
        ('Snooze',    'three small Zs floating above a pillow, sleep icon'),
        ('Slumber',   'a crescent moon with ZZZ text and deep blue dream cloud'),
        ('Petrify',   'a grey stone fist or figure mid-transformation to stone, cracking'),
        ('Entomb',    'a closed stone sarcophagus lid with hieroglyph cracks, ominous'),
        ('Delay',     'a clock face with hands frozen and a slow swirl around it'),
    ]),
    ('utility', [
        ('Halt',     'a clock with a red STOP hand / frozen snowflake merged, time stopped'),
        ('Quicken',  'a lightning bolt with speed streaks — yellow, energetic'),
        ('Allegro',  'two lightning bolts side by side with golden sparkles, party haste'),
        ('Protect',  'a blue kite shield with a gold cross emblem'),
        ('Teleport', 'a swirling purple-blue warp circle / portal'),
        ('Dash',     'a figure mid-sprint with speed blur lines, orange energy trail'),
    ]),
]


def _open_refs() -> list:
    return [open(p, 'rb') for p in REF_PATHS if p.exists()]


def _generate_batch(names: list[str], descs: list[str]) -> bytes | None:
    n      = len(names)
    # 4-up per row. Use 1536x512 for ≤4 icons (single row), 1536x1024 for 5-8 (two rows)
    if n <= 4:
        size   = '1536x512'
        layout = f'ONE ROW of exactly {n} icons side by side'
        cols, rows = n, 1
    else:
        size   = '1536x1024'
        layout = f'TWO ROWS of 4 icons each (row 1: icons 1-4 left-to-right, row 2: icons 5-8)'
        cols, rows = 4, 2

    style   = _STYLE.replace('{n}', str(n)).replace(
        'a horizontal strip of exactly {n} icons side by side',
        layout + ', no gaps, no labels, no borders, transparent background'
    )
    icon_list = '\n'.join(
        f'  Icon {i+1}: "{name}" — {desc}'
        for i, (name, desc) in enumerate(zip(names, descs))
    )
    prompt = (
        f"Generate a sheet of {n} pixel art icons in the style of SNES/GBA magic card "
        f"illustrations (like the bottom-right panel of the reference image). "
        f"IMPORTANT: NO card frame, NO card border, NO decorative frame of any kind around any icon — "
        f"just the raw artwork/illustration for each icon, nothing else. "
        f"Each icon: distinct, recognisable, 1-2px black outline, limited bright palette. "
        f"Each icon may have its own thematic background colour suited to its element/theme. "
        f"Layout: {layout}. No text, no numbers, no labels.\n\n"
        f"Icons to generate:\n{icon_list}\n\n"
        f"Make each icon clearly distinct and expressive of its theme. "
        f"More powerful cards in a tier (e.g., Immolate vs Ignite) should look bigger/more intense."
    )

    handles = _open_refs()
    print(f'  → Calling GPT-image-2 ({size}, {n} icons)…', flush=True)
    try:
        result = client.images.edit(
            model='gpt-image-2',
            image=handles,
            prompt=prompt,
            size=size,
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


def _slice_and_save(img_bytes: bytes, names: list[str], batch_name: str) -> None:
    img  = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    w, h = img.size
    n    = len(names)
    # Layout: ≤4 = single row; 5-8 = two rows of 4
    if n <= 4:
        cols, rows_n = n, 1
    else:
        cols, rows_n = 4, 2
    fw = w // cols
    fh = h // rows_n

    # Save full sheet
    sheet_path = OUT_DIR / f'_sheet_{batch_name}.png'
    img.save(sheet_path)
    print(f'  Sheet → {sheet_path.name}')

    for idx, name in enumerate(names):
        col_i = idx % cols
        row_i = idx // cols
        region = img.crop((col_i * fw, row_i * fh, (col_i + 1) * fw, (row_i + 1) * fh))
        # Scale to 64×64
        icon = region.resize((64, 64), Image.NEAREST)
        out  = OUT_DIR / f'{name.lower()}.png'
        icon.save(out)
        print(f'  {name:16s} → {out.name}')


def main():
    targets = sys.argv[1:] if sys.argv[1:] else [b[0] for b in BATCHES]
    batch_map = {b[0]: b for b in BATCHES}
    invalid = [t for t in targets if t not in batch_map]
    if invalid:
        sys.exit(f'Unknown batch(es): {invalid}. Choose from: {[b[0] for b in BATCHES]}')

    for batch_name in targets:
        _, chips = batch_map[batch_name]
        names = [c[0] for c in chips]
        descs = [c[1] for c in chips]
        print(f'\n[{batch_name.upper()}] — {len(chips)} icons: {names}')
        img_bytes = _generate_batch(names, descs)
        if not img_bytes:
            print('  FAILED\n')
            continue
        _slice_and_save(img_bytes, names, batch_name)

    print('\nDone.')


if __name__ == '__main__':
    main()
