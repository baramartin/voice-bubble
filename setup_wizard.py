"""Interactive setup for Voice Bubble: API keys, engines, voice, and dependencies.

Run with `npm run setup` or `python setup_wizard.py`. Uses only the standard library,
so it works before `pip install` has run. Re-running it keeps your current values as defaults.
"""
import base64
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, '.env')
PRICES_AS_OF = 'October 2026'

# Speech-to-text engines: (bubble engine id, provider, label, price, note)
STT_ENGINES = [
    ('gemini-3.5-transcribe', 'gemini', 'Gemini 3.5 Transcribe', '~$0.005/min',
     'Smart mode removes fillers, applies self-corrections, formats lists. Free tier available.'),
    ('gpt-transcribe', 'openai', 'OpenAI gpt-transcribe', '$0.0045/min',
     "OpenAI's recommended transcription model. Fast."),
    ('gpt-4o-transcribe', 'openai', 'OpenAI gpt-4o-transcribe', '$0.006/min',
     'Previous OpenAI model, close to word-for-word.'),
]

# Text-to-speech engines: (bubble engine id, Gemini model or None, label, price, note)
TTS_ENGINES = [
    ('gemini', 'gemini-3.8-flash-lite-tts', 'Gemini 3.8 Flash-Lite TTS', '~$0.009/min',
     'Fast, streams as it speaks. Free tier available. Price doubles on Jan 1, 2027.'),
    ('gemini', 'gemini-3.8-flash-tts', 'Gemini 3.8 Flash TTS', '~$0.0135/min',
     'More expressive, slower to start. Price doubles on Jan 1, 2027.'),
    ('openai', None, 'OpenAI gpt-4o-mini-tts', '~$0.015/min',
     'Plays once the whole clip is ready (no streaming).'),
]

GEMINI_VOICES = [
    ('Zephyr', 'Bright'), ('Puck', 'Upbeat'), ('Charon', 'Informative'), ('Kore', 'Firm'),
    ('Fenrir', 'Excitable'), ('Leda', 'Youthful'), ('Orus', 'Firm'), ('Aoede', 'Breezy'),
    ('Callirrhoe', 'Easy-going'), ('Autonoe', 'Bright'), ('Enceladus', 'Breathy'), ('Iapetus', 'Clear'),
    ('Umbriel', 'Easy-going'), ('Algieba', 'Smooth'), ('Despina', 'Smooth'), ('Erinome', 'Clear'),
    ('Algenib', 'Gravelly'), ('Rasalgethi', 'Informative'), ('Laomedeia', 'Upbeat'), ('Achernar', 'Soft'),
    ('Alnilam', 'Firm'), ('Schedar', 'Even'), ('Gacrux', 'Mature'), ('Pulcherrima', 'Forward'),
    ('Achird', 'Friendly'), ('Zubenelgenubi', 'Casual'), ('Vindemiatrix', 'Gentle'), ('Sadachbia', 'Lively'),
    ('Sadaltager', 'Knowledgeable'), ('Sulafat', 'Warm'),
]
OPENAI_VOICES = [(v, '') for v in
                 ['alloy', 'ash', 'ballad', 'cedar', 'coral', 'echo', 'fable', 'marin', 'nova', 'onyx', 'sage', 'shimmer', 'verse']]

# ---- Console helpers ----

os.system('')  # enables ANSI colors in older Windows consoles
BOLD, DIM, GREEN, YELLOW, RED, CYAN, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[33m', '\033[31m', '\033[36m', '\033[0m'

def heading(text):
    print(f'\n{BOLD}{CYAN}== {text} =={RESET}')

def ok(text):
    print(f'{GREEN}OK{RESET} {text}')

def warn(text):
    print(f'{YELLOW}!{RESET} {text}')

def ask_yes_no(prompt, default=True):
    hint = 'Y/n' if default else 'y/N'
    while True:
        answer = input(f'{prompt} [{hint}]: ').strip().lower()
        if not answer:
            return default
        if answer in ('y', 'yes', 'n', 'no'):
            return answer.startswith('y')

def choose(prompt, labels, default_index=0, on_preview=None):
    """Numbered menu. Returns the chosen index. With on_preview, 'p 3' previews option 3."""
    for i, label in enumerate(labels, 1):
        marker = f'{GREEN}*{RESET}' if i - 1 == default_index else ' '
        print(f' {marker} {i:>2}. {label}')
    hint = f'1-{len(labels)}, Enter for {default_index + 1}'
    if on_preview:
        hint += ', "p 3" to preview #3'
    while True:
        answer = input(f'{prompt} ({hint}): ').strip().lower()
        if not answer:
            return default_index
        if on_preview and answer.startswith('p'):
            number = answer[1:].strip()
            if number.isdigit() and 1 <= int(number) <= len(labels):
                on_preview(int(number) - 1)
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(labels):
            return int(answer) - 1

def mask(key):
    return f'{key[:5]}...{key[-4:]}' if len(key) > 12 else '***'

# ---- .env handling ----

def read_env():
    values = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
    return values

def write_env(updates):
    """Set/replace keys in .env, keeping any other lines. A value of None removes the key."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding='utf-8') as f:
            lines = f.read().splitlines()

    remaining = dict(updates)
    result = []
    for line in lines:
        key = line.split('=', 1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
        if key in remaining:
            value = remaining.pop(key)
            if value is not None:
                result.append(f'{key}={value}')
        else:
            result.append(line)
    result += [f'{k}={v}' for k, v in remaining.items() if v is not None]

    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result) + '\n')

# ---- API calls (stdlib only) ----

def http(url, headers, body=None, timeout=30):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, headers={**headers, 'Content-Type': 'application/json'},
                                 method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def check_key(provider, key):
    """Returns None if the key works, otherwise an error message."""
    try:
        if provider == 'openai':
            http('https://api.openai.com/v1/models', {'Authorization': f'Bearer {key}'})
        else:
            http('https://generativelanguage.googleapis.com/v1beta/models', {'x-goog-api-key': key})
        return None
    except urllib.error.HTTPError as e:
        return f'rejected (HTTP {e.code})'
    except urllib.error.URLError as e:
        return f'could not connect ({e.reason})'

def synthesize_wav(engine, gemini_model, voice, keys):
    text = f"Hi! I'm {voice}. This is how I'll read your text out loud."
    if engine == 'gemini':
        result = json.loads(http(
            'https://generativelanguage.googleapis.com/v1beta/interactions',
            {'x-goog-api-key': keys['gemini']},
            {'model': gemini_model,
             'input': [{'type': 'user_input', 'content': [{'type': 'text', 'text': text}]}],
             'response_format': {'type': 'audio', 'mime_type': 'audio/wav'},
             'generation_config': {'speech_config': [{'voice': voice}]}},
            timeout=60))
        audio = [block for step in result.get('steps', []) if step.get('type') == 'model_output'
                 for block in step.get('content', []) if block.get('data')]
        return base64.b64decode(audio[-1]['data'])
    return http('https://api.openai.com/v1/audio/speech', {'Authorization': f"Bearer {keys['openai']}"},
                {'model': 'gpt-4o-mini-tts', 'voice': voice, 'input': text, 'response_format': 'wav'}, timeout=60)

def play_wav(wav_bytes):
    import winsound
    winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)

# ---- Wizard steps ----

def step_keys(env):
    heading('1. API keys')
    print('You need at least one. Either provider alone covers dictation and read-aloud.')
    print(f'  OpenAI: https://platform.openai.com/api-keys')
    print(f'  Gemini: https://aistudio.google.com/apikey  {DIM}(has a free tier; free-tier data may be used by Google){RESET}')
    print(f'{DIM}Keys are hidden while you paste them (right-click or Ctrl+V), then press Enter.{RESET}')

    keys = {}
    for provider, env_name, label in [('openai', 'OPENAI_API_KEY', 'OpenAI'), ('gemini', 'GEMINI_API_KEY', 'Gemini')]:
        current = env.get(env_name, '')
        while True:
            suffix = f'Enter keeps {mask(current)}, "-" removes it' if current else 'Enter to skip'
            entered = getpass.getpass(f'{label} API key ({suffix}): ').strip()
            if entered == '-':
                key = ''
            else:
                key = entered or current
            if not key:
                print(f'  {DIM}No {label} key.{RESET}')
                break
            print(f'  Checking {mask(key)}...', end=' ', flush=True)
            error = check_key(provider, key)
            if not error:
                print(f'{GREEN}works{RESET}')
                keys[provider] = key
                break
            print(f'{RED}{error}{RESET}')
            if not ask_yes_no('  Try another key?'):
                if ask_yes_no(f'  Save this {label} key anyway?', default=False):
                    keys[provider] = key
                break
    if not keys:
        print(f'{RED}At least one key is required.{RESET}')
        return step_keys(env)
    return keys

def step_stt(env, keys):
    heading('2. Speech-to-text (dictation)')
    options = [e for e in STT_ENGINES if e[1] in keys]
    current = env.get('DEFAULT_STT_ENGINE')
    default = next((i for i, e in enumerate(options) if e[0] == current), 0)
    labels = [f'{name:<26} {BOLD}{price:<12}{RESET} {DIM}{note}{RESET}' for _, _, name, price, note in options]
    return options[choose('Transcription engine', labels, default)]

def step_tts(env, keys):
    heading('3. Text-to-speech (read aloud)')
    options = [e for e in TTS_ENGINES if e[0] in keys]
    current_engine = env.get('DEFAULT_TTS_ENGINE')
    current_model = env.get('GEMINI_TTS_MODEL', 'gemini-3.8-flash-lite-tts')
    default = next((i for i, e in enumerate(options)
                    if e[0] == current_engine and (e[1] is None or e[1] == current_model)), 0)
    labels = [f'{name:<26} {BOLD}{price:<12}{RESET} {DIM}{note}{RESET}' for _, _, name, price, note in options]
    return options[choose('Read-aloud engine', labels, default)]

def step_voice(env, keys, tts):
    engine, gemini_model, *_ = tts
    voices = GEMINI_VOICES if engine == 'gemini' else OPENAI_VOICES
    heading('4. Voice')
    current = env.get('DEFAULT_TTS_VOICE')
    default = next((i for i, (v, _) in enumerate(voices) if v == current), 3 if engine == 'gemini' else 0)
    labels = [f'{name:<14} {DIM}{desc}{RESET}' for name, desc in voices]

    def preview(index):
        voice = voices[index][0]
        print(f'  Generating a sample of {voice}...', end=' ', flush=True)
        try:
            wav = synthesize_wav(engine, gemini_model, voice, keys)
            print('playing.')
            play_wav(wav)
        except Exception as e:
            print(f'{RED}preview failed: {e}{RESET}')

    return voices[choose('Voice', labels, default, on_preview=preview)][0]

def step_vocabulary(env, stt):
    if stt[1] != 'gemini':
        return env.get('GEMINI_TRANSCRIBE_VOCABULARY')
    heading('5. Custom vocabulary (optional)')
    print('Names or jargon Gemini should recognize, comma-separated (e.g. "Kubernetes, BigQuery, Bára").')
    current = env.get('GEMINI_TRANSCRIBE_VOCABULARY', '')
    entered = input(f'Vocabulary ({"Enter keeps current, " if current else ""}"-" for none): ').strip()
    if entered == '-':
        return None
    return entered or current or None

def step_install():
    heading('Dependencies')
    commands = [([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 'Python packages'),
                (['npm', 'install'], 'Electron')]
    if not ask_yes_no('Install/update dependencies now (pip + npm)?'):
        return
    for command, label in commands:
        print(f'{DIM}> {" ".join(command)}{RESET}')
        try:
            subprocess.run(command, cwd=ROOT, check=True, shell=(command[0] == 'npm'))
            ok(f'{label} installed')
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            warn(f'{label} failed to install: {e}')

def main():
    print(f'{BOLD}Voice Bubble setup{RESET}')
    print(f'{DIM}Prices are approximate, as of {PRICES_AS_OF}, for the paid tiers. Check the providers\' pricing pages.{RESET}')
    if sys.platform != 'win32':
        warn('Voice Bubble currently runs on Windows only (pasting uses Win32 APIs).')

    env = read_env()
    keys = step_keys(env)
    stt = step_stt(env, keys)
    tts = step_tts(env, keys)
    voice = step_voice(env, keys, tts)
    vocabulary = step_vocabulary(env, stt)

    updates = {
        'OPENAI_API_KEY': keys.get('openai'),
        'GEMINI_API_KEY': keys.get('gemini'),
        'DEFAULT_STT_ENGINE': stt[0],
        'DEFAULT_TTS_ENGINE': tts[0],
        'DEFAULT_TTS_VOICE': voice,
        'GEMINI_TRANSCRIBE_VOCABULARY': vocabulary,
    }
    if tts[1]:
        updates['GEMINI_TTS_MODEL'] = tts[1]
    write_env(updates)

    heading('Saved')
    ok(f'Wrote {ENV_PATH}')
    print(f'  Dictation:  {stt[2]}')
    print(f'  Read-aloud: {tts[2]}, voice {voice}')
    print(f'{DIM}You can switch engines and voices anytime from the bubble\'s settings.{RESET}')

    step_install()
    print(f'\n{BOLD}Done!{RESET} Start Voice Bubble with: {CYAN}npm start{RESET}')
    print('Hotkeys: Ctrl+Shift+Space to dictate, Ctrl+Shift+S to read the selection aloud.')

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nSetup cancelled. Nothing was saved unless you saw "Saved".')
