import os
import sys
import platform

def enable_autostart(app_dir=None):
    if app_dir is None:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    system_type = platform.system().lower()

    if "linux" in system_type:
        # Check bundled runtime first, then venv, then sys.executable
        cand_pythons = [
            os.path.join(app_dir, "runtime", "bin", "python3"),
            os.path.join(app_dir, "runtime", "bin", "python"),
            os.path.join(app_dir, "venv", "bin", "python"),
            os.path.join(app_dir, "venv", "bin", "python3"),
            sys.executable
        ]
        python_exe = sys.executable
        for cand in cand_pythons:
            if os.path.exists(cand):
                python_exe = cand
                break

        server_script = os.path.join(app_dir, "server.py")
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_file = os.path.join(autostart_dir, "tilux-backend.desktop")
        
        content = f"""[Desktop Entry]
Type=Application
Name=Tilux ASM Backend
Comment=Tilux AI Assistant SocketIO & Remote Gateway
Exec="{python_exe}" "{server_script}"
Path={app_dir}
StartupNotify=false
Terminal=false
X-GNOME-Autostart-enabled=true
"""
        try:
            with open(desktop_file, "w") as f:
                f.write(content)
            os.chmod(desktop_file, 0o755)
            print(f"[Autostart] Linux autostart enabled: {desktop_file}")
            return desktop_file
        except Exception as e:
            print(f"[Autostart] Could not write Linux desktop entry: {e}")
            return None

    elif "windows" in system_type:
        appdata = os.getenv("APPDATA")
        if appdata:
            startup_folder = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
            os.makedirs(startup_folder, exist_ok=True)
            vbs_file = os.path.join(startup_folder, "tilux-backend.vbs")

            cand_pythons = [
                os.path.join(app_dir, "runtime", "pythonw.exe"),
                os.path.join(app_dir, "runtime", "python.exe"),
                os.path.join(app_dir, "venv", "Scripts", "pythonw.exe"),
                os.path.join(app_dir, "venv", "Scripts", "python.exe"),
                sys.executable
            ]
            win_python = sys.executable
            for cand in cand_pythons:
                if os.path.exists(cand):
                    win_python = cand
                    break

            server_script = os.path.join(app_dir, "server.py")
            # Set WshShell.CurrentDirectory so Python starts in app_dir and not System32
            content = (
                f'Set WshShell = CreateObject("WScript.Shell")\r\n'
                f'WshShell.CurrentDirectory = "{app_dir}"\r\n'
                f'WshShell.Run """{win_python}"" ""{server_script}""", 0, False\r\n'
            )
            try:
                with open(vbs_file, "w") as f:
                    f.write(content)
                print(f"[Autostart] Windows autostart enabled: {vbs_file}")
                return vbs_file
            except Exception as e:
                print(f"[Autostart] Notice: Could not write autostart VBS: {e}")
                return None

    elif "darwin" in system_type:
        cand_pythons = [
            os.path.join(app_dir, "runtime", "bin", "python3"),
            os.path.join(app_dir, "venv", "bin", "python"),
            sys.executable
        ]
        python_exe = sys.executable
        for cand in cand_pythons:
            if os.path.exists(cand):
                python_exe = cand
                break

        server_script = os.path.join(app_dir, "server.py")
        launch_dir = os.path.expanduser("~/Library/LaunchAgents")
        os.makedirs(launch_dir, exist_ok=True)
        plist_file = os.path.join(launch_dir, "com.tilux.backend.plist")
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tilux.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>{server_script}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{app_dir}</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        try:
            with open(plist_file, "w") as f:
                f.write(content)
            print(f"[Autostart] macOS autostart enabled: {plist_file}")
            return plist_file
        except Exception as e:
            print(f"[Autostart] Could not write macOS launchd plist: {e}")
            return None

def disable_autostart():
    """Removes any registered boot startup scripts/entries for Tilux."""
    system_type = platform.system().lower()
    try:
        if "linux" in system_type:
            desktop_file = os.path.expanduser("~/.config/autostart/tilux-backend.desktop")
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
                print(f"[Autostart] Removed {desktop_file}")
        elif "windows" in system_type:
            appdata = os.getenv("APPDATA")
            if appdata:
                vbs_file = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "tilux-backend.vbs")
                if os.path.exists(vbs_file):
                    os.remove(vbs_file)
                    print(f"[Autostart] Removed {vbs_file}")
        elif "darwin" in system_type:
            plist_file = os.path.expanduser("~/Library/LaunchAgents/com.tilux.backend.plist")
            if os.path.exists(plist_file):
                os.remove(plist_file)
                print(f"[Autostart] Removed {plist_file}")
        return True
    except Exception as e:
        print(f"[Autostart] Error disabling autostart: {e}")
        return False

if __name__ == "__main__":
    enable_autostart()
