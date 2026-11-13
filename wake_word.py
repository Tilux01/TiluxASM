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
    r'hello\s+tilux|hey\s+tilux|hi\s+tilux|ok\s+tilux|okay\s+tilux|yo\s+tilux|wake\s+up\s+tilux|'
    r'hello\s+assistant|hey\s+assistant|hi\s+assistant|ok\s+assistant|okay\s+assistant|'
    r'tilux|tlox|t-lux|t lux|tielux|tealux|deluxe|'
    r'(hey|hi|hello|ok|okay)\s+(deluxe|looks|locks|lux|lox|alex)|'
    r'(tea|tee|tie)\s+(looks|locks|lux|lox)'
    r')\b',
    re.IGNORECASE
)

class WakeWordEngine:
    def _locate_or_download_model(self) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data = os.environ.get("TILUX_USER_DATA_DIR")
        
        candidates = [
            "vosk-model",
            os.path.join(base_dir, "vosk-model"),
        ]
        if user_data:
            candidates.insert(0, os.path.join(user_data, "vosk-model"))
            
        for cand in candidates:
            if os.path.exists(cand) and os.path.isdir(cand) and os.path.exists(os.path.join(cand, "am")):
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
            "hello tilux", "hey tilux", "hi tilux", "ok tilux", "okay tilux", "yo tilux", "wake up tilux",
            "hello assistant", "hey assistant", "hi assistant", "ok assistant", "okay assistant",
            "tilux", "tlox", "t lox", "t-lux", "t lux", "tielux", "tie lux", "tealux", "tee lux", "tea lux",
            "deluxe", "de luxe", "d lux",
            "hey deluxe", "hi deluxe", "hello deluxe",
            "hey looks", "hey locks", "hey lux", "hi looks", "hi lux", "hello looks",
            "tea looks", "tee looks", "tie looks", "tea locks", "tee locks", "tie locks"
        ]

    def check_trigger(self, text: str) -> bool:
        is_trig, _ = self.extract_trigger_and_trailing(text)
        return is_trig

    def extract_trigger_and_trailing(self, text: str):
        if not text:
            return False, ""
        try:
            from voice import is_tts_speaking
            if is_tts_speaking():
                return False, ""
        except Exception:
            pass

        clean = text.lower().strip()
        m = WAKE_REGEX.search(clean)
        if m:
            trailing = clean[m.end():].strip(" ,.:;-")
            return True, trailing
        for kw in self.active_keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            m2 = re.search(pattern, clean)
            if m2:
                trailing = clean[m2.end():].strip(" ,.:;-")
                return True, trailing
        return False, ""

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        self.q.put(bytes(indata))

    def pause(self):
        self.is_paused = True
        
    def resume(self):
        # Clear any stale audio
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        try:
            from voice import is_tts_speaking
            if is_tts_speaking():
                return
        except Exception:
            pass
        self.is_paused = False

    def _listen_loop(self):
        if not os.path.exists(self.model_path) or Model is None:
            print("[WakeWord] Vosk model not found or dependencies missing.")
            return

        print("[WakeWord] Loading offline Vosk model...")
        model = Model(self.model_path)
        recognizer = KaldiRecognizer(model, 16000)

        while self.is_running:
            if self.is_paused:
                time.sleep(0.05)
                continue
                
            triggered = False
            triggered_trailing = ""
            try:
                # 2000 samples @ 16kHz = 125ms chunks for low-latency streaming recognition
                with sd.RawInputStream(samplerate=16000, blocksize=2000, dtype='int16',
                                       channels=1, callback=self._audio_callback):
                    print("[WakeWord] Engine started and listening...")
                    recognizer.Reset()
                    while self.is_running and not self.is_paused:
                        try:
                            data = self.q.get(timeout=1)
                        except queue.Empty:
                            continue

                        try:
                            from voice import is_tts_speaking
                            if is_tts_speaking():
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
