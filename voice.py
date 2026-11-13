import sys
import subprocess
import os
from ctypes import *
from contextlib import contextmanager

# ALSA Error Hiding Magic (Silences C-level Linux audio driver errors)
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    try:
        import platform
        if platform.system() == "Linux":
            asound = cdll.LoadLibrary('libasound.so')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except:
        yield

import json
import threading
from queue import Queue, Empty
import asyncio
import edge_tts

import collections

_speech_generation_id = 0
_speech_lock = threading.Lock()
_stop_speech_event = threading.Event()
_active_audio_proc = None
_is_tts_playing = False
_last_spoken_phrases = collections.deque(maxlen=10)

def is_speech_active() -> bool:
    """Returns True if TTS is actively playing or synthesizing audio."""
    global _is_tts_playing, _active_speech_streamer
    if _is_tts_playing:
        return True
    if _active_speech_streamer is not None and not _active_speech_streamer.stop_event.is_set():
        return True
    return False

def register_spoken_text(text: str):
    """Registers text that was spoken aloud to guard against microphone acoustic self-hearing."""
    global _last_spoken_phrases
    import re
    if not text:
        return
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower()).strip()
    if clean and len(clean) >= 3:
        _last_spoken_phrases.append(clean)
        for part in re.split(r'[.!?\n]', text):
            p_clean = re.sub(r'[^a-zA-Z0-9\s]', '', part.lower()).strip()
            if p_clean and len(p_clean) >= 4:
                _last_spoken_phrases.append(p_clean)

def _split_into_sentences(text: str) -> list:
    """Splits text into natural sentence-sized chunks for instant streaming speech."""
    import re
    raw_parts = re.split(r'(?<=[.!?\n])\s+', text)
    sentences = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        if len(part) > 180:
            subs = re.split(r'(?<=[,;:])\s+', part)
            for sub in subs:
                sub = sub.strip()
                if sub:
                    sentences.append(sub)
        else:
            sentences.append(part)
    return sentences or [text]

def resolve_piper_path(voice: str) -> str:
    if not voice:
        voice = "piper-model/en_US-lessac-medium.onnx"
    if os.path.isabs(voice) and os.path.exists(voice):
        return voice
    if os.path.exists(voice):
        return os.path.abspath(voice)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(base_dir, voice)
    if os.path.exists(bundled):
        return bundled
    user_data = os.environ.get("TILUX_USER_DATA_DIR")
    if user_data:
        cand = os.path.join(user_data, voice)
        if os.path.exists(cand):
            return cand
    cache_cand = os.path.join(os.path.expanduser("~/.cache/tilux"), voice)
    if os.path.exists(cache_cand):
        return cache_cand
    return voice

def _generate_audio_sync(text: str, voice: str, speed: str) -> bytes:
    try:
        import json
        if os.path.exists("settings.json"):
            with open("settings.json", "r") as f:
                settings = json.load(f)
        else:
            settings = {}
        tts_engine = settings.get("tts_engine", "piper")
    except:
        tts_engine = "piper"
        
    if "Neural" in voice or "piper-model" not in voice:
        voice = "piper-model/en_US-lessac-medium.onnx"
        
    if tts_engine == "edge":
        async def _gen():
            comm = edge_tts.Communicate(text, voice, rate=speed)
            audio_data = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data
        try:
            return asyncio.run(_gen())
        except Exception:
            return b""
    else:
        # Piper Offline Mode
        try:
            import platform, subprocess, os, sys
            piper_cmd = [sys.executable, "-m", "piper"]
            voice = resolve_piper_path(voice)
            
            if not os.path.exists(voice):
                import urllib.request
                print(f"[Voice] Downloading requested voice model: {voice}...")
                try:
                    speaker = voice.split("-")[1]
                    quality = voice.split("-")[2].replace(".onnx", "")
                    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/{speaker}/{quality}/en_US-{speaker}-{quality}.onnx"
                    target_dir = os.environ.get("TILUX_USER_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
                    if not os.access(target_dir, os.W_OK):
                        target_dir = os.path.expanduser("~/.cache/tilux")
                    save_dir = os.path.join(target_dir, "piper-model")
                    os.makedirs(save_dir, exist_ok=True)
                    dest_file = os.path.join(save_dir, os.path.basename(voice))
                    urllib.request.urlretrieve(base_url, dest_file)
                    urllib.request.urlretrieve(base_url + ".json", dest_file + ".json")
                    voice = dest_file
                    print(f"[Voice] Successfully downloaded {speaker} voice to {voice}!")
                except Exception as e:
                    print(f"[Voice] Failed to download {voice}: {e}")
                    voice = resolve_piper_path("piper-model/en_US-lessac-medium.onnx")
                
            piper_proc = subprocess.Popen(
                piper_cmd + ["--model", voice, "--output_raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            out, _ = piper_proc.communicate(input=text.encode('utf-8'))
            
            # Piper outputs raw s16le PCM at 22050Hz. Let's wrap it in a proper WAV header using Python's wave module so the browser can play it easily.
            import wave, io
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(out)
            return wav_io.getvalue()
        except Exception as e:
            print(f"Piper generation error: {e}")
            return b""

_active_speech_streamer = None

def clean_speech_text(text: str) -> str:
    """Sanitizes Markdown and syntax out of text for spoken speech."""
    import re
    clean = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    clean = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean)
    clean = re.sub(r'```[\s\S]*?```', '', clean)
    clean = re.sub(r'`[^`]+`', '', clean)
    clean = re.sub(r'https?://[^\s]+', '', clean)
    clean = re.sub(r'/[a-zA-Z0-9_./-]+', '', clean)
    clean = re.sub(r'[*_~`#>\-]', '', clean).strip()
    return clean

class SpeechStreamer:
    """Streams sentence chunks to Piper TTS with seamless pipelined playback and sub-second latency."""
    def __init__(self, on_chunk_start=None):
        global _active_speech_streamer, _speech_generation_id
        with _speech_lock:
            _speech_generation_id += 1
            self.gen_id = _speech_generation_id
            _stop_speech_event.clear()
            _active_speech_streamer = self

        self.queue = Queue()
        self.on_chunk_start = on_chunk_start
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def feed(self, sentence: str):
        if not self.stop_event.is_set() and sentence:
            self.queue.put(sentence)

    def finish(self):
        self.queue.put(None)

    def wait(self, timeout: float = 12.0):
        self.worker.join(timeout=timeout)

    def stop(self):
        self.stop_event.set()
        self.queue.put(None)
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def _run(self):
        import sounddevice as sd
        import numpy as np
        import time, sys
        settings = get_voice_settings()
        tts_voice = settings.get("tts_voice", "piper-model/en_US-lessac-medium.onnx")
        voice_obj = get_piper_voice(tts_voice)
        sample_rate = getattr(voice_obj.config, "sample_rate", 22050) if voice_obj else 22050

        while not self.stop_event.is_set() and not _stop_speech_event.is_set() and self.gen_id == _speech_generation_id:
            try:
                sentence = self.queue.get(timeout=0.05)
            except Empty:
                continue
            if sentence is None:
                break
            if not sentence.strip():
                continue

            if "server" in sys.modules:
                srv = sys.modules["server"]
                if getattr(srv.brain, "abort_flag", False) or not getattr(srv, "is_voice_assistant_active", True):
                    break

            clean = clean_speech_text(sentence)
            if not clean:
                continue

            if self.on_chunk_start and callable(self.on_chunk_start):
                try:
                    self.on_chunk_start(clean)
                except Exception:
                    pass

            if voice_obj:
                chunks = []
                for chunk in voice_obj.synthesize(clean):
                    if self.stop_event.is_set() or _stop_speech_event.is_set() or self.gen_id != _speech_generation_id:
                        break
                    chunks.append(chunk.audio_int16_bytes)
                if self.stop_event.is_set() or _stop_speech_event.is_set() or self.gen_id != _speech_generation_id:
                    break
                if chunks:
                    global _is_tts_playing
                    _is_tts_playing = True
                    register_spoken_text(clean)
                    audio_np = np.frombuffer(b"".join(chunks), dtype=np.int16)
                    sd.play(audio_np, samplerate=sample_rate)
                    duration_sec = len(audio_np) / float(sample_rate)
                    t0 = time.time()
                    while (time.time() - t0) < duration_sec:
                        if self.stop_event.is_set() or _stop_speech_event.is_set() or self.gen_id != _speech_generation_id:
                            sd.stop()
                            _is_tts_playing = False
                            return
                        if "server" in sys.modules:
                            srv = sys.modules["server"]
                            if getattr(srv.brain, "abort_flag", False) or not getattr(srv, "is_voice_assistant_active", True):
                                sd.stop()
                                _is_tts_playing = False
                                return
                        time.sleep(0.015)
                    try:
                        sd.wait()
                    except Exception:
                        pass
            else:
                speak_os_fallback(clean)

def speak(text: str):
    """Converts text to speech and plays it with instantaneous sentence-pipelined streaming and zero lag."""
    clean_text = clean_speech_text(text)
    if not clean_text:
        return
    
    # Load TTS Settings
    settings = get_voice_settings()
    if not settings.get("tts_enabled", True):
        return # Do not speak if disabled

    # Atomically claim new generation ID and reset stop event
    global _speech_generation_id
    with _speech_lock:
        _speech_generation_id += 1
        my_gen_id = _speech_generation_id
        _stop_speech_event.clear()

    # Pre-emptively stop previous hardware sound output before playing new turn
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
        
    try:
        tts_engine = settings.get("tts_engine", "piper")
        tts_voice = settings.get("tts_voice", "piper-model/en_US-lessac-medium.onnx")
        tts_speed = settings.get("tts_speed", "+20%")
        
        if tts_engine == "edge":
            try:
                import edge_tts, asyncio
                async def _stream_edge():
                    global _active_audio_proc
                    comm = edge_tts.Communicate(clean_text, tts_voice, rate=tts_speed)
                    p2 = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    _active_audio_proc = p2
                    async for chunk in comm.stream():
                        if my_gen_id != _speech_generation_id or _stop_speech_event.is_set():
                            p2.terminate()
                            break
                        if "server" in sys.modules and getattr(sys.modules["server"].brain, "abort_flag", False):
                            p2.terminate()
                            break
                        if chunk["type"] == "audio":
                            try:
                                p2.stdin.write(chunk["data"])
                                p2.stdin.flush()
                            except Exception:
                                break
                    try:
                        p2.stdin.close()
                        p2.wait()
                    except Exception:
                        pass
                asyncio.run(_stream_edge())
            except Exception:
                if 'p2' in locals() and p2.poll() is None:
                    p2.terminate()
        else:
            # Piper TTS Instant Sentence-Pipelined Streaming Mode
            try:
                voice_obj = get_piper_voice(tts_voice)
                if not voice_obj:
                    speak_os_fallback(clean_text)
                    return

                import sounddevice as sd
                import numpy as np
                import time

                sample_rate = getattr(voice_obj.config, "sample_rate", 22050)
                sentences = _split_into_sentences(clean_text)
                if not sentences:
                    return

                # Pipeline: synthesize sentences in background worker, play immediately as each chunk arrives
                audio_queue = Queue(maxsize=3)
                synth_done = threading.Event()

                def _synthesize_worker():
                    try:
                        for s in sentences:
                            if my_gen_id != _speech_generation_id or _stop_speech_event.is_set():
                                break
                            if "server" in sys.modules and getattr(sys.modules["server"].brain, "abort_flag", False):
                                break
                            chunks = []
                            for chunk in voice_obj.synthesize(s):
                                if my_gen_id != _speech_generation_id or _stop_speech_event.is_set():
                                    break
                                chunks.append(chunk.audio_int16_bytes)
                            if my_gen_id != _speech_generation_id or _stop_speech_event.is_set():
                                break
                            if chunks:
                                arr = np.frombuffer(b"".join(chunks), dtype=np.int16)
                                audio_queue.put(arr)
                    except Exception as e:
                        print(f"[Voice] Sentence synthesis notice: {e}")
                    finally:
                        synth_done.set()

                worker_thread = threading.Thread(target=_synthesize_worker, daemon=True)
                worker_thread.start()

                # Immediately play audio chunks as each sentence finishes synthesis (~40ms for 1st sentence)
                while not _stop_speech_event.is_set() and my_gen_id == _speech_generation_id:
                    if audio_queue.empty() and synth_done.is_set():
                        break
                    try:
                        audio_np = audio_queue.get(timeout=0.03)
                    except Empty:
                        continue

                    if my_gen_id != _speech_generation_id or _stop_speech_event.is_set():
                        sd.stop()
                        break

                    sd.stop()
                    sd.play(audio_np, samplerate=sample_rate)
                    duration_sec = len(audio_np) / float(sample_rate)
                    start_time = time.time()

                    # High-frequency polling (15ms) for instantaneous abort
                    while (time.time() - start_time) < duration_sec:
                        if my_gen_id != _speech_generation_id or _stop_speech_event.is_set():
                            sd.stop()
                            return
                        if "server" in sys.modules and getattr(sys.modules["server"].brain, "abort_flag", False):
                            sd.stop()
                            return
                        time.sleep(0.015)
                    try:
                        sd.wait()
                    except Exception:
                        pass

                sd.stop()
            except Exception as e:
                print(f"[Voice] Piper TTS error: {e}. Falling back to OS speech...")
                terminate_active_audio()
                speak_os_fallback(clean_text)
            finally:
                _is_tts_playing = False
    except Exception as e:
        print(f"[Voice] Speak error: {e}. Falling back to OS speech...")
        terminate_active_audio()
        speak_os_fallback(clean_text)
    finally:
        _is_tts_playing = False

def speak_os_fallback(text: str) -> bool:
    """Fallback to native OS speech (spd-say / pyttsx3 / say / SAPI)."""
    if not text or not text.strip():
        return False
    try:
        import platform, subprocess
        sys_name = platform.system()
        if sys_name == "Darwin":
            res = subprocess.run(["say", text], check=False)
            return res.returncode == 0
        elif sys_name == "Linux":
            res = subprocess.run(["spd-say", "-t", "female2", "-r", "10", text], capture_output=True)
            if res.returncode == 0:
                return True
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[Voice] OS speech fallback error: {e}")
        return False

def generate_audio_buffer(text: str, voice: str, speed: str) -> bytes:
    """Generates TTS audio and returns raw MP3 bytes (no playback)."""
    if not text.strip():
        return b""
    return _generate_audio_sync(text, voice, speed)

def terminate_active_audio():
    """Immediately stops all audio playback, kills sounddevice buffer, and aborts speech threads."""
    global _active_audio_proc, _speech_generation_id, _active_speech_streamer
    with _speech_lock:
        _speech_generation_id += 1
        _stop_speech_event.set()

    # 1. Immediately silence hardware sound output in native sounddevice
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass

    if _active_speech_streamer is not None:
        try:
            _active_speech_streamer.stop()
        except Exception:
            pass
        _active_speech_streamer = None

    # 2. Terminate any active external speech process (ffplay, etc.)
    if _active_audio_proc is not None:
        try:
            _active_audio_proc.kill()
        except Exception:
            pass
        _active_audio_proc = None

    import platform, subprocess
    if platform.system() == "Windows":
        subprocess.run("taskkill /F /IM ffplay.exe /T 2>NUL || exit /b 0", shell=True)
    elif platform.system() == "Darwin":
        subprocess.run("pkill -9 ffplay 2>/dev/null || killall -9 ffplay 2>/dev/null || true", shell=True)
        subprocess.run("pkill -9 say 2>/dev/null || killall -9 say 2>/dev/null || true", shell=True)
    else:
        subprocess.run("pkill -9 ffplay 2>/dev/null || killall -9 ffplay 2>/dev/null || true", shell=True)
        subprocess.run("spd-say -C 2>/dev/null || true", shell=True)
        subprocess.run("pkill -9 spd-say 2>/dev/null || killall -9 spd-say 2>/dev/null || true", shell=True)

def get_voice_settings():
    """Reads settings.json directly without relying on external module state."""
    settings = {"tts_enabled": True, "tts_voice": "piper-model/en_US-lessac-medium.onnx", "tts_speed": "+20%"}
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r") as f:
                settings.update(json.load(f))
        except Exception:
            pass
    return settings

_cached_piper_voice = None
_cached_piper_model_path = None

def get_piper_voice(model_path: str = None):
    global _cached_piper_voice, _cached_piper_model_path
    if model_path is None:
        settings = get_voice_settings()
        model_path = settings.get("tts_voice", "piper-model/en_US-lessac-medium.onnx")
        
    resolved_path = resolve_piper_path(model_path)
    if not os.path.exists(resolved_path):
        import urllib.request
        print(f"[Voice] Downloading requested voice model: {model_path}...")
        try:
            speaker = model_path.split("-")[1]
            quality = model_path.split("-")[2].replace(".onnx", "")
            base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/{speaker}/{quality}/en_US-{speaker}-{quality}.onnx"
            target_dir = os.environ.get("TILUX_USER_DATA_DIR") or os.path.dirname(os.path.abspath(__file__))
            if not os.access(target_dir, os.W_OK):
                target_dir = os.path.expanduser("~/.cache/tilux")
            save_dir = os.path.join(target_dir, "piper-model")
            os.makedirs(save_dir, exist_ok=True)
            dest_file = os.path.join(save_dir, os.path.basename(model_path))
            urllib.request.urlretrieve(base_url, dest_file)
            urllib.request.urlretrieve(base_url + ".json", dest_file + ".json")
            resolved_path = dest_file
            print(f"[Voice] Successfully downloaded {speaker} voice to {resolved_path}!")
        except Exception as e:
            print(f"[Voice] Failed to download {model_path}: {e}")
            resolved_path = resolve_piper_path("piper-model/en_US-lessac-medium.onnx")

    if _cached_piper_voice is None or _cached_piper_model_path != resolved_path:
        try:
            from piper import PiperVoice
            print(f"[Voice] Loading Piper ONNX voice into RAM ({resolved_path})...")
            _cached_piper_voice = PiperVoice.load(resolved_path)
            _cached_piper_model_path = resolved_path
            print("[Voice] Piper ONNX voice loaded successfully!")
        except Exception as e:
            print(f"[Voice] Error loading in-memory Piper voice: {e}")
            _cached_piper_voice = None
            
    return _cached_piper_voice

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            print("[Voice] Loading Whisper AI into RAM (first time only, please wait 2 seconds)...")
            from faster_whisper import WhisperModel
            import os
            # Use tiny.en for blazing fast CPU inference and utilize all cores
            _whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
        except Exception as e:
            print(f"[Voice] Failed to load Whisper: {e}")
    return _whisper_model

def init_voice_models():
    """Preloads Whisper, Piper, and warms up Groq client into RAM in background so first wake word is instant."""
    import threading
    def _loader():
        try:
            get_groq_client()
            get_whisper_model()
            settings = get_voice_settings()
            tts_voice = settings.get("tts_voice", "piper-model/en_US-lessac-medium.onnx")
            get_piper_voice(tts_voice)
        except Exception as e:
            print(f"[Voice] Model preload notice: {e}")
    threading.Thread(target=_loader, daemon=True).start()

_cached_groq_client = None

def get_groq_client():
    global _cached_groq_client
    if _cached_groq_client is not None:
        return _cached_groq_client
    import os
    try:
        try:
            from vault import get_credential
        except ImportError:
            from credentials import get_credential
        groq_key = get_credential("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    except Exception:
        groq_key = os.getenv("GROQ_API_KEY")
        
    if not groq_key:
        return None
    try:
        from openai import OpenAI
        _cached_groq_client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            timeout=4.5
        )
        return _cached_groq_client
    except Exception as e:
        print(f"[Voice] Groq client init notice: {e}")
        return None

def transcribe_groq_whisper(audio_np, sample_rate: int = 16000) -> str:
    """Ultra-fast Groq LPU Whisper transcription (~100-300ms latency)."""
    client = get_groq_client()
    if client is None:
        return ""
    try:
        import io, wave, time
        import numpy as np
        
        t0 = time.time()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes((np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
        buf.seek(0)
        buf.name = "audio.wav"

        res = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=buf,
            language="en"
        )
        text = getattr(res, "text", str(res)).strip()
        # Filter hallucinated single periods or generic silence markers
        if text and text not in [".", "..", "...", "you", "Thank you.", "Thank you!"]:
            elapsed = time.time() - t0
            print(f"[Voice] ⚡ Groq LPU Whisper STT ({elapsed:.2f}s): '{text}'")
            return text
    except Exception as e:
        print(f"[Voice] Groq Whisper error: {e}")
    return ""

def _filter_echo(text: str) -> str:
    """Verifies that recognized text is NOT an acoustic echo of the assistant's own recent speech."""
    if not text:
        return ""
    import re
    norm_transcribed = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower()).strip()
    if not norm_transcribed:
        return ""
    trans_words = set(norm_transcribed.split())
    for sp in list(_last_spoken_phrases):
        if not sp:
            continue
        sp_words = set(sp.split())
        # Direct containment check
        if norm_transcribed == sp or norm_transcribed in sp or sp in norm_transcribed:
            print(f"[Voice Echo Guard] 🛡️ Filtered self-echo (match with recent speech '{sp}'): '{text}'")
            return ""
        # High word-set overlap check (> 70%)
        if trans_words and sp_words:
            overlap = len(trans_words.intersection(sp_words)) / float(len(trans_words))
            if overlap >= 0.70 and len(trans_words) >= 2:
                print(f"[Voice Echo Guard] 🛡️ Filtered self-echo ({overlap*100:.0f}% word overlap with '{sp}'): '{text}'")
                return ""
    return text

def listen(on_recording_done=None) -> str:
    """Listens to the microphone using ultra-fast dynamic VAD and returns transcribed text."""
    model = get_whisper_model()
    if not model:
        return ""

    import time
    # 1. Acoustic Self-Hearing Guard: Wait only if TTS audio is actively playing on speakers
    t_wait_start = time.time()
    waited_for_tts = False
    while is_speech_active() and (time.time() - t_wait_start) < 2.5:
        waited_for_tts = True
        time.sleep(0.04)

    # 2. Reverb Settle Time: only needed if TTS was just outputting sound to speakers
    if waited_for_tts:
        time.sleep(0.10)
        
    sample_rate = 16000
    print("[Voice] Listening for user speech...")
    
    audio_buffer = []
    
    import numpy as np
    import sounddevice as sd
    
    SILENCE_DURATION = 0.45     # Seconds of trailing silence to finalize recording (~450ms for snappy turn-taking)
    MAX_RECORD_DURATION = 15.0  # Max seconds for a single voice utterance (avoids giant audio buffers)
    INITIAL_TIMEOUT = 25.0      # Stays awake 25s if user hasn't started speaking before auto-closing
    POST_SPEECH_TIMEOUT = 1.0   # Forceful cutoff 1.0s after user stops speaking even if room has ambient hum
    
    frames_per_chunk = 1600     # 0.10 seconds per chunk at 16kHz
    chunk_sec = 0.10
    
    max_silence_chunks = int(SILENCE_DURATION / chunk_sec)
    max_chunks = int(MAX_RECORD_DURATION / chunk_sec)
    initial_timeout_chunks = int(INITIAL_TIMEOUT / chunk_sec)
    min_speech_chunks = int(0.20 / chunk_sec)
    
    silence_chunks_count = 0
    speech_chunks_count = 0
    has_spoken = False
    last_speech_time = None
    peak_speech_rms = 0.001
    
    # Dynamic Adaptive VAD: calibrate against actual room/mic noise floor
    ambient_samples = []
    ambient_floor = 0.012
    dynamic_speech_threshold = 0.026
    dynamic_silence_threshold = 0.016
    is_calibrated = False
    
    try:
        with noalsaerr():
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', blocksize=frames_per_chunk) as stream:

                for chunk_idx in range(max_chunks):
                    chunk, overflowed = stream.read(frames_per_chunk)
                    chunk = np.squeeze(chunk)
                    audio_buffer.append(chunk)
                    
                    # Immediately exit if user closed popup or aborted
                    import sys
                    if "server" in sys.modules:
                        srv = sys.modules["server"]
                        if hasattr(srv, "brain") and (getattr(srv.brain, "abort_flag", False) or not getattr(srv, "is_voice_assistant_active", True)):
                            print("[Voice] Recording aborted by user / widget closed.")
                            return ""
                    
                    rms = float(np.sqrt(np.mean(chunk**2)))
                    now = time.time()
                    
                    # 1. Calibrate baseline from first 3 ambient chunks
                    if not is_calibrated:
                        ambient_samples.append(rms)
                        if len(ambient_samples) >= 3:
                            ambient_floor = float(np.median(ambient_samples))
                            dynamic_speech_threshold = max(0.024, (ambient_floor * 1.35) + 0.008)
                            dynamic_silence_threshold = max(0.016, (ambient_floor * 1.15) + 0.004)
                            is_calibrated = True
                    
                    # 2. Track speech detection
                    if not has_spoken:
                        if rms >= dynamic_speech_threshold:
                            has_spoken = True
                            speech_chunks_count = 1
                            silence_chunks_count = 0
                            last_speech_time = now
                            peak_speech_rms = rms
                        else:
                            # Adaptively track rising background noise (e.g. laptop fan spinning up)
                            if rms < 0.035:
                                ambient_floor = (0.90 * ambient_floor) + (0.10 * rms)
                                dynamic_speech_threshold = max(0.024, (ambient_floor * 1.35) + 0.008)
                                dynamic_silence_threshold = max(0.016, (ambient_floor * 1.15) + 0.004)
                    else:
                        peak_speech_rms = max(peak_speech_rms, rms)
                        # A chunk is considered active speech if it exceeds dynamic threshold or is within speech dynamic range
                        is_speech = (rms >= dynamic_silence_threshold and rms >= (peak_speech_rms * 0.40)) or (rms >= dynamic_speech_threshold)
                        if is_speech:
                            speech_chunks_count += 1
                            silence_chunks_count = 0
                            last_speech_time = now
                        else:
                            silence_chunks_count += 1
                            
                    # 3. Cutoff when speech is complete
                    if has_spoken and speech_chunks_count >= min_speech_chunks:
                        # Case A: Sustained silence detected
                        if silence_chunks_count >= max_silence_chunks:
                            print(f"[Voice] Speech ended (silence cutoff after {chunk_idx * chunk_sec:.2f}s). Processing speech.")
                            if on_recording_done:
                                try:
                                    on_recording_done()
                                except Exception:
                                    pass
                            break
                        # Case B: Post-speech safety timer (prevents hanging when mic has persistent hum/fan noise)
                        if last_speech_time and (now - last_speech_time) >= POST_SPEECH_TIMEOUT:
                            print(f"[Voice] Speech ended (post-speech safety cutoff after {chunk_idx * chunk_sec:.2f}s). Processing speech.")
                            if on_recording_done:
                                try:
                                    on_recording_done()
                                except Exception:
                                    pass
                            break
                        
                    # 4. Timeout if user triggered wake word but never spoke
                    if not has_spoken and chunk_idx >= initial_timeout_chunks:
                        print(f"[Voice] Initial timeout: No speech detected within {INITIAL_TIMEOUT:.0f}s.")
                        return ""
                        
        if not has_spoken or not audio_buffer:
            return ""
            
        audio_np = np.concatenate(audio_buffer)

        # Abort if user cancelled during recording
        import sys
        if "server" in sys.modules:
            srv = sys.modules["server"]
            if hasattr(srv, "brain") and getattr(srv.brain, "abort_flag", False):
                print("[Voice] Transcription cancelled by abort_flag.")
                return ""

        # 1. Ultra-Fast Groq Cloud Whisper (~100-300ms on Groq LPUs)
        groq_text = transcribe_groq_whisper(audio_np, sample_rate)
        if groq_text:
            return _filter_echo(groq_text)

        # 2. Fast Cloud Speech Recognition Fallback (Google STT ~350ms)
        try:
            import speech_recognition as sr
            int16_bytes = (np.clip(audio_np, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            audio_data = sr.AudioData(int16_bytes, sample_rate, 2)
            r = sr.Recognizer()
            try:
                text = r.recognize_google(audio_data, language="en-US").strip()
            except Exception:
                text = r.recognize_google(audio_data, language="en-NG").strip()
            if text:
                print(f"[Voice] Google STT transcript: '{text}'")
                return _filter_echo(text)
        except Exception as fast_err:
            print(f"[Voice] Google STT unavailable ({fast_err}). Using Faster-Whisper fallback...")

        # 3. Resilient Offline Fallback (Faster-Whisper on-device CPU)
        print("[Voice] Faster-Whisper transcribing speech...")
        segments, info = model.transcribe(
            audio_np, 
            beam_size=1, 
            best_of=1, 
            condition_on_previous_text=False, 
            language="en"
        )
        text = " ".join([segment.text for segment in segments]).strip()
        print(f"[Voice] Faster-whisper transcript: '{text}'")
        return _filter_echo(text)
    except Exception as e:
        print(f"[Voice] Microphone/Recognition Error: {e}")
        return ""


