"""Dev tool: render snapshots of each game state."""
import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
pygame.init()
import constants as C
screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))

import sprite_manager; sprite_manager.init()
from game import Game, GameState, BattleTransition
from battle import Battle, BattleState

g = Game(screen)

# 1. Title
for _ in range(10):
    g.update(0.016)
g.draw()
pygame.image.save(screen, '/tmp/flow_1_title.png')

# 2. Go to overworld
g._start_overworld()
for _ in range(5):
    g.update(0.016)
g.draw()
pygame.image.save(screen, '/tmp/flow_2_overworld.png')

# 3. Mid-transition
g.overworld.start_battle = True
g._begin_transition_to_battle()
# advance to ~75% of transition for a visually striking mid-frame
g.transition.t = g.transition.DURATION * 0.55
g.draw()
pygame.image.save(screen, '/tmp/flow_3_transition.png')

# 4. Late-transition (near flash)
g.transition.t = g.transition.DURATION * 0.92
g.draw()
pygame.image.save(screen, '/tmp/flow_4_transition_late.png')

# 5. Battle opening — DRAW! card just landed
g._start_battle_from_overworld()
# advance the opening to ~1.4s (after DRAW! has entered, before custom opens)
b = g.battle
b._opening_elapsed = 1.35
# Tick a frame
g.update(0.016)
g.draw()
pygame.image.save(screen, '/tmp/flow_5_battle_opening.png')

# 6. Mid-opening (DEAL entering)
b._opening_elapsed = 0.58
b.state = BattleState.OPENING
b.opening_timer = 1.6
b.custom_screen_obj = None
g.draw()
pygame.image.save(screen, '/tmp/flow_6_opening_mid.png')

print('saved: /tmp/flow_1..6_*.png')
pygame.quit()
