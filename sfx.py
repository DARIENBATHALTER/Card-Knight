"""
Sound effects system — pygame.mixer.Sound based (one-shot, multi-channel).
Independent of background music (pygame.mixer.music in game.py).
"""
from __future__ import annotations
import os
import pygame

_BASE   = os.path.dirname(os.path.abspath(__file__))
_SFX_DIR = os.path.join(_BASE, 'assets', 'sfx')
_CACHE: dict = {}


def init() -> None:
    """Load every audio file in assets/sfx/ keyed by stem. Idempotent.
    Call after pygame.init() (mixer is auto-inited if not already)."""
    if _CACHE:
        return  # already loaded
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
    except pygame.error as e:
        print(f"[sfx] mixer init failed: {e}")
        return

    if not os.path.isdir(_SFX_DIR):
        return

    for fname in sorted(os.listdir(_SFX_DIR)):
        if not fname.lower().endswith(('.mp3', '.wav', '.ogg')):
            continue
        name = os.path.splitext(fname)[0]
        path = os.path.join(_SFX_DIR, fname)
        try:
            _CACHE[name] = pygame.mixer.Sound(path)
        except pygame.error as e:
            print(f"[sfx] load failed for {fname}: {e}")

    # Allow up to 16 simultaneous sounds (deals can stack with other VFX)
    try:
        pygame.mixer.set_num_channels(16)
    except pygame.error:
        pass


def play(name: str, volume: float = 0.7) -> None:
    """Play a one-shot SFX by name (filename without extension)."""
    snd = _CACHE.get(name)
    if snd is None:
        return
    try:
        snd.set_volume(max(0.0, min(1.0, volume)))
        snd.play()
    except pygame.error:
        pass
