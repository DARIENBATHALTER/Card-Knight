"""
Asset generation pipeline for Card Knight: Astral Arcana.

Uses:
  - Fireworks FLUX.1 schnell  → card art, battle backgrounds, portraits
  - Pixellab SDK              → pixel sprites and animation (see also MCP tools)

Run:  python3 generate_assets.py [--phase 1|2|3] [--asset <name>]
"""
import os
import sys
import base64
import argparse
import requests
from pathlib import Path
from PIL import Image
import io

# ── Keys ──────────────────────────────────────────────────────────────────────
def _load_env():
    env = {}
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

ENV = _load_env()
FIREWORKS_KEY = ENV.get('FIREWORKS_API_KEY') or os.getenv('FIREWORKS_API_KEY')
PIXELLAB_KEY  = ENV.get('PIXELLAB_API_KEY')  or os.getenv('PIXELLAB_API_KEY')

OUT = Path(__file__).parent / 'assets' / 'generated'
OUT_CARDS   = OUT / 'cards'
OUT_BKGD    = OUT / 'backgrounds'
OUT_PORT    = OUT / 'portraits'
OUT_SPRITES = Path(__file__).parent / 'assets' / 'sprites'

# ── Fireworks FLUX.1 ──────────────────────────────────────────────────────────
FLUX_URL     = 'https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-schnell-fp8/text_to_image'
FLUX_URL_DEV = 'https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-dev-fp8/text_to_image'

STYLE_PREFIX = (
    "high quality pixel art illustration, Card Knight Astral Arcana indie RPG game art, "
    "Octopath Traveler meets Final Fantasy IV PSP aesthetic, painterly pixel art with "
    "atmospheric lighting and modern shader effects, rich fantasy medieval palette, "
    "vibrant and detailed, "
)


def flux(prompt: str, width=1024, height=1024, steps=4, dev=False, save_path=None) -> Image.Image:
    """Call Fireworks workflow endpoint — returns raw image bytes."""
    url = FLUX_URL_DEV if dev else FLUX_URL
    guidance = 3.5 if dev else 0.0
    resp = requests.post(url, headers={
        'Authorization': f'Bearer {FIREWORKS_KEY}',
        'Content-Type': 'application/json',
    }, json={
        'prompt': prompt,
        'width': width,
        'height': height,
        'num_inference_steps': steps,
        'guidance_scale': guidance,
    }, timeout=120)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(save_path)
        cost = 0.014 if dev else 0.0014
        print(f"  saved → {save_path}  (${cost:.4f})")
    return img


# ── Card art prompts ───────────────────────────────────────────────────────────
# Each entry: (filename, prompt_suffix, width, height)
CARD_ARTS = {
    # ── Fire magic
    'ignite':      ("roaring pillar of fire erupting from a magical circle, orange and red flame vortex, "
                    "glowing fire runes, ember sparks, dramatic fire magic spell card illustration, "
                    "dark atmospheric background, elemental fire magic, square card art"),
    'scorch':      ("intense white-hot fire column with radial heat wave, scorching magical blast, "
                    "yellow-white flame core surrounded by orange fire, fire magic attack, card illustration"),
    'immolate':    ("catastrophic all-consuming fire summon, massive flame dragon silhouette, "
                    "ancient fire ritual circle, apocalyptic fire magic, Ifrit-inspired, card illustration"),

    # ── Ice magic
    'freeze':      ("shard of crystalline ice magic, blue-white frost spike erupting, "
                    "ice crystal formation, magical cold aura, blizzard wind lines, "
                    "Shiva-inspired ice magic card art, cool blue palette"),
    'cryolize':    ("spiraling ice storm vortex, frozen magical circle, "
                    "multiple ice shards orbiting, deep blue and silver, blizzard spell card illustration"),
    'avalanche':   ("massive avalanche of magical ice and snow, glacier crash, "
                    "absolute zero cold, crystalline ice structures, blue-white spell card art"),

    # ── Lightning magic
    'jolt':        ("lightning bolt crashing down through a runic circle, yellow electric sparks, "
                    "thunder magic card art, electric discharge effects, Ramuh-inspired lightning spell"),
    'shock':       ("crackling electrical storm spell, multiple lightning arcs, blue-yellow electricity, "
                    "charged magical circle with volt effects, thunder magic card illustration"),
    'electrocute': ("Thundaga-style total lightning devastation, all-consuming electrical storm, "
                    "Ramuh's ultimate judgment bolt, massive yellow-white electric discharge, epic card art"),

    # ── Earth magic
    'crack':       ("earth magic stone spike erupting from cracked ground, terra magic, "
                    "brown-green earth energy, boulder and rock motifs, ground-shake spell card art"),
    'quake':       ("powerful earthquake magic, multiple stone pillars erupting, "
                    "earth cracking open with magic runes, terra elemental spell, brown and gold card art"),
    'landslide':   ("Stonega-style ultimate earth magic, mountain of boulders crashing down, "
                    "massive stone elemental, epic earth devastation, terra magic card illustration"),

    # ── Holy magic
    'pray':        ("soft golden holy magic, gentle prayer glow, angelic feathers and light motes, "
                    "warm gold and white light, divine blessing spell card art, peaceful radiance"),
    'exorcise':    ("bright silver-gold holy light beam, banishing dark energy, "
                    "cross and rune motifs, holy water splash, divine magic card illustration"),
    'absolve':     ("epic holy absolute light, divine judgment beam, radiant angelic wings, "
                    "all-light holy magic explosion, gold-white sacred spell art, powerful divine magic"),

    # ── Dark magic
    'night':       ("dark magic shadow bolt, void energy coalescing, purple-black dark spell, "
                    "shadow runes and dark mist, sinister dark magic card art"),
    'darkness':    ("consuming darkness void spell, shadowy tendrils, dark purple-black energy, "
                    "shadow magic circle, malevolent dark aura card illustration"),
    'oblivion':    ("ultimate void annihilation magic, total darkness consuming everything, "
                    "Flare-style dark magic explosion, purple-black cosmic void, epic dark spell card art"),

    # ── Healing magic
    'heal':        ("gentle green healing magic, warm healing glow, HP restore spell, "
                    "small glowing orbs of life energy, Cure magic from Final Fantasy, card art"),
    'cure':        ("radiant white healing magic, recovery spell with golden cross motif, "
                    "soothing warm light, HP restoration, Curaga-style healing card illustration"),
    'recover':     ("full HP restoration magic, brilliant white-green healing burst, "
                    "life energy flowing, recover all wounds spell, magical healing card art"),
    'rejuvenate':  ("ultimate regeneration magic, full-life restore, "
                    "shimmering gold-green life force, Phoenix-inspired revival energy, "
                    "HP restore card art, radiant healing magic illustration"),

    # ── Status clearing
    'unpoison':    ("antidote magic vial with green cure light, purifying magic, "
                    "toxin-clearing spell art, green healing cure, status removal card"),
    'return':      ("gentle revival magic, soft glowing return from KO, "
                    "white-blue light, Raise spell from Final Fantasy, revive card art"),
    'raise':       ("golden Raise spell, fallen warrior rising from glowing runes, "
                    "revival magic with white-gold light, raise from dead card illustration"),
    'resurrect':   ("epic Arise/Resurrect magic, full HP revival with golden light eruption, "
                    "dramatic resurrection spell, Phoenix-inspired, glorious revival card art"),

    # ── Weapons
    'sword':       ("glowing enchanted sword card art, fantasy RPG sword icon, "
                    "rune-etched steel blade with magical aura, Excalibur-style, weapon card illustration"),
    'axe':         ("powerful battle axe weapon card, heavy fantasy axe with rune engravings, "
                    "warrior weapon with glowing edge, RPG item card art"),
    'knife':       ("swift dagger/knife card art, fantasy rogue weapon, "
                    "gleaming enchanted blade, quick-strike weapon card illustration"),
    'crossbow':    ("magical crossbow weapon card, fantasy ranged weapon, "
                    "glowing bolt loaded, mechanical enchanted crossbow card art"),
    'bow':         ("elven longbow card art, graceful curved fantasy bow, "
                    "glowing arrow nocked, ranger weapon card illustration"),
    'hammer':      ("mighty war hammer card art, heavy enchanted hammer, "
                    "rune-carved hammerhead, warrior weapon with magic glow"),
    'lance':       ("gleaming lance/spear card art, holy lance with rune shaft, "
                    "dragoon-style weapon, piercing magic spear card illustration"),
    'staff':       ("magical staff card art, arcane focus staff, crystal orb top, "
                    "mage weapon with arcane glow, wizard staff card illustration"),

    # ── Items
    'potion':      ("HP potion item card, glowing red health potion bottle, "
                    "fantasy RPG consumable item, ruby liquid, potion card art"),
    'antidote':    ("antidote item card, green cure potion, "
                    "antidote vial with purifying light, status cure item card art"),
    'fairy':       ("fairy auto-revive item card, tiny glowing fairy spirit, "
                    "revival item with warm golden light, Phoenix Down equivalent, "
                    "delicate fairy wings with life energy glow, item card illustration"),

    # ── Summons
    'boulder':     ("summon boulder card art, massive magical boulder summoned from earth magic circle, "
                    "stone golem rolling forward, earth summon card illustration, "
                    "ancient stone elemental summon, dramatic impact"),
}

# ── Battle backgrounds ────────────────────────────────────────────────────────
BACKGROUNDS = {
    'forest': (
        "isometric pixel art battle arena, ancient forest clearing at dusk, "
        "mossy stone floor tiles for battle grid, atmospheric fog between dark trees, "
        "fireflies and glowing mushrooms, ruined stone arches, "
        "blue-green atmospheric lighting, Octopath Traveler forest battle background, "
        "16:9 landscape game background, depth and atmosphere"
    ),
    'dungeon': (
        "isometric pixel art battle arena, stone dungeon chamber, "
        "blue crystal pillars glowing, magical arcane circles on floor, "
        "torch-lit stone walls, gothic arches, mysterious atmosphere, "
        "Final Fantasy dungeon battle background, deep shadow and blue magic light"
    ),
    'castle_town': (
        "isometric pixel art battle arena, cobblestone town square at night, "
        "lantern-lit, castle walls visible in background, "
        "golden warm lamplight, stone and wood buildings, "
        "FFIV-style town battle background, atmospheric evening lighting"
    ),
    'river_town': (
        "isometric pixel art battle arena, river docks and wooden bridges, "
        "water reflections with ripples, market stalls, evening lighting, "
        "warm lantern glow reflected in water, RPG river town battle scene"
    ),
    'grassland': (
        "isometric pixel art battle arena, rolling green hills, "
        "wildflowers and tall grass, daytime sunny atmosphere, "
        "white clouds, ancient stone ruins in background, "
        "cheerful outdoor RPG battle background, Octopath outdoor scene"
    ),
    'castle': (
        "isometric pixel art battle arena, throne room of a fantasy castle, "
        "red carpet, ornate stone pillars, stained glass light shafts, "
        "golden royal lighting, epic fantasy final dungeon atmosphere, "
        "FFIV castle interior battle background"
    ),
}


# ── Pixellab helper ───────────────────────────────────────────────────────────
def pixellab_client():
    from pixellab.client import PixelLabClient
    return PixelLabClient(secret=PIXELLAB_KEY)


def pixellab_generate(description: str, size: tuple, no_bg=True,
                       direction='east', view='side', isometric=False,
                       save_path=None) -> Image.Image:
    from pixellab.generate_image_bitforge import generate_image_bitforge
    from pixellab.models import ImageSize
    client = pixellab_client()
    resp = generate_image_bitforge(
        client=client,
        description=description,
        image_size=ImageSize(width=size[0], height=size[1]),
        no_background=no_bg,
        direction=direction,
        view=view,
        isometric=isometric,
    )
    img = resp.image.pil_image()
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(save_path)
        print(f"  saved → {save_path}")
    return img


def pixellab_animate(reference_img: Image.Image, action: str, description: str,
                      n_frames=4, size=(64, 64), direction='east', view='side',
                      save_path=None) -> list:
    from pixellab.animate_with_text import animate_with_text
    from pixellab.models import ImageSize
    client = pixellab_client()
    resp = animate_with_text(
        client=client,
        image_size=ImageSize(width=size[0], height=size[1]),
        description=description,
        action=action,
        reference_image=reference_img,
        view=view,
        direction=direction,
        n_frames=n_frames,
        negative_description="",
    )
    frames = [f.pil_image() for f in resp.images]
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        for i, frame in enumerate(frames):
            p = save_path.parent / f"{save_path.stem}_f{i}{save_path.suffix}"
            frame.save(p)
        print(f"  saved {len(frames)} frames → {save_path.parent}")
    return frames


# ── Phase runners ─────────────────────────────────────────────────────────────

def run_phase1_cards(subset=None):
    """Generate all card art via FLUX.1 schnell."""
    print("\n=== Phase 1: Card Art (FLUX.1 schnell @ $0.0014/image) ===")
    targets = subset or list(CARD_ARTS.keys())
    cost = 0
    for name in targets:
        prompt_suffix = CARD_ARTS[name]
        out = OUT_CARDS / f"{name}.png"
        if out.exists():
            print(f"  skip (exists): {name}")
            continue
        print(f"  generating: {name}...")
        full_prompt = STYLE_PREFIX + prompt_suffix
        flux(full_prompt, width=1024, height=1024, save_path=out)
        cost += 0.0014
    print(f"\n  Total card art cost: ${cost:.4f}")


def run_phase1_backgrounds(subset=None):
    """Generate battle backgrounds via FLUX.1 schnell."""
    print("\n=== Phase 1: Backgrounds (FLUX.1 schnell) ===")
    targets = subset or list(BACKGROUNDS.keys())
    cost = 0
    for name in targets:
        out = OUT_BKGD / f"{name}.jpg"
        if out.exists():
            print(f"  skip (exists): {name}")
            continue
        print(f"  generating: {name}...")
        full_prompt = STYLE_PREFIX + BACKGROUNDS[name]
        # Landscape format for backgrounds
        img = flux(full_prompt, width=1280, height=720, save_path=out)
        cost += 0.0014
    print(f"\n  Total background cost: ${cost:.4f}")


def run_phase1_player_portrait():
    """Generate the player HUD portrait."""
    print("\n=== Phase 1: Player Portrait ===")
    out = OUT_PORT / "oden_portrait.png"
    if out.exists():
        print("  skip (exists)")
        return
    prompt = (
        STYLE_PREFIX +
        "character portrait of a young male RPG hero, blonde spiky hair with dark roots, "
        "intense blue eyes, wearing a dark blue travelling cape with leather adventurer armor, "
        "belts and buckles detail, slight smirk expression, "
        "Final Fantasy IV PSP character portrait style, close-up face and shoulders, "
        "pixel art portrait with modern detail, square format"
    )
    flux(prompt, width=512, height=512, dev=True, save_path=out)
    print("  (used FLUX dev for portrait quality, $0.014)")


def run_phase2_player_sprite():
    """Generate player battle sprite via Pixellab."""
    print("\n=== Phase 2: Player Battle Sprite (Pixellab) ===")
    desc = (
        "young male RPG hero pixel art character sprite, blonde spiky hair, "
        "dark blue adventurer cape, leather armor with belts and buckles, "
        "Final Fantasy IV PSP style, battle-ready stance, holding a glowing card"
    )
    out = OUT / 'player_base.png'
    if not out.exists():
        print("  generating base sprite...")
        img = pixellab_generate(desc, size=(64, 64), direction='east', view='side',
                                 save_path=out)
    else:
        img = Image.open(out)
        print("  loaded existing base sprite")

    # Generate animation frames
    anim_dir = OUT / 'player_anims'
    anim_dir.mkdir(exist_ok=True)
    for action, anim_name in [
        ("standing idle, subtle breathing", "idle"),
        ("walk cycle forward", "walk"),
        ("card attack, throwing glowing card forward", "attack_buster"),
        ("sword slash attack", "attack_sword"),
        ("casting magic spell, magical circle appearing", "cast_magic"),
        ("taking damage, recoiling", "hurt"),
    ]:
        frames_exist = list(anim_dir.glob(f"{anim_name}_f*.png"))
        if frames_exist:
            print(f"  skip anim (exists): {anim_name}")
            continue
        print(f"  animating: {anim_name}...")
        pixellab_animate(img, action=action, description=desc,
                          n_frames=4, size=(64, 64),
                          save_path=anim_dir / f"{anim_name}.png")


def run_phase2_enemy_sprite():
    """Generate slime enemy sprite via Pixellab."""
    print("\n=== Phase 2: Slime Enemy Sprite (Pixellab) ===")
    desc = (
        "cute green slime monster pixel art game sprite, "
        "translucent jelly body, small black beady eyes, simple round blob, "
        "Final Fantasy slime enemy style, vibrant green color"
    )
    out = OUT / 'slime_base.png'
    if not out.exists():
        print("  generating base slime...")
        img = pixellab_generate(desc, size=(64, 64), direction='west', view='side',
                                 save_path=out)
    else:
        img = Image.open(out)
        print("  loaded existing base")

    anim_dir = OUT / 'slime_anims'
    anim_dir.mkdir(exist_ok=True)
    for action, name in [
        ("idle bouncing", "idle"),
        ("taking damage recoiling", "hurt"),
    ]:
        if list(anim_dir.glob(f"{name}_f*.png")):
            print(f"  skip: {name}")
            continue
        print(f"  animating: {name}...")
        pixellab_animate(img, action=action, description=desc,
                          n_frames=4, size=(64, 64), direction='west',
                          save_path=anim_dir / f"{name}.png")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Card Knight asset generator")
    parser.add_argument('--phase', type=int, choices=[1, 2, 3], help="Run a full phase")
    parser.add_argument('--cards', nargs='*', help="Generate specific card(s) by name, or all if omitted")
    parser.add_argument('--backgrounds', nargs='*', help="Generate specific background(s)")
    parser.add_argument('--portrait', action='store_true')
    parser.add_argument('--player', action='store_true')
    parser.add_argument('--enemy', action='store_true')
    parser.add_argument('--list', action='store_true', help="List all available assets")
    args = parser.parse_args()

    if args.list:
        print("Cards:", ', '.join(CARD_ARTS.keys()))
        print("Backgrounds:", ', '.join(BACKGROUNDS.keys()))
        return

    if not FIREWORKS_KEY:
        print("ERROR: FIREWORKS_API_KEY not set in .env")
        sys.exit(1)

    if args.phase == 1 or args.cards is not None:
        run_phase1_cards(args.cards if args.cards else None)
    if args.phase == 1 or args.backgrounds is not None:
        run_phase1_backgrounds(args.backgrounds if args.backgrounds else None)
    if args.phase == 1 or args.portrait:
        run_phase1_player_portrait()
    if args.phase == 2 or args.player:
        run_phase2_player_sprite()
    if args.phase == 2 or args.enemy:
        run_phase2_enemy_sprite()

    if not any(vars(args).values()):
        parser.print_help()


if __name__ == '__main__':
    main()
