import pygame
import sys
from game import Game
import constants as C
import sprite_manager


def main():
    pygame.init()
    pygame.display.set_caption(C.TITLE)

    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.RESIZABLE)

    sprite_manager.init()
    clock = pygame.time.Clock()
    game  = Game(screen)

    while True:
        dt = clock.tick(C.FPS) / 1000.0
        dt = min(dt, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        game.update(dt)
        game.draw()
        pygame.display.flip()


if __name__ == "__main__":
    main()
