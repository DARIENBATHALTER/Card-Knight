"""
Centralized font loading. Two families:
  pixel(size)  — Press Start 2P: labels, UI, chip codes (retro/authentic)
  mono(size)   — VT323: descriptions, numbers, larger readout text
Both fall back to pygame's built-in Font(None) if the TTF is missing.
"""
import os
import pygame

_BASE  = os.path.dirname(os.path.abspath(__file__))
_PS2P  = os.path.join(_BASE, 'assets', 'fonts', 'PressStart2P.ttf')
_VT323 = os.path.join(_BASE, 'assets', 'fonts', 'VT323.ttf')
_cache: dict = {}


def pixel(size: int, bold: bool = False) -> pygame.font.Font:
    """Press Start 2P — blocky retro.  Best at multiples of 8 (8, 16, 24…)."""
    key = ('ps2p', size, bold)
    if key not in _cache:
        try:
            f = pygame.font.Font(_PS2P, size)
        except Exception:
            f = pygame.font.Font(None, size + 6)
        if bold:
            f.set_bold(True)
        _cache[key] = f
    return _cache[key]


def serif(size: int, bold: bool = False) -> pygame.font.Font:
    """Georgia / Palatino — fantasy serif for UI labels and dialogue."""
    key = ('serif', size, bold)
    if key not in _cache:
        for name in ('georgia', 'palatino', 'baskerville', 'times', 'serif'):
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                _cache[key] = f
                break
            except Exception:
                continue
        else:
            _cache[key] = pygame.font.Font(None, size + 4)
    return _cache[key]


def mono(size: int, bold: bool = False) -> pygame.font.Font:
    """VT323 — slim CRT mono.  Reads cleanly at 12-24px."""
    key = ('vt323', size, bold)
    if key not in _cache:
        try:
            f = pygame.font.Font(_VT323, size)
        except Exception:
            f = pygame.font.Font(None, size + 4)
        if bold:
            f.set_bold(True)
        _cache[key] = f
    return _cache[key]
