"""Generate icon.png (32x32) for orthogonal_measure plugin."""
import struct, zlib, os

W, H = 32, 32

BG      = (43, 87, 154, 255)
BORDER  = (26, 58, 106, 255)
BLUE    = (77, 166, 255, 255)
GREEN   = (77, 219, 122, 255)
RED     = (255, 68, 68, 255)
WHITE   = (255, 255, 255, 255)
WHITEA  = (255, 255, 255, 120)
TRANS   = (0, 0, 0, 0)

img = [[TRANS]*W for _ in range(H)]

# Circle background
cx, cy, R = 15.5, 15.5, 14.5
for y in range(H):
    for x in range(W):
        d2 = (x - cx)**2 + (y - cy)**2
        if d2 <= (R - 0.5)**2:
            img[y][x] = BG
        elif d2 <= (R + 0.5)**2:
            img[y][x] = BORDER

# Origin at pixel (8, 24)
ox, oy = 8, 24

# --- Y-axis (blue vertical from origin upward) ---
for y in range(4, oy + 1):
    for dx in (-1, 0):
        xx = ox + dx
        if 0 <= y < H and 0 <= xx < W:
            img[y][xx] = BLUE

# Y arrow head
for i in range(4):
    for s in (-1, 1):
        xx = ox + s * i - (1 if s == -1 else 0)
        yy = 5 + i
        if 0 <= yy < H and 0 <= xx < W:
            img[yy][xx] = BLUE

# --- X-axis (green horizontal from origin to right) ---
for x in range(ox, 28):
    for dy in (-1, 0):
        yy = oy + dy
        if 0 <= yy < H and 0 <= x < W:
            img[yy][x] = GREEN

# X arrow head
for i in range(4):
    for s in (-1, 1):
        yy = oy + s * i - (1 if s == -1 else 0)
        xx = 27 - i
        if 0 <= yy < H and 0 <= xx < W:
            img[yy][xx] = GREEN

# --- Right-angle mark at origin ---
size = 4
for i in range(size + 1):
    # vertical part
    yy = oy - i
    xx = ox
    if 0 <= yy < H and 0 <= xx < W:
        img[yy][xx] = WHITE
    # horizontal part
    yy2 = oy
    xx2 = ox + i
    if 0 <= yy2 < H and 0 <= xx2 < W:
        img[yy2][xx2] = WHITE
    # top of square
    yy3 = oy - size
    xx3 = ox + i
    if 0 <= yy3 < H and 0 <= xx3 < W:
        img[yy3][xx3] = WHITE
    # right of square
    yy4 = oy - i
    xx4 = ox + size
    if 0 <= yy4 < H and 0 <= xx4 < W:
        img[yy4][xx4] = WHITE

# --- Origin dot (red) ---
for dy in range(-2, 3):
    for dx in range(-2, 3):
        if abs(dy) + abs(dx) <= 2:
            yy, xx = oy + dy, ox + dx
            if 0 <= yy < H and 0 <= xx < W:
                img[yy][xx] = RED

# --- Constructed point at (22, 10) ---
px, py = 22, 10

# Dashed vertical line from (px, oy) up to (px, py)
for y in range(py, oy):
    if y % 3 != 0:
        if 0 <= y < H and 0 <= px < W:
            img[y][px] = WHITEA

# Dashed horizontal line from (ox, py) right to (px, py)
for x in range(ox, px):
    if x % 3 != 0:
        if 0 <= py < H and 0 <= x < W:
            img[py][x] = WHITEA

# Constructed point dot (red with white border)
for dy in range(-2, 3):
    for dx in range(-2, 3):
        d = abs(dy) + abs(dx)
        yy, xx = py + dy, px + dx
        if 0 <= yy < H and 0 <= xx < W:
            if d <= 1:
                img[yy][xx] = RED
            elif d == 2:
                img[yy][xx] = WHITE

# --- Encode as PNG ---
raw = b''
for row in img:
    raw += b'\x00'
    for r, g, b, a in row:
        raw += struct.pack('BBBB', r, g, b, a)

out = b'\x89PNG\r\n\x1a\n'

def chunk(ctype, data):
    c = ctype + data
    crc = zlib.crc32(c) & 0xffffffff
    return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)

out += chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 6, 0, 0, 0))
out += chunk(b'IDAT', zlib.compress(raw, 9))
out += chunk(b'IEND', b'')

icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
with open(icon_path, 'wb') as f:
    f.write(out)
print(f"icon.png written: {len(out)} bytes")
