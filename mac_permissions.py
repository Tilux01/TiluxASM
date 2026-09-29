import platform
import subprocess

def request_mac_permissions():
    """
    Automatically triggers the macOS permission popups (Accessibility, Screen Recording, Microphone)
    so the user is prompted to grant them immediately at startup, rather than failing silently later.
    """
    if platform.system() != "Darwin":
        return
        
    print("[Mac Permissions] Checking required macOS permissions...", flush=True)
    
    # 1. Trigger Accessibility & Automation popups by sending a dummy osascript event to System Events
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get name of current user'], 
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
        )
    except Exception:
        pass
        
    # 2. Trigger Screen Recording popup using mss to grab a tiny 1x1 pixel
    try:
        import mss
        with mss.mss() as sct:
            sct.grab({'top': 0, 'left': 0, 'width': 1, 'height': 1})
    except Exception:
        pass
        
    # 3. Trigger Microphone popup using SpeechRecognition
    try:
        import speech_recognition as sr
        with sr.Microphone() as source:
            pass
    except Exception:
        pass

    print("[Mac Permissions] Prompts triggered. If no popups appeared, permissions are already granted.", flush=True)
