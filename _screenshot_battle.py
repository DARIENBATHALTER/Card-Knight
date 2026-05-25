"""Dev tool: render one frame of the battle scene and save it to /tmp/battle_screenshot.png.
Usage: python3.13 _screenshot_battle.py [BATTLEFIELD]
       BATTLEFIELD = 'forest' (default) | 'crystalcave' | 'temple'
       Add --custom flag to show the custom menu open.
"""
import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
pygame.init()
import constants as C
screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))

import sprite_manager
sprite_manager.init()

from battle import Battle, BattleState
import chips

battlefield = 'forest'
show_custom = False
for arg in sys.argv[1:]:
    if arg == '--custom':
        show_custom = True
    elif arg in ('forest', 'crystalcave', 'temple'):
        battlefield = arg

Battle.BATTLEFIELD = battlefield
b = Battle(screen, folder=chips.make_sample_folder())

show_vfx = '--vfx' in sys.argv
show_victory = '--victory' in sys.argv

if not show_custom:
    selected = list(b.folder[:4])
    b.chip_queue.extend(selected)
    b.custom_screen_obj = None
    b.state = BattleState.BATTLE
    b.custom_gauge = 0.66

if show_vfx:
    import effects as FX
    target_slime = b.enemies[1]
    target_slime._fire_projectile(b.player, b.effects, 30, (50, 200, 80), 6)
    b._fire_buster(charged=False)
    # Fire an Ignite chip too — verifies chip travel flash
    from chips import CHIP_EFFECTS, CHIP_DB
    ignite_chip = next(c for c in CHIP_DB if c.name == 'Ignite')
    CHIP_EFFECTS['Ignite'](ignite_chip, b.player, b.grid, b.enemies, b.effects)
    for _ in range(12):
        b.update(1.0 / 60)
    b.draw()
elif show_victory:
    b.state = BattleState.VICTORY
    for e in b.enemies:
        e.alive = False
    b.update(1.0 / 60)
    b.draw()
else:
    b.update(1.0 / 60)
    b.draw()

out_path = '/tmp/battle_screenshot.png'
pygame.image.save(screen, out_path)
print(f"saved → {out_path}")
print(f"  battlefield: {battlefield}")
print(f"  state: {b.state}")
pygame.quit()
