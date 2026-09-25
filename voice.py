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
        tts_voice = settings.get("tts_voice", "en-US-AriaNeural")
        tts_speed = settings.get("tts_speed", "+20%")
        
        p1 = subprocess.Popen(
            [edge_tts_bin, "--voice", tts_voice, "--rate", tts_speed, "--text", clean_text, "--write-media", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        p2 = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "-"],
            stdin=p1.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        p2.wait()
    except Exception:
        pass

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
