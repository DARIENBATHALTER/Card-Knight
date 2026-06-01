#!/usr/bin/env python3
"""
Generate environment + NPC assets for Card Knight via GPT-image-2 (images.edit).

Sheet-based: each "job" produces ONE image containing many sprites/tiles arranged
on a solid MAGENTA (255,0,255) background for easy keying. We crop per-sprite in a
separate step (crop_env_assets.py) — never resizing, only cropping.

Style anchors: the five HD-2D / Octopath-style reference images on the Desktop.

Usage:
    python3 generate_env_assets.py                 # list jobs
    python3 generate_env_assets.py --all           # run every job (costs $)
    python3 generate_env_assets.py objects_nature  # run specific job(s)
    python3 generate_env_assets.py --test          # one cheap validation sheet
"""
from __future__ import annotations
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.environ.get('OPENAI_API_KEY', '')
if not API_KEY:
    sys.exit('OPENAI_API_KEY not set in .env')

BASE    = Path(__file__).parent
OUT     = BASE / 'assets' / 'generated_env'
DESKTOP = Path.home() / 'Desktop'

# Reference images (HD-2D style anchors)
REF_OBJECTS  = DESKTOP / '2e74d45b-88f9-4907-aa67-70dab7c75c28.png'  # object asset sheet
REF_TOWN     = DESKTOP / '0f72886f-c689-45d0-9188-0660ed863832.png'  # path/lamp/bridge town
REF_VISTA    = DESKTOP / 'a0724618-28e0-4846-b720-a01c7b109e2e.png'  # wide iso vista
REF_DOJO     = DESKTOP / 'd85d8038-9fa8-486f-8e65-5d8a02d70f50.png'  # walled iso interior
REF_OCTOPATH = DESKTOP / '900bc1a9-3060-45f2-8826-2b22639b893a.png'  # dense town w/ NPCs

client = OpenAI(api_key=API_KEY)

# ── Shared prompt fragments ─────────────────────────────────────────────────────

_STYLE = (
    "HD-2D / Octopath-Traveler style isometric pixel art, matching the lush detailed "
    "look of the reference images: rich painterly pixel shading, warm lighting, clean "
    "readable silhouettes, consistent 2:1 isometric (dimetric) projection."
)

_MAGENTA = (
    "CRITICAL: place every sprite on a SOLID PURE MAGENTA background, RGB (255, 0, 255), "
    "a single flat unbroken magenta fill with NO gradient, NO shadow on the background, "
    "NO checkerboard. Sprites must NOT use any magenta or pink in their own colors so the "
    "background can be keyed out cleanly. Leave clear magenta spacing between every sprite."
)

_GRID = (
    "Arrange the items in a neat evenly-spaced grid, each item fully separated from its "
    "neighbours by magenta space, no item touching or overlapping another, no labels, "
    "no text, no borders, no drop shadows extending between items."
)

# ── Job definitions ─────────────────────────────────────────────────────────────
# size: gpt-image-2 supports '1024x1024', '1536x1024', '1024x1536'.

JOBS: dict[str, dict] = {

    # ── OVERWORLD GROUND TILES ──────────────────────────────────────────────────
    'tiles_overworld': {
        'refs': [REF_TOWN, REF_VISTA, REF_OBJECTS],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} A reference sheet of seamless ISOMETRIC GROUND TILES, each drawn as a "
            "single 2:1 diamond/rhombus tile shape viewed from the same isometric angle. "
            "Include these tiles, each as its own diamond, with 3 distinct VARIATIONS of grass "
            "(lush green, with subtle clover/flower fleck variants) so a field can be tiled "
            "without obvious repetition: "
            "grass variation 1, grass variation 2, grass variation 3, "
            "dirt path, cobblestone path, packed earth/road, shallow water, stone floor. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── INTERIOR FLOOR/WALL TILES ────────────────────────────────────────────────
    'tiles_interior': {
        'refs': [REF_DOJO, REF_OBJECTS],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} A reference sheet of ISOMETRIC INTERIOR TILES matching the warm wooden "
            "dojo interior reference. Each as its own 2:1 diamond tile: "
            "polished wood plank floor (2 variations), woven tatami-style mat, stone interior "
            "floor, and a raised interior WALL segment block (wood-and-plaster, with the tall "
            "vertical face visible) for enclosing room edges. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── NATURE OBJECTS ───────────────────────────────────────────────────────────
    'objects_nature': {
        'refs': [REF_OBJECTS, REF_TOWN],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} A sprite sheet of ISOMETRIC NATURE OBJECTS in the exact style of the "
            "object-sheet reference (trees, bushes, rocks). Include: "
            "two pine/fir trees (different sizes), one large leafy oak tree, one gnarled dead "
            "tree, three bushes (plain, berry, flowering), a small rock, a rock cluster, a large "
            "mossy boulder, a tree stump, two patches of wildflowers (blue and purple), "
            "a glowing blue crystal cluster, a glowing purple crystal cluster. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── PROPS / STRUCTURES ────────────────────────────────────────────────────────
    'objects_props': {
        'refs': [REF_OBJECTS, REF_TOWN],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} A sprite sheet of ISOMETRIC PROPS & STRUCTURES in the style of the object "
            "reference sheet. Include: a wooden directional signpost, a flat wooden sign, "
            "a wooden fence segment, a fence post, a stone lamp post with a warm glowing lantern, "
            "a hanging lantern, a wooden treasure chest (closed), an ornate gold treasure chest, "
            "a wooden barrel, a stacked crate, a small stone shrine with a glowing blue crystal, "
            "a cracked RUINED stone shrine (dark, no glow), a market-stall awning. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── NPCs — group A (Cardhollow) ───────────────────────────────────────────────
    # Each NPC: two poses side by side — left facing NW (away, up-left), right facing
    # SW (toward camera, down-left). NE/SE produced by horizontal flip at load time.
    'npcs_cardhollow': {
        'refs': [REF_OCTOPATH],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} Character sprites for an HD-2D JRPG, chibi proportions (~5 heads tall), "
            "clean pixel shading like the townsfolk in the reference. For EACH character draw "
            "TWO standing poses: the LEFT pose facing AWAY up-and-to-the-left (north-west, back "
            "mostly to camera), the RIGHT pose facing TOWARD camera down-and-to-the-left "
            "(south-west). Characters, top row to bottom: "
            "(1) MIRA — a kind middle-aged village woman, simple warm earth-tone dress, apron, "
            "hair in a bun. "
            "(2) COURIER MASTER — a stout older man in a blue-grey postal uniform with a "
            "satchel, balding with grey side hair. "
            "(3) ODEN'S MOTHER — a gentle woman in a cream and dusty-rose homespun dress, shawl. "
            "(4) SHOPKEEPER — a cheerful merchant in a green vest and rolled-sleeve shirt, apron. "
            "Lay the 4 characters in 4 rows, each row = [NW pose] [SW pose]. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── BUILDINGS — Cardhollow (warm village) ─────────────────────────────────
    # Whole isometric building sprites (not tiles). Door clearly on the front
    # (lower) face. Same iso angle + lighting as the reference town shots.
    'buildings_cardhollow': {
        'refs': [REF_OCTOPATH, REF_TOWN, REF_VISTA],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} FOUR separate complete ISOMETRIC BUILDINGS for a warm fantasy "
            "village, each a freestanding structure viewed from the same 2:1 dimetric "
            "angle as the reference towns, with the DOOR on the front (lower) wall facing "
            "the viewer and a peaked tiled/thatched roof. Arrange the four in a 2x2 grid, "
            "well separated: "
            "(1) a small cozy timber-and-plaster COTTAGE (Oden's home), warm lit windows. "
            "(2) a COURIER POST / small post office with a hanging sign and parcel crates by "
            "the door. "
            "(3) a GENERAL STORE with an awning and goods barrels out front. "
            "(4) a modest neighbour's COTTAGE, slightly different roof colour. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── BUILDINGS — Veilgate (older stone town) ───────────────────────────────
    'buildings_veilgate': {
        'refs': [REF_OCTOPATH, REF_DOJO, REF_VISTA],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} FOUR separate complete ISOMETRIC BUILDINGS for an older weathered "
            "stone town, same 2:1 dimetric angle as the references, DOOR on the front face, "
            "peaked roofs, arranged in a 2x2 grid well separated: "
            "(1) a SCHOLAR'S HOUSE — stone-and-timber two-storey with tall arched windows and "
            "a deep blue roof (retired knight Edric's home). "
            "(2) a DOJO / martial dueling HALL — wide low building, dark timber, blue banners, "
            "a crest over the doorway (matches the dojo interior reference). "
            "(3) a cozy stone INN with a wooden 'INN' sign and warm windows. "
            "(4) a stone SHOP with an awning. "
            f"{_GRID} {_MAGENTA}"
        ),
    },

    # ── NPCs — group B (Veilgate) ───────────────────────────────────────────────
    'npcs_veilgate': {
        'refs': [REF_OCTOPATH],
        'size': '1536x1024',
        'prompt': (
            f"{_STYLE} Character sprites for an HD-2D JRPG, chibi proportions (~5 heads tall), "
            "clean pixel shading. For EACH character draw TWO standing poses: LEFT pose facing "
            "AWAY up-and-to-the-left (north-west), RIGHT pose facing TOWARD camera "
            "down-and-to-the-left (south-west). Characters, top to bottom: "
            "(1) EDRIC — a wise elderly retired knight-scholar, long grey beard, deep blue robe "
            "with faint gold trim, walking staff. "
            "(2) SAGE HANZO — a dignified martial dojo master, dark blue gi/hakama, topknot, "
            "stern calm posture. "
            "(3) TOWNSFOLK — a generic Veilgate villager in muted purple-grey tunic and cloak. "
            "(4) DOJO APPRENTICE — a young eager student in a light green training gi, headband. "
            "(5) TIRED TRAVELER — a weary road-worn wanderer in a brown hooded cloak, backpack. "
            "Lay the 5 characters in 5 rows, each row = [NW pose] [SW pose]. "
            f"{_GRID} {_MAGENTA}"
        ),
    },
}

# Cheapest representative validation sheet
TEST_JOB = 'objects_nature'


# ── Runner ──────────────────────────────────────────────────────────────────────

def _open_refs(paths):
    handles = []
    for p in paths:
        if Path(p).exists():
            handles.append(open(p, 'rb'))
        else:
            print(f'  [warn] reference missing: {p}')
    return handles


def _run_job(name: str) -> bool:
    job = JOBS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    print(f'[{name}]  size={job["size"]}  refs={len(job["refs"])}')
    handles = _open_refs(job['refs'])
    try:
        result = client.images.edit(
            model='gpt-image-2',
            image=handles,
            prompt=job['prompt'],
            size=job['size'],
            quality='high',
            n=1,
        )
    except Exception as e:
        print(f'  ERROR: {e}')
        return False
    finally:
        for h in handles:
            try: h.close()
            except Exception: pass

    raw = result.data[0].b64_json
    if not raw:
        print('  No image data returned.')
        return False
    out_path = OUT / f'{name}.png'
    out_path.write_bytes(base64.b64decode(raw))
    print(f'  Saved → {out_path}')
    return True


def main():
    args = sys.argv[1:]
    if not args:
        print('Jobs available:')
        for k, v in JOBS.items():
            print(f'  {k:20s} ({v["size"]})')
        print('\nRun: --all | --test | <job> [<job> ...]')
        return
    if args == ['--test']:
        jobs = [TEST_JOB]
    elif args == ['--all']:
        jobs = list(JOBS)
    else:
        jobs = args
        bad = [j for j in jobs if j not in JOBS]
        if bad:
            sys.exit(f'Unknown job(s): {bad}')

    print(f'Running {len(jobs)} job(s): {jobs}\n')
    ok = 0
    for j in jobs:
        if _run_job(j):
            ok += 1
        print()
    print(f'Done. {ok}/{len(jobs)} sheets generated → {OUT}')


if __name__ == '__main__':
    main()
