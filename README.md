<p align="center">
  <img src="static/icon.svg" width="96" alt="Voice Bubble icon">
</p>

<h1 align="center">Voice Bubble</h1>

<p align="center">
  A floating bubble for <b>Windows</b> that lets you <b>type anywhere with your voice</b> and <b>have any text read aloud</b>.
</p>

---

Press a hotkey, talk, press it again, and the transcript is pasted into whatever window you were using. Pick an output style and your rambling gets cleaned up, turned into bullet points, or rewritten as an email on the way. Select text anywhere and press another hotkey to hear it spoken.

It runs on your own API keys (Google Gemini and/or OpenAI), so you pay per minute of audio. A typical dictation costs a fraction of a cent, Gemini has a free tier, and there's no subscription.

> **Platform:** Windows 10/11 only for now. Pasting into other apps and refocusing windows use Win32 APIs.

## Features

- **System-wide dictation**: transcribed text is pasted straight into the window you were working in
- **Choice of transcription engines**
  - **Gemini 3.5 Transcribe**, whose *smart mode* removes filler words, applies spoken self-corrections ("Tuesday, actually no, Wednesday" → "Wednesday") and formats spoken lists
  - **OpenAI `gpt-transcribe`** and **`gpt-4o-transcribe`**
- **Output styles**: raw, no line breaks, clean up, professional email, bullet points, emojify, make concise
- **Text-to-speech** with streaming playback, so audio starts before the whole clip is generated
  - **Gemini 3.8 Flash-Lite / Flash TTS** (30 voices) or **OpenAI `gpt-4o-mini-tts`** (13 voices)
  - Speech styles: news anchor, casual, poetry reading, storytelling, calm
- **Setup wizard** that checks your keys, shows prices and lets you preview voices
- Microphone picker and live level meter

## Quick start

You need [Python 3.10+](https://www.python.org/downloads/) (on your `PATH` as `python`) and [Node.js 18+](https://nodejs.org/).

```bash
git clone https://github.com/baramartin/voice-bubble.git
cd voice-bubble
npm run setup
npm start
```

The setup wizard walks you through these steps (arrow keys to move, Enter to select):

1. **API keys**: paste a [Gemini key](https://aistudio.google.com/apikey) and/or an [OpenAI key](https://platform.openai.com/api-keys). Each one is checked on the spot.
2. **Dictation engine**, with prices
3. **Read-aloud engine**, with prices
4. **Voice**: press `P` to hear the highlighted voice before you pick it
5. **Custom vocabulary** (Gemini only): names or jargon it should recognize
6. **Installing dependencies** (`pip` + `npm`)

It writes a `.env` file. Run it again anytime to change your choices; your current values are kept as defaults.

## Usage

| Action | How |
|---|---|
| Start / stop dictation | `Ctrl+Shift+Space` or click the mic |
| Read selected text aloud | `Ctrl+Shift+S` (copies the selection, then speaks it; press again to stop) |
| Read the clipboard aloud | Click the speaker button |
| Change engine, style, mic or voice | Click the settings button on the bubble (the Help tab lists all of this too) |

Tip: choose **Clean up** with **Gemini 3.5 Transcribe** to get smart mode. It cleans up in a single call instead of transcribing first and rewriting afterwards.

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

Gemini TTS prices double on January 1, 2027.

## Configuration

The wizard handles this, but you can also edit `.env` by hand (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (none) | Gemini engines |
| `OPENAI_API_KEY` | (none) | OpenAI engines |
| `DEFAULT_STT_ENGINE` | Gemini if you have the key | Dictation engine the bubble starts with |
| `DEFAULT_TTS_ENGINE` / `DEFAULT_TTS_VOICE` | Gemini / `Kore` | Read-aloud engine and voice the bubble starts with |
| `GEMINI_TTS_MODEL` | `gemini-3.8-flash-lite-tts` | Or `gemini-3.8-flash-tts` |
| `GEMINI_TRANSCRIBE_VOCABULARY` | (none) | Comma-separated names or jargon, e.g. `Kubernetes, BigQuery` |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash-lite` | Output styles when you have no OpenAI key |

Choices you make in the bubble's settings are remembered and take precedence over these defaults.

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

## License

[MIT](LICENSE)
