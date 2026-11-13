import sys
import json
import subprocess

def run_media_task(data: dict) -> dict:
    import platform
    os_type = platform.system()
    action = data.get("action", "playpause").lower()
    app = data.get("app", "spotify").lower()
    
    if os_type == "Linux":
        query = data.get("query", data.get("payload", data.get("song", "")))
        if query and action in ["search", "play", "open"]:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            cmd = f"dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.OpenUri string:'spotify:search:{encoded_query}' 2>/dev/null || xdg-open 'spotify:search:{encoded_query}'"
        elif action in ["play", "pause", "toggle", "playpause"]:
            cmd = f"playerctl -p {app} play-pause 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.{app} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlayPause"
        elif action in ["next", "skip"]:
            cmd = f"playerctl -p {app} next 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.{app} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next"
        elif action in ["prev", "previous"]:
            cmd = f"playerctl -p {app} previous 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.{app} /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Previous"
        else:
            cmd = f"playerctl -p {app} play-pause 2>/dev/null"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out = res.stdout.strip()
    elif os_type == "Darwin": # macOS
        if action in ["next", "skip"]:
            cmd = f"osascript -e 'tell application \"{app.capitalize()}\" to next track'"
        elif action in ["prev", "previous"]:
            cmd = f"osascript -e 'tell application \"{app.capitalize()}\" to previous track'"
        else:
            cmd = f"osascript -e 'tell application \"{app.capitalize()}\" to playpause'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out = res.stdout.strip()
    else: # Windows
        query = data.get("query", data.get("payload", data.get("song", "")))
        if query and action in ["search", "play", "open"]:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            ps_cmd = f'Start-Process "spotify:search:{encoded_query}"; Start-Sleep -Milliseconds 850; (New-Object -ComObject wscript.shell).SendKeys("{{ENTER}}")'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
            out = f"Playing '{query}' on Spotify via Windows native protocol"
        elif action in ["next", "skip"]:
            ps_cmd = '(New-Object -ComObject wscript.shell).SendKeys([char]176)'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            out = "Skipped to next track"
        elif action in ["prev", "previous"]:
            ps_cmd = '(New-Object -ComObject wscript.shell).SendKeys([char]177)'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            out = "Returned to previous track"
        else:
            ps_cmd = '(New-Object -ComObject wscript.shell).SendKeys([char]179)'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
            out = "Toggled playback via Windows media control"

    return {"status": "success", "action": action, "output": out}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            payload = json.loads(sys.argv[1])
        except Exception:
            payload = {}
    else:
        payload = {}
        
    output = run_media_task(payload)
    print(json.dumps(output))
