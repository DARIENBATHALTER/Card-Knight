#!/usr/bin/env python3
"""
Generate game sound effects via ElevenLabs Sound Effects API.
Saves to assets/sfx/ — each file is auto-loaded by the sfx module at startup.

Usage:
    python3 generate_sfx.py               # all sounds not yet on disk
    python3 generate_sfx.py buster_shoot  # specific stem(s)
    python3 generate_sfx.py --redo        # regenerate everything, overwriting
"""
from __future__ import annotations
import os, sys, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
if not API_KEY:
    sys.exit('ELEVENLABS_API_KEY not set in .env')

BASE    = Path(__file__).parent
OUT_DIR = BASE / 'assets' / 'sfx'
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_URL = 'https://api.elevenlabs.io/v1/sound-generation'

# (stem, prompt, duration_seconds)   duration=None → API auto-chooses
SOUNDS: list[tuple[str, str, float | None]] = [

    # ── Buster ────────────────────────────────────────────────────────────────
    ('buster_shoot',
     'Quick snap of a playing card spinning and slicing through air, sharp card flick whoosh',
     0.6),
    ('buster_charged',
     'Powerful charged magical card blast releasing — deep resonant thump with electric crackle and energy burst',
     1.2),
    ('buster_charge_start',
     'Energy beginning to build up, soft electrical hum rising in pitch, gathering power',
     0.8),
    ('buster_charge_full',
     'Power-up complete chime — clean bright crystalline ping with shimmering harmonic overtone, capacitor fully charged ready to release',
     0.8),

    # ── Fire ──────────────────────────────────────────────────────────────────
    ('ignite',
     'Small single flame igniting with a crisp pop, one tongue of fire bursting to life',
     0.6),
    ('scorch',
     'Medium fire burst whoosh, intense wave of flame rushing outward with heat',
     0.9),
    ('immolate',
     'Massive roaring fire pillar erupts, thunderous deep flame explosion engulfing everything',
     1.6),

    # ── Ice ───────────────────────────────────────────────────────────────────
    ('freeze',
     'Ice rapidly crystallising, crisp cracking and delicate tinkling freeze forming',
     0.8),
    ('icicle',
     'Ice spike shattering into fragments, sharp crystalline break and scatter',
     0.7),
    ('blizzard',
     'Howling blizzard storm, swirling ice vortex with biting freezing wind roar',
     1.8),

    # ── Lightning ─────────────────────────────────────────────────────────────
    ('jolt',
     'Single sharp electric zap, quick lightning bolt snap and sizzle',
     0.5),
    ('shock',
     'Double electric crack, two sharp lightning strikes in rapid succession',
     0.7),
    ('electrocute',
     'Sustained crackling electrical arc, intense prolonged lightning buzzing and snapping',
     1.8),

    # ── Wind / Earth ──────────────────────────────────────────────────────────
    ('gust',
     'Light wind gust sweeping past, soft breezy air rush',
     0.6),
    ('gale',
     'Powerful horizontal wind burst, strong gale tearing through with force',
     1.0),
    ('tempest',
     'Violent storm vortex howl, whirling winds and distant thunder combined',
     1.8),
    ('crack',
     'Heavy boulder splitting, solid rock cracking apart with a deep impact thud',
     0.7),
    ('quake',
     'Ground tremor rumble, low frequency earth shaking with debris rattling',
     1.4),
    ('landslide',
     'Massive rockslide avalanche, enormous boulders crashing and tumbling with ground-shaking impact',
     2.2),

    # ── Light / Holy ──────────────────────────────────────────────────────────
    ('sanctify',
     'Holy bell chime resonating, bright divine tone with crystalline shimmer and warmth',
     1.0),
    ('exorcise',
     'Holy energy burst, radiant light explosion with angelic high resonance',
     1.1),
    ('absolution',
     'Grand divine energy wave, powerful holy surge washing over with choir shimmer and sacred resonance',
     2.0),

    # ── Dark ──────────────────────────────────────────────────────────────────
    ('hex',
     'Dark curse cast, low ominous magical drone with shadowy sinister whisper',
     0.9),
    ('curse',
     'Ominous dark energy swirl, shadowy malevolent hiss and spreading dark magic pulse',
     1.1),
    ('oblivion',
     'Void implosion, everything sucked into darkness with deep resonant collapse and silence',
     2.0),

    # ── Heal / Recovery ───────────────────────────────────────────────────────
    ('heal',
     'Gentle healing chime, soft warm sparkle with light bell shimmer',
     0.7),
    ('cure',
     'Restorative healing sparkle, brighter warm magical chime cascade',
     0.9),
    ('recover',
     'Health restoration wave, fuller healing surge with gentle glowing resonance',
     1.1),
    ('rejuvenate',
     'Powerful life force surging back, grand healing energy cascade with radiant shimmer',
     1.6),
    ('antidote',
     'Purifying cleanse, soft bubbling potion fizz and gentle cleansing shimmer',
     0.8),

    # ── Status clear ──────────────────────────────────────────────────────────
    ('voice',
     'Silence breaking, voice restored — a clear musical note pings free',
     0.6),
    ('wake',
     'Alerting wake-up, bright snapping bell jolt',
     0.5),
    ('stonebreak',
     'Stone prison shattering, solid rock cracking apart into pieces',
     0.8),
    ('return',
     'Gentle restoration, calm soft magical whoosh returning to normal',
     0.8),
    ('raise',
     'Revival energy rising upward, sweeping magical lift',
     1.0),
    ('revive',
     'Phoenix revival chime, triumphant warm restoration bell with golden shimmer',
     1.3),
    ('resurrect',
     'Grand resurrection surge, powerful divine burst of life energy returning in full glory',
     2.2),

    # ── Status inflict ────────────────────────────────────────────────────────
    ('toxin',
     'Mild venom drip, small toxic bubble pop and faint venomous hiss',
     0.6),
    ('poison',
     'Spreading poison, toxic bubbling and ominous thick dripping venom',
     0.9),
    ('mute',
     'Sound abruptly cutting off, sudden dull thud muffling all noise',
     0.5),
    ('silence',
     'Heavy silence wave spreading, all sound deeply dampened and muffled',
     0.8),
    ('snooze',
     'Gentle sleep magic washing over, dreamy lullaby swoosh descending softly',
     0.9),
    ('slumber',
     'Deep slumber descending, heavier sleep magic with slow dream-like whoosh',
     1.2),
    ('petrify',
     'Body freezing into stone, grinding crystalline hardening crack spreading',
     1.1),
    ('entomb',
     'Heavy stone sarcophagus lid slamming shut with a deep resonant thud',
     1.0),
    ('delay',
     'Time slowing warp, clock ticking slower with eerie descending pitch bend',
     1.0),

    # ── Utility ───────────────────────────────────────────────────────────────
    ('halt',
     'Time stopped, sharp clock-stop snap and everything freezing in silence',
     0.8),
    ('quicken',
     'Quick speed boost whoosh, energetic rush of sudden acceleration',
     0.6),
    ('allegro',
     'Party haste surge, bright energetic multiple whooshes of speed layering',
     1.0),
    ('protect',
     'Shield barrier activating, solid energy snapping into place with low resonant hum',
     0.9),
    ('teleport',
     'Spatial warp teleport, swirling portal energy opening and displacement whoosh',
     1.0),
    ('dash',
     'Sharp dash sprint burst, quick air explosion and speed blur',
     0.5),

    # ── Weapon cards ──────────────────────────────────────────────────────────
    ('sword',
     'Sharp clean sword slash, single blade swing cutting through air',
     0.5),
    ('wideblade',
     'Broad heavy blade swing, wide powerful sword slash with significant air displacement',
     0.7),
    ('partisan',
     'Spear thrust forward, pole lance stabbing with focused whoosh',
     0.5),
    ('excalibur',
     'Legendary holy sword strike, radiant blade slash with divine shimmer and light resonance',
     1.3),
    ('shortbow',
     'Short bow release, quick bowstring snap and arrow flight whistle',
     0.5),
    ('longbow',
     'Longbow arrow loose, deep bowstring thrum and arrow whistling through the air',
     0.7),

    # ── Combat feedback ───────────────────────────────────────────────────────
    ('oden_hurt',
     'Young adult male pain grunt, sharp gasp and short pained grunt from taking a hit in battle',
     0.6),
    ('enemy_hit',
     'Blunt magical impact, card-strike thud hitting an enemy with resonant force',
     0.5),
    ('enemy_explode',
     'Playing card enemy defeated and exploding, magical burst of cards and energy flying apart',
     1.3),
    ('player_guard',
     'Defensive block, impact deflected off energy shield with solid clunk',
     0.5),
    ('panel_crack',
     'Floor tile panel cracking under foot, sharp fracture snap',
     0.5),

    # ── UI / menus ────────────────────────────────────────────────────────────
    ('ui_confirm',
     'Clean bright menu confirm beep, short positive UI click',
     0.5),
    ('ui_cancel',
     'Short low menu cancel click, brief negative UI dismiss blip',
     0.5),
    ('ui_cursor',
     'Soft menu cursor navigation tick, light blip',
     0.5),
    ('ui_dialog_open',
     'Dialogue box popping open, quick soft whoosh and text box appear click',
     0.5),
    ('ui_tick',
     'Single typewriter letter tick, soft text blip',
     0.5),
    ('custom_open',
     'Card deck selection screen opening, satisfying card shuffle whoosh and interface snap',
     0.7),
    ('custom_close',
     'Card selection screen snapping closed, quick clean interface dismiss',
     0.5),
    ('card_select',
     'Card picked from hand, satisfying card lift and click',
     0.5),
]


def generate(stem: str, prompt: str, duration: float | None, redo: bool) -> str:
    """Returns 'ok', 'skip', or 'fail'."""
    out_path = OUT_DIR / f'{stem}.mp3'
    if out_path.exists() and not redo:
        print(f'  [skip] {stem}')
        return 'skip'

    payload: dict = {'text': prompt, 'prompt_influence': 0.4}
    if duration is not None:
        payload['duration_seconds'] = duration

    dur_label = f'{duration}s' if duration else 'auto'
    print(f'  → {stem:30s} ({dur_label}) …', flush=True)
    try:
        r = requests.post(
            API_URL,
            headers={'xi-api-key': API_KEY, 'Content-Type': 'application/json'},
            json=payload,
            timeout=90,
        )
        if r.status_code != 200:
            print(f'  ERROR {r.status_code}: {r.text[:300]}')
            return 'fail'
        out_path.write_bytes(r.content)
        kb = len(r.content) // 1024
        print(f'  ✓ {stem}.mp3  ({kb} KB)')
        return 'ok'
    except Exception as e:
        print(f'  ERROR: {e}')
        return 'fail'


def main():
    redo    = '--redo' in sys.argv
    filters = [a for a in sys.argv[1:] if not a.startswith('--')]
    sounds  = [(s, p, d) for s, p, d in SOUNDS if not filters or s in filters]

    print(f'ElevenLabs SFX generator — {len(sounds)} sounds → {OUT_DIR}')
    print(f'Mode: {"REDO (overwrite all)" if redo else "skip existing"}\n')

    counts = {'ok': 0, 'skip': 0, 'fail': 0}
    for stem, prompt, duration in sounds:
        result = generate(stem, prompt, duration, redo)
        counts[result] += 1
        if result == 'ok':
            time.sleep(0.75)   # polite pause between API calls

    print(f'\nDone — {counts["ok"]} generated, {counts["skip"]} skipped, {counts["fail"]} failed.')


if __name__ == '__main__':
    main()
