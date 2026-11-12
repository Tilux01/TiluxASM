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
            "tell looks",
            "they tell looks", "they tell us",
            "tea locks", "tee locks", "tie locks",
            "tea looks", "tee looks", "tie looks",
            "ty looks", "till acts",
            "assistant", "assistance",
            "hey deluxe", "hi deluxe", "hello deluxe",
            "hey looks", "hey locks", "hey lux"
        ]

    def check_trigger(self, text: str) -> bool:
        if not text:
            return False
        clean = text.lower().strip()
        if WAKE_REGEX.search(clean):
            return True
        for kw in self.active_keywords:
            if kw in clean:
                return True
        return False

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
                        
                        if recognizer.AcceptWaveform(data):
                            result = json.loads(recognizer.Result())
                            text = result.get("text", "").lower().strip()
                            if text:
                                print(f"[WakeWord Heard (Final)]: '{text}'")
                        else:
                            result = json.loads(recognizer.PartialResult())
                            text = result.get("partial", "").lower().strip()
                            
                        if text and self.check_trigger(text):
                            print(f"[WakeWord] Trigger word detected in audio: '{text}'")
                            recognizer.Reset()
                            self.is_paused = True
                            triggered = True
                            break
            except Exception as stream_err:
                print(f"[WakeWord] Stream error: {stream_err}")
                time.sleep(0.5)
                
            # Safely invoke callback ONLY after the microphone stream is fully closed
            if triggered:
                print("[WakeWord] Trigger active! Closing wake mic and launching assistant...")
                try:
                    self.callback()
                except Exception as e:
                    print(f"[WakeWord] Callback error: {e}")
                
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
