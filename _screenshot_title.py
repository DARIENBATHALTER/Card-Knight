"""Snapshot the new intro/title/menu/save-panel flow."""
import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
pygame.init()
import constants as C
screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
import sprite_manager; sprite_manager.init()
from game import Game, GameState, TitleSubstate, LoadingScreen

g = Game(screen)

# Frame 1: title PROMPT state — baked "Press Z to Start" visible
g.intro.done = True
g.state = GameState.TITLE
g.title_alpha_t = 1.0
g.title_substate = TitleSubstate.PROMPT
g.title_timer = 0.8
for _ in range(60):
    g._update_title_card_particles(1/60)
g.draw()
pygame.image.save(screen, '/tmp/title_1_prompt.png')

# Frame 2: save panel mid-animation (frac=0.55)
g.title_substate = TitleSubstate.SAVE
g.save_open_t = 0.55
g.draw()
pygame.image.save(screen, '/tmp/title_2_save_opening.png')

# Frame 3: save panel fully open
g.save_open_t = 1.0
g.draw()
pygame.image.save(screen, '/tmp/title_3_save_open.png')

# Frame 4: loading screen mid-fill
g.state = GameState.LOADING
g.loading = LoadingScreen()
g.loading.t = 0.55
g.draw()
pygame.image.save(screen, '/tmp/title_4_loading.png')

print('saved /tmp/title_1..4_*.png')
pygame.quit()
