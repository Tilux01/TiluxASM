import queue
import threading
import json
import os
import time

try:
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
except ImportError:
    sd = None
    Model = None
    KaldiRecognizer = None

import re

WAKE_REGEX = re.compile(
    r'\b('
    r'hello\s+tilux|hey\s+assistant|'
    r'tilux|tlox|tielux|tealux|deluxe|'
    r'assistant|assistance|'
    r'(hey|hi|hello|ok|okay|yo|wake\s+up)\s+(tilux|tlox|deluxe|assistant|looks|locks|lux|lox|alex)|'
    r'(to|two|too|the|til|till|tell|tea|tee|tie|ty|t|de|d)\s+(looks|locks|lux|lox|luke\'?s|alex|acts)|'
    r'still\s+looks|'
    r'they\s+tell\s+(looks|us)'
    r')\b',
    re.IGNORECASE
)

class WakeWordEngine:
    def _locate_or_download_model(self) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data = os.environ.get("TILUX_USER_DATA_DIR")
        res_dir = os.environ.get("TILUX_RESOURCES_DIR")
        
        candidates = [
            "vosk-model",
            os.path.join(base_dir, "vosk-model"),
        ]
        if user_data:
            candidates.insert(0, os.path.join(user_data, "vosk-model"))
        if res_dir:
            candidates.insert(0, os.path.join(res_dir, "vosk-model"))
            candidates.insert(0, os.path.join(res_dir, "backend", "vosk-model"))
        parent_dir = os.path.dirname(base_dir)
        candidates.append(os.path.join(parent_dir, "vosk-model"))
        candidates.append(os.path.join(parent_dir, "backend", "vosk-model"))
        candidates.append(os.path.expanduser("~/.cache/tilux/vosk-model"))
            
        for cand in candidates:
            if cand and os.path.exists(cand) and os.path.isdir(cand) and (os.path.exists(os.path.join(cand, "am")) or os.path.exists(os.path.join(cand, "conf"))):
                print(f"[WakeWord] Found local Vosk model: {cand}")
                return cand
                
        # If model is not found, auto-download in background
        print("[WakeWord] Vosk model not found locally. Auto-downloading offline engine (40MB)...")
        target_dir = user_data if user_data and os.path.exists(user_data) else base_dir
        if not os.access(target_dir, os.W_OK):
            target_dir = os.path.expanduser("~/.cache/tilux")
            os.makedirs(target_dir, exist_ok=True)
            
        zip_path = os.path.join(target_dir, "vosk.zip")
        final_dir = os.path.join(target_dir, "vosk-model")
        vosk_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        
        try:
            import urllib.request
            import zipfile
            import shutil
            urllib.request.urlretrieve(vosk_url, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            extracted = os.path.join(target_dir, "vosk-model-small-en-us-0.15")
            if os.path.exists(extracted):
                if os.path.exists(final_dir):
                    shutil.rmtree(final_dir, ignore_errors=True)
                os.rename(extracted, final_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            print(f"[WakeWord] Vosk model downloaded successfully to: {final_dir}")
            return final_dir
        except Exception as e:
            print(f"[WakeWord] Auto-download error: {e}")
            if os.path.exists(zip_path):
                try: os.remove(zip_path)
                except Exception: pass
            return "vosk-model"

    def __init__(self, callback):
        self.callback = callback
        self.is_running = False
        self.is_paused = False
        self.thread = None
        self.q = queue.Queue()
        self.model_path = self._locate_or_download_model()
        self.active_keywords = [
            "hello tilux", "hey assistant",
            "hey tilux", "hi tilux", "ok tilux", "okay tilux", "yo tilux",
            "hello assistant", "hi assistant", "ok assistant", "okay assistant",
            "tilux", "tlox", "t lox", "t-lux", "t lux", "tielux", "tie lux", "tealux", "tee lux", "tea lux",
            "deluxe", "de luxe", "d lux",
            "to looks", "to locks", "to lux", "to lox",
            "two looks", "two locks", "two lux",
            "too looks", "too locks",
            "the looks", "the locks", "the lux", "the lox", "the alex",
            "til looks", "til locks", "til lux",
            "still looks",
            "it's looks",
            "tell looks",
            "she looks",
            "it looks",
            "tie looks",
            "he looks",
            "haiti looks",
            "haiti locks",
            "tie locks"
            "they tell looks", "they tell us",
            "tea locks", "tee locks", "tie locks",
            "tea looks", "tee looks", "tie looks",
            "ty looks", "till acts",
            "assistant", "assistance",
            "hey deluxe", "hi deluxe", "hello deluxe",
            "hey looks", "hey locks", "hey lux"
        ]

    def check_trigger(self, text: str) -> bool:
        is_trig, _ = self.extract_trigger_and_trailing(text)
        return is_trig

    def extract_trigger_and_trailing(self, text: str):
        if not text:
            return False, ""
        clean = text.lower().strip()
        m = WAKE_REGEX.search(clean)
        if m:
            trailing = clean[m.end():].strip(" ,.:;-")
            if not any(c.isalnum() for c in trailing):
                trailing = ""
            return True, trailing
        for kw in self.active_keywords:
            if kw in clean:
                idx = clean.find(kw)
                trailing = clean[idx + len(kw):].strip(" ,.:;-")
                if not any(c.isalnum() for c in trailing):
                    trailing = ""
                return True, trailing
        return False, ""

    def pause(self):
        self.is_paused = True
        
    def resume(self):
        # Clear any stale audio
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        self.is_paused = False

    def _get_input_stream_config(self):
        """Finds optimal microphone stream configuration: native 16kHz or hardware rate with transparent downsampling."""
        if sd is None:
            return 16000, 2000, False
        # 1. Native 16000Hz stream (direct pass-through, zero overhead)
        try:
            sd.check_input_settings(samplerate=16000, channels=1, dtype='int16')
            return 16000, 2000, False
        except Exception:
            pass

        # 2. Windows WASAPI or driver shared mode requiring 48kHz or 44.1kHz
        candidates = [48000, 44100, 32000, 22050]
        try:
            dev_info = sd.query_devices(kind='input')
            preferred = int(dev_info.get('default_samplerate', 48000))
            if preferred in candidates:
                candidates.remove(preferred)
            candidates.insert(0, preferred)
        except Exception:
            pass

        for sr in candidates:
            try:
                sd.check_input_settings(samplerate=sr, channels=1, dtype='int16')
                block_size = int(sr * 0.125) # ~125ms chunk
                return sr, block_size, True
            except Exception:
                continue

        return 16000, 2000, False

    def _listen_loop(self):
        if not os.path.exists(self.model_path) or Model is None:
            self.model_path = self._locate_or_download_model()
            if not os.path.exists(self.model_path) or Model is None:
                print("[WakeWord] Vosk model not found or dependencies missing.")
                return

        print("[WakeWord] Loading offline Vosk model at 16000Hz...")
        model = Model(self.model_path)
        recognizer = KaldiRecognizer(model, 16000)

        while self.is_running:
            if self.is_paused:
                time.sleep(0.05)
                continue
                
            triggered = False
            triggered_trailing = ""
            try:
                hw_rate, block_size, needs_downsample = self._get_input_stream_config()

                def _stream_callback(indata, frames, time_info, status):
                    if status:
                        pass
                    try:
                        import numpy as np
                        raw_pcm = np.frombuffer(indata, dtype=np.int16)
                        if needs_downsample:
                            target_len = int(round(len(raw_pcm) * 16000 / hw_rate))
                            indices = np.linspace(0, len(raw_pcm) - 1, target_len)
                            raw_pcm = np.interp(indices, np.arange(len(raw_pcm)), raw_pcm).astype(np.int16)
                        
                        # Apply gentle digital boost (1.6x) so distant/quiet microphones trigger easily
                        boosted = np.clip(raw_pcm.astype(np.float32) * 1.6, -32768, 32767).astype(np.int16)
                        self.q.put(boosted.tobytes())
                    except Exception:
                        self.q.put(bytes(indata))

                mode_label = "16000Hz native" if not needs_downsample else f"{hw_rate}Hz -> 16000Hz (downsampled)"
                with sd.RawInputStream(samplerate=hw_rate, blocksize=block_size, dtype='int16',
                                       channels=1, callback=_stream_callback):
                    print(f"[WakeWord] Engine started and listening ({mode_label})...")
                    recognizer.Reset()
                    while self.is_running and not self.is_paused:
                        try:
                            data = self.q.get(timeout=1)
                        except queue.Empty:
                            continue

                        # Guard against assistant self-triggering while audio is playing
                        try:
                            import voice
                            if voice.is_speech_active():
                                recognizer.Reset()
                                continue
                        except Exception:
                            pass
                        
                        if recognizer.AcceptWaveform(data):
                            result = json.loads(recognizer.Result())
                            text = result.get("text", "").lower().strip()
                            if text:
                                print(f"[WakeWord Heard (Final)]: '{text}'")
                        else:
                            result = json.loads(recognizer.PartialResult())
                            text = result.get("partial", "").lower().strip()
                            
                        if text:
                            is_trig, trailing = self.extract_trigger_and_trailing(text)
                            if is_trig:
                                print(f"[WakeWord] Trigger word detected! Trailing command: '{trailing}'")
                                recognizer.Reset()
                                self.is_paused = True
                                triggered = True
                                triggered_trailing = trailing
                                break
            except Exception as stream_err:
                print(f"[WakeWord] Microphone stream notice: {stream_err}. Retrying in 2s...")
                time.sleep(2.0)
                
            # Safely invoke callback ONLY after the microphone stream is fully closed
            if triggered:
                print(f"[WakeWord] Trigger active! Launching assistant (trailing: '{triggered_trailing}')...")
                try:
                    self.callback(triggered_trailing)
                except TypeError:
                    self.callback()
                
        print("[WakeWord] Engine stopped.")

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
            
wake_engine = None

def start_wake_word(callback):
    global wake_engine
    if not wake_engine:
        wake_engine = WakeWordEngine(callback)
    wake_engine.start()

def stop_wake_word():
    global wake_engine
    if wake_engine:
        wake_engine.stop()

def pause_wake_word():
    global wake_engine
    if wake_engine:
        wake_engine.pause()

def resume_wake_word():
    global wake_engine
    if wake_engine:
        wake_engine.resume()
