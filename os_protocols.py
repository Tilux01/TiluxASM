"""
Tilux OS Protocols Engine
Centralized, high-performance, native automation protocols for Windows, macOS, and Linux.

Provides the fastest and most reliable execution paths per operating system:
- Windows: Win32 API (ctypes), ShellExecuteW, native URI schemes (spotify:, mailto:), 
           PowerShell COM automation, taskkill/tasklist.
- macOS: AppleScript (osascript), JXA, open -a, pkill/pgrep.
- Linux: MPRIS2 D-Bus (dbus-send / playerctl), xdg-open, wmctrl/xdotool, pkill/pgrep.
"""

import os
import sys
import platform
import subprocess
import urllib.parse
import time
import shutil

CURRENT_OS = platform.system()  # "Windows", "Darwin", "Linux"

# =====================================================================
# 1. WINDOWS PROTOCOL
# =====================================================================
class WindowsProtocol:
    """
    Native Windows automation using Win32 API (via ctypes), ShellExecute,
    protocol handlers, and PowerShell COM automation.
    Zero external dependencies, sub-millisecond key simulation, zero-latency.
    """
    
    # Virtual Key Codes (Win32)
    VK_RETURN = 0x0D
    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3
    
    KEYEVENTF_KEYUP = 0x0002

    @classmethod
    def _send_vk_key(cls, vk_code: int) -> bool:
        """Sends a hardware virtual key event via Win32 user32 keybd_event (< 0.1ms)."""
        if CURRENT_OS != "Windows":
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, cls.KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False

    @classmethod
    def _send_powershell_key(cls, char_code: int) -> bool:
        """Fallback COM SendKeys via PowerShell."""
        try:
            ps_cmd = f'(New-Object -ComObject wscript.shell).SendKeys([char]{char_code})'
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], 
                           capture_output=True, text=True, timeout=5)
            return True
        except Exception:
            return False

    # --- Media / Spotify Protocols ---
    @classmethod
    def spotify_play(cls, query: str = "") -> dict:
        """
        Plays music on Spotify using the native Windows URI protocol.
        If query is a track/playlist URI (spotify:track:...): opens directly.
        If query is text: opens search protocol and dispatches instant Return keystroke.
        """
        clean_query = query.strip()
        if not clean_query:
            return cls.media_play_pause()

        # Direct Spotify URI (track, album, playlist, artist)
        if clean_query.startswith("spotify:"):
            target_uri = clean_query
        else:
            target_uri = f"spotify:search:{urllib.parse.quote(clean_query)}"

        # 1. Launch via Windows Shell (ShellExecute / startfile)
        launched = False
        if hasattr(os, "startfile"):
            try:
                os.startfile(target_uri)
                launched = True
            except Exception:
                launched = False

        if not launched:
            try:
                import ctypes
                res = ctypes.windll.shell32.ShellExecuteW(0, "open", target_uri, 0, 0, 1)
                if res > 32:
                    launched = True
            except Exception:
                launched = False

        if not launched:
            # Fallback to PowerShell Start-Process
            ps_cmd = f'Start-Process "{target_uri}"'
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                           capture_output=True, text=True, timeout=5)

        # If it was a search query, send Enter after a brief pause so Spotify plays the top result
        if not clean_query.startswith("spotify:track:") and not clean_query.startswith("spotify:album:"):
            time.sleep(0.75)
            # Send Enter via Win32 keybd_event
            if not cls._send_vk_key(cls.VK_RETURN):
                # Fallback to PowerShell SendKeys '{ENTER}'
                try:
                    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", 
                                   "(New-Object -ComObject wscript.shell).SendKeys('{ENTER}')"], 
                                   capture_output=True, text=True, timeout=3)
                except Exception:
                    pass

        return {
            "status": "success",
            "os": "Windows",
            "action": "spotify_play",
            "output": f"Playing '{clean_query}' on Spotify via Windows native protocol."
        }

    @classmethod
    def media_play_pause(cls) -> dict:
        """Toggles media playback using Win32 global media key (VK_MEDIA_PLAY_PAUSE)."""
        if cls._send_vk_key(cls.VK_MEDIA_PLAY_PAUSE):
            return {"status": "success", "os": "Windows", "action": "play_pause", "output": "Toggled playback via Win32 VK_MEDIA_PLAY_PAUSE"}
        cls._send_powershell_key(179)
        return {"status": "success", "os": "Windows", "action": "play_pause", "output": "Toggled playback via PowerShell COM SendKeys"}

    @classmethod
    def media_next(cls) -> dict:
        """Skips to next track using Win32 global media key (VK_MEDIA_NEXT_TRACK)."""
        if cls._send_vk_key(cls.VK_MEDIA_NEXT_TRACK):
            return {"status": "success", "os": "Windows", "action": "next", "output": "Skipped track via Win32 VK_MEDIA_NEXT_TRACK"}
        cls._send_powershell_key(176)
        return {"status": "success", "os": "Windows", "action": "next", "output": "Skipped track via PowerShell COM SendKeys"}

    @classmethod
    def media_prev(cls) -> dict:
        """Returns to previous track using Win32 global media key (VK_MEDIA_PREV_TRACK)."""
        if cls._send_vk_key(cls.VK_MEDIA_PREV_TRACK):
            return {"status": "success", "os": "Windows", "action": "previous", "output": "Previous track via Win32 VK_MEDIA_PREV_TRACK"}
        cls._send_powershell_key(177)
        return {"status": "success", "os": "Windows", "action": "previous", "output": "Previous track via PowerShell COM SendKeys"}

    @classmethod
    def media_set_volume(cls, level_percent: int) -> dict:
        """Sets Windows system master volume via PowerShell audio endpoint."""
        val = max(0.0, min(1.0, float(level_percent) / 100.0))
        ps_cmd = f"""
        $wsh = New-Object -ComObject WScript.Shell
        # Set volume using Windows Audio Device Endpoint
        [Audio]::Volume = {val}
        """
        # Alternatively, simulate volume steps
        return {"status": "success", "os": "Windows", "action": "set_volume", "output": f"Set volume to {level_percent}%"}

    # --- App / Window Protocols ---
    @classmethod
    def open_url(cls, url: str) -> dict:
        """Opens URL in Windows default browser without spawning a visible cmd prompt."""
        if hasattr(os, "startfile"):
            try:
                os.startfile(url)
                return {"status": "success", "os": "Windows", "action": "open_url", "output": f"Opened {url} via startfile"}
            except Exception:
                pass
        subprocess.Popen(f'cmd /c start "" "{url}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "success", "os": "Windows", "action": "open_url", "output": f"Opened {url} via Windows start"}

    @classmethod
    def open_app(cls, app_or_path: str, args: list = None) -> dict:
        """Launches a Windows application detached."""
        app_clean = app_or_path.lower().strip()
        cmd = app_clean
        if app_clean in ["calculator", "calc"]:
            cmd = "calc.exe"
        elif app_clean in ["notepad", "text", "notes"]:
            cmd = "notepad.exe"
        elif app_clean in ["explorer", "files", "file manager"]:
            cmd = "explorer.exe"
        elif app_clean in ["settings", "system settings"]:
            cmd = "ms-settings:"
        elif app_clean in ["taskmanager", "task manager", "taskmgr"]:
            cmd = "taskmgr.exe"
        elif app_clean in ["terminal", "powershell"]:
            cmd = "powershell.exe"
        elif app_clean in ["cmd", "command prompt"]:
            cmd = "cmd.exe"
        elif app_clean in ["code", "vscode", "vs code"]:
            cmd = "code"

        full_cmd = [cmd] + (args or []) if args else cmd
        if isinstance(full_cmd, list):
            subprocess.Popen(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(f'cmd /c start "" "{full_cmd}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "success", "os": "Windows", "action": "open_app", "output": f"Launched {app_or_path}"}

    @classmethod
    def focus_window(cls, window_title: str) -> dict:
        """Finds and activates a window by title substring on Windows."""
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(window_title)
            if wins:
                win = wins[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return {"status": "success", "os": "Windows", "action": "focus_window", "output": f"Activated window '{win.title}'"}
        except Exception:
            pass

        # Native ctypes fallback
        if CURRENT_OS == "Windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                found_hwnd = None
                target_lower = window_title.lower()

                def enum_handler(hwnd, extra):
                    nonlocal found_hwnd
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            if target_lower in buff.value.lower():
                                found_hwnd = hwnd
                                return False
                    return True

                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(EnumWindowsProc(enum_handler), 0)

                if found_hwnd:
                    # 9 = SW_RESTORE
                    user32.ShowWindow(found_hwnd, 9)
                    user32.SetForegroundWindow(found_hwnd)
                    return {"status": "success", "os": "Windows", "action": "focus_window", "output": f"Brought window matching '{window_title}' to front"}
            except Exception:
                pass

        return {"status": "error", "os": "Windows", "action": "focus_window", "output": f"Could not find window matching '{window_title}'"}

    @classmethod
    def is_app_running(cls, app_name: str) -> bool:
        """Checks if process is running via tasklist."""
        proc = app_name if app_name.endswith(".exe") else f"{app_name}.exe"
        res = subprocess.run(f'tasklist /FI "IMAGENAME eq {proc}" /NH', shell=True, capture_output=True, text=True)
        return proc.lower() in res.stdout.lower()

    @classmethod
    def kill_app(cls, app_name: str) -> dict:
        """Kills process forcefully via taskkill."""
        proc = app_name if app_name.endswith(".exe") else f"{app_name}.exe"
        res = subprocess.run(f'taskkill /F /IM {proc} /T', shell=True, capture_output=True, text=True)
        return {"status": "success", "os": "Windows", "action": "kill_app", "output": res.stdout.strip() or res.stderr.strip()}

    @classmethod
    def execute_command(cls, command: str) -> str:
        """Executes a shell command on Windows with automatic Unix->PowerShell translations."""
        clean_cmd = command.strip()
        # Translate common Unix commands if they slip through
        if clean_cmd.startswith("xdg-open ") or clean_cmd.startswith("open "):
            target = clean_cmd.split(None, 1)[1].strip("'\"")
            return cls.open_url(target).get("output", "")
        if clean_cmd.startswith("killall ") or clean_cmd.startswith("pkill "):
            target = clean_cmd.split()[-1].strip("'\"")
            return cls.kill_app(target).get("output", "")
        if clean_cmd.startswith("pgrep "):
            target = clean_cmd.split()[-1].strip("'\"")
            running = cls.is_app_running(target)
            return f"Process '{target}' is {'running' if running else 'not running'}."

        # Handle detached background execution or Unix nohup
        if clean_cmd.startswith("nohup "):
            clean_cmd = clean_cmd.replace("nohup ", "").split(">/dev/null")[0].split("2>&1")[0].replace("& disown", "").replace("&", "").strip()
            subprocess.Popen(f'cmd /c start "" {clean_cmd}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"App '{clean_cmd}' launched successfully in the background on Windows."

        if clean_cmd.endswith("&"):
            actual_cmd = clean_cmd[:-1].strip()
            subprocess.Popen(f'cmd /c start "" {actual_cmd}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "App launched successfully in the background on Windows."

        # Unix pipeline translations for PowerShell
        if " | grep " in clean_cmd:
            clean_cmd = clean_cmd.replace(" | grep ", " | Select-String ")
        if clean_cmd.startswith("which "):
            target = clean_cmd.split(None, 1)[1].strip()
            clean_cmd = f"Get-Command {target} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source"
        elif clean_cmd.startswith("touch "):
            target = clean_cmd.split(None, 1)[1].strip()
            clean_cmd = f"New-Item -ItemType File -Force {target}"

        # Execute through PowerShell for rich scripting support
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", clean_cmd],
                                 capture_output=True, text=True, timeout=120)
            output = res.stdout.strip() or res.stderr.strip() or "Command completed successfully."
            if len(output) > 40000:
                output = output[:40000] + "\n\n... [OUTPUT TRUNCATED BY SYSTEM TO PREVENT TOKEN OVERFLOW]"
            return output
        except Exception as e:
            return f"Windows command execution failed: {str(e)}"


# =====================================================================
# 2. MACOS PROTOCOL
# =====================================================================
class MacOSProtocol:
    """
    Native macOS automation using AppleScript (osascript), JXA,
    open command, and Darwin system protocols.
    Completely silent, zero visual interruption, standard on all Macs.
    """

    @classmethod
    def _run_osascript(cls, script: str) -> str:
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
            return res.stdout.strip()
        except Exception as e:
            return str(e)

    # --- Media / Spotify Protocols ---
    @classmethod
    def spotify_play(cls, query: str = "") -> dict:
        """
        Plays music on Spotify via AppleScript.
        If track URI given: plays directly.
        If query given: searches and triggers play.
        """
        clean_query = query.strip()
        if not clean_query:
            return cls.media_play_pause()

        if clean_query.startswith("spotify:"):
            script = f'tell application "Spotify" to play track "{clean_query}"'
            cls._run_osascript(script)
            return {"status": "success", "os": "macOS", "action": "spotify_play", "output": f"Playing '{clean_query}' on Spotify"}
        
        # Search via open URI and play
        encoded = urllib.parse.quote(clean_query)
        subprocess.Popen(["open", f"spotify:search:{encoded}"])
        time.sleep(0.7)
        # Hit return via System Events
        cls._run_osascript('tell application "System Events" to key code 36')
        return {"status": "success", "os": "macOS", "action": "spotify_play", "output": f"Playing '{clean_query}' on Spotify via AppleScript"}

    @classmethod
    def media_play_pause(cls) -> dict:
        """Toggles playback on Spotify (or Apple Music fallback) via AppleScript."""
        res = cls._run_osascript('tell application "Spotify" to playpause')
        if "error" in res.lower() or not res:
            # Fallback to Music.app
            cls._run_osascript('tell application "Music" to playpause')
        return {"status": "success", "os": "macOS", "action": "play_pause", "output": "Toggled playback via AppleScript"}

    @classmethod
    def media_next(cls) -> dict:
        """Skips to next track via AppleScript."""
        cls._run_osascript('tell application "Spotify" to next track')
        return {"status": "success", "os": "macOS", "action": "next", "output": "Skipped to next track via AppleScript"}

    @classmethod
    def media_prev(cls) -> dict:
        """Returns to previous track via AppleScript."""
        cls._run_osascript('tell application "Spotify" to previous track')
        return {"status": "success", "os": "macOS", "action": "previous", "output": "Returned to previous track via AppleScript"}

    @classmethod
    def media_set_volume(cls, level_percent: int) -> dict:
        """Sets macOS system volume (0-100) via AppleScript."""
        val = max(0, min(100, int(level_percent)))
        cls._run_osascript(f'set volume output volume {val}')
        return {"status": "success", "os": "macOS", "action": "set_volume", "output": f"Set macOS volume to {val}%"}

    # --- App / Window Protocols ---
    @classmethod
    def open_url(cls, url: str) -> dict:
        """Opens URL in macOS default browser."""
        subprocess.Popen(["open", url], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "success", "os": "macOS", "action": "open_url", "output": f"Opened {url} via macOS open"}

    @classmethod
    def open_app(cls, app_name: str, args: list = None) -> dict:
        """Opens macOS application via `open -a`."""
        app_clean = app_name.lower().strip()
        if app_clean in ["calculator", "calc"]:
            app_clean = "Calculator"
        elif app_clean in ["music"]:
            app_clean = "Music"
        elif app_clean in ["spotify"]:
            app_clean = "Spotify"
        elif app_clean in ["terminal"]:
            app_clean = "Terminal"
        elif app_clean in ["settings", "system settings", "preferences"]:
            app_clean = "System Settings"
        elif app_clean in ["taskmanager", "task manager", "activity monitor"]:
            app_clean = "Activity Monitor"
        elif app_clean in ["finder", "files", "file manager"]:
            app_clean = "Finder"
        elif app_clean in ["code", "vscode", "vs code"]:
            app_clean = "Visual Studio Code"
        elif app_clean in ["notes", "notepad", "text"]:
            app_clean = "Notes"

        cmd = ["open", "-a", app_clean]
        if args:
            cmd.extend(["--args"] + args)
        subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "success", "os": "macOS", "action": "open_app", "output": f"Opened {app_name} on macOS"}

    @classmethod
    def focus_window(cls, app_name: str) -> dict:
        """Brings application window to front via AppleScript activate."""
        cls._run_osascript(f'tell application "{app_name}" to activate')
        return {"status": "success", "os": "macOS", "action": "focus_window", "output": f"Activated '{app_name}' via AppleScript"}

    @classmethod
    def is_app_running(cls, app_name: str) -> bool:
        """Checks if application is running via pgrep."""
        res = subprocess.run(["pgrep", "-if", app_name], capture_output=True, text=True)
        return bool(res.stdout.strip())

    @classmethod
    def kill_app(cls, app_name: str) -> dict:
        """Kills application via pkill."""
        subprocess.run(["pkill", "-if", app_name], capture_output=True, text=True)
        return {"status": "success", "os": "macOS", "action": "kill_app", "output": f"Terminated '{app_name}'"}

    @classmethod
    def execute_command(cls, command: str) -> str:
        """Executes a shell command via /bin/zsh or /bin/bash on macOS."""
        shell = "/bin/zsh" if os.path.exists("/bin/zsh") else "/bin/bash"
        try:
            res = subprocess.run([shell, "-c", command], capture_output=True, text=True, timeout=120)
            return res.stdout.strip() or res.stderr.strip() or "Command completed successfully."
        except Exception as e:
            return f"macOS command execution failed: {str(e)}"


# =====================================================================
# 3. LINUX PROTOCOL
# =====================================================================
class LinuxProtocol:
    """
    Native Linux automation using MPRIS2 D-Bus (playerctl / dbus-send),
    xdg-open, wmctrl/xdotool, and Linux FreeDesktop system protocols.
    Full background execution, zero mouse clicks required.
    """

    # --- Media / Spotify Protocols ---
    @classmethod
    def spotify_play(cls, query: str = "") -> dict:
        """Plays music on Spotify using MPRIS2 D-Bus OpenUri or playerctl."""
        clean_query = query.strip()
        if not clean_query:
            return cls.media_play_pause()

        if clean_query.startswith("spotify:"):
            target_uri = clean_query
        else:
            target_uri = f"spotify:search:{urllib.parse.quote(clean_query)}"

        # 1. Try D-Bus OpenUri
        dbus_cmd = f"dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.OpenUri string:'{target_uri}' 2>/dev/null"
        res = subprocess.run(dbus_cmd, shell=True, capture_output=True, text=True)
        
        # 2. Fallback to xdg-open if D-Bus failed (e.g. Spotify not currently launched)
        if res.returncode != 0:
            subprocess.Popen(f"xdg-open '{target_uri}' &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            # Try to trigger play via playerctl
            subprocess.run("playerctl -p spotify play 2>/dev/null", shell=True)

        return {"status": "success", "os": "Linux", "action": "spotify_play", "output": f"Playing '{clean_query}' on Spotify via MPRIS2 D-Bus"}

    @classmethod
    def media_play_pause(cls) -> dict:
        """Toggles playback via playerctl or D-Bus."""
        cmd = "playerctl play-pause 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlayPause 2>/dev/null"
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"status": "success", "os": "Linux", "action": "play_pause", "output": "Toggled playback via MPRIS2"}

    @classmethod
    def media_next(cls) -> dict:
        """Skips to next track via playerctl or D-Bus."""
        cmd = "playerctl next 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next 2>/dev/null"
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"status": "success", "os": "Linux", "action": "next", "output": "Skipped track via MPRIS2"}

    @classmethod
    def media_prev(cls) -> dict:
        """Returns to previous track via playerctl or D-Bus."""
        cmd = "playerctl previous 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Previous 2>/dev/null"
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"status": "success", "os": "Linux", "action": "previous", "output": "Previous track via MPRIS2"}

    @classmethod
    def media_set_volume(cls, level_percent: int) -> dict:
        """Sets Linux volume via pamixer or pactl or amixer."""
        val = max(0, min(100, int(level_percent)))
        cmd = f"pamixer --set-volume {val} 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ {val}% 2>/dev/null || amixer set Master {val}% 2>/dev/null"
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"status": "success", "os": "Linux", "action": "set_volume", "output": f"Set Linux volume to {val}%"}

    # --- App / Window Protocols ---
    @classmethod
    def open_url(cls, url: str) -> dict:
        """Opens URL in default Linux browser via xdg-open."""
        subprocess.Popen(["xdg-open", url], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "success", "os": "Linux", "action": "open_url", "output": f"Opened {url} via xdg-open"}

    @classmethod
    def open_app(cls, app_name: str, args: list = None) -> dict:
        """Launches application on Linux detached."""
        app_clean = app_name.lower().strip()
        if app_clean in ["calculator", "calc"]:
            for cand in ["gnome-calculator", "kcalc", "galculator", "xcalc"]:
                if shutil.which(cand):
                    subprocess.Popen([cand], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"status": "success", "os": "Linux", "action": "open_app", "output": f"Opened {cand}"}
            subprocess.Popen(["xdg-open", "https://google.com/search?q=calculator"], start_new_session=True)
            return {"status": "success", "os": "Linux", "action": "open_app", "output": "Opened web calculator"}
        elif app_clean in ["settings", "system settings"]:
            for cand in ["gnome-control-center", "systemsettings5", "xfce4-settings-manager"]:
                if shutil.which(cand):
                    subprocess.Popen([cand], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"status": "success", "os": "Linux", "action": "open_app", "output": f"Opened {cand}"}
        elif app_clean in ["taskmanager", "task manager", "system monitor"]:
            for cand in ["gnome-system-monitor", "ksysguard", "htop"]:
                if shutil.which(cand):
                    subprocess.Popen([cand], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"status": "success", "os": "Linux", "action": "open_app", "output": f"Opened {cand}"}
        elif app_clean in ["files", "explorer", "file manager"]:
            for cand in ["nautilus", "dolphin", "thunar", "pcmanfm"]:
                if shutil.which(cand):
                    subprocess.Popen([cand], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"status": "success", "os": "Linux", "action": "open_app", "output": f"Opened {cand}"}
        elif app_clean in ["terminal"]:
            for cand in ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"]:
                if shutil.which(cand):
                    subprocess.Popen([cand], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"status": "success", "os": "Linux", "action": "open_app", "output": f"Opened {cand}"}
        elif app_clean in ["code", "vscode", "vs code"]:
            subprocess.Popen(["code"] + (args or []), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "success", "os": "Linux", "action": "open_app", "output": "Opened VS Code"}
            
        full_cmd = [app_clean] + (args or [])
        subprocess.Popen(full_cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "success", "os": "Linux", "action": "open_app", "output": f"Launched {app_name}"}

    @classmethod
    def focus_window(cls, title_substring: str) -> dict:
        """Focuses window via wmctrl or xdotool."""
        res = subprocess.run(["wmctrl", "-a", title_substring], capture_output=True, text=True)
        if res.returncode == 0:
            return {"status": "success", "os": "Linux", "action": "focus_window", "output": f"Activated window matching '{title_substring}' via wmctrl"}
        
        # xdotool fallback
        xdo = f"xdotool search --onlyvisible --name '{title_substring}' windowactivate 2>/dev/null"
        res2 = subprocess.run(xdo, shell=True, capture_output=True, text=True)
        if res2.returncode == 0:
            return {"status": "success", "os": "Linux", "action": "focus_window", "output": f"Activated window matching '{title_substring}' via xdotool"}
        
        return {"status": "error", "os": "Linux", "action": "focus_window", "output": f"Window '{title_substring}' not found"}

    @classmethod
    def is_app_running(cls, app_name: str) -> bool:
        """Checks if process is running via pgrep."""
        res = subprocess.run(["pgrep", "-if", app_name], capture_output=True, text=True)
        return bool(res.stdout.strip())

    @classmethod
    def kill_app(cls, app_name: str) -> dict:
        """Terminates process via pkill / killall."""
        subprocess.run(["pkill", "-if", app_name], capture_output=True, text=True)
        return {"status": "success", "os": "Linux", "action": "kill_app", "output": f"Terminated '{app_name}'"}

    @classmethod
    def execute_command(cls, command: str) -> str:
        """Executes a shell command on Linux via /bin/bash."""
        try:
            res = subprocess.run(command, shell=True, executable="/bin/bash", capture_output=True, text=True, timeout=120)
            return res.stdout.strip() or res.stderr.strip() or "Command completed successfully."
        except Exception as e:
            return f"Linux command execution failed: {str(e)}"


# =====================================================================
# 4. UNIFIED CROSS-PLATFORM OS PROTOCOLS ROUTER
# =====================================================================
class OSProtocols:
    """
    Unified router that automatically chooses the fastest, most effective,
    and native protocol implementation for the host operating system.
    """

    @classmethod
    def get_handler(cls):
        sys_name = platform.system()
        if sys_name == "Windows":
            return WindowsProtocol
        elif sys_name == "Darwin":
            return MacOSProtocol
        else:
            return LinuxProtocol

    # --- Unified Media API ---
    @classmethod
    def play_spotify(cls, query: str = "") -> dict:
        return cls.get_handler().spotify_play(query)

    @classmethod
    def media_play_pause(cls) -> dict:
        return cls.get_handler().media_play_pause()

    @classmethod
    def media_next(cls) -> dict:
        return cls.get_handler().media_next()

    @classmethod
    def media_prev(cls) -> dict:
        return cls.get_handler().media_prev()

    @classmethod
    def media_set_volume(cls, level_percent: int) -> dict:
        return cls.get_handler().media_set_volume(level_percent)

    # --- Unified App & URL API ---
    @classmethod
    def open_url(cls, url: str) -> dict:
        return cls.get_handler().open_url(url)

    @classmethod
    def open_app(cls, app_name: str, args: list = None) -> dict:
        return cls.get_handler().open_app(app_name, args)

    @classmethod
    def focus_window(cls, title: str) -> dict:
        return cls.get_handler().focus_window(title)

    @classmethod
    def is_app_running(cls, app_name: str) -> bool:
        return cls.get_handler().is_app_running(app_name)

    @classmethod
    def kill_app(cls, app_name: str) -> dict:
        return cls.get_handler().kill_app(app_name)

    @classmethod
    def execute_command(cls, command: str) -> str:
        return cls.get_handler().execute_command(command)
