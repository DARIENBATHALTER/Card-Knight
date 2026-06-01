import pygame
import sys
from game import Game
from music import music as _music
import constants as C
import sprite_manager
import sfx
import gamepad

# Steam Controller / Steam Deck button → key mapping
_BUTTON_KEY = {
    0: pygame.K_z,       # A → confirm / action
    1: pygame.K_x,       # B → cancel / back
    7: pygame.K_ESCAPE,  # Start/Menu → pause / escape
}
_FULLSCREEN_BUTTON = 4   # L1 → fullscreen toggle
_DIR_KEY = {
    'up':    pygame.K_UP,
    'down':  pygame.K_DOWN,
    'left':  pygame.K_LEFT,
    'right': pygame.K_RIGHT,
}
_DEADZONE = 0.4


_fullscreen = False


def _fake_key(key: int, typ: int = pygame.KEYDOWN) -> pygame.event.Event:
    return pygame.event.Event(typ, key=key, mod=0, unicode='', scancode=0)


def _toggle_fullscreen(screen):
    global _fullscreen
    _fullscreen = not _fullscreen
    flags = pygame.FULLSCREEN if _fullscreen else pygame.RESIZABLE
    return pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), flags)


def _dispatch_dir_changes(game, new_dirs: set, prev_dirs: set) -> None:
    """Post synthetic KEYDOWN/UP events for direction state changes (menu nav)."""
    for d, k in _DIR_KEY.items():
        if d in new_dirs and d not in prev_dirs:
            game.handle_event(_fake_key(k, pygame.KEYDOWN))
        elif d not in new_dirs and d in prev_dirs:
            game.handle_event(_fake_key(k, pygame.KEYUP))


def main():
    pygame.init()
    pygame.joystick.init()
    pygame.display.set_caption(C.TITLE)

    screen = pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H), pygame.RESIZABLE)

    sprite_manager.init()
    sfx.init()
    clock = pygame.time.Clock()
    game  = Game(screen)

    joysticks: dict = {}
    prev_dirs: set  = set()

    try:
        while True:
            dt = clock.tick(C.FPS) / 1000.0
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

                elif event.type == pygame.JOYDEVICEADDED:
                    joy = pygame.joystick.Joystick(event.device_index)
                    joy.init()
                    joysticks[joy.get_instance_id()] = joy

                elif event.type == pygame.JOYDEVICEREMOVED:
                    joysticks.pop(event.instance_id, None)

                elif event.type == pygame.JOYBUTTONDOWN:
                    gamepad.buttons_held.add(event.button)
                    if event.button == _FULLSCREEN_BUTTON:
                        screen = _toggle_fullscreen(screen)
                        game.screen = screen
                    else:
                        k = _BUTTON_KEY.get(event.button)
                        if k:
                            game.handle_event(_fake_key(k, pygame.KEYDOWN))

                elif event.type == pygame.JOYBUTTONUP:
                    gamepad.buttons_held.discard(event.button)
                    k = _BUTTON_KEY.get(event.button)
                    if k:
                        game.handle_event(_fake_key(k, pygame.KEYUP))

                elif event.type == pygame.JOYHATMOTION:
                    hx, hy = event.value
                    gamepad.update_hat(hx, hy)
                    new_dirs = gamepad.active()
                    _dispatch_dir_changes(game, new_dirs, prev_dirs)
                    prev_dirs = set(new_dirs)

                elif event.type == pygame.JOYAXISMOTION:
                    gamepad.update_axis(event.axis, event.value, _DEADZONE)
                    new_dirs = gamepad.active()
                    _dispatch_dir_changes(game, new_dirs, prev_dirs)
                    prev_dirs = set(new_dirs)

                else:
                    game.handle_event(event)

            game.update(dt)
            game.draw()
            pygame.display.flip()
    finally:
        _music.stop()
        pygame.quit()


if __name__ == "__main__":
    main()
