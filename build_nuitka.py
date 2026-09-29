import os
import shutil
import subprocess
import sys
import platform

def main():
    print("Starting Nuitka build process for Tilux ASM...")

    # PRE-BUILD PRIVACY SCRUB: Clear static/uploads so user files aren't bundled
    uploads_dir = os.path.join("static", "uploads")
    if os.path.exists(uploads_dir):
        print("Scrubbing /static/uploads directory to prevent bundling private user files...")
        shutil.rmtree(uploads_dir)
        os.makedirs(uploads_dir, exist_ok=True)

    # Define Nuitka build command
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        # Include hidden packages and socket backends
        "--include-package=engineio.async_drivers.threading",
        "--include-package=flask_socketio",
        "--include-package=playwright",
        "--include-package=edge_tts",
        # Bundle UI assets
        "--include-data-dir=frontend=frontend",
        "--include-data-dir=static=static",
        "--include-data-dir=templates=templates",
        "server.py"
    ]

    print(f"Executing: {' '.join(nuitka_cmd)}")
    result = subprocess.run(nuitka_cmd)
    
    if result.returncode != 0:
        print("Nuitka build failed! Aborting.")
        sys.exit(result.returncode)

    print("Nuitka build completed. server.dist folder created.")
    
    # Locate Playwright Chromium binaries cache
    # On Linux it's usually ~/.cache/ms-playwright
    # On Windows it's %USERPROFILE%\AppData\Local\ms-playwright
    # On macOS it's ~/Library/Caches/ms-playwright
    
    home_dir = os.path.expanduser("~")
    system = platform.system()
    if system == "Linux":
        playwright_cache = os.path.join(home_dir, ".cache", "ms-playwright")
    elif system == "Windows":
        playwright_cache = os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(home_dir, "AppData", "Local")), "ms-playwright")
    elif system == "Darwin":
        playwright_cache = os.path.join(home_dir, "Library", "Caches", "ms-playwright")
    else:
        print("Unsupported OS for automated Playwright copy.")
        sys.exit(1)

    dist_dir = "server.dist"
    target_playwright_dir = os.path.join(dist_dir, "playwright_browsers")

    if os.path.exists(playwright_cache):
        print(f"Found Playwright browsers at {playwright_cache}. Copying to {target_playwright_dir}...")
        if os.path.exists(target_playwright_dir):
            shutil.rmtree(target_playwright_dir)
            
        shutil.copytree(playwright_cache, target_playwright_dir, dirs_exist_ok=True)
        print("Playwright browsers successfully bundled!")
    else:
        print(f"WARNING: Playwright cache not found at {playwright_cache}. You may need to install them manually via 'playwright install'.")

    print("Build step finished successfully! Remember to configure os.environ['PLAYWRIGHT_BROWSERS_PATH'] in server.py to point to 'playwright_browsers'.")

if __name__ == "__main__":
    main()
