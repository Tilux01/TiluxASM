import os
import sys
import platform
import subprocess
import socket
import urllib.request
import json

def check_mark(status):
    return "✅ [PASS]" if status else "❌ [FAIL]"

def warn_mark(status):
    return "✅ [PASS]" if status else "⚠️  [WARN]"

def main():
    print("=" * 65)
    print("       TILUX ASM - WINDOWS ENVIRONMENT DIAGNOSTIC TOOL       ")
    print("=" * 65)
    
    issues = []
    warnings = []

    # 1. OS & Architecture Check
    os_name = platform.system()
    os_release = platform.release()
    os_arch = platform.machine()
    is_64bit_os = sys.maxsize > 2**32
    print(f"\n1. OPERATING SYSTEM:")
    print(f"   OS: {os_name} {os_release} ({os_arch})")
    print(f"   64-bit Python Process: {'Yes (64-bit)' if is_64bit_os else 'No (32-bit - WARNING)'}")
    
    if not is_64bit_os:
        issues.append("CRITICAL: You are running 32-bit Python! AI packages (faster-whisper, piper-tts) require 64-bit Python. Please uninstall 32-bit Python and install 64-bit Python 3.11 or 3.12.")

    # 2. Python Version Check
    py_ver = sys.version_info
    print(f"\n2. PYTHON ENVIRONMENT:")
    print(f"   Executable: {sys.executable}")
    print(f"   Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    
    ver_ok = py_ver >= (3, 11)
    print(f"   Python >= 3.11: {check_mark(ver_ok)}")
    if not ver_ok:
        issues.append(f"Python 3.11+ is strictly required. Current version: {py_ver.major}.{py_ver.minor}.")

    # 3. Microsoft Visual C++ Runtime Check (Windows only)
    if os_name == "Windows":
        sys_dir = os.environ.get("WINDIR", r"C:\Windows") + r"\System32"
        vc_runtime_exists = os.path.exists(os.path.join(sys_dir, "vcruntime140.dll"))
        print(f"\n3. C++ RUNTIME:")
        print(f"   vcruntime140.dll present: {warn_mark(vc_runtime_exists)}")
        if not vc_runtime_exists:
            warnings.append("Microsoft Visual C++ 2015-2022 Redistributable may be missing. If AI speech fails, install it from: https://aka.ms/vs/17/release/vc_redist.x64.exe")

    # 4. External CLI Tools
    print(f"\n4. EXTERNAL SYSTEM TOOLS:")
    def tool_exists(cmd):
        return subprocess.run(f"where {cmd} 2>NUL" if os_name == "Windows" else f"command -v {cmd}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    ffmpeg_ok = tool_exists("ffmpeg")
    ffplay_ok = tool_exists("ffplay")
    tesseract_ok = tool_exists("tesseract")
    winget_ok = tool_exists("winget")
    cloudflared_ok = tool_exists("cloudflared")

    print(f"   FFmpeg / ffplay:    {warn_mark(ffmpeg_ok and ffplay_ok)} (Audio playback & conversion)")
    print(f"   Tesseract OCR:      {warn_mark(tesseract_ok)} (Screen text recognition)")
    print(f"   Windows Winget:     {warn_mark(winget_ok)} (Windows package manager)")
    print(f"   Cloudflared:        {warn_mark(cloudflared_ok)} (Mobile remote tunnel)")

    if not (ffmpeg_ok and ffplay_ok):
        warnings.append("FFmpeg/ffplay not found in PATH. Install via: winget install Gyan.FFmpeg (or download manually and add to PATH).")
    if not tesseract_ok:
        warnings.append("Tesseract OCR not found. Install via: winget install UB-Mannheim.TesseractOCR")

    # 5. Core Python Dependencies
    print(f"\n5. PYTHON MODULE CHECK:")
    core_modules = [
        ("Flask", "flask"),
        ("Flask-CORS", "flask_cors"),
        ("Flask-SocketIO", "flask_socketio"),
        ("OpenAI SDK", "openai"),
        ("Faster-Whisper", "faster_whisper"),
        ("Edge-TTS", "edge_tts"),
        ("MSS (Screenshots)", "mss"),
        ("PyAutoGUI", "pyautogui"),
        ("Pyperclip", "pyperclip"),
        ("Playwright", "playwright"),
        ("NumPy", "numpy"),
        ("SoundDevice (Audio)", "sounddevice"),
        ("Vosk (Wake Word)", "vosk"),
        ("Pillow (Images)", "PIL"),
        ("PyWin32", "win32gui") if os_name == "Windows" else ("Psutil", "psutil")
    ]

    missing_modules = []
    for display_name, mod_name in core_modules:
        try:
            __import__(mod_name)
            print(f"   {display_name:<22}: ✅ [INSTALLED]")
        except ImportError:
            print(f"   {display_name:<22}: ❌ [MISSING]")
            missing_modules.append(display_name)
        except Exception as e:
            print(f"   {display_name:<22}: ⚠️  [ERROR: {e}]")
            missing_modules.append(display_name)

    if missing_modules:
        issues.append(f"Missing Python dependencies: {', '.join(missing_modules)}. Run: pip install -r requirements.txt")

    # 6. Offline AI Models
    print(f"\n6. OFFLINE MODELS:")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vosk_path = os.path.join(base_dir, "vosk-model")
    piper_path = os.path.join(base_dir, "piper-model")
    
    vosk_ok = os.path.exists(vosk_path) and len(os.listdir(vosk_path)) > 0
    piper_ok = os.path.exists(piper_path) and any(f.endswith(".onnx") for f in os.listdir(piper_path))

    print(f"   Vosk Wake Word Model: {warn_mark(vosk_ok)} ({vosk_path})")
    print(f"   Piper Offline Voice:  {warn_mark(piper_ok)} ({piper_path})")
    
    if not vosk_ok:
        warnings.append("Vosk offline model is not downloaded yet. Run python install.py to cache it.")
    if not piper_ok:
        warnings.append("Piper offline voice model is not cached. Tilux will fallback to Edge TTS or OS speech.")

    # 7. Port 8932 Check
    print(f"\n7. PORT & BACKEND STATUS:")
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    port_open = is_port_in_use(8932)
    print(f"   Port 8932 Active:   {'Yes (Server Running)' if port_open else 'No (Server Idle/Off)'}")
    if port_open:
        try:
            req = urllib.request.urlopen("http://127.0.0.1:8932/api/host_info", timeout=2)
            data = json.loads(req.read().decode())
            print(f"   API Response:       ✅ HTTP 200 OK (Host: {data.get('pc_name', 'Unknown')})")
        except Exception as e:
            print(f"   API Response:       ⚠️ Error querying /api/host_info: {e}")

    # Summary
    print("\n" + "=" * 65)
    print("DIAGNOSTIC SUMMARY:")
    if not issues and not warnings:
        print("🎉 ALL CHECKS PASSED! Your Windows environment is 100% ready for Tilux ASM.")
    else:
        if issues:
            print(f"\n❌ {len(issues)} ACTION REQUIRED ITEMS:")
            for i, issue in enumerate(issues, 1):
                print(f"   {i}. {issue}")
        if warnings:
            print(f"\n⚠️  {len(warnings)} NOTICES / RECOMMENDED OPTIMIZATIONS:")
            for i, warn in enumerate(warnings, 1):
                print(f"   {i}. {warn}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
