# Whisper Dictation

A small floating bubble for Windows that lets you **type anywhere with your voice** and **have any text read aloud**.

Press a hotkey, talk, press it again, and the transcript is pasted into whatever window you were using. Pick an output style and your rambling gets cleaned up, turned into bullet points, or rewritten as an email on the way. Select text anywhere and press another hotkey to hear it spoken.

It runs on your own API keys (OpenAI and/or Google Gemini), so you pay per minute of audio. A typical dictation costs a fraction of a cent, and there's no subscription.

## Features

- **System-wide dictation**: transcribed text is pasted straight into the window you were working in
- **Choice of transcription engines**
  - **Gemini 3.5 Transcribe** (default), whose *smart mode* removes filler words, applies spoken self-corrections ("Tuesday, actually no, Wednesday" → "Wednesday") and formats spoken lists
  - **OpenAI `gpt-transcribe`** and **`gpt-4o-transcribe`**
- **Output styles**: raw, no line breaks, clean up, professional email, bullet points, emojify, make concise
- **Text-to-speech** with streaming playback, so audio starts before the whole clip is generated
  - **Gemini 3.8 Flash-Lite TTS** (30 voices) or **OpenAI `gpt-4o-mini-tts`** (13 voices)
  - Speech styles: news anchor, casual, poetry reading, storytelling, calm
- Microphone picker and live level meter
- Always-on-top bubble that stays out of the way

## Requirements

- Windows 10/11 (pasting uses Win32 APIs through PowerShell)
- Python 3.10+ on your `PATH` as `python`
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/api-keys) and/or a [Gemini API key](https://aistudio.google.com/apikey)

## Setup

```bash
git clone https://github.com/baramartin/whisper-dictation.git
cd whisper-dictation
pip install -r requirements.txt
npm install
```

Copy `.env.example` to `.env` and fill in your keys:

```ini
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```

Start it:

```bash
npm start
```

This launches the bubble and starts the local Python backend on `http://localhost:5000` automatically.

## Usage

| Action | How |
|---|---|
| Start / stop dictation | `Ctrl+Shift+Space` or click the mic |
| Read selected text aloud | `Ctrl+Shift+S` (copies the selection, then speaks it; press again to stop) |
| Read the clipboard aloud | Click the speaker button |
| Change engine, style, mic or voice | Click the settings button on the bubble |

Tip: choose **Clean up** with **Gemini 3.5 Transcribe** to get smart mode. It cleans up in a single call instead of transcribing first and rewriting afterwards.

## Configuration

All optional settings go in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | (required) | OpenAI transcription, TTS and the style rewrites |
| `GEMINI_API_KEY` | (none) | Needed for the Gemini engines |
| `GEMINI_TRANSCRIBE_MODEL` | `gemini-3.5-transcribe` | Gemini transcription model |
| `GEMINI_TRANSCRIBE_VOCABULARY` | (none) | Comma-separated names or jargon to help recognition, e.g. `Kubernetes, BigQuery` |
| `GEMINI_TTS_MODEL` | `gemini-3.8-flash-lite-tts` | Use `gemini-3.8-flash-tts` for the larger model |

## How it works

- `main.js` (Electron) is the floating bubble window, the global hotkeys, and pasting into the target window
- `bubble.html` is the bubble UI: recording, settings, and streaming audio playback
- `app.py` (Flask) is a local backend that keeps your API keys out of the UI and calls OpenAI / Gemini
  - `POST /transcribe` turns audio into text
  - `POST /transform` restyles text with GPT-4o
  - `POST /tts` turns text into speech (Gemini streams raw PCM)

## Privacy

Audio and text are sent to OpenAI and/or Google for processing, depending on the engines you pick. Nothing is stored locally beyond your settings.

## License

[MIT](LICENSE)
