import os
import sys
import platform
import subprocess

def run_command(command, use_shell=True):
    print(f"Running: {command}")
    try:
        subprocess.run(command, shell=use_shell, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        sys.exit(1)

def install_system_dependencies():
    os_name = platform.system()
    if os_name == "Linux":
        print("Linux detected. Installing system dependencies for PyAutoGUI, Playwright, and Audio...")
        # Check if apt is available (Debian/Ubuntu)
        if subprocess.run("command -v apt-get", shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            print("Please provide your sudo password to install OS-level packages if prompted.")
            run_command("sudo apt-get update")
            run_command("sudo apt-get install -y python3-xlib scrot xdotool portaudio19-dev ffmpeg cmake tesseract-ocr wmctrl")
        else:
            print("Notice: 'apt-get' not found. Please install xdotool, scrot, python3-xlib, and wmctrl using your package manager manually.")
    elif os_name == "Darwin":
        print("macOS detected. System dependencies are usually handled by pip/brew.")
        if subprocess.run("command -v brew", shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            print("Installing ffmpeg, portaudio, and tesseract via Homebrew...")
            run_command("brew install ffmpeg portaudio cmake tesseract")
    elif os_name == "Windows":
        print("Windows detected. Attempting to install FFmpeg and Tesseract via winget...")
        if subprocess.run("winget --version", shell=True, stdout=subprocess.DEVNULL).returncode == 0:
            print("Installing FFmpeg...")
            run_command("winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements")
            print("Installing Tesseract OCR...")
            run_command("winget install -e --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements")
        else:
            print("WARNING: 'winget' not found. You MUST manually install Tesseract OCR and FFmpeg and add them to your PATH.")

def install_python_dependencies():
    print("\nInstalling Python dependencies...")
    # Determine correct pip path (assume venv is used)
    pip_cmd = "./venv/bin/pip" if platform.system() != "Windows" else ".\\venv\\Scripts\\pip"
    
    # Fallback to global pip if venv doesn't exist
    if not os.path.exists(pip_cmd.replace("./", "").replace(".\\", "")):
        pip_cmd = sys.executable + " -m pip"

    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if os.path.exists(req_file):
        run_command(f"{pip_cmd} install -r \"{req_file}\"")
    else:
        print("requirements.txt not found! Skipping dependency install.")
    # Playwright browser download skipped - App uses Host Browser via CDP

def install_cloudflared():
    print("\nEnsuring Secure Tunnel dependency is available...")
    if subprocess.run("command -v cloudflared || npx --yes cloudflared --version", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        print("✅ Secure Tunnel is installed and ready!")
        return

    os_name = platform.system()
    try:
        if os_name == "Linux":
            print("Installing cloudflared via npm...")
            subprocess.run("npm install -g cloudflared || true", shell=True)
        elif os_name == "Darwin":
            print("Installing cloudflared via brew...")
            subprocess.run("brew install cloudflared || npm install -g cloudflared || true", shell=True)
        elif os_name == "Windows":
            print("Installing cloudflared via winget...")
            subprocess.run("winget install --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements || npm install -g cloudflared || true", shell=True)
    except Exception as e:
        print(f"Notice: tunnel auto-install notice: {e}. Tilux will run npx cloudflared dynamically.")

def download_offline_engines():
    print("\nDownloading required offline AI models (this may take a few minutes)...")
    print("Total required data: ~200MB. Cost: $0 (Free).")
    import urllib.request
    import zipfile
    import sys
    
    last_reported_percent = -10
    
    def progress_hook(filename):
        def hook(count, block_size, total_size):
            nonlocal last_reported_percent
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                # Only print every 5% to avoid flooding the UI with Server-Sent Events
                if percent - last_reported_percent >= 5 or percent == 100:
                    downloaded_mb = count * block_size / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    print(f"Downloading {filename}: {percent}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)", flush=True)
                    last_reported_percent = percent
        return hook

    # 1. Download Vosk Wake Word Model (40MB)
    if not os.path.exists("vosk-model"):
        print("Starting Vosk wake word model download...")
        last_reported_percent = -10
        vosk_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        urllib.request.urlretrieve(vosk_url, "vosk.zip", reporthook=progress_hook("Vosk Engine"))
        with zipfile.ZipFile("vosk.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
        os.rename("vosk-model-small-en-us-0.15", "vosk-model")
        os.remove("vosk.zip")
        print("✅ Vosk downloaded.")
        
    # 2. Download Piper TTS Model (20MB)
    if not os.path.exists("piper-model"):
        os.makedirs("piper-model")
    if not os.path.exists("piper-model/en_US-lessac-medium.onnx"):
        print("Starting Piper offline TTS model download...")
        last_reported_percent = -10
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
        urllib.request.urlretrieve(base_url, "piper-model/en_US-lessac-medium.onnx", reporthook=progress_hook("Piper TTS Data"))
        urllib.request.urlretrieve(base_url + ".json", "piper-model/en_US-lessac-medium.onnx.json")
        print("✅ Piper TTS downloaded.")

    # 3. Cache Whisper AI Model (140MB)
    try:
        python_cmd = "./venv/bin/python" if platform.system() != "Windows" else ".\\venv\\Scripts\\python"
        if not os.path.exists(python_cmd.replace("./", "").replace(".\\", "")):
            python_cmd = sys.executable
        print("Caching Faster-Whisper AI into memory...")
        script = "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"
        run_command(f"{python_cmd} -c \"{script}\"")
        print("✅ Whisper downloaded.")
    except Exception as e:
        print(f"Notice: Whisper download deferred until first run. Error: {e}")
    
    print("\n✅ All Offline AI engines are fully installed and cached!")

if __name__ == "__main__":
    print("=== TILUX UNIVERSAL INSTALLER ===")
    if sys.version_info < (3, 11):
        print("\n[ERROR] Python 3.11 or higher is strictly required!")
        print(f"You are running Python {sys.version_info.major}.{sys.version_info.minor}.")
        print("Please upgrade your Python version to install Tilux dependencies (browser-use requires Python >= 3.11).")
        sys.exit(1)
        
    install_system_dependencies()
    install_python_dependencies()
    install_cloudflared()
    download_offline_engines()
    try:
        from autostart import enable_autostart
        enable_autostart()
        print("✅ System boot autostart enabled!")
    except Exception as e:
        print(f"Notice: Autostart setup error: {e}")
        
    # Write setup complete flag
    setup_flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".setup_complete")
    with open(setup_flag, "w") as f:
        f.write("done")
        
    print("\n✅ Tilux Agent successfully installed for this OS!")
