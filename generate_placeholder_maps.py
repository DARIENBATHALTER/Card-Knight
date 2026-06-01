"""Generate placeholder overworld map backgrounds.

Run once: python3 generate_placeholder_maps.py
Replace PNGs with real art when ready — overworld loads them by path.
"""
import pygame
import os

pygame.init()
BASE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(BASE, 'assets', 'overworld')
os.makedirs(OUT, exist_ok=True)


def save(surf, name):
    path = os.path.join(OUT, name)
    from PIL import Image
    w, h = surf.get_size()
    raw = pygame.image.tostring(surf, 'RGB')
    img = Image.frombytes('RGB', (w, h), raw)
    img.save(path)
    print(f"  Saved {path}")


def fill_grad(surf, top_col, bot_col):
    w, h = surf.get_size()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))


def draw_building(surf, x, y, w, h, wall_col, roof_col, label=''):
    roof_h = h // 3
    # Wall
    pygame.draw.rect(surf, wall_col, (x, y + roof_h, w, h - roof_h))
    pygame.draw.rect(surf, (0, 0, 0), (x, y + roof_h, w, h - roof_h), 2)
    # Roof (triangle)
    pts = [(x, y + roof_h), (x + w, y + roof_h), (x + w // 2, y)]
    pygame.draw.polygon(surf, roof_col, pts)
    pygame.draw.polygon(surf, (0, 0, 0), pts, 2)
    # Door
    dw, dh = max(8, w // 5), max(12, h // 3)
    dx = x + w // 2 - dw // 2
    dy = y + h - dh
    pygame.draw.rect(surf, (60, 35, 15), (dx, dy, dw, dh))
    pygame.draw.rect(surf, (0, 0, 0), (dx, dy, dw, dh), 1)
    # Window
    if w > 48:
        ww, wh = max(8, w // 5), max(8, h // 5)
        wx = x + w // 4 - ww // 2
        wy = y + roof_h + (h - roof_h) // 3
        pygame.draw.rect(surf, (180, 220, 255), (wx, wy, ww, wh))
        pygame.draw.rect(surf, (0, 0, 0), (wx, wy, ww, wh), 1)
    # Label
    if label:
        font = pygame.font.Font(None, 18)
        ts = font.render(label, True, (240, 235, 220))
        surf.blit(ts, (x + w // 2 - ts.get_width() // 2, y - 18))


def draw_tree(surf, x, y, r=22):
    pygame.draw.circle(surf, (30, 80, 30), (x, y - r // 2), r)
    pygame.draw.circle(surf, (50, 110, 50), (x - 4, y - r // 2 - 4), r - 6)
    pygame.draw.rect(surf, (80, 50, 20), (x - 4, y, 8, 14))


def draw_path(surf, points, width=28, col=(160, 140, 100)):
    for i in range(len(points) - 1):
        pygame.draw.line(surf, col, points[i], points[i + 1], width)


def draw_exit_marker(surf, rect, label='EXIT'):
    pygame.draw.rect(surf, (255, 220, 60), rect, 3)
    font = pygame.font.Font(None, 16)
    ts = font.render(label, True, (255, 220, 60))
    surf.blit(ts, (rect.x + 2, rect.y + 2))


def draw_shrine(surf, cx, cy):
    # Simple stone arch
    pygame.draw.rect(surf, (100, 95, 90), (cx - 20, cy - 30, 40, 35))
    pygame.draw.rect(surf, (80, 75, 70), (cx - 20, cy - 30, 40, 35), 2)
    # Arch cap
    pygame.draw.polygon(surf, (120, 115, 110),
                         [(cx - 22, cy - 30), (cx + 22, cy - 30), (cx, cy - 50)])
    # Crystal glow
    pygame.draw.circle(surf, (80, 160, 255), (cx, cy - 38), 6)
    pygame.draw.circle(surf, (200, 230, 255), (cx, cy - 38), 3)


# ──────────────────────────────────────────────────────────────────────────────
# CARDHOLLOW  1280×720
# ──────────────────────────────────────────────────────────────────────────────
print("Generating Cardhollow...")
W, H = 1280, 720
surf = pygame.Surface((W, H))
fill_grad(surf, (88, 140, 72), (62, 105, 50))

# Ground path (leads to west exit)
path_pts = [(0, 360), (180, 360), (280, 400), (400, 400),
            (500, 360), (640, 360), (780, 380), (900, 360)]
draw_path(surf, path_pts, 40, (155, 138, 95))

# Trees around edges
for tx, ty in [(80, 120), (200, 80), (900, 100), (1050, 130), (1150, 80),
               (120, 600), (300, 640), (1000, 620), (1150, 580), (1220, 300)]:
    draw_tree(surf, tx, ty)

# Card Shrine (center)
draw_shrine(surf, 640, 340)
font = pygame.font.Font(None, 16)
ts = font.render("Card Shrine", True, (200, 195, 160))
surf.blit(ts, (616, 300))

# Buildings
draw_building(surf, 160, 180, 120, 100, (200, 175, 140), (160, 80, 60), "Oden's House")
draw_building(surf, 360, 200, 140, 110, (185, 168, 135), (140, 70, 55), "Courier Post")
draw_building(surf, 820, 190, 110, 90,  (190, 172, 138), (130, 75, 50), "Store")
draw_building(surf, 1020, 220, 100, 85, (195, 178, 142), (145, 82, 58), "Neighbor")

# West exit marker
exit_rect = pygame.Rect(0, 285, 35, 150)
draw_exit_marker(surf, exit_rect, '→ Briar')

# Location label
font_big = pygame.font.Font(None, 48)
ts = font_big.render("CARDHOLLOW", True, (240, 235, 220))
surf.blit(ts, (W // 2 - ts.get_width() // 2, 22))

save(surf, 'cardhollow.png')


# ──────────────────────────────────────────────────────────────────────────────
# BRIAR ROAD  1280×2880
# ──────────────────────────────────────────────────────────────────────────────
print("Generating Briar Road...")
W, H = 1280, 2880
surf = pygame.Surface((W, H))
fill_grad(surf, (35, 65, 30), (45, 80, 38))

# Winding path: bottom → top with curves
path_segs = [
    [(580, 2880), (580, 2600), (620, 2400)],
    [(620, 2400), (700, 2200), (680, 2000)],
    [(680, 2000), (600, 1800), (640, 1600)],
    [(640, 1600), (700, 1400), (660, 1200)],
    [(660, 1200), (580, 1000), (620, 800)],
    [(620, 800),  (660, 600),  (640, 400)],
    [(640, 400),  (620, 200),  (640, 0)],
]
for seg in path_segs:
    draw_path(surf, seg, 48, (148, 132, 90))

# Trees lining the path
import random; random.seed(42)
for _ in range(80):
    tx = random.choice([random.randint(20, 520), random.randint(740, 1260)])
    ty = random.randint(20, H - 20)
    draw_tree(surf, tx, ty, random.randint(18, 30))

# Ruined shrine (atmosphere)
draw_shrine(surf, 380, 1800)
ts = font.render("Ruined Shrine", True, (160, 150, 120))
surf.blit(ts, (350, 1760))

# Encounter zone marker (middle of road)
enc_rect = pygame.Rect(540, 1350, 200, 200)
pygame.draw.rect(surf, (200, 60, 60), enc_rect, 3)
ts = font.render("! ENCOUNTER ZONE", True, (200, 60, 60))
surf.blit(ts, (enc_rect.x, enc_rect.y - 18))

# Exit markers
draw_exit_marker(surf, pygame.Rect(540, 0, 200, 30),   '→ Veilgate')
draw_exit_marker(surf, pygame.Rect(540, 2850, 200, 30), '→ Cardhollow')

# Location label
ts = font_big.render("THE BRIAR ROAD", True, (210, 205, 180))
surf.blit(ts, (W // 2 - ts.get_width() // 2, 40))

save(surf, 'briar_road.png')


# ──────────────────────────────────────────────────────────────────────────────
# VEILGATE  1280×720
# ──────────────────────────────────────────────────────────────────────────────
print("Generating Veilgate...")
W, H = 1280, 720
surf = pygame.Surface((W, H))
fill_grad(surf, (72, 80, 100), (55, 62, 82))

# Stone cobble ground (lighter strip)
pygame.draw.rect(surf, (90, 88, 84), (0, 300, W, 200))

# Path from east entrance
path_pts = [(1280, 360), (1100, 360), (950, 380), (800, 360), (640, 360)]
draw_path(surf, path_pts, 40, (110, 105, 95))

# Trees / atmosphere
for tx, ty in [(60, 100), (180, 80), (100, 580), (200, 620),
               (1100, 90), (1200, 120), (1150, 600)]:
    draw_tree(surf, tx, ty)

# Card Shrine (left of center)
draw_shrine(surf, 420, 340)

# Buildings
draw_building(surf, 150, 180, 130, 105, (155, 148, 162), (90, 70, 110), "Edric's House")
draw_building(surf, 700, 160, 180, 140, (145, 140, 155), (80, 65, 100), "Dojo")
draw_building(surf, 980, 200, 120, 95,  (150, 145, 158), (95, 72, 108), "Inn")
draw_building(surf, 1100, 230, 110, 90, (148, 142, 155), (88, 68, 105), "Store")

# East exit marker
draw_exit_marker(surf, pygame.Rect(1245, 285, 35, 150), '→ Briar')

# Location label
ts = font_big.render("VEILGATE", True, (230, 225, 245))
surf.blit(ts, (W // 2 - ts.get_width() // 2, 22))

save(surf, 'veilgate.png')


# ──────────────────────────────────────────────────────────────────────────────
# INTERIORS  640×360 each
# ──────────────────────────────────────────────────────────────────────────────

def make_interior(wall_col, floor_col, title, door_label='EXIT'):
    W, H = 1280, 720
    s = pygame.Surface((W, H))
    # Floor
    s.fill(floor_col)
    # Walls (top band)
    pygame.draw.rect(s, wall_col, (0, 0, W, 90))
    pygame.draw.line(s, (0, 0, 0), (0, 90), (W, 90), 3)
    # Baseboard
    pygame.draw.rect(s, tuple(max(0, c - 30) for c in floor_col), (0, 310, W, 12))
    # Door (south center)
    pygame.draw.rect(s, (55, 32, 12), (W // 2 - 24, 290, 48, 70))
    pygame.draw.rect(s, (0, 0, 0), (W // 2 - 24, 290, 48, 70), 2)
    pygame.draw.circle(s, (180, 140, 50), (W // 2 + 18, 330), 4)
    # Title
    font_t = pygame.font.Font(None, 32)
    ts = font_t.render(title, True, (240, 235, 210))
    s.blit(ts, (W // 2 - ts.get_width() // 2, 8))
    # Exit marker
    ex_rect = pygame.Rect(W // 2 - 40, 330, 80, 30)
    draw_exit_marker(s, ex_rect, door_label)
    return s


print("Generating interiors...")

# Oden's House
s = make_interior((130, 100, 75), (175, 148, 110), "Oden's House")
# Furniture suggestion
pygame.draw.rect(s, (100, 75, 50), (80, 140, 60, 40))   # table
pygame.draw.rect(s, (90, 68, 45), (440, 150, 80, 30))   # bed
save(s, 'interior_cardhollow_home.png')

# Courier Post
s = make_interior((90, 80, 70), (155, 142, 118), "Courier Post")
# Counter
pygame.draw.rect(s, (110, 88, 62), (180, 180, 280, 40))
pygame.draw.rect(s, (80, 62, 42), (180, 180, 280, 40), 2)
# Mailboxes on wall
for i in range(5):
    pygame.draw.rect(s, (70, 60, 50), (100 + i * 90, 110, 70, 45))
    pygame.draw.rect(s, (0, 0, 0), (100 + i * 90, 110, 70, 45), 1)
save(s, 'interior_cardhollow_courier.png')

# Edric's House
s = make_interior((55, 48, 72), (88, 80, 105), "Edric's Study")
# Bookshelves on walls
pygame.draw.rect(s, (65, 50, 38), (30, 95, 100, 140))
pygame.draw.rect(s, (65, 50, 38), (510, 95, 100, 140))
for row in range(3):
    for col in range(4):
        c = ((150 + col * 30) % 256, (80 + row * 40) % 256, (60 + col * 20) % 256)
        pygame.draw.rect(s, c, (35 + col * 22, 100 + row * 42, 18, 36))
        pygame.draw.rect(s, c, (515 + col * 22, 100 + row * 42, 18, 36))
# Desk
pygame.draw.rect(s, (80, 62, 44), (220, 200, 200, 40))
# Card case on desk
pygame.draw.rect(s, (40, 35, 60), (290, 185, 60, 20))
pygame.draw.rect(s, (180, 160, 220), (290, 185, 60, 20), 2)
save(s, 'interior_veilgate_edric.png')

# Dojo (overworld version — for walking around before/after battle)
s = make_interior((40, 35, 35), (70, 65, 65), "The Dojo")
# Duel mat outline
pygame.draw.rect(s, (80, 80, 90), (120, 130, 400, 160))
pygame.draw.rect(s, (100, 100, 120), (120, 130, 400, 160), 3)
pygame.draw.line(s, (120, 100, 100), (320, 130), (320, 290), 2)
# Banner placeholders
pygame.draw.rect(s, (40, 60, 120), (30,  100, 25, 60))
pygame.draw.rect(s, (120, 40, 40), (585, 100, 25, 60))
save(s, 'interior_veilgate_dojo.png')

print("Done. All placeholder maps saved to assets/overworld/")
