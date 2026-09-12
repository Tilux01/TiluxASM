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

    packages = [
        "pyautogui", 
        "pillow", 
        "playwright", 
        "requests", 
        "beautifulsoup4",
        "browser-use",
        "open-interpreter",
        "pytesseract",
        "pyperclip",
        "flask",
        "flask-cors",
        "psutil",
        "SpeechRecognition",
        "PyAudio",
        "edge-tts",
        "langchain_openai",
        "langchain_community"
    ]
    
    run_command(f"{pip_cmd} install " + " ".join(packages))
    
    print("\nInstalling Playwright browsers...")
    playwright_cmd = "./venv/bin/playwright" if platform.system() != "Windows" else ".\\venv\\Scripts\\playwright"
    if not os.path.exists(playwright_cmd.replace("./", "").replace(".\\", "")):
        playwright_cmd = "playwright"
        
    if platform.system() == "Linux":
        print("Installing Playwright system dependencies...")
        run_command(f"sudo {playwright_cmd} install-deps")
        
    run_command(f"{playwright_cmd} install")

if __name__ == "__main__":
    print("=== TILUX UNIVERSAL INSTALLER ===")
    install_system_dependencies()
    install_python_dependencies()
    print("\n✅ Tilux Agent successfully installed for this OS!")
