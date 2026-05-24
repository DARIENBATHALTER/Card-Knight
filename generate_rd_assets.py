#!/usr/bin/env python3
"""
RetroDiffusion asset generator for Card Knight: Astral Arcana.

Requires RETRODIFFUSION_API_KEY in .env (or environment variable).

Usage:
  python3 generate_rd_assets.py --list
  python3 generate_rd_assets.py --credits
  python3 generate_rd_assets.py --dry-run --batch priority
  python3 generate_rd_assets.py --batch priority
  python3 generate_rd_assets.py --batch characters|enemies|tiles|cards|vfx|environment|ui
  python3 generate_rd_assets.py --asset slime_green goblin_mage
  python3 generate_rd_assets.py --force --asset oden_battle_idle
"""
import os
import sys
import base64
import time
import argparse
from pathlib import Path
from io import BytesIO

import requests
from PIL import Image

# ─── Keys ─────────────────────────────────────────────────────────────────────

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
RD_KEY  = ENV.get('RETRODIFFUSION_API_KEY') or os.getenv('RETRODIFFUSION_API_KEY')
RD_BASE = 'https://api.retrodiffusion.ai/v1'

ASSETS_ROOT = Path(__file__).parent / 'assets'

# ─── Visual Style Guide: Card Knight: Astral Arcana ───────────────────────────
#
# The style sits between:
#   Mega Man Battle Network / Boktai / Kingdom Hearts: Chain of Memories overworld
#   + Final Fantasy IV PSP-era sprite richness
#   + Octopath-like lighting sensibility
# but with flat isometric presentation rather than 3D diorama scenes.
#
# Core palette: deep navy, antique gold, warm leather/brass, cream cloth,
#   muted red, moss green, stone gray, blue-white magic, violet void, warm orange.
#
# The heart of the style: a GBA-era action RPG from an alternate timeline where
# Square made a fantasy card-battle game with PSP-level sprite polish.

# Base prompt injected into every asset
GLOBAL = (
    "Fantasy JRPG pixel art, flat isometric early-2000s handheld RPG style, "
    "inspired by Mega Man Battle Network, Boktai, Kingdom Hearts Chain of Memories, "
    "and PSP-era Final Fantasy sprite richness. "
    "Humanoid proportions, clean readable silhouettes, detailed but not noisy, "
    "painterly pixel shading, deep navy and antique gold accents, warm leather and brass, "
    "celestial arcana motifs, compass roses, subtle modern glow effects, "
    "magical atmosphere, asset-ready game art."
)

# Negative prompt applied to every generation
NEG = (
    "chibi, super deformed, squat body, fat proportions, huge head tiny body, "
    "toy-like, realistic 3D render, Octopath diorama, tilt-shift blur, "
    "excessive clutter, modern sci-fi, cyberpunk, guns, futuristic UI, "
    "smooth vector art, plastic gradients, blurry, low readability, "
    "over-detailed noise, bulky medieval plate armor, photorealistic, "
    "painterly non-pixel art, watercolor, sketch, concept art"
)

# Category-specific style additions
_CHAR = (
    "Humanoid overworld proportions, not chibi, not squat. "
    "Transparent background."
)
_BATTLE = (
    "Fantasy tactical grid battle pixel art, ornate navy-and-gold aesthetic, "
    "card-based magic system, readable action pose, dramatic pixel art. "
    "Player character always faces RIGHT (toward the enemy, toward the right side of the screen). "
    "Transparent background."
)
_OW_ENV = (
    "Flat isometric fantasy RPG asset, painterly pixel grass and stone, "
    "modular asset-ready, soft atmospheric lighting, transparent background."
)
_OW_TERRAIN = (
    "Flat isometric fantasy RPG terrain tile, painterly pixel grass and stone, "
    "open walkable spaces, subtle flowers and pebbles, no baked-in large objects, "
    "no 3D diorama look, no tilt-shift blur, seamless tile edge."
)
_VFX = (
    "Dramatic pixel art VFX, runic circles, star particles, JRPG elemental magic. "
    "Transparent background."
)
_CARD = (
    "Fantasy battle card icon, dark navy card frame with antique gold border, "
    "arcane deckbuilding interface aesthetic, readable at small scale. "
    "Transparent background."
)
_UI = (
    "Fantasy JRPG UI asset, dark navy panel, antique gold border, "
    "old-world spellbook elegance, arcane manuscript aesthetic. "
    "Transparent background."
)

# Oden's canonical visual identity
ODEN = (
    "young heroic card knight named Oden, sandy blond spiky hair, blue eyes, "
    "navy scarf-cape with antique gold trim, leather adventurer armor, "
    "brass pauldrons and bracers, dark blue trousers, brown boots, "
    "red waist cloth tabs, sword on back, agile JRPG protagonist energy, "
    "always facing RIGHT toward the viewer's right side in battle"
)

# ─── Prompt builder helpers ────────────────────────────────────────────────────

def _p(*parts):
    """Join style parts into a single prompt string."""
    return " ".join(p.strip().rstrip('.') + '.' for p in parts if p.strip())

# ─── Asset Table ───────────────────────────────────────────────────────────────
# key → (save_path_relative, prompt, prompt_style, width, height, remove_bg)
#
# rd_pro styles available: fantasy, isometric, spritesheet, ui_panel,
#   inventory_items, topdown, platformer, dungeon_map, painterly, simple
#
# All assets use rd_pro__* for maximum quality.
# Cost: $0.18 per image (flat rate for all rd_pro styles).

ASSETS = {}

# ── Oden Overworld ─────────────────────────────────────────────────────────────
ASSETS['oden_overworld_idle'] = (
    'sprites/characters/oden/overworld_idle_sheet.png',
    _p(GLOBAL, _CHAR,
       f"{ODEN}. Eight-direction overworld idle sprite sheet — one static pose each for: "
       "up, down, left, right, up-left, up-right, down-left, down-right. "
       "Cape hangs naturally per direction, sword hilt visible on back. "
       "Each pose evenly spaced on a single sheet."),
    'rd_pro__fantasy', 512, 256, True,
)
ASSETS['oden_run_cardinal'] = (
    'sprites/characters/oden/run_cardinal_sheet.png',
    _p(GLOBAL, _CHAR,
       f"{ODEN}. Four-frame run animation spritesheet, cardinal directions only: "
       "up, down, left, right. One row per direction, four frames per row. "
       "Alternating feet clearly readable, cape flapping behind in motion."),
    'rd_pro__fantasy', 256, 256, True,
)
ASSETS['oden_run_diagonal'] = (
    'sprites/characters/oden/run_diagonal_sheet.png',
    _p(GLOBAL, _CHAR,
       f"{ODEN}. Four-frame run animation spritesheet, diagonal directions: "
       "up-left, up-right, down-left, down-right. One row per direction, four frames per row. "
       "Cape streams backward, alternating feet."),
    'rd_pro__fantasy', 256, 256, True,
)

# ── Oden Battle ────────────────────────────────────────────────────────────────
ASSETS['oden_battle_idle'] = (
    'sprites/characters/oden/battle_idle.png',
    _p(GLOBAL, _BATTLE,
       f"{ODEN}. Battle idle stance, facing RIGHT. Wide grounded stance, "
       "one hand resting near card deck at belt, focused expression, "
       "blue scarf-cape flowing behind him to the LEFT. Full body visible, no clipping."),
    'rd_pro__fantasy', 160, 160, True,
)
ASSETS['oden_battle_cast'] = (
    'sprites/characters/oden/battle_cast.png',
    _p(GLOBAL, _BATTLE,
       f"{ODEN}. Card casting pose, facing RIGHT. One hand extended toward the RIGHT "
       "holding a glowing arcane card radiating blue-white light, other arm drawn back, "
       "standing on a faint magical circle, cape swept to the LEFT. Full body visible."),
    'rd_pro__fantasy', 160, 160, True,
)
ASSETS['oden_battle_slash'] = (
    'sprites/characters/oden/battle_slash.png',
    _p(GLOBAL, _BATTLE,
       f"{ODEN}. Mid-sword-slash, facing RIGHT, attacking toward the RIGHT. "
       "Drawn blade leaving a blue crescent slash arc to the RIGHT, "
       "dynamic forward lean, cape trailing to the LEFT, feet planted. Full body visible."),
    'rd_pro__fantasy', 160, 160, True,
)
ASSETS['oden_battle_throw'] = (
    'sprites/characters/oden/battle_throw.png',
    _p(GLOBAL, _BATTLE,
       f"{ODEN}. Card throw pose, facing RIGHT, throwing toward the RIGHT. "
       "Flicking a glowing blue-gold card forward to the RIGHT, "
       "motion trail behind card, red cloth and cape swept to the LEFT. Full body visible."),
    'rd_pro__fantasy', 160, 160, True,
)
ASSETS['oden_battle_hit'] = (
    'sprites/characters/oden/battle_hit.png',
    _p(GLOBAL, _BATTLE,
       f"{ODEN}. Hit-reaction pose, facing RIGHT. Recoiling slightly to the LEFT from impact, "
       "pained expression, slight white damage-flash edge on the sprite. Full body visible."),
    'rd_pro__fantasy', 160, 160, True,
)
ASSETS['oden_battle_victory'] = (
    'sprites/characters/oden/battle_victory.png',
    _p(GLOBAL, _BATTLE,
       f"{ODEN}. Victory celebration pose, facing RIGHT. One arm raised triumphantly to the RIGHT, "
       "bright expression, cape billowing, confident heroic energy. Full body visible."),
    'rd_pro__fantasy', 160, 160, True,
)

# ── Enemies ────────────────────────────────────────────────────────────────────
ASSETS['slime_green'] = (
    'sprites/enemies/slime_green.png',
    _p(GLOBAL, _BATTLE,
       "Cute green slime enemy. Small rounded translucent jelly body, "
       "simple mischievous face, shiny specular highlight on body. Facing left. "
       "Full body fits within frame with padding around edges."),
    'rd_pro__fantasy', 80, 80, True,
)
ASSETS['slime_aqua'] = (
    'sprites/enemies/slime_aqua.png',
    _p(GLOBAL, _BATTLE,
       "Aqua water-element slime enemy. Translucent cyan-blue jelly body with "
       "watery inner shimmer, mischievous face. Facing left. "
       "Full body fits within frame with padding around edges."),
    'rd_pro__fantasy', 80, 80, True,
)
ASSETS['slime_ember'] = (
    'sprites/enemies/slime_ember.png',
    _p(GLOBAL, _BATTLE,
       "Ember fire-element slime enemy. Orange-red jelly body with glowing inner core "
       "and small flame wisps on top, mischievous face. Facing left. "
       "Full body fits within frame with padding around edges."),
    'rd_pro__fantasy', 80, 80, True,
)
ASSETS['slime_void'] = (
    'sprites/enemies/slime_void.png',
    _p(GLOBAL, _BATTLE,
       "Void dark-element slime enemy. Dark purple-black jelly body, faint violet inner glow, "
       "small sinister expression. Facing left. "
       "Full body fits within frame with padding around edges."),
    'rd_pro__fantasy', 80, 80, True,
)
ASSETS['goblin_mage'] = (
    'sprites/enemies/goblin_mage.png',
    _p(GLOBAL, _BATTLE,
       "Small goblin spellcaster enemy. Purple hood and robes, crooked wooden staff topped "
       "with a glowing green orb, hunched posture, wide mischievous grin. Facing left. "
       "Full body including staff tip fits within frame, no clipping."),
    'rd_pro__fantasy', 96, 128, True,
)
ASSETS['wolf_beast'] = (
    'sprites/enemies/wolf_beast.png',
    _p(GLOBAL, _BATTLE,
       "Armored wolf enemy. Gray fur, leather harness with small metal plates on shoulders, "
       "low aggressive stance, sharp fangs bared, clawed forepaws forward. Facing left. "
       "Full body including tail and ears fits within frame, no clipping."),
    'rd_pro__fantasy', 128, 96, True,
)
ASSETS['pumpkin_imp'] = (
    'sprites/enemies/pumpkin_imp.png',
    _p(GLOBAL, _BATTLE,
       "Pumpkin-headed imp enemy. Orange jack-o-lantern head with carved grin, vine-tendril body, "
       "small clawed hands, spooky but charming. Facing left. "
       "Full body including pumpkin stem fits within frame, no clipping."),
    'rd_pro__fantasy', 96, 128, True,
)
ASSETS['lizard_knight'] = (
    'sprites/enemies/lizard_knight.png',
    _p(GLOBAL, _BATTLE,
       "Reptilian knight enemy. Dark green scales, bronze breastplate and greaves, "
       "short spear held ready, battle-ready crouch. Facing left. "
       "Full body including spear tip fits within frame, no clipping."),
    'rd_pro__fantasy', 96, 128, True,
)
ASSETS['ruin_guardian'] = (
    'sprites/enemies/ruin_guardian.png',
    _p(GLOBAL, _BATTLE,
       "Stone golem guardian enemy. Mossy ancient stone body, glowing blue rune core "
       "embedded in chest, heavy defensive stance, large stone fists. Facing left. "
       "Full body fits within frame with padding, no clipping."),
    'rd_pro__fantasy', 128, 160, True,
)
ASSETS['astral_wisp'] = (
    'sprites/enemies/astral_wisp.png',
    _p(GLOBAL, _BATTLE,
       "Floating magical wisp enemy. Translucent blue-white glowing body, "
       "tiny orbiting star particles, no legs, hovering. Ethereal and otherworldly. "
       "Full form including particle aura fits within frame."),
    'rd_pro__fantasy', 80, 80, True,
)

# ── Battle Tiles ───────────────────────────────────────────────────────────────
ASSETS['tile_player'] = (
    'tiles/tile_player.png',
    _p(GLOBAL,
       "Blue stone battle grid tile, player side. Square flat slab, beveled edges, "
       "slight surface cracks, faint blue magical rim-light glow. Top-down game tile."),
    'rd_pro__fantasy', 96, 64, True,
)
ASSETS['tile_enemy'] = (
    'tiles/tile_enemy.png',
    _p(GLOBAL,
       "Red-brown stone battle grid tile, enemy side. Square flat slab, beveled edges, "
       "subtle red magical tint, cracked surface. Top-down game tile."),
    'rd_pro__fantasy', 96, 64, True,
)
ASSETS['tile_neutral'] = (
    'tiles/tile_neutral.png',
    _p(GLOBAL,
       "Gray mossy stone square battle tile. Cracked ancient slab, no color allegiance. "
       "Top-down game tile."),
    'rd_pro__fantasy', 96, 64, True,
)
ASSETS['tile_broken'] = (
    'tiles/tile_broken.png',
    _p(GLOBAL,
       "Damaged cracked battle tile. Missing chunks, dark void gaps, "
       "shattered stone edges. Fantasy tactical grid tile."),
    'rd_pro__fantasy', 96, 64, True,
)
ASSETS['tile_magic_circle'] = (
    'tiles/tile_magic_circle.png',
    _p(GLOBAL,
       "Stone battle tile with glowing blue-white magic circle. "
       "Ancient compass-star rune pattern etched and glowing. Top-down game tile."),
    'rd_pro__fantasy', 96, 64, True,
)

# ── Card Icons ─────────────────────────────────────────────────────────────────

def _card(filename, icon_desc):
    return (
        f'chips/icons/{filename}.png',
        _p(GLOBAL, _CARD, icon_desc),
        'rd_pro__inventory_items', 64, 64, True,
    )

ASSETS['card_sword_slash']  = _card('sword_slash',  "Glowing blue crescent sword slash arc, central icon.")
ASSETS['card_ranged']       = _card('ranged',        "Two glowing throwing cards with silver-blue motion trails, central icon.")
ASSETS['card_ignis']        = _card('ignis',         "Orange-red flame sigil, fire magic icon.")
ASSETS['card_aqua']         = _card('aqua',          "Glowing blue water droplet, water magic icon.")
ASSETS['card_terra']        = _card('terra',         "Stone fist or rocky shard, brown-gold earth tones, earth magic icon.")
ASSETS['card_aero']         = _card('aero',          "Green spiral wind gust, wind magic icon.")
ASSETS['card_fulgis']       = _card('fulgis',        "Golden lightning bolt with electric glow, lightning magic icon.")
ASSETS['card_glacis']       = _card('glacis',        "Pale blue snowflake or ice spear with frosty glow, ice magic icon.")
ASSETS['card_cure_leaf']    = _card('cure_leaf',     "Bright green leaf with soft warm healing glow, healing icon.")
ASSETS['card_holy']         = _card('holy',          "Golden-white starburst with sacred divine glow, light/holy icon.")
ASSETS['card_void']         = _card('void',          "Purple-black orb with dark vortex and faint violet haze, void magic icon.")
ASSETS['card_bomb_flask']   = _card('bomb_flask',    "Round bomb flask with burning fuse, orange ember glow, item icon.")
ASSETS['card_astral_aegis'] = _card('astral_aegis',  "Miniature celestial wolf-dragon silhouette, blue cosmic background, legendary summon icon.")

# ── Projectiles ────────────────────────────────────────────────────────────────
ASSETS['proj_card'] = (
    'vfx/proj_card.png',
    _p(GLOBAL, _VFX,
       "Small glowing blue-gold magical card projectile traveling to the right. "
       "Angled forward in flight, trailing pale blue arcane particles behind it. "
       "Full projectile fits within frame with room around edges."),
    'rd_pro__fantasy', 80, 64, True,
)
ASSETS['proj_sword_beam'] = (
    'vfx/proj_sword_beam.png',
    _p(GLOBAL, _VFX,
       "Blue crescent sword beam projectile traveling to the right. "
       "Sharp curved arc shape, bright leading edge, dark trailing edge. "
       "Full crescent fits within frame."),
    'rd_pro__fantasy', 128, 80, True,
)
ASSETS['proj_fireball'] = (
    'vfx/proj_fireball.png',
    _p(GLOBAL, _VFX,
       "Fireball projectile traveling to the right. Orange-red outer flame, "
       "bright yellow core, small ember trail behind. Fire elemental. "
       "Full fireball fits within frame."),
    'rd_pro__fantasy', 80, 64, True,
)
ASSETS['proj_ice_lance'] = (
    'vfx/proj_ice_lance.png',
    _p(GLOBAL, _VFX,
       "Ice spear projectile traveling to the right. Long pale-blue lance with "
       "crystalline facets, frosty sparkle trail behind. Ice elemental. "
       "Full lance including tip fits within frame."),
    'rd_pro__fantasy', 128, 64, True,
)
ASSETS['proj_lightning'] = (
    'vfx/proj_lightning.png',
    _p(GLOBAL, _VFX,
       "Lightning bolt projectile traveling to the right. Jagged golden arc "
       "with branching sub-arcs, high contrast electric white core. "
       "Full bolt fits within frame."),
    'rd_pro__fantasy', 128, 80, True,
)
ASSETS['proj_wind_crescent'] = (
    'vfx/proj_wind_crescent.png',
    _p(GLOBAL, _VFX,
       "Wind crescent gust projectile traveling to the right. Green swirling "
       "crescent shape, small leaves and air-particle trail. Wind elemental. "
       "Full crescent fits within frame."),
    'rd_pro__fantasy', 96, 80, True,
)
ASSETS['proj_void_orb'] = (
    'vfx/proj_void_orb.png',
    _p(GLOBAL, _VFX,
       "Void orb projectile traveling to the right. Purple-black sphere with "
       "smoky violet trail, faint gravitational distortion at edges. Void elemental. "
       "Full orb fits within frame."),
    'rd_pro__fantasy', 80, 64, True,
)

# ── Elemental VFX ──────────────────────────────────────────────────────────────
ASSETS['vfx_fire_t1']     = ('vfx/fire_t1.png',
    _p(GLOBAL, _VFX, "Ignis — small fire burst impact. Orange flame splash, a few rising sparks."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_fire_t2']     = ('vfx/fire_t2.png',
    _p(GLOBAL, _VFX, "Ignora — medium circular flame eruption. Red-orange ring of fire, embers rising outward."),
    'rd_pro__fantasy', 128, 128, True)
ASSETS['vfx_fire_t3']     = ('vfx/fire_t3.png',
    _p(GLOBAL, _VFX, "Ignaeon — large astral flame pillar. Golden-orange fire column, glowing magic circle at base, star embers."),
    'rd_pro__fantasy', 192, 192, True)

ASSETS['vfx_ice_t1']      = ('vfx/ice_t1.png',
    _p(GLOBAL, _VFX, "Glacis — small ice shard impact. Blue-white crystal shards radiating outward."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_ice_t2']      = ('vfx/ice_t2.png',
    _p(GLOBAL, _VFX, "Glacora — medium frost lance eruption. Ice spires from ground, snow particle cloud."),
    'rd_pro__fantasy', 128, 128, True)
ASSETS['vfx_ice_t3']      = ('vfx/ice_t3.png',
    _p(GLOBAL, _VFX, "Glacaeon — large crystalline ice bloom. Massive frost burst, glowing blue-white magic circle, shimmering crystal shards."),
    'rd_pro__fantasy', 192, 192, True)

ASSETS['vfx_lightning_t1']= ('vfx/lightning_t1.png',
    _p(GLOBAL, _VFX, "Fulgis — small lightning strike impact. Yellow bolt hitting ground, spark burst."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_lightning_t2']= ('vfx/lightning_t2.png',
    _p(GLOBAL, _VFX, "Fulgora — branching lightning bolt. Multiple arcs hitting target, electric ground crackle."),
    'rd_pro__fantasy', 128, 128, True)
ASSETS['vfx_lightning_t3']= ('vfx/lightning_t3.png',
    _p(GLOBAL, _VFX, "Fulgaeon — massive golden lightning storm. Multiple bright arcs across wide area, glowing magic circle."),
    'rd_pro__fantasy', 256, 192, True)

ASSETS['vfx_wind_t1']     = ('vfx/wind_t1.png',
    _p(GLOBAL, _VFX, "Aero — small wind slash. Green crescent gust with spiral air lines."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_wind_t2']     = ('vfx/wind_t2.png',
    _p(GLOBAL, _VFX, "Aerora — medium wind vortex. Spiraling gust with leaves and circular wind lines."),
    'rd_pro__fantasy', 128, 128, True)

ASSETS['vfx_water_t1']    = ('vfx/water_t1.png',
    _p(GLOBAL, _VFX, "Aqua — small water splash impact. Blue droplets radiating outward."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_water_t2']    = ('vfx/water_t2.png',
    _p(GLOBAL, _VFX, "Aquora — medium spiraling water column. Blue-white water arcing upward and outward."),
    'rd_pro__fantasy', 128, 128, True)

ASSETS['vfx_healing']     = ('vfx/healing.png',
    _p(GLOBAL, _VFX, "Healing magic burst. Gentle green-white glow, small glowing orbs of life energy rising upward."),
    'rd_pro__fantasy', 96, 96, True)
ASSETS['vfx_hit_spark']   = ('vfx/hit_spark.png',
    _p(GLOBAL, _VFX, "Hit impact spark. White-yellow starburst, sharp pixel spikes radiating from center."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_holy_t1']     = ('vfx/holy_t1.png',
    _p(GLOBAL, _VFX, "Lucis — small holy starburst. Gold-white sparkle impact, sacred divine light."),
    'rd_pro__fantasy', 64, 64, True)
ASSETS['vfx_void_t1']     = ('vfx/void_t1.png',
    _p(GLOBAL, _VFX, "Nyxis — small void shadow burst. Purple-black energy explosion, violet particle haze."),
    'rd_pro__fantasy', 64, 64, True)

# ── Summons ─────────────────────────────────────────────────────────────────────
ASSETS['summon_astral_aegis'] = (
    'vfx/summon_astral_aegis.png',
    _p(GLOBAL, _VFX,
       "Astral Aegis summon creature — large celestial wolf-dragon. "
       "White and pale blue fur with flowing cosmic energy mane, gold astral armor lines along body, "
       "luminous eyes, rotating golden rune rings orbiting it, blue star particle cloud. "
       "Epic JRPG summon sprite."),
    'rd_pro__fantasy', 256, 256, True,
)
ASSETS['summon_astral_aegis_circle'] = (
    'vfx/summon_astral_aegis_circle.png',
    _p(GLOBAL, _VFX,
       "Astral Aegis summon magic circle. Large blue-white circular sigil, "
       "compass rose at center, ancient arcane script in concentric rings, "
       "rotating star glyph band, glowing celestial light."),
    'rd_pro__fantasy', 256, 256, True,
)
ASSETS['summon_arrival_flash'] = (
    'vfx/summon_arrival_flash.png',
    _p(GLOBAL, _VFX,
       "Summon arrival flash burst. Blue-white star-shard explosion, "
       "circular rune flare ring, divine arrival light effect."),
    'rd_pro__fantasy', 192, 192, True,
)

# ── Environmental Objects ──────────────────────────────────────────────────────
ASSETS['tree_pine_small'] = (
    'overworld/objects/tree_pine_small.png',
    _p(GLOBAL, _OW_ENV,
       "Small evergreen pine tree. Dark green layered needles, brown trunk, "
       "soft warm highlight on one side. Three-quarter isometric angle."),
    'rd_pro__fantasy', 64, 96, True,
)
ASSETS['tree_pine_large'] = (
    'overworld/objects/tree_pine_large.png',
    _p(GLOBAL, _OW_ENV,
       "Tall evergreen pine tree. Multiple dark green branch layers with yellow-green highlights, "
       "broad silhouette readable at distance. Three-quarter isometric angle."),
    'rd_pro__fantasy', 96, 128, True,
)
ASSETS['tree_broadleaf'] = (
    'overworld/objects/tree_broadleaf.png',
    _p(GLOBAL, _OW_ENV,
       "Round leafy fantasy tree. Thick trunk, full lush green canopy, "
       "painterly pixel texture, soft warm highlight. Three-quarter isometric angle."),
    'rd_pro__fantasy', 96, 128, True,
)
ASSETS['tree_dead'] = (
    'overworld/objects/tree_dead.png',
    _p(GLOBAL, _OW_ENV,
       "Twisted dead tree. Leafless, dark gray-brown bark, crooked branching, "
       "ominous fantasy obstacle. Three-quarter isometric angle."),
    'rd_pro__fantasy', 80, 128, True,
)
ASSETS['bush_plain'] = (
    'overworld/objects/bush_plain.png',
    _p(GLOBAL, _OW_ENV,
       "Small round green bush. Low dense leaf cluster, a few tiny white flowers, "
       "grass at base. Fantasy overworld prop."),
    'rd_pro__fantasy', 64, 48, True,
)
ASSETS['bush_blue_berries'] = (
    'overworld/objects/bush_blue_berries.png',
    _p(GLOBAL, _OW_ENV,
       "Green berry bush with small clustered blue berries. "
       "Fantasy gathering/resource node. Grass at base."),
    'rd_pro__fantasy', 64, 48, True,
)
ASSETS['rock_small'] = (
    'overworld/objects/rock_small.png',
    _p(GLOBAL, _OW_ENV,
       "Small gray stone. Soft moss patch and grass blades at base. "
       "Simple fantasy overworld pebble prop."),
    'rd_pro__fantasy', 48, 48, True,
)
ASSETS['rock_cluster'] = (
    'overworld/objects/rock_cluster.png',
    _p(GLOBAL, _OW_ENV,
       "Cluster of three or four gray stones. Varied sizes, moss between stones, "
       "tiny wildflower at edge. Medium overworld obstacle."),
    'rd_pro__fantasy', 96, 64, True,
)
ASSETS['rock_boulder'] = (
    'overworld/objects/rock_boulder.png',
    _p(GLOBAL, _OW_ENV,
       "Large mossy boulder. Angular faceted stone surface, gray with green moss patches, "
       "small blue wildflowers growing at base. Overworld obstacle."),
    'rd_pro__fantasy', 96, 80, True,
)
ASSETS['crystal_blue'] = (
    'overworld/objects/crystal_blue.png',
    _p(GLOBAL, _OW_ENV,
       "Blue crystal cluster. Glowing pale blue crystal formations growing from stone and grass, "
       "inner light glow, magical arcane node."),
    'rd_pro__fantasy', 64, 80, True,
)
ASSETS['crystal_purple'] = (
    'overworld/objects/crystal_purple.png',
    _p(GLOBAL, _OW_ENV,
       "Purple crystal cluster. Glowing violet-purple crystal formations, "
       "inner arcane glow, void/occult resource node."),
    'rd_pro__fantasy', 64, 80, True,
)
ASSETS['chest_wooden'] = (
    'overworld/objects/chest_wooden.png',
    _p(GLOBAL, _OW_ENV,
       "Small closed wooden treasure chest. Metal band and latch, "
       "dark wood grain, fantasy RPG loot chest."),
    'rd_pro__fantasy', 48, 40, True,
)
ASSETS['chest_astral'] = (
    'overworld/objects/chest_astral.png',
    _p(GLOBAL, _OW_ENV,
       "Ornate magical chest. Blue-and-gold lacquered wood, "
       "compass star emblem on lid, soft blue magical glow at seam, card reward chest."),
    'rd_pro__fantasy', 48, 40, True,
)
ASSETS['signpost_single'] = (
    'overworld/objects/signpost_single.png',
    _p(GLOBAL, _OW_ENV,
       "Simple wooden fantasy signpost. Single plank arm pointing to one side, "
       "weathered post, grass at base. No readable text on sign."),
    'rd_pro__fantasy', 48, 64, True,
)
ASSETS['tree_stump'] = (
    'overworld/objects/tree_stump.png',
    _p(GLOBAL, _OW_ENV,
       "Cut tree stump. Short with visible growth rings on top, "
       "moss on side, small grass blades at base."),
    'rd_pro__fantasy', 48, 40, True,
)
ASSETS['flower_patch_white'] = (
    'overworld/objects/flower_patch_white.png',
    _p(GLOBAL, _OW_ENV,
       "Small patch of white wildflowers. Green stems and leaves, "
       "clustered small white blooms, ground decoration."),
    'rd_pro__fantasy', 64, 40, True,
)
ASSETS['flower_patch_purple'] = (
    'overworld/objects/flower_patch_purple.png',
    _p(GLOBAL, _OW_ENV,
       "Small patch of purple wildflowers. Green stems, clustered lavender-purple blooms, "
       "fantasy meadow ground decoration."),
    'rd_pro__fantasy', 64, 40, True,
)

# ── Terrain Tiles ──────────────────────────────────────────────────────────────
ASSETS['terrain_grassland'] = (
    'overworld/terrain/grassland.png',
    _p(GLOBAL, _OW_TERRAIN,
       "Flat grassy terrain tile. Soft varied green grass texture, "
       "tiny scattered wildflowers, small pebbles, gentle color variation. "
       "No trees, no rocks, no large props — base map tile only."),
    'rd_pro__isometric', 256, 256, False,
)
ASSETS['terrain_dirt_path'] = (
    'overworld/terrain/dirt_path.png',
    _p(GLOBAL, _OW_TERRAIN,
       "Flat dirt path tile. Worn beige-brown compacted earth, soft grassy edges, "
       "small embedded pebbles. Seamless route tile."),
    'rd_pro__isometric', 256, 128, False,
)
ASSETS['terrain_cobblestone'] = (
    'overworld/terrain/cobblestone.png',
    _p(GLOBAL, _OW_TERRAIN,
       "Flat cobblestone road tile. Pale tan and gray uneven stones, "
       "hand-laid pattern, moss growing in cracks. Fantasy village road tile."),
    'rd_pro__isometric', 256, 128, False,
)

# ── UI / Title Screen ──────────────────────────────────────────────────────────
ASSETS['card_back_flat'] = (
    'ui/card_back_flat.png',
    _p(GLOBAL, _UI,
       "Flat dead-on view of a fantasy card back. Deep navy textured surface, "
       "antique gold compass rose centered, thin concentric circle lines, "
       "celestial star chart dots, ornate gold border, subtle worn paper texture. "
       "Perfectly symmetrical, no perspective tilt, no glow."),
    'rd_pro__fantasy', 128, 192, True,
)
ASSETS['card_back_glow'] = (
    'ui/card_back_glow.png',
    _p(GLOBAL, _UI,
       "Animated-variant fantasy card back. Deep navy compass rose design, "
       "floating slightly, soft blue magical glow around edges, "
       "tiny orbiting astral particles, faint star-ring aura. "
       "Title screen animation variant, dark background."),
    'rd_pro__fantasy', 128, 192, False,
)
ASSETS['particle_blue_star'] = (
    'vfx/particle_blue_star.png',
    _p(GLOBAL, _VFX,
       "Tiny blue-white star sparkle particle. Simple 4-point or 8-point star shape, "
       "clean pixel art, glow center. Single isolated particle."),
    'rd_pro__fantasy', 32, 32, True,
)
ASSETS['particle_gold_spark'] = (
    'vfx/particle_gold_spark.png',
    _p(GLOBAL, _VFX,
       "Tiny gold magical sparkle particle. Bright gold pixel star or diamond shape, "
       "clean pixel art. Single isolated particle."),
    'rd_pro__fantasy', 32, 32, True,
)

# ─── Batches (Section 16 priority order) ──────────────────────────────────────

BATCHES = {
    'priority': [
        'oden_overworld_idle', 'oden_run_cardinal', 'oden_run_diagonal',
        'oden_battle_idle', 'oden_battle_cast', 'oden_battle_slash',
        'oden_battle_throw', 'oden_battle_hit', 'oden_battle_victory',
        'terrain_grassland', 'terrain_dirt_path', 'terrain_cobblestone',
        'tree_pine_small', 'tree_pine_large', 'tree_broadleaf',
        'rock_small', 'rock_cluster', 'rock_boulder', 'crystal_blue',
        'tile_player', 'tile_enemy', 'tile_neutral', 'tile_broken', 'tile_magic_circle',
        'slime_green', 'goblin_mage', 'wolf_beast', 'pumpkin_imp',
        'card_sword_slash', 'card_ranged', 'card_ignis', 'card_aqua',
        'card_terra', 'card_aero', 'card_fulgis', 'card_glacis', 'card_cure_leaf',
        'vfx_fire_t1', 'vfx_lightning_t1', 'vfx_ice_t1', 'vfx_wind_t1',
        'vfx_healing', 'vfx_hit_spark',
        'card_back_flat', 'card_back_glow',
        'summon_astral_aegis', 'summon_astral_aegis_circle',
    ],
    'characters': [
        'oden_overworld_idle', 'oden_run_cardinal', 'oden_run_diagonal',
        'oden_battle_idle', 'oden_battle_cast', 'oden_battle_slash',
        'oden_battle_throw', 'oden_battle_hit', 'oden_battle_victory',
    ],
    'enemies': [
        'slime_green', 'slime_aqua', 'slime_ember', 'slime_void',
        'goblin_mage', 'wolf_beast', 'pumpkin_imp', 'lizard_knight',
        'ruin_guardian', 'astral_wisp',
    ],
    'tiles': [
        'tile_player', 'tile_enemy', 'tile_neutral', 'tile_broken', 'tile_magic_circle',
    ],
    'cards': [
        'card_sword_slash', 'card_ranged', 'card_ignis', 'card_aqua',
        'card_terra', 'card_aero', 'card_fulgis', 'card_glacis', 'card_cure_leaf',
        'card_holy', 'card_void', 'card_bomb_flask', 'card_astral_aegis',
    ],
    'vfx': [
        'vfx_fire_t1', 'vfx_fire_t2', 'vfx_fire_t3',
        'vfx_ice_t1', 'vfx_ice_t2', 'vfx_ice_t3',
        'vfx_lightning_t1', 'vfx_lightning_t2', 'vfx_lightning_t3',
        'vfx_wind_t1', 'vfx_wind_t2',
        'vfx_water_t1', 'vfx_water_t2',
        'vfx_healing', 'vfx_hit_spark', 'vfx_holy_t1', 'vfx_void_t1',
        'proj_card', 'proj_sword_beam', 'proj_fireball', 'proj_ice_lance',
        'proj_lightning', 'proj_wind_crescent', 'proj_void_orb',
        'summon_astral_aegis', 'summon_astral_aegis_circle', 'summon_arrival_flash',
        'particle_blue_star', 'particle_gold_spark',
    ],
    'environment': [
        'terrain_grassland', 'terrain_dirt_path', 'terrain_cobblestone',
        'tree_pine_small', 'tree_pine_large', 'tree_broadleaf', 'tree_dead',
        'bush_plain', 'bush_blue_berries',
        'rock_small', 'rock_cluster', 'rock_boulder',
        'crystal_blue', 'crystal_purple',
        'chest_wooden', 'chest_astral', 'signpost_single', 'tree_stump',
        'flower_patch_white', 'flower_patch_purple',
    ],
    'ui': [
        'card_back_flat', 'card_back_glow',
        'particle_blue_star', 'particle_gold_spark',
    ],
}

# Cost reference (rd_pro flat rate):
COST_PER_IMAGE = 0.18  # USD per image, all rd_pro__* styles

# ─── API ───────────────────────────────────────────────────────────────────────

def _headers():
    return {'X-RD-Token': RD_KEY, 'Content-Type': 'application/json'}


def get_credits() -> float:
    resp = requests.get(f"{RD_BASE}/inferences/credits", headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get('credits', data.get('remaining_balance', data.get('balance', 0.0)))


def rd_generate(prompt: str, style: str, width: int, height: int,
                remove_bg: bool = True, check_cost: bool = False) -> tuple:
    """
    Returns (image_bytes_or_None, cost, remaining_balance).
    With check_cost=True, returns (None, estimated_cost, current_balance) without spending.
    """
    payload = {
        'prompt': prompt,
        'prompt_style': style,
        'width': width,
        'height': height,
        'num_images': 1,
        'remove_bg': remove_bg,
    }
    if check_cost:
        payload['check_cost'] = True
    resp = requests.post(f"{RD_BASE}/inferences",
                         headers=_headers(),
                         json=payload,
                         timeout=180)
    resp.raise_for_status()
    data = resp.json()
    cost      = float(data.get('balance_cost', COST_PER_IMAGE))
    remaining = float(data.get('remaining_balance', 0.0))
    if check_cost or not data.get('base64_images'):
        return None, cost, remaining
    img_bytes = base64.b64decode(data['base64_images'][0])
    return img_bytes, cost, remaining


def save_image(img_bytes: bytes, save_path: Path) -> tuple:
    save_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(BytesIO(img_bytes))
    img.save(save_path, 'PNG')
    return img.size


# ─── Runner ────────────────────────────────────────────────────────────────────

def run_assets(keys: list, dry_run: bool = False, skip_existing: bool = True, auto_yes: bool = False):
    if not RD_KEY and not dry_run:
        print("ERROR: RETRODIFFUSION_API_KEY not set.")
        print("Add to .env:  RETRODIFFUSION_API_KEY=your_key_here")
        sys.exit(1)

    balance = None
    if RD_KEY and not dry_run:
        try:
            balance = get_credits()
            print(f"\nBalance: ${balance:.4f}")
        except Exception as e:
            print(f"Warning: could not fetch balance — {e}")

    # Build target list
    targets = []
    skipped = 0
    for key in keys:
        if key not in ASSETS:
            print(f"  unknown key: {key!r}")
            continue
        save_rel, prompt, style, w, h, remove_bg = ASSETS[key]
        save_path = ASSETS_ROOT / save_rel
        if skip_existing and save_path.exists():
            skipped += 1
            continue
        targets.append((key, save_rel, prompt, style, w, h, remove_bg, save_path))

    if skipped:
        print(f"  skipping {skipped} already-generated assets (use --force to regenerate)")

    if not targets:
        print("Nothing to generate.")
        return

    est_cost = len(targets) * COST_PER_IMAGE
    col_w = max(len(k) for k, *_ in targets)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}{len(targets)} assets  "
          f"(estimated cost: ${est_cost:.2f})\n")
    for key, save_rel, _, style, w, h, _, _ in targets:
        exists = ' ✓' if (ASSETS_ROOT / save_rel).exists() else ''
        print(f"  {key:{col_w}}  {style:25}  {w:>3}x{h:<3}  → {save_rel}{exists}")

    if dry_run:
        print(f"\n(dry-run: no API calls made)")
        if balance is None and RD_KEY:
            try:
                balance = get_credits()
                print(f"Current balance: ${balance:.4f}  →  after run: ~${balance - est_cost:.4f}")
            except Exception:
                pass
        return

    if not auto_yes:
        print(f"\nProceed? [y/N] ", end='', flush=True)
        if input().strip().lower() not in ('y', 'yes'):
            print("Aborted.")
            return

    total_cost = 0.0
    errors = []
    for i, (key, save_rel, prompt, style, w, h, remove_bg, save_path) in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {key} ...", end='', flush=True)
        try:
            img_bytes, cost, remaining = rd_generate(prompt, style, w, h, remove_bg)
            size = save_image(img_bytes, save_path)
            total_cost += cost
            print(f" {size[0]}x{size[1]}  cost=${cost:.4f}  balance=${remaining:.4f}")
            print(f"  → {save_path}")
            if i < len(targets):
                time.sleep(0.8)
        except requests.HTTPError as e:
            msg = f"HTTP {e.response.status_code}: {e.response.text[:160]}"
            print(f" FAILED — {msg}")
            errors.append((key, msg))
        except Exception as e:
            print(f" FAILED — {e}")
            errors.append((key, str(e)))

    print(f"\n{'─'*60}")
    print(f"Done: {len(targets) - len(errors)}/{len(targets)} generated  "
          f"total_cost=${total_cost:.4f}")
    if errors:
        print(f"\nFailed ({len(errors)}):")
        for key, msg in errors:
            print(f"  {key}: {msg}")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="RetroDiffusion pixel-art generator — Card Knight: Astral Arcana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Batches:  priority | characters | enemies | tiles | cards | vfx | environment | ui

Cost reference:  all rd_pro__* styles = $0.18/image

Examples:
  python3 generate_rd_assets.py --list
  python3 generate_rd_assets.py --credits
  python3 generate_rd_assets.py --dry-run --batch priority
  python3 generate_rd_assets.py --batch priority
  python3 generate_rd_assets.py --asset slime_green goblin_mage
  python3 generate_rd_assets.py --force --asset oden_battle_idle
        """,
    )
    p.add_argument('--list',    action='store_true', help="List all assets")
    p.add_argument('--credits', action='store_true', help="Show balance")
    p.add_argument('--test',    action='store_true', help="Fire one small test image to validate API")
    p.add_argument('--batch',   choices=list(BATCHES.keys()), help="Run a named batch")
    p.add_argument('--asset',   nargs='+', metavar='KEY',     help="Run specific asset(s)")
    p.add_argument('--dry-run', action='store_true', help="Show plan, no API calls")
    p.add_argument('--force',   action='store_true', help="Regenerate existing files")
    p.add_argument('--yes',     action='store_true', help="Skip confirmation prompt")
    args = p.parse_args()

    if args.list:
        total = len(ASSETS)
        exist = sum(1 for path, *_ in ASSETS.values() if (ASSETS_ROOT / path).exists())
        print(f"=== Assets ({exist}/{total} already generated) ===")
        for key, (path, _, style, w, h, _) in ASSETS.items():
            mark = '✓' if (ASSETS_ROOT / path).exists() else ' '
            print(f"  [{mark}] {key:45}  {style:25}  {w}x{h}")
        print(f"\n=== Batches ===")
        for name, keys in BATCHES.items():
            cost = len(keys) * COST_PER_IMAGE
            print(f"  {name:15} {len(keys):3} assets  ~${cost:.2f}")
        print(f"\n  Full catalog:  {total} assets  ~${total * COST_PER_IMAGE:.2f}")
        return

    if args.credits:
        if not RD_KEY:
            print("ERROR: RETRODIFFUSION_API_KEY not set in .env")
            sys.exit(1)
        bal = get_credits()
        total = len(ASSETS)
        print(f"Balance:        ${bal:.4f}")
        print(f"Full catalog:   {total} assets × $0.18 = ${total * COST_PER_IMAGE:.2f}")
        print(f"Priority batch: {len(BATCHES['priority'])} assets × $0.18 = "
              f"${len(BATCHES['priority']) * COST_PER_IMAGE:.2f}")
        print(f"After full run: ~${bal - total * COST_PER_IMAGE:.2f} remaining")
        return

    if args.test:
        if not RD_KEY:
            print("ERROR: RETRODIFFUSION_API_KEY not set in .env")
            sys.exit(1)
        print("Sending test request: 64x64 rd_pro__fantasy green slime ...")
        try:
            img_bytes, cost, remaining = rd_generate(
                "cute green slime enemy, pixel art, transparent background",
                'rd_pro__fantasy', 64, 64, True,
            )
            out = ASSETS_ROOT / 'test_rd_output.png'
            save_image(img_bytes, out)
            print(f"  OK — cost=${cost:.4f}  balance=${remaining:.4f}")
            print(f"  saved → {out}")
        except requests.HTTPError as e:
            print(f"  FAILED — HTTP {e.response.status_code}: {e.response.text[:300]}")
        except Exception as e:
            print(f"  FAILED — {e}")
        return

    if args.batch:
        run_assets(BATCHES[args.batch], dry_run=args.dry_run,
                   skip_existing=not args.force, auto_yes=args.yes)
    elif args.asset:
        run_assets(args.asset, dry_run=args.dry_run,
                   skip_existing=not args.force, auto_yes=args.yes)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
