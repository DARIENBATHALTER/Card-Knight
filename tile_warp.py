"""
Perspective projection for the battle grid.

The grid is a 4-corner trapezoid measured off the platform.png reference:
    TL=(246, 312)  TR=(1034, 312)
    BL=(136, 550)  BR=(1144, 550)

This module:
  - Computes the 4 screen-space corners of any tile (col, row).
  - Provides tile_center() / tile_floor_center() for placing entities.
  - Bakes a source sprite into a warped pygame.Surface via PIL's PERSPECTIVE transform.
"""
from __future__ import annotations
import math
import numpy as np
import pygame
from PIL import Image

import constants as C


# ── Grid corners (measured from platform.png, 1280×720) ───────────────────────

GRID_TL = (246.0, 312.0)
GRID_TR = (1034.0, 312.0)
GRID_BL = (136.0, 550.0)
GRID_BR = (1144.0, 550.0)

GRID_COLS = C.GRID_COLS   # 8
GRID_ROWS = C.GRID_ROWS   # 4


def _row_endpoints(row: float):
    """Linearly interpolate left/right grid edges at a fractional row (0=back, ROWS=front)."""
    t = row / GRID_ROWS
    lx = GRID_TL[0] + t * (GRID_BL[0] - GRID_TL[0])
    rx = GRID_TR[0] + t * (GRID_BR[0] - GRID_TR[0])
    y  = GRID_TL[1] + t * (GRID_BL[1] - GRID_TL[1])
    return lx, rx, y


def _grid_corner(col: float, row: float):
    """Screen-space position of a grid vertex (col in [0..COLS], row in [0..ROWS])."""
    lx, rx, y = _row_endpoints(row)
    x = lx + (col / GRID_COLS) * (rx - lx)
    return (x, y)


def tile_quad(col: int, row: int):
    """(TL, TR, BR, BL) screen-space corners of tile (col, row)."""
    return (
        _grid_corner(col,     row),
        _grid_corner(col + 1, row),
        _grid_corner(col + 1, row + 1),
        _grid_corner(col,     row + 1),
    )


def tile_center(col: int, row: int):
    """Center of tile (col, row) in screen space."""
    quad = tile_quad(col, row)
    cx = sum(p[0] for p in quad) / 4
    cy = sum(p[1] for p in quad) / 4
    return (int(round(cx)), int(round(cy)))


def tile_floor_center(col: int, row: int):
    """Bottom-center of tile (col, row) — where an entity's feet would rest."""
    bl = _grid_corner(col,     row + 1)
    br = _grid_corner(col + 1, row + 1)
    return (int(round((bl[0] + br[0]) / 2)), int(round((bl[1] + br[1]) / 2)))


def row_center_y(row: int) -> int:
    """Vertical center of row `row` in screen space (uniform across columns in a row)."""
    _, _, y = _row_endpoints(row + 0.5)
    return int(round(y))


def row_x_bounds(row: int):
    """(left_x, right_x) at the vertical center of row `row`."""
    lx, rx, _ = _row_endpoints(row + 0.5)
    return lx, rx


def col_at_x_in_row(x: float, row: int) -> int:
    """Reverse-map screen x within row `row` to a column index; returns -1 if outside."""
    lx, rx = row_x_bounds(row)
    if x < lx or x > rx:
        return -1
    return int((x - lx) / (rx - lx) * GRID_COLS)


def row_scale(row: int) -> float:
    """Depth scale factor for entities sitting on row `row` (back rows smaller)."""
    # Row 0 width per tile ≈ 98, row 3 width ≈ 126. Scale linearly.
    front_w = (GRID_BR[0] - GRID_BL[0]) / GRID_COLS
    back_w  = (GRID_TR[0] - GRID_TL[0]) / GRID_COLS
    row_w   = back_w + (row + 0.5) / GRID_ROWS * (front_w - back_w)
    return row_w / front_w


# ── Perspective transform ─────────────────────────────────────────────────────

def find_perspective_coeffs(dst_corners, src_corners):
    """Solve for 8 coefficients (a..h) such that PIL.Image.transform(..., PERSPECTIVE, coeffs)
    samples src_corners[i] for output pixel dst_corners[i].

    PIL maps OUTPUT->INPUT: src_x = (a*x+b*y+c)/(g*x+h*y+1), src_y = (d*x+e*y+f)/(g*x+h*y+1).
    Each corner gives 2 equations → 8 equations, 8 unknowns.
    """
    matrix = []
    target = []
    for (dx, dy), (sx, sy) in zip(dst_corners, src_corners):
        matrix.append([dx, dy, 1, 0, 0, 0, -dx * sx, -dy * sx])
        matrix.append([0, 0, 0, dx, dy, 1, -dx * sy, -dy * sy])
        target.append(sx)
        target.append(sy)
    A = np.array(matrix, dtype=np.float64)
    B = np.array(target, dtype=np.float64)
    return np.linalg.solve(A, B).tolist()


def bake_quad(pil_img: Image.Image, dst_quad):
    """Warp pil_img into the trapezoid `dst_quad` (TL, TR, BR, BL in screen coords).

    Returns (pygame.Surface, (anchor_x, anchor_y)). Blit the surface at the anchor
    to position the warped quad on the destination screen.
    """
    xs = [p[0] for p in dst_quad]
    ys = [p[1] for p in dst_quad]
    min_x = int(math.floor(min(xs)))
    min_y = int(math.floor(min(ys)))
    max_x = int(math.ceil(max(xs)))
    max_y = int(math.ceil(max(ys)))
    out_w = max(1, max_x - min_x)
    out_h = max(1, max_y - min_y)

    # Destination corners in local (output-image) coordinates
    dst_local = [(p[0] - min_x, p[1] - min_y) for p in dst_quad]

    src_rgba = pil_img.convert('RGBA')
    src_w, src_h = src_rgba.size
    src_corners = [(0, 0), (src_w, 0), (src_w, src_h), (0, src_h)]

    coeffs = find_perspective_coeffs(dst_local, src_corners)

    warped = src_rgba.transform(
        (out_w, out_h),
        Image.PERSPECTIVE,
        coeffs,
        Image.BICUBIC,
    )

    surf = pygame.image.frombuffer(warped.tobytes(), (out_w, out_h), 'RGBA').convert_alpha()
    return surf, (min_x, min_y)
