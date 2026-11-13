import sys
import os
import json

# Ensure parent directory is in python path to load os_protocols
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from os_protocols import OSProtocols

def run_media_task(data: dict) -> dict:
    """
    Executes media tasks (Spotify, playback, volume) using centralized native OS protocols.
    """
    action = data.get("action", "playpause").lower().strip()
    query = data.get("query", data.get("payload", data.get("song", ""))).strip()

    if action in ["search", "play", "open"]:
        return OSProtocols.play_spotify(query)
    elif action in ["next", "skip"]:
        return OSProtocols.media_next()
    elif action in ["prev", "previous"]:
        return OSProtocols.media_prev()
    elif action in ["volume", "set_volume"]:
        raw_vol = data.get("level", 80)
        try:
            vol = int(raw_vol)
        except Exception:
            vol = 80
        return OSProtocols.media_set_volume(vol)
    else:
        return OSProtocols.media_play_pause()

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
