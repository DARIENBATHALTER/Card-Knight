"""
Background music — cross-platform via pygame.mixer.music.
Singleton `music` instance. Use music.play(path), music.stop(fade_ms=...).
"""
from __future__ import annotations
import os
import pygame

_BASE = os.path.dirname(os.path.abspath(__file__))


class _MixerMusic:
    """Looping background music via pygame.mixer.music.

    Tracks the current path so repeated play() calls with the same file are
    no-ops (avoids restarting music when re-entering the same state).
    """

    def __init__(self):
        self._initialized = False
        self._path        = None

    def _ensure_init(self) -> bool:
        if self._initialized:
            return True
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 1024)
                pygame.mixer.init()
            self._initialized = True
            return True
        except pygame.error as e:
            print(f"[music] mixer init failed: {e}")
            return False

    def play(self, path: str, volume: float = 0.75, loop: bool = True):
        if not os.path.exists(path):
            print(f"[music] file not found: {path}")
            return
        if not self._ensure_init():
            return
        if self._path == path and pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(volume)
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=-1 if loop else 0)
            self._path = path
        except pygame.error as e:
            print(f"[music] failed to play {path}: {e}")
            self._path = None

    def stop(self, fade_ms: int = 0):
        if not self._initialized:
            return
        try:
            if fade_ms > 0:
                pygame.mixer.music.fadeout(fade_ms)
            else:
                pygame.mixer.music.stop()
        except pygame.error:
            pass
        self._path = None

    def set_volume(self, volume: float):
        if self._initialized:
            try:
                pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            except pygame.error:
                pass


music = _MixerMusic()


def track_path(name: str) -> str:
    """Convenience: full path to a track file in assets/music/."""
    return os.path.join(_BASE, 'assets', 'music', f'{name}.mp3')
