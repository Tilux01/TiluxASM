import os
import sys
import platform
import subprocess

def run_command(command, use_shell=True, fatal=True):
    print(f"Running: {command}", flush=True)
    try:
        res = subprocess.run(command, shell=use_shell, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}", flush=True)
        if fatal:
            sys.exit(1)
        return False
    except Exception as e:
        print(f"Execution error: {e}", flush=True)
        if fatal:
            sys.exit(1)
        return False

def install_system_dependencies():
    os_name = platform.system()
    if os_name == "Linux":
        print("Linux detected. Installing system dependencies for PyAutoGUI, Playwright, and Audio...", flush=True)
        if subprocess.run("command -v apt-get", shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            print("Please provide your sudo password to install OS-level packages if prompted.", flush=True)
            run_command("sudo apt-get update", fatal=False)
            run_command("sudo apt-get install -y python3-xlib scrot xdotool portaudio19-dev ffmpeg cmake tesseract-ocr wmctrl", fatal=False)
        else:
            print("Notice: 'apt-get' not found. Please install xdotool, scrot, python3-xlib, and wmctrl using your package manager manually.", flush=True)
    elif os_name == "Darwin":
        print("macOS detected. Checking Homebrew dependencies...", flush=True)
        if subprocess.run("command -v brew", shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            print("Installing ffmpeg, portaudio, and tesseract via Homebrew...", flush=True)
            run_command("brew install ffmpeg portaudio cmake tesseract", fatal=False)
        else:
            print("\n[Notice] Homebrew ('brew') is not installed. Tilux will use native macOS speech and fallbacks.", flush=True)
    elif os_name == "Windows":
        print("Windows detected. Checking system dependencies (FFmpeg, Tesseract)...", flush=True)
        ffmpeg_found = subprocess.run("ffmpeg -version", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        tesseract_found = subprocess.run("tesseract --version", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        
        if ffmpeg_found:
            print("✅ FFmpeg is already installed and in PATH.", flush=True)
        if tesseract_found:
            print("✅ Tesseract OCR is already installed and in PATH.", flush=True)

        if not ffmpeg_found or not tesseract_found:
            has_winget = subprocess.run("winget --version", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            if has_winget:
                if not ffmpeg_found:
                    print("Attempting to install FFmpeg via winget...", flush=True)
                    run_command("winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements", fatal=False)
                if not tesseract_found:
                    print("Attempting to install Tesseract OCR via winget...", flush=True)
                    run_command("winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements", fatal=False)
            else:
                print("Notice: 'winget' not found. Tilux will use software fallbacks (Windows SAPI & Pillow) if FFmpeg/OCR are absent.", flush=True)

def install_python_dependencies():
    print("\nInstalling Python dependencies...", flush=True)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    is_win = platform.system() == "Windows"
    
    venv_pip = os.path.join(app_dir, "venv", "Scripts", "pip.exe") if is_win else os.path.join(app_dir, "venv", "bin", "pip")
    
    if os.path.exists(venv_pip):
        pip_cmd = f'"{venv_pip}"'
    else:
        pip_cmd = f'"{sys.executable}" -m pip'

    req_file = os.path.join(app_dir, "requirements.txt")
    if os.path.exists(req_file):
        # Upgrade pip first to ensure wheel resolution works properly
        run_command(f"{pip_cmd} install --upgrade pip", fatal=False)
        
        print(f"Installing dependencies from {req_file}...", flush=True)
        batch_success = run_command(f"{pip_cmd} install -r \"{req_file}\"", fatal=False)
        
        if not batch_success:
            print("\nNotice: Batch installation hit a conflict. Running resilient package-by-package installation...", flush=True)
            with open(req_file, "r") as rf:
                lines = [l.strip() for l in rf if l.strip() and not l.strip().startswith("#")]
            for pkg in lines:
                print(f"Installing {pkg}...", flush=True)
                run_command(f"{pip_cmd} install {pkg}", fatal=False)
        print("✅ Python packages installed.")
    else:
        print("requirements.txt not found! Skipping dependency install.", flush=True)

def install_cloudflared():
    print("\nEnsuring Secure Tunnel dependency is available...", flush=True)
    if subprocess.run("command -v cloudflared || npx --yes cloudflared --version", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        print("✅ Secure Tunnel is installed and ready!", flush=True)
        return

    os_name = platform.system()
    try:
        if os_name == "Linux":
            subprocess.run("npm install -g cloudflared || true", shell=True)
        elif os_name == "Darwin":
            subprocess.run("brew install cloudflared || npm install -g cloudflared || true", shell=True)
        elif os_name == "Windows":
            subprocess.run("winget install --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements || npm install -g cloudflared || true", shell=True)
    except Exception as e:
        print(f"Notice: Tunnel auto-install notice: {e}. Tilux will run cloudflared dynamically when needed.", flush=True)

def download_offline_engines():
    print("\nDownloading required offline AI models (this may take a few minutes)...", flush=True)
    print("Total required data: ~200MB. Cost: $0 (Free).", flush=True)
    import urllib.request
    import zipfile
    
    last_reported_percent = -10
    
    def progress_hook(filename):
        def hook(count, block_size, total_size):
            nonlocal last_reported_percent
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                if percent - last_reported_percent >= 5 or percent == 100:
                    downloaded_mb = count * block_size / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    print(f"Downloading {filename}: {percent}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)", flush=True)
                    last_reported_percent = percent
        return hook

    # 1. Download Vosk Wake Word Model (40MB)
    if not os.path.exists("vosk-model"):
        print("Starting Vosk wake word model download...", flush=True)
        last_reported_percent = -10
        vosk_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        try:
            urllib.request.urlretrieve(vosk_url, "vosk.zip", reporthook=progress_hook("Vosk Engine"))
            with zipfile.ZipFile("vosk.zip", 'r') as zip_ref:
                zip_ref.extractall(".")
            if os.path.exists("vosk-model-small-en-us-0.15"):
                os.rename("vosk-model-small-en-us-0.15", "vosk-model")
            if os.path.exists("vosk.zip"):
                os.remove("vosk.zip")
            print("✅ Vosk downloaded.", flush=True)
        except Exception as e:
            print(f"Notice: Vosk download deferred: {e}. Wake word can be downloaded later.", flush=True)
            if os.path.exists("vosk.zip"):
                try: os.remove("vosk.zip")
                except: pass
        
    # 2. Download Piper TTS Model (20MB)
    if not os.path.exists("piper-model"):
        os.makedirs("piper-model", exist_ok=True)
    if not os.path.exists("piper-model/en_US-lessac-medium.onnx"):
        print("Starting Piper offline TTS model download...", flush=True)
        last_reported_percent = -10
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        try:
            urllib.request.urlretrieve(base_url, "piper-model/en_US-lessac-medium.onnx", reporthook=progress_hook("Piper TTS Data"))
            urllib.request.urlretrieve(base_url + ".json", "piper-model/en_US-lessac-medium.onnx.json")
            print("✅ Piper TTS downloaded.", flush=True)
        except Exception as e:
            print(f"Notice: Piper TTS download deferred: {e}. Edge TTS and OS speech will be used as fallback.", flush=True)

    # 3. Cache Whisper AI Model (140MB)
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        is_win = platform.system() == "Windows"
        venv_py = os.path.join(app_dir, "venv", "Scripts", "python.exe") if is_win else os.path.join(app_dir, "venv", "bin", "python")
        python_cmd = f'"{venv_py}"' if os.path.exists(venv_py) else f'"{sys.executable}"'
        print("Caching Faster-Whisper AI into memory...", flush=True)
        script = "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"
        run_command(f"{python_cmd} -c \"{script}\"", fatal=False)
        print("✅ Whisper downloaded.", flush=True)
    except Exception as e:
        print(f"Notice: Whisper download deferred until first run. Error: {e}", flush=True)
    
    print("\n✅ Offline AI engines setup completed!", flush=True)

if __name__ == "__main__":
    print("=== TILUX UNIVERSAL INSTALLER ===", flush=True)
    if sys.version_info < (3, 11):
        print("\n[ERROR] Python 3.11 or higher is strictly required!", flush=True)
        print(f"You are running Python {sys.version_info.major}.{sys.version_info.minor}.", flush=True)
        print("Please upgrade your Python version to install Tilux dependencies (browser-use requires Python >= 3.11).", flush=True)
        sys.exit(1)
        
    install_system_dependencies()
    install_python_dependencies()
    install_cloudflared()
    download_offline_engines()
    try:
        from autostart import enable_autostart
        enable_autostart()
        print("✅ System boot autostart checked!", flush=True)
    except Exception as e:
        print(f"Notice: Autostart setup notice: {e}", flush=True)
        
    # Write setup complete flag
    setup_flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_complete")
    try:
        with open(setup_flag, "w") as f:
            f.write("done")
    except Exception:
        pass
        
    print("\n✅ Tilux Agent successfully installed for this OS!", flush=True)
