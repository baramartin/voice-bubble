"""Interactive setup for Voice Bubble: API keys, engines, voice, and dependencies.

Run with `npm run setup` or `python setup_wizard.py`. Uses only the standard library,
so it works before `pip install` has run. Re-running it keeps your current values as defaults.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
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

# Output styles: (bubble style id, label, description). Keep in sync with STYLES in bubble.html.
STYLES = [
    ('clean', 'Smart mode', 'Removes ums and false starts, keeps only your corrections ("Tuesday, no, Wednesday" -> '
                            '"Wednesday") and turns spoken lists into real lists. Recommended.'),
    ('none', 'Raw', 'Exactly what you said, word for word, including ums.'),
    ('no-newlines', 'No new lines', 'Raw text joined into one line. Handy for chat boxes where Enter sends.'),
    ('professional', 'Professional email', 'Rewritten as a polished email with greeting and sign-off.'),
    ('bullet-points', 'Bullet points', 'Your ideas grouped into a tidy bullet list.'),
    ('emojify', 'Emojify', 'Your words, plus fitting emojis.'),
    ('concise', 'Make concise', 'Shortened to the key points.'),
]

KEY_PREFIXES = {'gemini': 'AIza', 'openai': 'sk-'}

# Global hotkeys, in Electron accelerator format. Keep defaults in sync with main.js.
# Read aloud is the dictation hotkey plus Alt: hardly any app uses it, on any OS.
DEFAULT_HOTKEYS = {
    'HOTKEY_DICTATE': 'Ctrl+Shift+Space',
    'HOTKEY_READ_ALOUD': 'Ctrl+Alt+Shift+Space',
}
HOTKEY_MODIFIERS = {'ctrl', 'control', 'alt', 'option', 'shift', 'cmd', 'command', 'cmdorctrl',
                    'commandorcontrol', 'super', 'meta', 'altgr'}
# Combinations that other apps commonly use, worth a warning
BUSY_HOTKEYS = {
    'ctrl+shift+s': '"Save As" in many apps', 'ctrl+shift+r': 'hard refresh in browsers',
    'ctrl+shift+t': 'reopen closed tab in browsers', 'ctrl+shift+n': 'new incognito window in browsers',
    'ctrl+shift+p': 'command palette in VS Code', 'ctrl+shift+c': 'copy in terminals',
    'ctrl+shift+v': 'paste in terminals', 'ctrl+shift+esc': 'Task Manager',
}
CHANGE_LATER = "You can change this anytime in the bubble's settings."

# ---- Console helpers ----

os.system('')  # enables ANSI colors in older Windows consoles
BOLD, DIM, GREEN, YELLOW, RED, CYAN, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[33m', '\033[31m', '\033[36m', '\033[0m'
# Arrow-key menus need a real terminal; piped input falls back to numbered menus
INTERACTIVE = sys.stdin.isatty() and sys.stdout.isatty()
STEPS = ['Keys', 'Dictation', 'Style', 'Read aloud', 'Voice', 'Vocabulary', 'Hotkeys', 'Finish']

def screen(step):
    """Clear the terminal and show the title plus a breadcrumb of the steps."""
    if INTERACTIVE:
        sys.stdout.write('\033[2J\033[3J\033[H')
    trail = f' {DIM}>{RESET} '.join(
        f'{BOLD}{CYAN}{name}{RESET}' if name == step else f'{DIM}{name}{RESET}' for name in STEPS)
    print(f'{BOLD}Voice Bubble setup{RESET}\n{trail}\n')

def ok(text):
    print(f'{GREEN}OK{RESET} {text}')

def warn(text):
    print(f'{YELLOW}!{RESET} {text}')

def read_key():
    """Read one keypress: 'up', 'down', 'home', 'end', 'enter', or a lowercase character."""
    if os.name == 'nt':
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):  # arrow/navigation keys arrive as a two-character sequence
            return {'H': 'up', 'P': 'down', 'G': 'home', 'O': 'end'}.get(msvcrt.getwch(), '')
    else:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                return {'[A': 'up', '[B': 'down', '[H': 'home', '[F': 'end'}.get(sys.stdin.read(2), '')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch == '\x03':
        raise KeyboardInterrupt
    return 'enter' if ch in ('\r', '\n') else ch.lower()

def masked_input(prompt):
    """Like input(), but shows * for each character so you can see typing and pasting worked."""
    if not INTERACTIVE:
        return input(prompt)
    sys.stdout.write(prompt)
    sys.stdout.flush()
    chars = []
    while True:
        if os.name == 'nt':
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ('\x00', '\xe0'):  # ignore arrow/function keys
                msvcrt.getwch()
                continue
        else:
            import termios, tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if ch in ('\r', '\n'):
            sys.stdout.write('\n')
            return ''.join(chars)
        if ch == '\x03':
            raise KeyboardInterrupt
        if ch in ('\x08', '\x7f'):  # backspace
            if chars:
                chars.pop()
                sys.stdout.write('\b \b')
        elif ch.isprintable():
            chars.append(ch)
            sys.stdout.write('*')
        sys.stdout.flush()

def choose(prompt, labels, default_index=0, details=None, on_preview=None):
    """Menu returning the chosen index. Arrow keys + Enter in a terminal; details[i] is shown for the
    highlighted option. on_preview(i) is called on P and returns a status message."""
    if not INTERACTIVE:
        return choose_numbered(prompt, labels, default_index, on_preview)

    hint = 'Up/Down to move, Enter to select' + (', P to preview' if on_preview else '')
    print(f'{BOLD}{prompt}{RESET}  {DIM}{hint}{RESET}')
    index, status, drawn = default_index, '', 0
    rows = min(len(labels), 12)  # long lists scroll
    while True:
        top = min(max(0, index - rows // 2), len(labels) - rows)
        lines = [f'  {DIM}^ {top} more{RESET}' if top > 0 else '']
        for i in range(top, top + rows):
            lines.append(f'{CYAN}> {labels[i]}{RESET}' if i == index else f'  {labels[i]}')
        below = len(labels) - top - rows
        lines.append(f'  {DIM}v {below} more{RESET}' if below > 0 else '')
        # Wrap the description ourselves: a line the terminal wraps would throw off the in-place redraw
        width = max(20, shutil.get_terminal_size().columns - 4)
        detail = textwrap.wrap(details[index], width) if details and details[index] else ['']
        lines += [f'  {DIM}{line}{RESET}' for line in detail]
        lines.append(status)

        if drawn:
            sys.stdout.write(f'\033[{drawn}F')  # back to the top of the menu and redraw in place
        # \033[J clears leftovers when this frame is shorter than the previous one
        sys.stdout.write(''.join(f'\033[2K{line}\n' for line in lines) + '\033[J')
        sys.stdout.flush()
        drawn = len(lines)

        key = read_key()
        if key == 'up':
            index = (index - 1) % len(labels)
        elif key == 'down':
            index = (index + 1) % len(labels)
        elif key == 'home':
            index = 0
        elif key == 'end':
            index = len(labels) - 1
        elif key == 'enter':
            return index
        elif key == 'p' and on_preview:
            sys.stdout.write(f'\033[1F\033[2K  {DIM}Generating a sample...{RESET}\n')
            sys.stdout.flush()
            status = on_preview(index)

def choose_numbered(prompt, labels, default_index, on_preview):
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
                print(on_preview(int(number) - 1))
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(labels):
            return int(answer) - 1

def ask_yes_no(prompt, default=True):
    return choose(prompt, ['Yes', 'No'], 0 if default else 1) == 0

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

def audio_player():
    """Command that plays a WAV file on this system (None on Windows, which uses winsound)."""
    if sys.platform == 'darwin':
        return ['afplay']
    for player in (['paplay'], ['aplay', '-q']):
        if shutil.which(player[0]):
            return player
    return None

def can_play_audio():
    return os.name == 'nt' or audio_player() is not None

def play_wav(wav_bytes):
    if os.name == 'nt':
        import winsound
        winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
        return
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(wav_bytes)
    try:
        subprocess.run(audio_player() + [f.name], check=True)
    finally:
        os.unlink(f.name)

# ---- Wizard steps ----

def step_keys(env):
    screen('Keys')
    if sys.platform != 'win32':
        warn('Voice Bubble is built for Windows; macOS and Linux support is experimental.\n')
    print('You need at least one key. Either provider alone covers dictation and read-aloud.\n')
    print(f'  Gemini: https://aistudio.google.com/apikey  {DIM}(free tier; free-tier data may be used by Google){RESET}')
    print(f'  OpenAI: https://platform.openai.com/api-keys  {DIM}(optional){RESET}\n')
    print(f'{DIM}Paste with right-click or Ctrl+V; the key shows as *** while you type.{RESET}\n')

    keys = {}
    for provider, env_name, label in [('gemini', 'GEMINI_API_KEY', 'Gemini'), ('openai', 'OPENAI_API_KEY', 'OpenAI')]:
        current = env.get(env_name, '')
        if current:
            print(f'{BOLD}{label}{RESET}: you already have a key ({mask(current)}).')
            action = choose(f'{label} key', ['Keep it', 'Replace it', 'Remove it'], 0)
            if action == 0:
                print(f'  Checking {mask(current)}...', end=' ', flush=True)
                error = check_key(provider, current)
                print(f'{GREEN}works{RESET}' if not error else f'{YELLOW}{error}; keeping it anyway{RESET}')
                keys[provider] = current
                print()
                continue
            if action == 2:
                print(f'  {DIM}{label} key removed.{RESET}\n')
                continue
        key = ask_key(provider, label)
        if key:
            keys[provider] = key
        print()
    if not keys:
        input(f'\n{RED}At least one key is required.{RESET} Press Enter to try again.')
        return step_keys(env)
    return keys

def ask_key(provider, label):
    """Prompt until a key validates, or the user skips. Returns the key or None."""
    prefix = KEY_PREFIXES[provider]
    while True:
        key = masked_input(f'{label} API key (Enter to skip): ').strip()
        if not key:
            print(f'  {DIM}No {label} key.{RESET}')
            return None
        if not key.startswith(prefix):
            print(f'  {YELLOW}{label} keys usually start with "{prefix}"; checking anyway.{RESET}')
        print(f'  Checking {mask(key)}...', end=' ', flush=True)
        error = check_key(provider, key)
        if not error:
            print(f'{GREEN}works{RESET}')
            return key
        print(f'{RED}{error}{RESET}')
        if choose('What now?', ['Try again', f'Skip {label}'], 0) == 1:
            return None

def engine_menu(prompt, options, default):
    labels = [f'{name:<26} {price}' for _, _, name, price, _ in options]
    return options[choose(prompt, labels, default, details=[note for *_, note in options])]

def step_stt(env, keys):
    screen('Dictation')
    print(f'{DIM}Approximate paid-tier prices as of {PRICES_AS_OF}. {CHANGE_LATER}{RESET}\n')
    options = [e for e in STT_ENGINES if e[1] in keys]
    current = env.get('DEFAULT_STT_ENGINE')
    default = next((i for i, e in enumerate(options) if e[0] == current), 0)
    return engine_menu('Transcription engine', options, default)

def step_style(env):
    screen('Style')
    print('What should happen to your words before they are pasted?')
    print(f'{DIM}{CHANGE_LATER}{RESET}\n')
    current = env.get('DEFAULT_STYLE', 'clean')
    default = next((i for i, s in enumerate(STYLES) if s[0] == current), 0)
    labels = [label for _, label, _ in STYLES]
    return STYLES[choose('Output style', labels, default, details=[desc for *_, desc in STYLES])]

def step_tts(env, keys):
    screen('Read aloud')
    print(f'{DIM}Approximate paid-tier prices as of {PRICES_AS_OF}. {CHANGE_LATER}{RESET}\n')
    options = [e for e in TTS_ENGINES if e[0] in keys]
    current_engine = env.get('DEFAULT_TTS_ENGINE')
    current_model = env.get('GEMINI_TTS_MODEL', 'gemini-3.8-flash-lite-tts')
    default = next((i for i, e in enumerate(options)
                    if e[0] == current_engine and (e[1] is None or e[1] == current_model)), 0)
    return engine_menu('Read-aloud engine', options, default)

def step_voice(env, keys, tts):
    engine, gemini_model, *_ = tts
    voices = GEMINI_VOICES if engine == 'gemini' else OPENAI_VOICES
    screen('Voice')
    print(f'{DIM}{CHANGE_LATER} The bubble plays a sample when you click a voice.{RESET}\n')
    current = env.get('DEFAULT_TTS_VOICE')
    default = next((i for i, (v, _) in enumerate(voices) if v == current), 3 if engine == 'gemini' else 0)
    labels = [f'{name:<14} {DIM}{desc}{RESET}' for name, desc in voices]

    def preview(index):
        voice = voices[index][0]
        try:
            play_wav(synthesize_wav(engine, gemini_model, voice, keys))
            return f'  {GREEN}Played {voice}.{RESET}'
        except Exception as e:
            return f'  {RED}Preview failed: {e}{RESET}'

    return voices[choose('Voice', labels, default, on_preview=preview if can_play_audio() else None)][0]

def step_vocabulary(env, stt):
    if stt[1] != 'gemini':
        return env.get('GEMINI_TRANSCRIBE_VOCABULARY')
    screen('Vocabulary')
    print('Optional: names or jargon Gemini should recognize, comma-separated.')
    print(f'{DIM}Example: Kubernetes, BigQuery, Bara{RESET}\n')
    current = env.get('GEMINI_TRANSCRIBE_VOCABULARY', '')
    if current:
        print(f'Current: {current}\n')
    entered = input(f'Vocabulary ({"Enter keeps current, " if current else "Enter to skip, "}"-" for none): ').strip()
    if entered == '-':
        return None
    return entered or current or None

def hotkey_problem(hotkey):
    """Returns why a hotkey can't be used, or None. Needs at least one modifier plus one key."""
    parts = [p.strip() for p in hotkey.split('+')]
    if any(not p for p in parts):
        return 'it has an empty part; write it like Ctrl+Alt+R'
    if parts[-1].lower() in HOTKEY_MODIFIERS:
        return 'it needs a key after the modifiers, like Space or a letter'
    if not any(p.lower() in HOTKEY_MODIFIERS for p in parts[:-1]) or len(parts) < 2:
        return 'it needs at least one of Ctrl, Alt or Shift, so it does not fire while you type'
    return None

def ask_hotkey(label, current):
    while True:
        entered = input(f'{label} (Enter keeps {current}): ').strip()
        if not entered:
            return current
        # Normalize "ctrl + alt + space" to "Ctrl+Alt+Space" (Electron's accelerator format)
        entered = '+'.join(p.strip()[:1].upper() + p.strip()[1:] for p in entered.split('+'))
        problem = hotkey_problem(entered)
        if problem:
            print(f'  {RED}That will not work: {problem}.{RESET}')
            continue
        busy = BUSY_HOTKEYS.get(entered.lower().replace(' ', ''))
        if busy and not ask_yes_no(f'{entered} is {busy}. Use it anyway?', default=False):
            continue
        return entered

def step_hotkeys(env):
    screen('Hotkeys')
    current = {name: env.get(name) or default for name, default in DEFAULT_HOTKEYS.items()}
    print('These work in every app, so they should be combinations other apps don\'t use.\n')
    print(f'  Dictate:     {BOLD}{current["HOTKEY_DICTATE"]}{RESET}')
    print(f'  Read aloud:  {BOLD}{current["HOTKEY_READ_ALOUD"]}{RESET}\n')
    if choose('Hotkeys', ['Keep these', 'Change them'], 0) == 0:
        return current
    print(f'\n{DIM}Write them like Ctrl+Alt+R or Ctrl+Shift+F9. Modifiers: Ctrl, Alt, Shift'
          f'{", Cmd" if sys.platform == "darwin" else ""}.{RESET}')
    while True:
        dictate = ask_hotkey('Dictate', current['HOTKEY_DICTATE'])
        read_aloud = ask_hotkey('Read aloud', current['HOTKEY_READ_ALOUD'])
        if dictate.lower() != read_aloud.lower():
            return {'HOTKEY_DICTATE': dictate, 'HOTKEY_READ_ALOUD': read_aloud}
        print(f'  {RED}The two hotkeys need to be different.{RESET}')

def step_install():
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

SHORTCUT_NAME = 'Voice Bubble.lnk'
ELECTRON_EXE = os.path.join(ROOT, 'node_modules', 'electron', 'dist', 'electron.exe')

def powershell(script, **env):
    """Run a PowerShell snippet. Values go in as environment variables ($env:NAME) to avoid quoting issues."""
    result = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True, text=True,
                            env={**os.environ, **env}, check=True)
    return result.stdout.strip()

def create_shortcut(path):
    # Launches electron.exe directly (no console window); the app folder is its argument
    powershell(
        '$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:VB_LNK);'
        '$s.TargetPath = $env:VB_TARGET; $s.Arguments = \'"\' + $env:VB_ROOT + \'"\';'
        '$s.WorkingDirectory = $env:VB_ROOT; $s.IconLocation = $env:VB_ICON;'
        '$s.Description = "Voice Bubble: dictate anywhere"; $s.Save()',
        VB_LNK=path, VB_TARGET=ELECTRON_EXE, VB_ROOT=ROOT, VB_ICON=os.path.join(ROOT, 'static', 'icon.ico'))

def step_shortcuts():
    """Windows: desktop shortcut and start-with-Windows, each detected if already there."""
    if os.name != 'nt':
        return
    if not os.path.exists(ELECTRON_EXE):
        warn('Electron is not installed yet, so no shortcuts were created. Run the setup again after `npm install`.')
        return
    places = [
        ('Desktop', 'Desktop shortcut', 'Create a desktop shortcut?', True),
        ('Startup', 'Start with Windows', 'Start Voice Bubble automatically when you sign in to Windows?', False),
    ]
    for folder_name, label, question, default in places:
        # GetFolderPath follows redirected folders, e.g. a Desktop that lives in OneDrive
        folder = powershell(f"[Environment]::GetFolderPath('{folder_name}')")
        path = os.path.join(folder, SHORTCUT_NAME)
        print()
        if os.path.exists(path):
            print(f'{BOLD}{label}{RESET}: already set up.')
            action = choose(label, ['Keep it', 'Update it', 'Remove it'], 0)
            if action == 2:
                os.remove(path)
                ok(f'{label} removed')
                continue
            if action == 0:
                continue
        elif not ask_yes_no(question, default):
            continue
        try:
            create_shortcut(path)
            ok(f'{label}: {path}')
        except subprocess.CalledProcessError as e:
            warn(f'Could not create the shortcut: {e.stderr.strip() or e}')

def main():
    env = read_env()
    keys = step_keys(env)
    stt = step_stt(env, keys)
    style = step_style(env)
    tts = step_tts(env, keys)
    voice = step_voice(env, keys, tts)
    vocabulary = step_vocabulary(env, stt)
    hotkeys = step_hotkeys(env)

    updates = {
        **hotkeys,
        'GEMINI_API_KEY': keys.get('gemini'),
        'OPENAI_API_KEY': keys.get('openai'),
        'DEFAULT_STT_ENGINE': stt[0],
        'DEFAULT_STYLE': style[0],
        'DEFAULT_TTS_ENGINE': tts[0],
        'DEFAULT_TTS_VOICE': voice,
        'GEMINI_TRANSCRIBE_VOCABULARY': vocabulary,
    }
    if tts[1]:
        updates['GEMINI_TTS_MODEL'] = tts[1]
    write_env(updates)

    screen('Finish')
    ok(f'Saved your settings to {ENV_PATH}')
    print(f'   Dictation:  {stt[2]}, style {style[1]}')
    print(f'   Read-aloud: {tts[2]}, voice {voice}')
    print(f'   Hotkeys:    {hotkeys["HOTKEY_DICTATE"]} to dictate, {hotkeys["HOTKEY_READ_ALOUD"]} to read aloud')
    print(f"{DIM}   You can switch engines and voices anytime in the bubble's settings.{RESET}\n")

    step_install()
    step_shortcuts()
    start_hint = 'the desktop shortcut or ' if os.name == 'nt' else ''
    print(f'\n{BOLD}Done!{RESET} Start Voice Bubble with {start_hint}{CYAN}npm start{RESET}')
    print('If it is already running, quit it from the tray icon and start it again to apply the changes.')

if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(f'{RESET}\nSetup cancelled. Nothing was saved unless you saw "Saved your settings".')
