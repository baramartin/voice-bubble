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
    draw.text((x, 290), 'Type anywhere with your voice.', font=font('seguisb.ttf', 40), fill=TEXT)
    draw.text((x, 342), 'Have any text read aloud.', font=font('seguisb.ttf', 40), fill=TEXT)

    # "Bring your own key" pill: the first thing to know before trying it
    pill_font = font('seguisb.ttf', 26)
    pill_text = 'Bring your own key: Gemini (free tier) or OpenAI'
    left, top, right, bottom = draw.textbbox((0, 0), pill_text, font=pill_font)
    pad_x, pad_y, pill_y = 22, 12, 425
    draw.rounded_rectangle((x, pill_y, x + right - left + 2 * pad_x, pill_y + bottom - top + 2 * pad_y + 4),
                           radius=26, fill=(60, 58, 110), outline=ACCENT, width=2)
    draw.text((x + pad_x - left, pill_y + pad_y - top + 2), pill_text, font=pill_font, fill=TEXT)

    draw.text((x, 505), 'Free & open source  ·  smart cleanup  ·  30 voices  ·  Windows',
              font=font('segoeui.ttf', 26), fill=MUTED)
    draw.text((x, 548), 'github.com/baramartin/voice-bubble', font=font('segoeui.ttf', 26), fill=ACCENT)

    out = os.path.join(ROOT, 'docs', 'social-preview.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    image.save(out, optimize=True)
    print(f'Wrote {os.path.relpath(out, ROOT)}')

if __name__ == '__main__':
    main()
