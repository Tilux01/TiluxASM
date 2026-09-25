import os
import sys
import platform

def enable_autostart(app_dir=None):
    if app_dir is None:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    system_type = platform.system().lower()

    if "linux" in system_type:
        python_exe = os.path.join(app_dir, "venv", "bin", "python")
        server_script = os.path.join(app_dir, "server.py")
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_file = os.path.join(autostart_dir, "tilux-backend.desktop")
        
        content = f"""[Desktop Entry]
Type=Application
Name=Tilux ASM Backend
Comment=Tilux AI Assistant SocketIO & Remote Gateway
Exec="{python_exe}" "{server_script}"
StartupNotify=false
Terminal=false
X-GNOME-Autostart-enabled=true
"""
        with open(desktop_file, "w") as f:
            f.write(content)
        os.chmod(desktop_file, 0o755)
        print(f"Linux autostart enabled: {desktop_file}")
        return desktop_file

    elif "windows" in system_type:
        appdata = os.getenv("APPDATA")
        if appdata:
            startup_folder = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
            vbs_file = os.path.join(startup_folder, "tilux-backend.vbs")
            win_python = os.path.join(app_dir, "venv", "Scripts", "pythonw.exe")
            server_script = os.path.join(app_dir, "server.py")
            content = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run "\"{win_python}\" \"{server_script}\"", 0, False'
            with open(vbs_file, "w") as f:
                f.write(content)
            print(f"Windows autostart enabled: {vbs_file}")
            return vbs_file

    elif "darwin" in system_type:
        python_exe = os.path.join(app_dir, "venv", "bin", "python")
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
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        with open(plist_file, "w") as f:
            f.write(content)
        print(f"macOS autostart enabled: {plist_file}")
        return plist_file

if __name__ == "__main__":
    enable_autostart()
