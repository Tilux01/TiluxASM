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

class WakeWordEngine:
    def __init__(self, callback):
        self.callback = callback
        self.is_running = False
        self.thread = None
        self.q = queue.Queue()
        self.model_path = "vosk-model"
        self.active_keywords = ["tlox", "t lox", "Hello Tlox","tilux", "tielux", "tie lux" "tealux", "tee lux", "tea lux", "t lux", "hello assistant", "assistant", "assistance", "hello assistance"]

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
            if getattr(self, "is_paused", False):
                time.sleep(0.5)
                continue
                
            try:
                with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                                       channels=1, callback=self._audio_callback):
                    print("[WakeWord] Engine started and listening...")
                    while self.is_running and not getattr(self, "is_paused", False):
                        try:
                            data = self.q.get(timeout=1)
                        except queue.Empty:
                            continue
                        
                        if recognizer.AcceptWaveform(data):
                            result = json.loads(recognizer.Result())
                            text = result.get("text", "").lower()
                        else:
                            result = json.loads(recognizer.PartialResult())
                            text = result.get("partial", "").lower()
                            
                        if text:
                            for kw in self.active_keywords:
                                if kw in text:
                                    print(f"[WakeWord] Trigger word detected: {text} (transcript: {text})")
                                    # Reset recognizer to clear the partial state
                                    recognizer.Reset()
                                    self.is_paused = True # Instantly pause to release mic lock
                                    
                                    try:
                                        self.callback()
                                    except Exception as e:
                                        print(f"[WakeWord] Callback error: {e}")
                                    
                                    break
            except Exception as stream_err:
                print(f"[WakeWord] Stream error: {stream_err}")
                time.sleep(1)
                
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
