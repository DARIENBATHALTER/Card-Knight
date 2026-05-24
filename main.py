import pygame
import sys
from game import Game, _music
import constants as C
import sprite_manager


def main():
    pygame.init()
    pygame.display.set_caption(C.TITLE)

    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.RESIZABLE)

    sprite_manager.init()
    clock = pygame.time.Clock()
    game  = Game(screen)

    try:
        while True:
            dt = clock.tick(C.FPS) / 1000.0
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                game.handle_event(event)

            game.update(dt)
            game.draw()
            pygame.display.flip()
    finally:
        _music.stop()
        pygame.quit()


if __name__ == "__main__":
    main()
