"""Generate animated wipe-edge sprites using gpt-image-2.

Each frame shows playing-card silhouettes fluttering against a magenta
background (#FF00FF).  The user will add the flat left edge and chroma-key
in Photoshop.  Four frames with different card arrangements give the
flutter animation.

Output: assets/fx/wipe_edge/wipe_edge_00.png … wipe_edge_03.png
"""

import os, base64, json
from pathlib import Path
from openai import OpenAI

OUTPUT_DIR = Path(__file__).parent / 'assets' / 'fx' / 'wipe_edge'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

BASE = (
    "Game sprite art. Playing cards (classic rectangular playing cards with rounded corners, "
    "no text or pips visible) as bold flat BLACK silhouettes tumbling mid-air against a "
    "SOLID BRIGHT MAGENTA background (pure #FF00FF, RGB 255 0 255). "
    "Portrait composition. Cards are scattered at various angles as if exploding outward "
    "from the left edge. 4-6 cards visible at different rotation angles and distances. "
    "Clean flat shapes only — NO gradients, NO shadows, NO outlines beyond card shape, "
    "NO text. The magenta must be pure saturated #FF00FF with no anti-aliasing fringe. "
    "Pixel-art inspired, bold and graphic. "
)

FRAMES = [
    "Frame 1 of 4: Cards clustered near the left edge — two cards nearly parallel, "
    "one card steeply angled (70°), one horizontal card just leaving the edge.",

    "Frame 2 of 4: Cards mid-scatter — three cards spread evenly across the image, "
    "one rotated 30°, one at 55°, one almost vertical (85°).",

    "Frame 3 of 4: Cards in full flutter — five cards at varied angles (15°, 40°, 65°, "
    "80°, 20°), overlapping slightly, some closer to viewer (larger), some farther (smaller).",

    "Frame 4 of 4: Cards returning toward left edge — two large cards dominating, "
    "angled 45° and 25°, three small cards behind them at acute angles (10°, 70°, 50°).",
]

for i, frame_desc in enumerate(FRAMES):
    prompt = BASE + frame_desc
    print(f"Generating frame {i} …")
    resp = client.images.generate(
        model='gpt-image-2',
        prompt=prompt,
        n=1,
        size='1024x1536',
    )
    # gpt-image-2 may return url or b64_json depending on API version
    item = resp.data[0]
    if hasattr(item, 'b64_json') and item.b64_json:
        img_bytes = base64.b64decode(item.b64_json)
    elif hasattr(item, 'url') and item.url:
        import urllib.request
        with urllib.request.urlopen(item.url) as r:
            img_bytes = r.read()
    else:
        raise RuntimeError(f"Unexpected response item: {item}")

    out = OUTPUT_DIR / f'wipe_edge_{i:02d}.png'
    out.write_bytes(img_bytes)
    print(f"  Saved {out} ({len(img_bytes)//1024} KB)")

print("Done. All 4 frames saved to", OUTPUT_DIR)
