from flask import Flask, request, jsonify, Response
from openai import OpenAI
from dotenv import load_dotenv
import tempfile
import os
import threading
from werkzeug.serving import make_server
import time
import signal
import sys
import atexit
import base64
import json
import urllib.request
import urllib.error

load_dotenv()

# Global server variable that can be accessed by signal handlers
server = None
app = Flask(__name__)

# At least one provider is needed; either one alone is enough. Run `npm run setup` to create .env.
api_key = os.getenv('OPENAI_API_KEY')
gemini_api_key = os.getenv('GEMINI_API_KEY')
if not api_key and not gemini_api_key:
    print("ERROR: no API keys found. Run `npm run setup` (or copy .env.example to .env) "
          "and add OPENAI_API_KEY and/or GEMINI_API_KEY.")
    sys.exit(1)

client = OpenAI(api_key=api_key) if api_key else None

# Defaults the bubble uses until the user picks something in its settings (written by the setup wizard)
DEFAULT_STT_ENGINE = os.getenv('DEFAULT_STT_ENGINE', 'gemini-3.5-transcribe' if gemini_api_key else 'gpt-transcribe')
DEFAULT_TTS_ENGINE = os.getenv('DEFAULT_TTS_ENGINE', 'gemini' if gemini_api_key else 'openai')
DEFAULT_TTS_VOICE = os.getenv('DEFAULT_TTS_VOICE', 'Kore' if DEFAULT_TTS_ENGINE == 'gemini' else 'alloy')

GEMINI_TEXT_MODEL = os.getenv('GEMINI_TEXT_MODEL', 'gemini-3.5-flash-lite')
GEMINI_TTS_MODEL = os.getenv('GEMINI_TTS_MODEL', 'gemini-3.8-flash-lite-tts')
GEMINI_TRANSCRIBE_MODEL = os.getenv('GEMINI_TRANSCRIBE_MODEL', 'gemini-3.5-transcribe')
# Comma-separated names/jargon to bias recognition toward, e.g. "Kubernetes, BigQuery, Bára"
GEMINI_VOCABULARY = [t.strip() for t in os.getenv('GEMINI_TRANSCRIBE_VOCABULARY', '').split(',') if t.strip()]
GEMINI_INTERACTIONS_URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'

GEMINI_SAMPLE_RATE = 24000

def gemini_post(body):
    """POST to the Gemini Interactions API and return the open response (caller closes it)."""
    req = urllib.request.Request(
        GEMINI_INTERACTIONS_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={'x-goog-api-key': gemini_api_key, 'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        return urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini API {e.code}: {e.read().decode('utf-8', 'replace')}")

def model_output_text(result):
    """Join the text blocks of an interaction's model_output steps."""
    return ''.join(
        block.get('text', '')
        for step in result.get('steps', []) if step.get('type') == 'model_output'
        for block in step.get('content', []) if block.get('type') == 'text'
    )

def gemini_generate_text(prompt):
    with gemini_post({'model': GEMINI_TEXT_MODEL, 'input': [{'type': 'text', 'text': prompt}]}) as resp:
        return model_output_text(json.loads(resp.read()))

def gemini_transcribe(audio_bytes, mime_type, mode):
    """Transcribe inline audio with Gemini 3.5 Transcribe. mode is 'verbatim' or 'smart'
    (smart removes fillers, applies spoken self-corrections and formats lists)."""
    transcription_config = {'mode': mode}
    if GEMINI_VOCABULARY:
        transcription_config['custom_vocabulary'] = GEMINI_VOCABULARY

    body = {
        'model': GEMINI_TRANSCRIBE_MODEL,
        'input': [{'type': 'audio', 'data': base64.b64encode(audio_bytes).decode('ascii'), 'mime_type': mime_type}],
        'generation_config': {'transcription_config': transcription_config}
    }
    with gemini_post(body) as resp:
        return model_output_text(json.loads(resp.read()))

def gemini_tts_stream(text, voice, style):
    """Stream from the Gemini Interactions API; returns a generator of raw PCM chunks
    (16-bit signed little-endian, mono, 24 kHz). Connection errors raise before the first chunk."""
    content = {'type': 'text', 'text': text}
    if style:
        content['annotations'] = [{'type': 'speech_metadata', 'style': style}]

    body = {
        'model': GEMINI_TTS_MODEL,
        'input': [{'type': 'user_input', 'content': [content]}],
        'response_format': {'type': 'audio', 'mime_type': 'audio/l16', 'sample_rate': GEMINI_SAMPLE_RATE},
        'generation_config': {'speech_config': [{'voice': voice}]},
        'stream': True
    }
    resp = gemini_post(body)

    def generate():
        # Server-sent events: audio arrives as base64 in "step.delta" events. The live API marks audio
        # deltas with mime_type "audio/l16" (no "type" field), so accept either form.
        chunks = 0
        try:
            for raw_line in resp:
                line = raw_line.decode('utf-8').strip()
                if not line.startswith('data:'):
                    continue
                payload = line[len('data:'):].strip()
                if payload == '[DONE]':
                    break
                event = json.loads(payload)
                event_type = event.get('event_type')
                delta = event.get('delta', {})
                is_audio = delta.get('type') == 'audio' or delta.get('mime_type', '').startswith('audio/')
                if event_type == 'step.delta' and is_audio and delta.get('data'):
                    chunks += 1
                    yield base64.b64decode(delta['data'])
                elif event_type == 'error':
                    print(f"Gemini TTS stream error: {event.get('error')}")
                    break
        finally:
            resp.close()
            if chunks == 0:
                print("Gemini TTS stream ended without any audio chunks")

    return generate()

def openai_missing():
    return jsonify({'error': 'OPENAI_API_KEY not set in .env', 'success': False}), 500

@app.route('/config')
def get_config():
    """Which providers have keys, and the defaults chosen in the setup wizard."""
    return jsonify({
        'providers': {'openai': bool(api_key), 'gemini': bool(gemini_api_key)},
        'defaults': {'stt_engine': DEFAULT_STT_ENGINE, 'tts_engine': DEFAULT_TTS_ENGINE, 'tts_voice': DEFAULT_TTS_VOICE}
    })

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        style_instruction = request.form.get('style', '')
        model_name = request.form.get('model', 'gpt-4o-transcribe')  # Default to latest model
        provider = request.form.get('provider', 'openai')

        if provider == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'GEMINI_API_KEY not set in .env', 'success': False}), 500
            mode = request.form.get('mode', 'verbatim')
            mime_type = (audio_file.mimetype or 'audio/webm').split(';')[0]
            audio_bytes = audio_file.read()
            text = gemini_transcribe(audio_bytes, mime_type, mode)
            return jsonify({
                'text': text.strip(),
                'success': True,
                'debug_info': {
                    'model_used': GEMINI_TRANSCRIBE_MODEL,
                    'mode': mode,
                    'file_size_bytes': len(audio_bytes)
                }
            })

        if not client:
            return openai_missing()

        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp_file:
            audio_file.save(tmp_file.name)
            tmp_file_path = tmp_file.name
        
        try:
            # Open the audio file for OpenAI API
            with open(tmp_file_path, 'rb') as audio_data:
                # Get file size for debugging
                file_size = os.path.getsize(tmp_file_path)
                
                # Different response formats for different models
                if model_name == 'whisper-1':
                    # Whisper-1 supports verbose_json
                    api_params = {
                        'model': model_name,
                        'file': audio_data,
                        'response_format': 'verbose_json'
                    }
                else:
                    # gpt-4o models only support json or text
                    api_params = {
                        'model': model_name,
                        'file': audio_data,
                        'response_format': 'json'  # Changed from verbose_json
                    }
                
                if style_instruction:
                    api_params['prompt'] = f"Please transcribe this audio with the following style: {style_instruction}"
                
                # Make the API call
                transcription = client.audio.transcriptions.create(**api_params)
                
                # Handle different response formats
                if model_name == 'whisper-1':
                    # Whisper returns a rich object with segments
                    transcription_text = transcription.text
                    duration = getattr(transcription, 'duration', 'N/A')
                    language = getattr(transcription, 'language', 'N/A')
                    
                    # Convert segments to JSON-serializable format
                    segments = []
                    if hasattr(transcription, 'segments'):
                        segments = [
                            {
                                'text': seg.text,
                                'start': seg.start,
                                'end': seg.end
                            } for seg in transcription.segments[:3]  # First 3 segments
                        ]
                else:
                    # gpt-4o models return simpler responses
                    if hasattr(transcription, 'text'):
                        transcription_text = transcription.text
                    else:
                        transcription_text = str(transcription)
                    
                    duration = 'N/A (not provided by this model)'
                    language = 'N/A (not provided by this model)'
                    segments = []
                
                # Return detailed response for debugging
                return jsonify({
                    'text': transcription_text.strip(),
                    'success': True,
                    'debug_info': {
                        'model_used': model_name,
                        'file_size_bytes': file_size,
                        'audio_duration': duration,
                        'language': language,
                        'style_instruction': style_instruction or 'None',
                        'segments': segments,
                        'raw_response_type': str(type(transcription))
                    }
                })
                
        finally:
            # Clean up temp file - Windows-friendly cleanup
            for attempt in range(3):
                try:
                    os.unlink(tmp_file_path)
                    break
                except (OSError, PermissionError):
                    if attempt < 2:
                        time.sleep(0.1)
            
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False,
            'debug_info': {
                'error_type': type(e).__name__,
                'model_attempted': request.form.get('model', 'unknown'),
                'style_attempted': request.form.get('style', 'none'),
                'error_details': str(e)
            }
        }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/transform', methods=['POST'])
def transform_text():
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided', 'success': False}), 400
        
        text = data['text']
        instruction = data.get('instruction', 'Format this text professionally')
        style = data.get('style', 'professional-email')
        
        system_prompt = "You are an expert editor who can transform dictated text according to instructions."
        user_prompt = f"Please transform the following dictated text according to this instruction: {instruction}\n\n{text}"

        if client:
            response = client.chat.completions.create(
                model="gpt-4o",  # Using GPT-4o for transformation
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            transformed_text = response.choices[0].message.content
        else:
            # Gemini-only setup
            transformed_text = gemini_generate_text(
                f"{system_prompt} Reply with only the transformed text.\n\n{user_prompt}")
        
        # Return the transformed text
        return jsonify({
            'success': True,
            'transformed_text': transformed_text,
            'original_text': text,
            'style': style,
            'instruction': instruction
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False,
            'debug_info': {
                'error_type': type(e).__name__,
                'error_details': str(e)
            }
        }), 500

@app.route('/tts', methods=['POST'])
def text_to_speech():
    try:
        data = request.json
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided', 'success': False}), 400

        text = data['text']
        voice = data.get('voice', 'alloy')
        instruction = data.get('instruction', '')
        provider = data.get('provider', 'openai')

        if provider == 'gemini':
            if not gemini_api_key:
                return jsonify({'error': 'GEMINI_API_KEY not set in .env', 'success': False}), 500
            return Response(
                gemini_tts_stream(text, voice, instruction),
                mimetype=f'audio/l16; rate={GEMINI_SAMPLE_RATE}; channels=1',
                headers={'X-Sample-Rate': str(GEMINI_SAMPLE_RATE), 'Access-Control-Expose-Headers': 'X-Sample-Rate'}
            )

        if not client:
            return openai_missing()

        if len(text) > 4096:
            text = text[:4096]

        api_params = {
            'model': 'gpt-4o-mini-tts',
            'voice': voice,
            'input': text,
            'response_format': 'mp3'
        }

        if instruction:
            api_params['instructions'] = instruction

        response = client.audio.speech.create(**api_params)

        return Response(response.content, mimetype='audio/mpeg')

    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

# Multiple exit strategies to ensure clean shutdown
def force_exit():
    """Force exit the application after 1 second if clean shutdown fails"""
    print("Force exiting application...")
    time.sleep(1)
    os._exit(0)

def shutdown_server_handler(signal_received, frame):
    """Signal handler for graceful shutdown"""
    global server
    print(f"\nSignal {signal_received} received. Shutting down server...")
    
    # Set a timer for force exit in case graceful shutdown hangs
    force_exit_timer = threading.Timer(3.0, force_exit)
    force_exit_timer.daemon = True
    force_exit_timer.start()
    
    try:
        if server:
            print("Stopping server...")
            server.shutdown()
    except Exception as e:
        print(f"Error during shutdown: {e}")
        sys.exit(1)
    
    # Exit the process
    sys.exit(0)

def cleanup_on_exit():
    """Atexit handler for any final cleanup"""
    print("Cleaning up resources...")

if __name__ == '__main__':
    # Register cleanup function
    atexit.register(cleanup_on_exit)

    # Register signal handlers for various termination signals
    signal.signal(signal.SIGINT, shutdown_server_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, shutdown_server_handler)  # Termination signal
    if hasattr(signal, 'SIGBREAK'):  # Windows Ctrl+Break
        signal.signal(signal.SIGBREAK, shutdown_server_handler)

    print("Starting dictation API server on http://localhost:5000 ...")
    print("Press Ctrl+C to stop the server")
    
    # Create server that we can shutdown gracefully
    # threaded so a long-running TTS stream doesn't block other requests
    server = make_server('localhost', 5000, app, threaded=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Directly call sys.exit() if KeyboardInterrupt is caught here
        # This ensures we exit even if the signal handler is bypassed
        print("\nKeyboardInterrupt caught. Exiting...")
        sys.exit(0)