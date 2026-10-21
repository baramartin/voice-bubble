<p align="center">
  <img src="static/icon.svg" width="96" alt="Voice Bubble icon">
</p>

<h1 align="center">Voice Bubble</h1>

<p align="center">
  A floating bubble for <b>Windows</b> that lets you <b>type anywhere with your voice</b> and <b>have any text read aloud</b>.
</p>

<p align="center">
  <sub>🤖 Written by <a href="https://claude.com/claude-code">Claude</a> (Anthropic's AI) in Claude Code, from ideas, direction and testing by <a href="https://github.com/baramartin">Martin Bara</a>.</sub>
</p>

---

A free, open-source **voice typing** (speech-to-text) and **text-to-speech** tool, powered by Google Gemini or OpenAI.

Press a hotkey, talk, press it again, and the transcript is pasted into whatever window you were using. By default **Smart mode** tidies up what you said on the way: the ums disappear, "Tuesday, no, Wednesday" becomes "Wednesday", and spoken lists become real lists. Other styles turn your words into bullet points or an email. Select text anywhere and press another hotkey to hear it spoken.

It runs on your own API keys (Google Gemini and/or OpenAI), so you pay per minute of audio. A typical dictation costs a fraction of a cent, Gemini has a free tier, and there's no subscription.

> **Platform:** built for and tested on **Windows 10/11**. macOS and Linux support is **experimental and untested**; see [Other platforms](#other-platforms).

## Features

- **System-wide dictation**: transcribed text is pasted straight into the window you were working in
- **Output styles**
  - **Smart mode** (default): removes filler words and false starts, applies your spoken corrections and formats lists
  - **Raw**, **No new lines**, **Professional email**, **Bullet points**, **Emojify**, **Make concise**
- **Choice of transcription engines**: **Gemini 3.5 Transcribe** (Smart mode is built in), **OpenAI `gpt-transcribe`** or **`gpt-4o-transcribe`**
- **Text-to-speech** with streaming playback, so audio starts before the whole clip is generated
  - **Gemini 3.8 Flash-Lite / Flash TTS** (30 voices) or **OpenAI `gpt-4o-mini-tts`** (13 voices)
  - Speech styles: news anchor, casual, poetry reading, storytelling, calm
- **Setup wizard** that checks your keys, shows prices and lets you preview voices
- Microphone picker, live level meter, and a Help tab right in the settings

## Quick start

You need [Python 3.10+](https://www.python.org/downloads/) and [Node.js 18+](https://nodejs.org/).

```bash
git clone https://github.com/baramartin/voice-bubble.git
cd voice-bubble
npm run setup
npm start
```

The setup wizard walks you through these steps (arrow keys to move, Enter to select):

1. **API keys**: paste a [Gemini key](https://aistudio.google.com/apikey) and/or an [OpenAI key](https://platform.openai.com/api-keys). Each one is checked on the spot.
2. **Dictation engine**, with prices
3. **Output style**: Smart mode is recommended
4. **Read-aloud engine**, with prices
5. **Voice**: press `P` to hear the highlighted voice before you pick it
6. **Custom vocabulary** (Gemini only): names or jargon it should recognize
7. **Hotkeys**: keep the defaults or pick your own
8. **Installing dependencies** (`pip` + `npm`)
9. **Shortcuts** (Windows): a desktop shortcut and, if you like, starting with Windows

It writes a `.env` file. Run it again anytime to change your choices; your current values are kept as defaults. Everything except the API keys can also be changed later in the bubble's settings.

## Usage

| Action | How |
|---|---|
| Start / stop dictation | `Ctrl+Shift+Space` or click the mic |
| Read selected text aloud | `Ctrl+Alt+Shift+Space` (the same plus Alt). Press again to stop. Your clipboard is left as it was |
| Read the clipboard aloud | Click the speaker button |
| Change style, engine, mic or voice | Click the settings button on the bubble (the Help tab lists all of this too) |
| Hear a voice | Click it in Settings → Read aloud |

The hotkeys are global, so they work in every app and take over those combinations everywhere. If another app already owns one of them, the bubble tells you on startup; pick different ones with `npm run setup` (or `HOTKEY_DICTATE` / `HOTKEY_READ_ALOUD` in `.env`).

## Pricing

Approximate paid-tier prices as of October 2026. Check [Gemini](https://ai.google.dev/gemini-api/docs/pricing) and [OpenAI](https://openai.com/api/pricing/) for current numbers.

| Engine | Price |
|---|---|
| Gemini 3.5 Transcribe | ~$0.005 / min (free tier available) |
| OpenAI gpt-transcribe | $0.0045 / min |
| OpenAI gpt-4o-transcribe | $0.006 / min |
| Gemini 3.8 Flash-Lite TTS | ~$0.009 / min (free tier available) |
| Gemini 3.8 Flash TTS | ~$0.0135 / min |
| OpenAI gpt-4o-mini-tts | ~$0.015 / min |

Gemini TTS prices double on January 1, 2027. Styles other than Smart mode and Raw make one extra, very cheap text-model call.

## Configuration

The wizard handles this, but you can also edit `.env` by hand (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (none) | Gemini engines |
| `OPENAI_API_KEY` | (none) | OpenAI engines |
| `DEFAULT_STT_ENGINE` | Gemini if you have the key | Dictation engine the bubble starts with |
| `DEFAULT_STYLE` | `clean` (Smart mode) | Output style the bubble starts with |
| `DEFAULT_TTS_ENGINE` / `DEFAULT_TTS_VOICE` | Gemini / `Kore` | Read-aloud engine and voice the bubble starts with |
| `GEMINI_TTS_MODEL` | `gemini-3.8-flash-lite-tts` | Or `gemini-3.8-flash-tts` |
| `GEMINI_TRANSCRIBE_VOCABULARY` | (none) | Comma-separated names or jargon, e.g. `Kubernetes, BigQuery` |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash-lite` | Output styles when you have no OpenAI key |
| `HOTKEY_DICTATE` | `Ctrl+Shift+Space` | Global dictation hotkey ([Electron accelerator](https://www.electronjs.org/docs/latest/api/accelerator) format) |
| `HOTKEY_READ_ALOUD` | `Ctrl+Alt+Shift+Space` | Global read-aloud hotkey |

Choices you make in the bubble's settings are remembered and take precedence over these defaults.

## Other platforms

Everything except pasting into other apps is cross-platform. Pasting works like this:

- **macOS (experimental):** the bubble is a floating panel that doesn't take focus, and pasting sends ⌘V through `osascript`. macOS will ask you to allow **Accessibility** access (System Settings → Privacy & Security → Accessibility) for the app or terminal you start Voice Bubble from.
- **Linux (experimental):** on X11, install `xdotool` for automatic pasting. Without it (for example on Wayland), the text is copied and the bubble shows *Copied, paste it*.

The hotkeys are the same on every platform (`Ctrl` is the Control key on a Mac, `Alt` is Option). If you try it on a Mac or Linux, issues and fixes are very welcome.

## How it works

- `main.js` (Electron) is the floating bubble window, the global hotkeys, and pasting into the target window
- `bubble.html` is the bubble UI: recording, settings, and streaming audio playback
- `app.py` (Flask) is a local backend on `localhost:5000` that keeps your API keys out of the UI and calls Gemini / OpenAI
  - `POST /transcribe` turns audio into text
  - `POST /transform` restyles text (GPT-4o, or Gemini without an OpenAI key)
  - `POST /tts` turns text into speech (Gemini streams raw PCM)
  - `GET /config` reports which providers are configured and the default engines
- `setup_wizard.py` is the interactive setup (standard library only)
- `scripts/make_icon.py` regenerates the icons (`npm run icon`, needs Pillow)

## Privacy

Audio and text are sent to Google and/or OpenAI for processing, depending on the engines you pick. On Gemini's free tier, Google may use that data to improve its products. Nothing is stored locally beyond your settings.

## Credits

Voice Bubble was written by **Claude**, Anthropic's AI model, working in [Claude Code](https://claude.com/claude-code). **Martin Bara** came up with the idea, decided what it should do, and tested every step.

## Disclaimer

Voice Bubble is a hobby project provided **as is**, without warranty of any kind (see the [license](LICENSE)). You are responsible for your own API keys and for any costs your usage incurs with Google or OpenAI. Double-check dictated text before sending it anywhere important; speech recognition and the AI styles can make mistakes.

## License

[MIT](LICENSE)
