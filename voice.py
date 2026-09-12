import speech_recognition as sr
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

def speak(text: str):
    """Converts text to speech and plays it using Edge TTS (Dynamic Voice/Speed)."""
    clean_text = text.replace("*", "").replace("`", "")
    
    # Load TTS Settings
    settings = {"tts_enabled": True, "tts_voice": "en-US-AriaNeural", "tts_speed": "+20%"}
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r") as f:
                saved = json.load(f)
                settings.update(saved)
        except:
            pass
            
    if not settings.get("tts_enabled", True):
        return # Do not speak if disabled
        
    try:
        import platform
        edge_tts_bin = "./venv/bin/edge-tts" if platform.system() != "Windows" else ".\\venv\\Scripts\\edge-tts.exe"
        subprocess.run(
            [edge_tts_bin, "--voice", settings.get("tts_voice", "en-US-AriaNeural"), "--rate", settings.get("tts_speed", "+20%"), "--text", clean_text, "--write-media", "response.mp3"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "response.mp3"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if os.path.exists("response.mp3"):
            os.remove("response.mp3")
    except Exception:
        pass # Silently fail if TTS fails to keep terminal clean

def listen() -> str:
    """Listens to the microphone and returns the transcribed text silently."""
    recognizer = sr.Recognizer()
    try:
        # Wrap the microphone initialization in the ALSA error silencer
        with noalsaerr():
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = recognizer.listen(source, timeout=7, phrase_time_limit=15)
                
        # Still using en-NG to perfectly understand Nigerian accents and Pidgin
        text = recognizer.recognize_google(audio, language="en-NG")
        return text
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        return ""
    except Exception:
        return ""
