from dataclasses import dataclass
from typing import List
import constants as C


@dataclass
class ChipData:
    name: str
    code: str        # single letter A-Z or "*"
    damage: int
    element: int
    chip_class: str
    mb: int
    description: str
    rarity: int = 1
    heals: int = 0
    effect_key: str = ""

    def __post_init__(self):
        if not self.effect_key:
            self.effect_key = self.name


# ── Effect resolvers ──────────────────────────────────────────────────────────
# resolve(chip, player, grid, enemies, eff_list) -> None

def _pc(col, row):
    import tile_warp
    return tile_warp.tile_center(col, row)

def _eff():
    import effects
    return effects

def _dmg(entity, damage, element):
    if not entity.alive:
        return
    mult = 2.0 if (element != C.ELEM_NONE and C.ELEM_BEATS.get(element) == entity.element) else 1.0
    entity.take_damage(int(damage * mult), element)


def _add_travel_flash(eff, player_col, row, flash_color=(255, 215, 40)):
    """Insert a shockwave PanelFlash along the row from just past the player to grid edge.
    Use when spawning a TravelingHit so the projectile leaves a lit-up trail of tiles."""
    path = [(c, row) for c in range(player_col + 1, C.GRID_COLS)]
    if path:
        eff.insert(0, _eff().PanelFlash(path, color=flash_color, wave_speed=2.8))


# ── Physical weapons ──────────────────────────────────────────────────────────

def _sword_resolve(chip, player, grid, enemies, eff):
    col, row = player.col + 1, player.row
    for e in enemies:
        if e.col == col and e.row == row and e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().SlashEffect([(col, row)], C.CYAN, 0.3))

def _wideblade_resolve(chip, player, grid, enemies, eff):
    col = player.col + 1
    for e in enemies:
        if e.col == col and e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().SlashEffect([(col, r) for r in range(C.GRID_ROWS)], C.CYAN, 0.3))

def _partisan_resolve(chip, player, grid, enemies, eff):
    row = player.row
    cols = [player.col + 1, player.col + 2]
    cols = [c for c in cols if 0 <= c < C.GRID_COLS]
    for e in enemies:
        if e.col in cols and e.row == row and e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().SlashEffect([(c, row) for c in cols], C.CYAN, 0.3))

def _excalibur_resolve(chip, player, grid, enemies, eff):
    cols = [player.col + i for i in range(1, 4) if player.col + i < C.GRID_COLS]
    for e in enemies:
        if e.col in cols and e.alive:
            _dmg(e, chip.damage, chip.element)
    panels = [(c, r) for c in cols for r in range(C.GRID_ROWS)]
    eff.append(_eff().SlashEffect(panels, C.PURPLE, 0.4))

def _bow_resolve(chip, player, grid, enemies, eff):
    row = player.row
    hit = False
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            _dmg(targets[0], chip.damage, chip.element)
            eff.append(_eff().ProjectileEffect(_pc(player.col, row), _pc(col, row), C.YELLOW, 7))
            hit = True
            break
    if not hit:
        eff.append(_eff().ProjectileEffect(_pc(player.col, row), _pc(C.GRID_COLS - 1, row), C.YELLOW, 7))

def _longbow_resolve(chip, player, grid, enemies, eff):
    row = player.row
    for col in range(player.col + 1, C.GRID_COLS):
        for e in enemies:
            if e.col == col and e.row == row and e.alive:
                _dmg(e, chip.damage, chip.element)
    eff.append(_eff().ProjectileEffect(_pc(player.col, row), _pc(C.GRID_COLS - 1, row), C.YELLOW, 9))


# ── Fire (Ignite / Scorch / Immolate) ─────────────────────────────────────────

def _fire_resolve(chip, player, grid, enemies, eff):
    """T1/T2: row-aimed card with adjacent-row splash."""
    row = player.row
    primary = None
    hit_col = C.GRID_COLS - 1
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            primary = targets[0]
            hit_col = col
            for e in enemies:
                if e.col == col and abs(e.row - row) == 1 and e.alive:
                    _dmg(e, chip.damage // 2, chip.element)
            eff.append(_eff().ExplosionEffect(_pc(col, row), C.ORANGE, 35, 0.28))
            break
    _add_travel_flash(eff, player.col, row, (255, 130, 40))
    src = player.shoot_origin()
    dst = _pc(hit_col, row)
    eff.append(_eff().CardProjectileEffect(
        src, dst, charged=False,
        target=primary, damage=chip.damage, element=chip.element,
    ))

def _immolate_resolve(chip, player, grid, enemies, eff):
    """T3: column eruption — first hit column burns top-to-bottom."""
    row = player.row
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            for r in range(C.GRID_ROWS):
                for e in enemies:
                    if e.col == col and e.row == r and e.alive:
                        _dmg(e, chip.damage, chip.element)
            eff.append(_eff().ExplosionEffect(_pc(col, row), C.ORANGE, 55, 0.35))
            break


# ── Ice (Freeze / Icicle / Blizzard) ──────────────────────────────────────────

def _freeze_resolve(chip, player, grid, enemies, eff):
    """T1/T2: ice card with adjacent-row splash."""
    row = player.row
    primary = None
    hit_col = C.GRID_COLS - 1
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            primary = targets[0]
            hit_col = col
            for e in enemies:
                if e.col == col and abs(e.row - row) == 1 and e.alive:
                    _dmg(e, chip.damage // 2, chip.element)
            break
    _add_travel_flash(eff, player.col, row, (140, 210, 255))
    src = player.shoot_origin()
    dst = _pc(hit_col, row)
    eff.append(_eff().CardProjectileEffect(
        src, dst, charged=False,
        target=primary, damage=chip.damage, element=chip.element,
    ))

def _blizzard_resolve(chip, player, grid, enemies, eff):
    """T3: column ice explosion."""
    row = player.row
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            for r in range(C.GRID_ROWS):
                for e in enemies:
                    if e.col == col and e.row == r and e.alive:
                        _dmg(e, chip.damage, chip.element)
            eff.append(_eff().ExplosionEffect(_pc(col, row), C.ICE_BLUE, 55, 0.35))
            break


# ── Lightning (Jolt / Shock / Electrocute) ────────────────────────────────────

def _jolt_resolve(chip, player, grid, enemies, eff):
    """T1/T2: lightning card down the row, then chain-arcs through column on hit."""
    row = player.row
    primary = None
    hit_col = C.GRID_COLS - 1
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            primary = targets[0]
            hit_col = col
            for r in range(C.GRID_ROWS):
                if r != row:
                    for e in enemies:
                        if e.col == col and e.row == r and e.alive:
                            _dmg(e, chip.damage // 2, chip.element)
            eff.append(_eff().ElecEffect(_pc(col, row)))
            break
    _add_travel_flash(eff, player.col, row, (255, 240, 100))
    src = player.shoot_origin()
    dst = _pc(hit_col, row)
    eff.append(_eff().CardProjectileEffect(
        src, dst, charged=False,
        target=primary, damage=chip.damage, element=chip.element,
    ))

def _electrocute_resolve(chip, player, grid, enemies, eff):
    """T3: lightning strikes every living enemy."""
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().ScreenFlash(C.YELLOW, 0.2))
    eff.append(_eff().TextEffect("ELECTROCUTE!", _pc(6, 2), C.YELLOW, 1.2))


# ── Wind (Gust / Gale / Tempest — non-elemental "force" cards) ────────────────

def _gust_resolve(chip, player, grid, enemies, eff):
    """T1: row-aimed wind blast, knocks target back 1 tile if possible."""
    row = player.row
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            e = targets[0]
            _dmg(e, chip.damage, chip.element)
            if e.col + 1 < C.GRID_COLS:
                p = grid.get(e.col + 1, e.row)
                if p and p.is_passable() and p.owner == C.OWN_ENEMY:
                    e.col += 1
            eff.append(_eff().ProjectileEffect(_pc(player.col, row), _pc(col, row), C.WHITE, 7))
            break

def _gale_resolve(chip, player, grid, enemies, eff):
    """T2: hits every enemy in row, boomerang VFX."""
    row = player.row
    for e in enemies:
        if e.row == row and e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().BoomerangEffect(_pc(player.col, row), _pc(C.GRID_COLS - 1, row)))

def _tempest_resolve(chip, player, grid, enemies, eff):
    """T3: column eruption on first hit."""
    row = player.row
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            for r in range(C.GRID_ROWS):
                for e in enemies:
                    if e.col == col and e.row == r and e.alive:
                        _dmg(e, chip.damage, chip.element)
            eff.append(_eff().ExplosionEffect(_pc(col, row), C.WHITE, 50, 0.3))
            break


# ── Earth (Crack / Quake / Landslide) ─────────────────────────────────────────

def _crack_resolve(chip, player, grid, enemies, eff):
    """T1: homing boulder, cracks target's panel."""
    import random
    alive = [e for e in enemies if e.alive]
    if not alive:
        return
    target = random.choice(alive)
    _dmg(target, chip.damage, chip.element)
    grid.crack_panel(target.col, target.row)
    eff.append(_eff().HomingEffect(_pc(player.col, player.row), _pc(target.col, target.row)))

def _quake_resolve(chip, player, grid, enemies, eff):
    """T2: 3x3 crack centered on target."""
    import random
    alive = [e for e in enemies if e.alive]
    if not alive:
        return
    target = random.choice(alive)
    _dmg(target, chip.damage, chip.element)
    for dc in range(-1, 2):
        for dr in range(-1, 2):
            grid.crack_panel(target.col + dc, target.row + dr)
    eff.append(_eff().ExplosionEffect(_pc(target.col, target.row), C.GREEN, 45, 0.3))

def _landslide_resolve(chip, player, grid, enemies, eff):
    """T3: every enemy hit + every panel cracked."""
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, chip.element)
            grid.crack_panel(e.col, e.row)
    eff.append(_eff().ScreenFlash(C.DARK_GREEN, 0.25))
    eff.append(_eff().TextEffect("LANDSLIDE!", _pc(6, 2), C.GREEN, 1.2))


# ── Recovery / Defense ────────────────────────────────────────────────────────

def _heal_resolve(chip, player, grid, enemies, eff):
    player.hp = min(player.max_hp, player.hp + chip.heals)
    eff.append(_eff().RecoveryEffect(_pc(player.col, player.row), chip.heals))

def _protect_resolve(chip, player, grid, enemies, eff):
    player.guarding = True
    player.guard_timer = 2.0
    eff.append(_eff().TextEffect("PROTECT!", _pc(player.col, player.row), C.WHITE, 0.8))


# ── Utility ───────────────────────────────────────────────────────────────────

def _teleport_resolve(chip, player, grid, enemies, eff):
    grid.area_grab(1)
    eff.append(_eff().TextEffect("TELEPORT!", _pc(6, 2), C.YELLOW, 1.0))

def _dash_resolve(chip, player, grid, enemies, eff):
    row = player.row
    for col in range(player.col + 1, C.GRID_COLS):
        for e in enemies:
            if e.col == col and e.row == row and e.alive:
                _dmg(e, chip.damage, chip.element)
    eff.append(_eff().DashEffect(_pc(player.col, row), _pc(C.GRID_COLS - 1, row)))


# ── Stub resolvers for new canonical cards (mechanics TBD) ────────────────────
# These exist so the cards are real DB entries usable for asset/UI work.
# Replace with bespoke mechanics once each spell is designed.

def _stub_dmg_row_resolve(chip, player, grid, enemies, eff):
    """Generic placeholder: hits all enemies in player's row."""
    row = player.row
    color = C.ELEM_COLOR.get(chip.element, C.WHITE)
    for e in enemies:
        if e.row == row and e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().ProjectileEffect(
        _pc(player.col, row), _pc(C.GRID_COLS - 1, row), color, 7))

def _stub_dmg_all_resolve(chip, player, grid, enemies, eff):
    """Generic placeholder for T3 / all-enemy spells."""
    color = C.ELEM_COLOR.get(chip.element, C.WHITE)
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().ScreenFlash(color, 0.25))
    eff.append(_eff().TextEffect(chip.name.upper() + "!", _pc(6, 2), color, 1.2))

def _stub_status_resolve(chip, player, grid, enemies, eff):
    """Placeholder for Green afflictions and White status clears — visible feedback only."""
    color = C.ELEM_COLOR.get(chip.element, C.WHITE)
    eff.append(_eff().TextEffect(
        chip.name.upper() + "!", _pc(player.col, player.row), color, 0.9))

def _stub_revive_resolve(chip, player, grid, enemies, eff):
    """Placeholder — no party-death system in real-time grid combat yet.
    Falls back to a full heal as visible feedback."""
    player.hp = player.max_hp
    eff.append(_eff().RecoveryEffect(_pc(player.col, player.row), player.max_hp))
    eff.append(_eff().TextEffect(
        chip.name.upper() + "!", _pc(player.col, player.row), C.WHITE, 1.2))


# ── Limit Breaks (Program Advance equivalents) ────────────────────────────────

def _grand_cross_resolve(chip, player, grid, enemies, eff):
    panels = [(c, r) for c in range(4, C.GRID_COLS) for r in range(C.GRID_ROWS)]
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, C.ELEM_NONE)
    eff.append(_eff().SlashEffect(panels, C.PURPLE, 0.5))
    eff.append(_eff().TextEffect("GRAND CROSS!", _pc(6, 2), C.PURPLE, 1.8))

def _absolute_zero_resolve(chip, player, grid, enemies, eff):
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, C.ELEM_ICE)
    eff.append(_eff().ScreenFlash(C.ICE_BLUE, 0.4))
    eff.append(_eff().TextEffect("ABSOLUTE ZERO!", _pc(6, 2), C.ICE_BLUE, 1.8))

def _stormcall_resolve(chip, player, grid, enemies, eff):
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, C.ELEM_LIGHTNING)
    eff.append(_eff().ScreenFlash(C.YELLOW, 0.35))
    eff.append(_eff().TextEffect("STORMCALL!", _pc(6, 2), C.YELLOW, 1.8))


CHIP_EFFECTS = {
    # Weapons
    "Sword":        _sword_resolve,
    "WideBlade":    _wideblade_resolve,
    "Partisan":     _partisan_resolve,
    "Excalibur":    _excalibur_resolve,
    "Shortbow":     _bow_resolve,
    "Longbow":      _longbow_resolve,

    # Fire
    "Ignite":       _fire_resolve,
    "Scorch":       _fire_resolve,
    "Immolate":     _immolate_resolve,

    # Ice
    "Freeze":       _freeze_resolve,
    "Icicle":       _freeze_resolve,
    "Blizzard":     _blizzard_resolve,

    # Lightning
    "Jolt":         _jolt_resolve,
    "Shock":        _jolt_resolve,
    "Electrocute":  _electrocute_resolve,

    # Wind (non-elemental)
    "Gust":         _gust_resolve,
    "Gale":         _gale_resolve,
    "Tempest":      _tempest_resolve,

    # Earth
    "Crack":        _crack_resolve,
    "Quake":        _quake_resolve,
    "Landslide":    _landslide_resolve,

    # Light (mechanics TBD)
    "Sanctify":     _stub_dmg_row_resolve,
    "Exorcise":     _stub_dmg_row_resolve,
    "Absolution":   _stub_dmg_all_resolve,

    # Dark (mechanics TBD)
    "Hex":          _stub_dmg_row_resolve,
    "Curse":        _stub_dmg_row_resolve,
    "Oblivion":     _stub_dmg_all_resolve,

    # White — HP restoration
    "Heal":         _heal_resolve,
    "Cure":         _heal_resolve,
    "Recover":      _heal_resolve,
    "Rejuvenate":   _heal_resolve,

    # White — status clears (mechanics TBD)
    "Antidote":     _stub_status_resolve,
    "Voice":        _stub_status_resolve,
    "Wake":         _stub_status_resolve,
    "Stonebreak":   _stub_status_resolve,

    # White — revive (mechanics TBD)
    "Return":       _stub_revive_resolve,
    "Raise":        _stub_revive_resolve,
    "Revive":       _stub_revive_resolve,
    "Resurrect":    _stub_revive_resolve,

    # Green — afflictions (mechanics TBD)
    "Toxin":        _stub_status_resolve,
    "Poison":       _stub_status_resolve,
    "Mute":         _stub_status_resolve,
    "Silence":      _stub_status_resolve,
    "Snooze":       _stub_status_resolve,
    "Slumber":      _stub_status_resolve,
    "Petrify":      _stub_status_resolve,
    "Entomb":       _stub_status_resolve,
    "Delay":        _stub_status_resolve,
    "Halt":         _stub_status_resolve,
    "Quicken":      _stub_status_resolve,
    "Allegro":      _stub_status_resolve,

    # Defense / Utility
    "Protect":      _protect_resolve,
    "Teleport":     _teleport_resolve,
    "Dash":         _dash_resolve,

    # Limit Breaks
    "GrandCross":   _grand_cross_resolve,
    "AbsoluteZero": _absolute_zero_resolve,
    "Stormcall":    _stormcall_resolve,
}


# ── Chip database ─────────────────────────────────────────────────────────────

def _c(name, code, dmg, elem, cls_, mb, desc, rarity=1, heals=0):
    return ChipData(name, code, dmg, elem, cls_, mb, desc, rarity, heals, name)


CHIP_DB: List[ChipData] = [
    # ── Weapons: Swords ──────────────────────────────────────────────────────
    _c("Sword",       "S", 80,  C.ELEM_NONE, C.CLS_STANDARD, 20, "Slash 1 panel ahead",        1),
    _c("Sword",       "A", 80,  C.ELEM_NONE, C.CLS_STANDARD, 20, "Slash 1 panel ahead",        1),
    _c("Sword",       "B", 80,  C.ELEM_NONE, C.CLS_STANDARD, 20, "Slash 1 panel ahead",        1),
    _c("WideBlade",   "S", 140, C.ELEM_NONE, C.CLS_STANDARD, 28, "Slash the entire column",    2),
    _c("WideBlade",   "W", 140, C.ELEM_NONE, C.CLS_STANDARD, 28, "Slash the entire column",    2),
    _c("Partisan",    "P", 170, C.ELEM_NONE, C.CLS_STANDARD, 32, "Lance thrust 2 panels deep", 2),
    _c("Partisan",    "S", 170, C.ELEM_NONE, C.CLS_STANDARD, 32, "Lance thrust 2 panels deep", 2),
    _c("Excalibur",   "E", 380, C.ELEM_NONE, C.CLS_MEGA,     72, "Holy blade hits all rows",   4),

    # ── Weapons: Bows ─────────────────────────────────────────────────────────
    _c("Shortbow",    "A", 60,  C.ELEM_NONE, C.CLS_STANDARD, 16, "Quick arrow forward",        1),
    _c("Shortbow",    "B", 60,  C.ELEM_NONE, C.CLS_STANDARD, 16, "Quick arrow forward",        1),
    _c("Shortbow",    "C", 60,  C.ELEM_NONE, C.CLS_STANDARD, 16, "Quick arrow forward",        1),
    _c("Longbow",     "L", 130, C.ELEM_NONE, C.CLS_STANDARD, 28, "Arrow pierces entire row",   2),
    _c("Longbow",     "A", 130, C.ELEM_NONE, C.CLS_STANDARD, 28, "Arrow pierces entire row",   2),

    # ── Fire ──────────────────────────────────────────────────────────────────
    _c("Ignite",      "I", 80,  C.ELEM_FIRE, C.CLS_STANDARD, 22, "Fire bolt + side spread",    1),
    _c("Ignite",      "F", 80,  C.ELEM_FIRE, C.CLS_STANDARD, 22, "Fire bolt + side spread",    1),
    _c("Scorch",      "I", 160, C.ELEM_FIRE, C.CLS_STANDARD, 38, "Stronger fire + spread",     2),
    _c("Immolate",    "I", 300, C.ELEM_FIRE, C.CLS_MEGA,     60, "Column fire eruption",       3),

    # ── Ice ───────────────────────────────────────────────────────────────────
    _c("Freeze",      "F", 80,  C.ELEM_ICE,  C.CLS_STANDARD, 22, "Ice shard + adjacent hits",  1),
    _c("Freeze",      "B", 80,  C.ELEM_ICE,  C.CLS_STANDARD, 22, "Ice shard + adjacent hits",  1),
    _c("Icicle",      "F", 160, C.ELEM_ICE,  C.CLS_STANDARD, 38, "Stronger ice + adjacent",    2),
    _c("Blizzard",    "F", 300, C.ELEM_ICE,  C.CLS_MEGA,     60, "Column ice explosion",       3),

    # ── Lightning ─────────────────────────────────────────────────────────────
    _c("Jolt",        "J", 80,  C.ELEM_LIGHTNING, C.CLS_STANDARD, 26, "Lightning bolt, row bounce", 1),
    _c("Jolt",        "T", 80,  C.ELEM_LIGHTNING, C.CLS_STANDARD, 26, "Lightning bolt, row bounce", 1),
    _c("Shock",       "J", 160, C.ELEM_LIGHTNING, C.CLS_STANDARD, 42, "Stronger bolt, bounces",     2),
    _c("Electrocute", "J", 300, C.ELEM_LIGHTNING, C.CLS_MEGA,     60, "Lightning strikes all foes", 3),

    # ── Wind (non-elemental force) ────────────────────────────────────────────
    _c("Gust",        "W", 40,  C.ELEM_NONE, C.CLS_STANDARD, 14, "Wind blast, pushes foe back",   1),
    _c("Gale",        "W", 110, C.ELEM_NONE, C.CLS_STANDARD, 24, "Wind hits all foes in row",     2),
    _c("Tempest",     "W", 200, C.ELEM_NONE, C.CLS_MEGA,     44, "Gale blast, column erupts",     3),

    # ── Earth ─────────────────────────────────────────────────────────────────
    _c("Crack",       "C", 80,  C.ELEM_EARTH, C.CLS_STANDARD, 24, "Homing boulder cracks panel",   2),
    _c("Quake",       "C", 140, C.ELEM_EARTH, C.CLS_STANDARD, 38, "Rock bomb, cracks 3×3 area",    2),
    _c("Landslide",   "C", 250, C.ELEM_EARTH, C.CLS_MEGA,     56, "All foes hit, panels cracked",  3),

    # ── Light ─────────────────────────────────────────────────────────────────
    _c("Sanctify",    "L", 80,  C.ELEM_LIGHT, C.CLS_STANDARD, 22, "Hallowed light strikes a row",  2),
    _c("Exorcise",    "L", 160, C.ELEM_LIGHT, C.CLS_STANDARD, 40, "Cleansing radiance, row burst", 3),
    _c("Absolution",  "L", 320, C.ELEM_LIGHT, C.CLS_MEGA,     64, "Judgment — strikes all foes",   4),

    # ── Dark ──────────────────────────────────────────────────────────────────
    _c("Hex",         "H", 80,  C.ELEM_DARK, C.CLS_STANDARD, 22, "A curse-bolt down the row",     2),
    _c("Curse",       "H", 160, C.ELEM_DARK, C.CLS_STANDARD, 40, "Deeper curse, row affliction",  3),
    _c("Oblivion",    "H", 320, C.ELEM_DARK, C.CLS_MEGA,     64, "Void-erasure of all foes",      4),

    # ── White: HP restoration ─────────────────────────────────────────────────
    _c("Heal",        "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 12, "Restore 200 HP",                 1, heals=200),
    _c("Cure",        "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 22, "Restore 500 HP",                 2, heals=500),
    _c("Recover",     "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 34, "Restore 1000 HP",                3, heals=1000),
    _c("Rejuvenate",  "*", 0, C.ELEM_NONE, C.CLS_MEGA,     50, "Restore 2200 HP",                4, heals=2200),

    # ── White: status clears (mechanics TBD) ──────────────────────────────────
    _c("Antidote",    "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 10, "Clear poison/toxin",             1),
    _c("Voice",       "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 10, "Clear silence/mute",             1),
    _c("Wake",        "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 10, "Clear slumber/snooze",           1),
    _c("Stonebreak",  "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 14, "Clear petrify/entomb",           2),

    # ── White: revive (mechanics TBD) ─────────────────────────────────────────
    _c("Return",      "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 20, "Recall a fallen ally",           2),
    _c("Raise",       "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 36, "Revive with partial HP",         3),
    _c("Revive",      "*", 0, C.ELEM_NONE, C.CLS_MEGA,     56, "Revive with full HP",            4),
    _c("Resurrect",   "*", 0, C.ELEM_NONE, C.CLS_MEGA,     72, "Revive entire party",            5),

    # ── Green: afflictions (mechanics TBD) ────────────────────────────────────
    _c("Toxin",       "T", 0, C.ELEM_NONE, C.CLS_STANDARD, 18, "Inflict mild poison",            2),
    _c("Poison",      "T", 0, C.ELEM_NONE, C.CLS_STANDARD, 32, "Inflict heavy poison",           3),
    _c("Mute",        "M", 0, C.ELEM_NONE, C.CLS_STANDARD, 16, "Disable enemy magic briefly",    2),
    _c("Silence",     "M", 0, C.ELEM_NONE, C.CLS_STANDARD, 28, "Disable enemy magic",            3),
    _c("Snooze",      "Z", 0, C.ELEM_NONE, C.CLS_STANDARD, 18, "Brief sleep on target",          2),
    _c("Slumber",     "Z", 0, C.ELEM_NONE, C.CLS_STANDARD, 32, "Deep sleep on target",           3),
    _c("Petrify",     "P", 0, C.ELEM_NONE, C.CLS_STANDARD, 24, "Briefly turn target to stone",   3),
    _c("Entomb",      "P", 0, C.ELEM_NONE, C.CLS_MEGA,     44, "Permanently entomb a target",    4),
    _c("Delay",       "D", 0, C.ELEM_NONE, C.CLS_STANDARD, 18, "Slow an enemy's next action",    2),
    _c("Halt",        "D", 0, C.ELEM_NONE, C.CLS_STANDARD, 32, "Stop an enemy briefly",          3),
    _c("Quicken",     "Q", 0, C.ELEM_NONE, C.CLS_STANDARD, 18, "Speed up next ally action",      2),
    _c("Allegro",     "Q", 0, C.ELEM_NONE, C.CLS_MEGA,     40, "Party-wide haste",               4),

    # ── Defense / Utility ─────────────────────────────────────────────────────
    _c("Protect",     "*", 0,   C.ELEM_NONE, C.CLS_STANDARD, 14, "Guard next attack 2s",        1),
    _c("Teleport",    "T", 0,   C.ELEM_NONE, C.CLS_STANDARD, 28, "Steal 1 enemy column",        2),
    _c("Dash",        "D", 110, C.ELEM_NONE, C.CLS_STANDARD, 36, "Dash through entire row",     2),
]


# ── Limit Break definitions ───────────────────────────────────────────────────

LB_DEFINITIONS = [
    ("GrandCross",   [("Sword",  "S"), ("WideBlade", "S"), ("Partisan",    "S")]),
    ("AbsoluteZero", [("Freeze", "F"), ("Icicle",    "F"), ("Blizzard",    "F")]),
    ("Stormcall",    [("Jolt",   "J"), ("Shock",     "J"), ("Electrocute", "J")]),
]

LB_CHIPS = {
    "GrandCross":   ChipData("GrandCross",   "*", 520, C.ELEM_NONE,      C.CLS_GIGA, 100, "LIMIT BREAK!", 5, 0, "GrandCross"),
    "AbsoluteZero": ChipData("AbsoluteZero", "*", 630, C.ELEM_ICE,       C.CLS_GIGA, 100, "LIMIT BREAK!", 5, 0, "AbsoluteZero"),
    "Stormcall":    ChipData("Stormcall",    "*", 740, C.ELEM_LIGHTNING, C.CLS_GIGA, 100, "LIMIT BREAK!", 5, 0, "Stormcall"),
}


def check_program_advance(selected: List[ChipData]):
    if len(selected) < 2:
        return None
    for lb_name, requirements in LB_DEFINITIONS:
        if len(selected) != len(requirements):
            continue
        if all(c.name == req[0] and (req[1] == "*" or c.code == req[1])
               for c, req in zip(selected, requirements)):
            return LB_CHIPS[lb_name]
    return None


def can_add_chip(selected: List[ChipData], candidate: ChipData) -> bool:
    if not selected:
        return True
    if candidate.code == "*":
        return True
    non_star = [c for c in selected if c.code != "*"]
    if not non_star:
        return True
    if all(c.name == non_star[0].name for c in non_star):
        if candidate.name == non_star[0].name:
            return True
    codes = set(c.code for c in non_star)
    if len(codes) == 1 and candidate.code == next(iter(codes)):
        return True
    return False


# ── Sample folder (30 chips, starter kit) ────────────────────────────────────

def make_sample_folder() -> List[ChipData]:
    db = {(c.name, c.code): c for c in CHIP_DB}

    def get(name, code, count=1):
        key = (name, code)
        if key in db:
            return [db[key]] * count
        for c in CHIP_DB:
            if c.name == name:
                return [c] * count
        return []

    folder = (
        get("Sword",       "S", 3) +    # S-code swords → GrandCross LB
        get("WideBlade",   "S", 2) +
        get("Partisan",    "S", 2) +
        get("Shortbow",    "A", 3) +
        get("Ignite",      "I", 2) +    # I-code fire
        get("Scorch",      "I", 2) +
        get("Freeze",      "F", 2) +    # F-code ice → AbsoluteZero LB
        get("Icicle",      "F", 2) +
        get("Blizzard",    "F", 1) +
        get("Jolt",        "J", 2) +    # J-code lightning → Stormcall LB
        get("Shock",       "J", 2) +
        get("Electrocute", "J", 1) +
        get("Heal",        "*", 3) +    # wildcard heals
        get("Protect",     "*", 3)      # wildcard guard
    )                                   # 3+2+2+3+2+2+2+2+1+2+2+1+3+3 = 30
    return folder[:30]
