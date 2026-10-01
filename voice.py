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
            import platform, subprocess, os
            piper_bin = "./venv/bin/piper" if platform.system() != "Windows" else ".\\venv\\Scripts\\piper.exe"
            
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
                [piper_bin, "--model", voice, "--output_raw"],
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
                # Piper TTS Offline Mode
                try:
                    import platform
                    piper_bin = "./venv/bin/piper" if platform.system() != "Windows" else ".\\venv\\Scripts\\piper.exe"
                    
                    model_path = tts_voice
                    if not os.path.exists(model_path):
                        import urllib.request
                        print(f"[Voice] Downloading requested voice model: {model_path}...")
                        try:
                            # Extract speaker from path (e.g. 'piper-model/en_US-amy-medium.onnx' -> 'amy')
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
                        
                    piper_proc = subprocess.Popen(
                        [piper_bin, "--model", model_path, "--output_raw"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL
                    )
                    
                    ffplay_proc = subprocess.Popen(
                        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-f", "s16le", "-ar", "22050", "-ac", "1", "-i", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
                    piper_proc.stdin.write(clean_text.encode("utf-8"))
                    piper_proc.stdin.close()
                    
                    while True:
                        chunk = piper_proc.stdout.read(4096)
                        if not chunk:
                            break
                        
                        import sys
                        if "server" in sys.modules:
                            srv = sys.modules["server"]
                            if hasattr(srv, "brain") and getattr(srv.brain, "abort_flag", False):
                                piper_proc.terminate()
                                ffplay_proc.terminate()
                                break
                                
                        try:
                            ffplay_proc.stdin.write(chunk)
                            ffplay_proc.stdin.flush()
                        except:
                            break
                            
                    ffplay_proc.stdin.close()
                    ffplay_proc.wait()
                    piper_proc.wait()
                except Exception as e:
                    print(f"[Voice] Piper TTS error: {e}")
                    if 'piper_proc' in locals() and piper_proc.poll() is None:
                        piper_proc.terminate()
                    if 'ffplay_proc' in locals() and ffplay_proc.poll() is None:
                        ffplay_proc.terminate()
                
        asyncio.run(_stream_play())
    except Exception as e:
        print(f"[Voice] Speak error: {e}")

def generate_audio_buffer(text: str, voice: str, speed: str) -> bytes:
    """Generates TTS audio and returns raw MP3 bytes (no playback)."""
    if not text.strip():
        return b""
    return _generate_audio_sync(text, voice, speed)

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

def listen() -> str:
    """Listens to the microphone using VAD and returns the transcribed text."""
    model = get_whisper_model()
    if not model:
        return ""
        
    sample_rate = 16000
    print("[Voice] Listening for user speech...")
    
    audio_buffer = []
    
    # Simple VAD (Voice Activity Detection) Parameters
    import numpy as np
    import sounddevice as sd
    
    SILENCE_THRESHOLD = 0.015  # Amplitude threshold
    SILENCE_DURATION = 0.7     # Seconds of silence to stop recording
    MAX_DURATION = 15.0        # Max seconds to record
    
    frames_per_chunk = 4000    # 0.25 seconds per chunk at 16kHz
    max_silence_chunks = int(SILENCE_DURATION / 0.25)
    max_chunks = int(MAX_DURATION / 0.25)
    
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
                        break
                        
        if not has_spoken:
            print("[Voice] Listen timeout (no speech detected).")
            return ""
            
        print("[Voice] Sending audio to Faster-Whisper...")
        audio_np = np.concatenate(audio_buffer)
        
        segments, info = model.transcribe(audio_np, beam_size=5, language="en")
        text = " ".join([segment.text for segment in segments]).strip()
        print(f"[Voice] Faster-whisper transcription complete: '{text}'")
        return text
    except Exception as e:
        print(f"[Voice] Microphone/Recognition Error: {e}")
        return ""
