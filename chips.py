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
    x = C.GRID_X + col * C.PANEL_W + C.PANEL_W // 2
    y = C.GRID_Y + row * C.PANEL_H + C.PANEL_H // 2
    return (x, y)

def _eff():
    import effects
    return effects

def _dmg(entity, damage, element):
    if not entity.alive:
        return
    mult = 2.0 if (element != C.ELEM_NONE and C.ELEM_BEATS.get(element) == entity.element) else 1.0
    entity.take_damage(int(damage * mult), element)


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


# ── Fire magic ────────────────────────────────────────────────────────────────

def _fire_resolve(chip, player, grid, enemies, eff):
    row = player.row
    primary = None
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            primary = targets[0]
            # Splash damage is instant (player aimed the orb, splash is physics)
            for e in enemies:
                if e.col == col and abs(e.row - row) == 1 and e.alive:
                    _dmg(e, chip.damage // 2, chip.element)
            eff.append(_eff().ExplosionEffect(_pc(col, row), C.ORANGE, 35, 0.28))
            break
    src = _pc(player.col, row)
    eff.append(_eff().TravelingHit(
        src, row, player.col, C.GRID_COLS - 1,
        chip.damage, chip.element, primary, C.ORANGE, 9
    ))

def _firaga_resolve(chip, player, grid, enemies, eff):
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


# ── Ice magic ─────────────────────────────────────────────────────────────────

def _blizzard_resolve(chip, player, grid, enemies, eff):
    row = player.row
    primary = None
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            primary = targets[0]
            for e in enemies:
                if e.col == col and abs(e.row - row) == 1 and e.alive:
                    _dmg(e, chip.damage // 2, chip.element)
            break
    src = _pc(player.col, row)
    eff.append(_eff().TravelingHit(
        src, row, player.col, C.GRID_COLS - 1,
        chip.damage, chip.element, primary, C.LIGHT_BLUE, 10
    ))

def _blizzaga_resolve(chip, player, grid, enemies, eff):
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


# ── Thunder magic ─────────────────────────────────────────────────────────────

def _thunder_resolve(chip, player, grid, enemies, eff):
    row = player.row
    primary = None
    for col in range(player.col + 1, C.GRID_COLS):
        targets = [e for e in enemies if e.col == col and e.row == row and e.alive]
        if targets:
            primary = targets[0]
            # Column-wide chain lightning is instant (secondary arc)
            for r in range(C.GRID_ROWS):
                if r != row:
                    for e in enemies:
                        if e.col == col and e.row == r and e.alive:
                            _dmg(e, chip.damage // 2, chip.element)
            eff.append(_eff().ElecEffect(_pc(col, row)))
            break
    src = _pc(player.col, row)
    eff.append(_eff().TravelingHit(
        src, row, player.col, C.GRID_COLS - 1,
        chip.damage, chip.element, primary, C.YELLOW, 7
    ))

def _thundaga_resolve(chip, player, grid, enemies, eff):
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().ScreenFlash(C.YELLOW, 0.2))
    eff.append(_eff().TextEffect("THUNDAGA!", _pc(6, 2), C.YELLOW, 1.2))


# ── Wind magic ────────────────────────────────────────────────────────────────

def _aero_resolve(chip, player, grid, enemies, eff):
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

def _aerora_resolve(chip, player, grid, enemies, eff):
    row = player.row
    for e in enemies:
        if e.row == row and e.alive:
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().BoomerangEffect(_pc(player.col, row), _pc(C.GRID_COLS - 1, row)))

def _aeroga_resolve(chip, player, grid, enemies, eff):
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


# ── Earth magic ───────────────────────────────────────────────────────────────

def _stone_resolve(chip, player, grid, enemies, eff):
    import random
    alive = [e for e in enemies if e.alive]
    if not alive:
        return
    target = random.choice(alive)
    _dmg(target, chip.damage, chip.element)
    grid.crack_panel(target.col, target.row)
    eff.append(_eff().HomingEffect(_pc(player.col, player.row), _pc(target.col, target.row)))

def _stonera_resolve(chip, player, grid, enemies, eff):
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

def _stonega_resolve(chip, player, grid, enemies, eff):
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, chip.element)
            grid.crack_panel(e.col, e.row)
    eff.append(_eff().ScreenFlash(C.DARK_GREEN, 0.25))
    eff.append(_eff().TextEffect("STONEGA!", _pc(6, 2), C.GREEN, 1.2))


# ── Dark magic ────────────────────────────────────────────────────────────────

def _drain_resolve(chip, player, grid, enemies, eff):
    import random
    alive = [e for e in enemies if e.alive]
    if not alive:
        return
    target = random.choice(alive)
    _dmg(target, chip.damage, chip.element)
    heal = chip.damage // 2
    player.hp = min(player.max_hp, player.hp + heal)
    eff.append(_eff().ProjectileEffect(
        _pc(target.col, target.row), _pc(player.col, player.row), C.PURPLE, 8))
    eff.append(_eff().RecoveryEffect(_pc(player.col, player.row), heal))

def _flare_resolve(chip, player, grid, enemies, eff):
    import random
    alive = [e for e in enemies if e.alive]
    if not alive:
        return
    target = random.choice(alive)
    for e in enemies:
        if e.alive and (
            (e.col == target.col and e.row == target.row) or
            (e.col == target.col and abs(e.row - target.row) == 1) or
            (e.row == target.row and abs(e.col - target.col) == 1)
        ):
            _dmg(e, chip.damage, chip.element)
    eff.append(_eff().BombTrajectory(_pc(player.col, player.row), _pc(target.col, target.row)))
    eff.append(_eff().TextEffect("FLARE!", _pc(6, 2), C.PURPLE, 1.2))


# ── Recovery / White magic ────────────────────────────────────────────────────

def _cure_resolve(chip, player, grid, enemies, eff):
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


# ── Summons (Giga class — all enemies) ───────────────────────────────────────

def _make_summon(display_name, flash_color):
    def resolve(chip, player, grid, enemies, eff):
        for e in enemies:
            if e.alive:
                _dmg(e, chip.damage, chip.element)
        eff.append(_eff().ScreenFlash(flash_color, 0.3))
        eff.append(_eff().TextEffect(f"{display_name}!", _pc(6, 2), flash_color, 1.8))
    return resolve

def _phoenix_resolve(chip, player, grid, enemies, eff):
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, chip.element)
    player.hp = player.max_hp
    eff.append(_eff().ScreenFlash(C.ORANGE, 0.35))
    eff.append(_eff().RecoveryEffect(_pc(player.col, player.row), player.max_hp))
    eff.append(_eff().TextEffect("PHOENIX!", _pc(6, 2), C.ORANGE, 1.8))


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
            _dmg(e, chip.damage, C.ELEM_AQUA)
    eff.append(_eff().ScreenFlash(C.ICE_BLUE, 0.4))
    eff.append(_eff().TextEffect("ABSOLUTE ZERO!", _pc(6, 2), C.ICE_BLUE, 1.8))

def _raiden_resolve(chip, player, grid, enemies, eff):
    for e in enemies:
        if e.alive:
            _dmg(e, chip.damage, C.ELEM_ELEC)
    eff.append(_eff().ScreenFlash(C.YELLOW, 0.35))
    eff.append(_eff().TextEffect("RAIDEN!", _pc(6, 2), C.YELLOW, 1.8))


CHIP_EFFECTS = {
    # Weapons
    "Sword":        _sword_resolve,
    "WideBlade":    _wideblade_resolve,
    "Partisan":     _partisan_resolve,
    "Excalibur":    _excalibur_resolve,
    "Shortbow":     _bow_resolve,
    "Longbow":      _longbow_resolve,
    # Fire
    "Fire":         _fire_resolve,
    "Fira":         _fire_resolve,
    "Firaga":       _firaga_resolve,
    # Ice
    "Blizzard":     _blizzard_resolve,
    "Blizzara":     _blizzard_resolve,
    "Blizzaga":     _blizzaga_resolve,
    # Thunder
    "Thunder":      _thunder_resolve,
    "Thundara":     _thunder_resolve,
    "Thundaga":     _thundaga_resolve,
    # Wind
    "Aero":         _aero_resolve,
    "Aerora":       _aerora_resolve,
    "Aeroga":       _aeroga_resolve,
    # Earth
    "Stone":        _stone_resolve,
    "Stonera":      _stonera_resolve,
    "Stonega":      _stonega_resolve,
    # Dark
    "Drain":        _drain_resolve,
    "Flare":        _flare_resolve,
    # White magic
    "Cure":         _cure_resolve,
    "Cura":         _cure_resolve,
    "Curaga":       _cure_resolve,
    "Protect":      _protect_resolve,
    # Utility
    "Teleport":     _teleport_resolve,
    "Dash":         _dash_resolve,
    # Summons
    "Ifrit":        _make_summon("IFRIT",    C.ORANGE),
    "Shiva":        _make_summon("SHIVA",    C.ICE_BLUE),
    "Ramuh":        _make_summon("RAMUH",    C.YELLOW),
    "Bahamut":      _make_summon("BAHAMUT",  C.PURPLE),
    "Phoenix":      _phoenix_resolve,
    # Limit Breaks
    "GrandCross":   _grand_cross_resolve,
    "AbsoluteZero": _absolute_zero_resolve,
    "Raiden":       _raiden_resolve,
}


# ── Chip database ─────────────────────────────────────────────────────────────

def _c(name, code, dmg, elem, cls_, mb, desc, rarity=1, heals=0):
    return ChipData(name, code, dmg, elem, cls_, mb, desc, rarity, heals, name)


CHIP_DB: List[ChipData] = [
    # ── Weapons: Swords ──────────────────────────────────────────────────────
    _c("Sword",     "S", 80,  C.ELEM_NONE, C.CLS_STANDARD, 20, "Slash 1 panel ahead",       1),
    _c("Sword",     "A", 80,  C.ELEM_NONE, C.CLS_STANDARD, 20, "Slash 1 panel ahead",       1),
    _c("Sword",     "B", 80,  C.ELEM_NONE, C.CLS_STANDARD, 20, "Slash 1 panel ahead",       1),
    _c("WideBlade", "S", 140, C.ELEM_NONE, C.CLS_STANDARD, 28, "Slash the entire column",   2),
    _c("WideBlade", "W", 140, C.ELEM_NONE, C.CLS_STANDARD, 28, "Slash the entire column",   2),
    _c("Partisan",  "P", 170, C.ELEM_NONE, C.CLS_STANDARD, 32, "Lance thrust 2 panels deep", 2),
    _c("Partisan",  "S", 170, C.ELEM_NONE, C.CLS_STANDARD, 32, "Lance thrust 2 panels deep", 2),
    _c("Excalibur", "E", 380, C.ELEM_NONE, C.CLS_MEGA,     72, "Holy blade hits all rows",  4),

    # ── Weapons: Bows ─────────────────────────────────────────────────────────
    _c("Shortbow",  "A", 60,  C.ELEM_NONE, C.CLS_STANDARD, 16, "Quick arrow forward",       1),
    _c("Shortbow",  "B", 60,  C.ELEM_NONE, C.CLS_STANDARD, 16, "Quick arrow forward",       1),
    _c("Shortbow",  "C", 60,  C.ELEM_NONE, C.CLS_STANDARD, 16, "Quick arrow forward",       1),
    _c("Longbow",   "L", 130, C.ELEM_NONE, C.CLS_STANDARD, 28, "Arrow pierces entire row",  2),
    _c("Longbow",   "A", 130, C.ELEM_NONE, C.CLS_STANDARD, 28, "Arrow pierces entire row",  2),

    # ── Fire Magic ────────────────────────────────────────────────────────────
    _c("Fire",      "F", 80,  C.ELEM_FIRE, C.CLS_STANDARD, 22, "Fire bolt + side spread",   1),
    _c("Fire",      "I", 80,  C.ELEM_FIRE, C.CLS_STANDARD, 22, "Fire bolt + side spread",   1),
    _c("Fira",      "F", 160, C.ELEM_FIRE, C.CLS_STANDARD, 38, "Stronger fire + spread",    2),
    _c("Firaga",    "F", 300, C.ELEM_FIRE, C.CLS_MEGA,     60, "Column fire eruption",       3),

    # ── Ice Magic ─────────────────────────────────────────────────────────────
    _c("Blizzard",  "B", 80,  C.ELEM_AQUA, C.CLS_STANDARD, 22, "Ice shard + adjacent hits", 1),
    _c("Blizzard",  "I", 80,  C.ELEM_AQUA, C.CLS_STANDARD, 22, "Ice shard + adjacent hits", 1),
    _c("Blizzara",  "B", 160, C.ELEM_AQUA, C.CLS_STANDARD, 38, "Stronger ice + adjacent",   2),
    _c("Blizzaga",  "B", 300, C.ELEM_AQUA, C.CLS_MEGA,     60, "Column ice explosion",       3),

    # ── Thunder Magic ─────────────────────────────────────────────────────────
    _c("Thunder",   "T", 80,  C.ELEM_ELEC, C.CLS_STANDARD, 26, "Lightning bolt, row bounce", 1),
    _c("Thunder",   "U", 80,  C.ELEM_ELEC, C.CLS_STANDARD, 26, "Lightning bolt, row bounce", 1),
    _c("Thundara",  "T", 160, C.ELEM_ELEC, C.CLS_STANDARD, 42, "Stronger bolt, bounces",    2),
    _c("Thundaga",  "T", 300, C.ELEM_ELEC, C.CLS_MEGA,     60, "Lightning strikes all foes", 3),

    # ── Wind Magic ────────────────────────────────────────────────────────────
    _c("Aero",      "W", 40,  C.ELEM_NONE, C.CLS_STANDARD, 14, "Wind blast, pushes foe back", 1),
    _c("Aerora",    "W", 110, C.ELEM_NONE, C.CLS_STANDARD, 24, "Wind hits all foes in row", 2),
    _c("Aeroga",    "W", 200, C.ELEM_NONE, C.CLS_MEGA,     44, "Gale blast, column erupts", 3),

    # ── Earth Magic ───────────────────────────────────────────────────────────
    _c("Stone",     "G", 80,  C.ELEM_WOOD, C.CLS_STANDARD, 24, "Homing boulder cracks panel", 2),
    _c("Stonera",   "G", 140, C.ELEM_WOOD, C.CLS_STANDARD, 38, "Rock bomb, cracks 3x3 area", 2),
    _c("Stonega",   "G", 250, C.ELEM_WOOD, C.CLS_MEGA,     56, "Quake — all foes, all panels", 3),

    # ── Dark Magic ────────────────────────────────────────────────────────────
    _c("Drain",     "D", 140, C.ELEM_NONE, C.CLS_STANDARD, 32, "Drains half damage as HP",  2),
    _c("Flare",     "D", 340, C.ELEM_NONE, C.CLS_MEGA,     68, "Non-elemental cross blast", 4),

    # ── White Magic / Recovery ────────────────────────────────────────────────
    _c("Cure",      "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 16, "Restore 300 HP",    1, heals=300),
    _c("Cura",      "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 28, "Restore 800 HP",    2, heals=800),
    _c("Curaga",    "*", 0, C.ELEM_NONE, C.CLS_MEGA,     50, "Restore 2000 HP",   3, heals=2000),
    _c("Protect",   "*", 0, C.ELEM_NONE, C.CLS_STANDARD, 14, "Guard next attack 2s", 1),

    # ── Utility ───────────────────────────────────────────────────────────────
    _c("Teleport",  "T", 0,   C.ELEM_NONE, C.CLS_STANDARD, 28, "Steal 1 enemy column",      2),
    _c("Dash",      "D", 110, C.ELEM_NONE, C.CLS_STANDARD, 36, "Dash through entire row",   2),

    # ── Summons (Giga, * wildcard, very rare) ─────────────────────────────────
    _c("Ifrit",     "*", 420, C.ELEM_FIRE, C.CLS_GIGA, 100, "Hellfire — all foes",      5),
    _c("Shiva",     "*", 420, C.ELEM_AQUA, C.CLS_GIGA, 100, "Diamond Dust — all foes",  5),
    _c("Ramuh",     "*", 420, C.ELEM_ELEC, C.CLS_GIGA, 100, "Judgment Bolt — all foes", 5),
    _c("Bahamut",   "*", 650, C.ELEM_NONE, C.CLS_GIGA, 100, "Mega Flare — all foes",    5),
    _c("Phoenix",   "*", 280, C.ELEM_FIRE, C.CLS_GIGA, 100, "Flames all + full heal",   5),
]


# ── Limit Break definitions (replaces Program Advances) ───────────────────────

LB_DEFINITIONS = [
    ("GrandCross",   [("Sword", "S"), ("WideBlade", "S"), ("Partisan", "S")]),
    ("AbsoluteZero", [("Blizzard", "B"), ("Blizzara", "B"), ("Blizzaga", "B")]),
    ("Raiden",       [("Thunder", "T"), ("Thundara", "T"), ("Thundaga", "T")]),
]

LB_CHIPS = {
    "GrandCross":   ChipData("GrandCross",   "*", 520, C.ELEM_NONE, C.CLS_GIGA, 100, "LIMIT BREAK!", 5, 0, "GrandCross"),
    "AbsoluteZero": ChipData("AbsoluteZero", "*", 630, C.ELEM_AQUA, C.CLS_GIGA, 100, "LIMIT BREAK!", 5, 0, "AbsoluteZero"),
    "Raiden":       ChipData("Raiden",       "*", 740, C.ELEM_ELEC, C.CLS_GIGA, 100, "LIMIT BREAK!", 5, 0, "Raiden"),
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
        get("Sword",    "S", 3) +   # S-code swords — part of Grand Cross LB
        get("WideBlade","S", 2) +   # S-code wide
        get("Partisan", "S", 2) +   # S-code deep → GrandCross: Sword+Wide+Partisan all S
        get("Shortbow", "A", 3) +   # A-code ranged
        get("Fire",     "F", 2) +   # F-code fire magic
        get("Fira",     "F", 2) +   # F-code
        get("Blizzard", "B", 2) +   # B-code ice → AbsoluteZero: Blizzard+Blizzara+Blizzaga all B
        get("Blizzara", "B", 2) +
        get("Blizzaga", "B", 1) +   # 1× for Limit Break completion
        get("Thunder",  "T", 2) +   # T-code thunder → Raiden: Thunder+Thundara+Thundaga all T
        get("Thundara", "T", 2) +
        get("Thundaga", "T", 1) +   # 1× for Limit Break completion
        get("Cure",     "*", 3) +   # wildcard heals
        get("Protect",  "*", 3)     # wildcard guard
    )                               # 3+2+2+3+2+2+2+2+1+2+2+1+3+3 = 30
    return folder[:30]
