"""Generates docs/social-preview.png (1280x640), the image shown when the repo link is shared.

Upload it on GitHub under Settings > General > Social preview. Requires Pillow and Windows' Segoe UI fonts:
python scripts/make_social_preview.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FONTS = r'C:\Windows\Fonts'
W, H = 1280, 640
BACKGROUND = ((24, 24, 34), (38, 30, 58))  # dark, like the bubble, drifting toward its purple
TEXT, MUTED, ACCENT = (255, 255, 255), (178, 178, 200), (139, 156, 255)

def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)

def main():
    image = Image.new('RGB', (W, H))
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            t = (x / W) * 0.6 + (y / H) * 0.4
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(*BACKGROUND))

    icon = Image.open(os.path.join(ROOT, 'static', 'icon.png')).convert('RGBA').resize((220, 220), Image.LANCZOS)
    image.paste(icon, (110, (H - 220) // 2 - 10), icon)

    draw = ImageDraw.Draw(image)
    x = 380
    draw.text((x, 170), 'Voice Bubble', font=font('segoeuib.ttf', 92), fill=TEXT)
    draw.text((x, 300), 'Type anywhere with your voice.', font=font('seguisb.ttf', 40), fill=TEXT)
    draw.text((x, 352), 'Have any text read aloud.', font=font('seguisb.ttf', 40), fill=TEXT)
    draw.text((x, 440), 'Gemini or OpenAI  ·  smart cleanup  ·  30 voices  ·  free & open source',
              font=font('segoeui.ttf', 26), fill=MUTED)
    draw.text((x, 485), 'Windows  ·  github.com/baramartin/voice-bubble', font=font('segoeui.ttf', 26), fill=ACCENT)

    out = os.path.join(ROOT, 'docs', 'social-preview.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    image.save(out, optimize=True)
    print(f'Wrote {os.path.relpath(out, ROOT)}')

if __name__ == '__main__':
    main()
