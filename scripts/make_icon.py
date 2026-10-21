"""Generates the Voice Bubble icons: a speech bubble with sound bars, in the bubble's gradient.

Writes static/icon.svg (master/README), static/icon.png (256px), and static/icon.ico (16-256px, used by the tray).
Small sizes use a 3-bar variant so they stay readable. Requires Pillow: python scripts/make_icon.py
"""
import os
from PIL import Image, ImageDraw

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
GRADIENT = ('#667eea', '#764ba2')  # same as the mic button in bubble.html

# Geometry in a 100x100 box
BUBBLE = (4, 8, 96, 76)          # rounded rectangle
RADIUS = 22
TAIL = [(20, 68), (44, 74), (12, 94)]  # bottom-left tail
BARS_LARGE = ([16, 30, 44, 30, 16], 8, 6)  # heights, width, gap
BARS_SMALL = ([26, 46, 26], 12.5, 12.5)  # 2px bars + 2px gaps at 16px, pixel-aligned
BAR_CENTER_Y = 42

def bar_rects(variant):
    heights, width, gap = variant
    total = len(heights) * width + (len(heights) - 1) * gap
    x = 50 - total / 2
    for h in heights:
        yield (x, BAR_CENTER_Y - h / 2, x + width, BAR_CENTER_Y + h / 2)
        x += width + gap

def hex_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))

def render(size, variant):
    ss = 8 if size < 64 else 4  # supersampling factor
    px = size * ss
    scale = px / 100

    def s(points):
        return [v * scale for v in points]

    mask = Image.new('L', (px, px), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(s(BUBBLE), radius=RADIUS * scale, fill=255)
    draw.polygon([(x * scale, y * scale) for x, y in TAIL], fill=255)

    # Diagonal gradient, top-left to bottom-right
    start, end = hex_rgb(GRADIENT[0]), hex_rgb(GRADIENT[1])
    gradient = Image.new('RGB', (px, px))
    g = gradient.load()
    for y in range(px):
        for x in range(px):
            t = (x + y) / (2 * (px - 1))
            g[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(start, end))

    icon = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)
    bars = ImageDraw.Draw(icon)
    for rect in bar_rects(variant):
        width = (rect[2] - rect[0]) * scale
        bars.rounded_rectangle(s(rect), radius=width / 2, fill=(255, 255, 255, 255))
    return icon.resize((size, size), Image.LANCZOS)

def svg():
    x0, y0, x1, y1 = BUBBLE
    tail = ' '.join(f'{x},{y}' for x, y in TAIL)
    bars = '\n  '.join(
        f'<rect x="{r[0]:g}" y="{r[1]:g}" width="{r[2] - r[0]:g}" height="{r[3] - r[1]:g}" rx="{(r[2] - r[0]) / 2:g}" fill="#fff"/>'
        for r in bar_rects(BARS_LARGE))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="100" y2="100">
      <stop offset="0" stop-color="{GRADIENT[0]}"/>
      <stop offset="1" stop-color="{GRADIENT[1]}"/>
    </linearGradient>
  </defs>
  <rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="{RADIUS}" fill="url(#g)"/>
  <polygon points="{tail}" fill="url(#g)"/>
  {bars}
</svg>
'''

if __name__ == '__main__':
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = {size: render(size, BARS_SMALL if size <= 24 else BARS_LARGE) for size in sizes}

    images[256].save(os.path.join(STATIC, 'icon.png'))
    # Pillow builds the .ico from the largest image unless given each size explicitly
    images[256].save(os.path.join(STATIC, 'icon.ico'), sizes=[(s, s) for s in sizes],
                     append_images=[images[s] for s in sizes if s != 256])
    with open(os.path.join(STATIC, 'icon.svg'), 'w', encoding='utf-8') as f:
        f.write(svg())
    print('Wrote static/icon.png, static/icon.ico, static/icon.svg')
