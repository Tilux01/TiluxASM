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

import asyncio
import edge_tts

def _generate_audio_sync(text: str, voice: str, speed: str) -> bytes:
    try:
        from main import load_settings
        settings = load_settings()
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
            
            if not os.path.exists(voice):
                import urllib.request
                print(f"[Voice] Downloading requested voice model: {voice}...")
                try:
                    speaker = voice.split("-")[1]
                    quality = voice.split("-")[2].replace(".onnx", "")
                    base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/{speaker}/{quality}/en_US-{speaker}-{quality}.onnx"
                    os.makedirs("piper-model", exist_ok=True)
                    urllib.request.urlretrieve(base_url, voice)
                    urllib.request.urlretrieve(base_url + ".json", voice + ".json")
                    print(f"[Voice] Successfully downloaded {speaker} voice!")
                except Exception as e:
                    print(f"[Voice] Failed to download {voice}: {e}")
                    voice = "piper-model/en_US-lessac-medium.onnx"
                
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

def speak(text: str):
    """Converts text to speech and plays it using Edge TTS (Dynamic Voice/Speed)."""
    import re
    clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    clean_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_text)
    clean_text = re.sub(r'```[\s\S]*?```', '', clean_text)
    clean_text = re.sub(r'`[^`]+`', '', clean_text)
    clean_text = re.sub(r'https?://[^\s]+', '', clean_text)
    clean_text = re.sub(r'/[a-zA-Z0-9_./-]+', '', clean_text)
    clean_text = re.sub(r'[*_~`#>\-]', '', clean_text).strip()
    if not clean_text:
        return
    
    # Load TTS Settings
    settings = {"tts_enabled": True, "tts_voice": "piper-model/en_US-lessac-medium.onnx", "tts_speed": "+20%"}
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r") as f:
                saved = json.load(f)
                settings.update(saved)
        except:
            pass
            
    if "Neural" in settings.get("tts_voice", "") or "piper-model" not in settings.get("tts_voice", ""):
        settings["tts_voice"] = "piper-model/en_US-lessac-medium.onnx"
            
    if not settings.get("tts_enabled", True):
        return # Do not speak if disabled
        
    try:
        tts_engine = settings.get("tts_engine", "piper")
        tts_voice = settings.get("tts_voice", "piper-model/en_US-lessac-medium.onnx")
        tts_speed = settings.get("tts_speed", "+20%")
        
        async def _stream_play():
            if tts_engine == "edge":
                try:
                    comm = edge_tts.Communicate(clean_text, tts_voice, rate=tts_speed)
                    p2 = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    async for chunk in comm.stream():
                        if chunk["type"] == "audio":
                            try:
                                import sys
                                if "server" in sys.modules:
                                    srv = sys.modules["server"]
                                    if hasattr(srv, "brain") and getattr(srv.brain, "abort_flag", False):
                                        p2.terminate()
                                        break
                                p2.stdin.write(chunk["data"])
                                p2.stdin.flush()
                            except:
                                break
                    p2.stdin.close()
                    p2.wait()
                except Exception:
                    if 'p2' in locals() and p2.poll() is None:
                        p2.terminate()
            else:
                # Piper TTS Offline In-Memory Streaming Mode
                try:
                    voice_obj = get_piper_voice(tts_voice)
                    if voice_obj:
                        global _active_audio_proc
                        sample_rate = str(getattr(voice_obj.config, "sample_rate", 22050))
                        ffplay_proc = subprocess.Popen(
                            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-f", "s16le", "-ar", sample_rate, "-ac", "1", "-i", "-"],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        _active_audio_proc = ffplay_proc
                        for audio_chunk in voice_obj.synthesize(clean_text):
                            import sys
                            if "server" in sys.modules:
                                srv = sys.modules["server"]
                                if hasattr(srv, "brain") and getattr(srv.brain, "abort_flag", False):
                                    try:
                                        ffplay_proc.kill()
                                    except:
                                        pass
                                    _active_audio_proc = None
                                    return
                            try:
                                ffplay_proc.stdin.write(audio_chunk.audio_int16_bytes)
                                ffplay_proc.stdin.flush()
                            except:
                                break
                        try:
                            ffplay_proc.stdin.close()
                        except (BrokenPipeError, OSError):
                            pass
                        
                        # Non-blocking poll so we can abort instantly if window closes or user cancels
                        import time
                        while ffplay_proc.poll() is None:
                            import sys
                            if "server" in sys.modules:
                                srv = sys.modules["server"]
                                if hasattr(srv, "brain") and getattr(srv.brain, "abort_flag", False):
                                    try:
                                        ffplay_proc.kill()
                                    except:
                                        pass
                                    break
                            time.sleep(0.04)
                        _active_audio_proc = None
                    else:
                        speak_os_fallback(clean_text)
                except Exception as e:
                    print(f"[Voice] Piper TTS error: {e}. Falling back to OS speech...")
                    terminate_active_audio()
                    speak_os_fallback(clean_text)
                
        asyncio.run(_stream_play())
    except Exception as e:
        print(f"[Voice] Speak error: {e}. Falling back to OS speech...")
        speak_os_fallback(clean_text)

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
    """Immediately stops all audio playback and child speech processes."""
    global _active_audio_proc
    if _active_audio_proc is not None:
        try:
            _active_audio_proc.kill()
        except Exception:
            pass
        _active_audio_proc = None
    import platform, subprocess
    if platform.system() == "Windows":
        subprocess.run("taskkill /F /IM ffplay.exe /T 2>NUL || exit /b 0", shell=True)
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
        
    if not os.path.exists(model_path):
        import urllib.request
        print(f"[Voice] Downloading requested voice model: {model_path}...")
        try:
            speaker = model_path.split("-")[1]
            quality = model_path.split("-")[2].replace(".onnx", "")
            base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/{speaker}/{quality}/en_US-{speaker}-{quality}.onnx"
            os.makedirs("piper-model", exist_ok=True)
            urllib.request.urlretrieve(base_url, model_path)
            urllib.request.urlretrieve(base_url + ".json", model_path + ".json")
            print(f"[Voice] Successfully downloaded {speaker} voice!")
        except Exception as e:
            print(f"[Voice] Failed to download {model_path}: {e}")
            model_path = "piper-model/en_US-lessac-medium.onnx"

    if _cached_piper_voice is None or _cached_piper_model_path != model_path:
        try:
            from piper import PiperVoice
            print(f"[Voice] Loading Piper ONNX voice into RAM ({model_path})...")
            _cached_piper_voice = PiperVoice.load(model_path)
            _cached_piper_model_path = model_path
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
    """Preloads Whisper and Piper into RAM in background so first wake word is instant."""
    import threading
    def _loader():
        try:
            get_whisper_model()
            settings = get_voice_settings()
            tts_voice = settings.get("tts_voice", "piper-model/en_US-lessac-medium.onnx")
            get_piper_voice(tts_voice)
        except Exception as e:
            print(f"[Voice] Model preload notice: {e}")
    threading.Thread(target=_loader, daemon=True).start()

def listen(on_recording_done=None) -> str:
    """Listens to the microphone using VAD and returns the transcribed text."""
    model = get_whisper_model()
    if not model:
        return ""
        
    sample_rate = 16000
    print("[Voice] Listening for user speech...")
    
    audio_buffer = []
    
    import numpy as np
    import sounddevice as sd
    
    SILENCE_THRESHOLD = 0.015  # Amplitude threshold
    SILENCE_DURATION = 0.55    # Seconds of silence to stop recording (fast responsive cutoff)
    MAX_DURATION = 15.0        # Max seconds to record
    
    frames_per_chunk = 2000    # 0.125 seconds per chunk at 16kHz for responsive VAD
    max_silence_chunks = int(SILENCE_DURATION / 0.125)
    max_chunks = int(MAX_DURATION / 0.125)
    
    silence_chunks_count = 0
    has_spoken = False
    
    try:
        with noalsaerr():
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', blocksize=frames_per_chunk) as stream:
                for _ in range(max_chunks):
                    chunk, overflowed = stream.read(frames_per_chunk)
                    chunk = np.squeeze(chunk)
                    audio_buffer.append(chunk)
                    
                    # Calculate volume (RMS)
                    rms = np.sqrt(np.mean(chunk**2))
                    
                    if rms > SILENCE_THRESHOLD:
                        has_spoken = True
                        silence_chunks_count = 0
                    elif has_spoken:
                        silence_chunks_count += 1
                        
                    if has_spoken and silence_chunks_count >= max_silence_chunks:
                        print("[Voice] Silence detected. Stopping recording.")
                        # Immediately notify callback so UI switches to 'Processing...' with 0 delay!
                        if on_recording_done:
                            try:
                                on_recording_done()
                            except Exception:
                                pass
                        break
                        
        if not has_spoken:
            print("[Voice] Listen timeout (no speech detected).")
            return ""
            
        print("[Voice] Sending audio to Faster-Whisper...")
        audio_np = np.concatenate(audio_buffer)
        
        segments, info = model.transcribe(
            audio_np, 
            beam_size=1, 
            best_of=1, 
            condition_on_previous_text=False, 
            language="en"
        )
        text = " ".join([segment.text for segment in segments]).strip()
        print(f"[Voice] Faster-whisper transcription complete: '{text}'")
        return text
    except Exception as e:
        print(f"[Voice] Microphone/Recognition Error: {e}")
        return ""
