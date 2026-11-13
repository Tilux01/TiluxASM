"""
Tilux Reflex Fast-Path Router
Executes deterministic local OS and media actions in < 50ms with ZERO LLM latency and ZERO token burn.
Security-conscious: Only safe, read-only or explicit UI/media actions are handled here.
Everything else falls through to the full LLM brain.
"""

import re
import datetime
import platform
from typing import Optional, Dict, Any

from os_protocols import OSProtocols

# Compiled regex patterns for ultra-fast matching
_RE_PAUSE = re.compile(r'^(?:media\s+)?(pause|stop)(?:\s+(?:the\s+)?(?:music|media|song|playback))?$', re.I)
_RE_PLAY_RESUME = re.compile(r'^(?:media\s+)?(play|resume|toggle)(?:\s+(?:the\s+)?(?:music|media|song|playback))?$', re.I)
_RE_NEXT = re.compile(r'^(?:play\s+)?(?:the\s+)?(next|skip)(?:\s+(?:song|track|music))?$', re.I)
_RE_PREV = re.compile(r'^(?:play\s+)?(?:the\s+)?(previous|prev|last)(?:\s+(?:song|track|music))?$', re.I)
_RE_MUTE = re.compile(r'^(?:unmute|mute)(?:\s+(?:the\s+)?(?:sound|audio|volume|speaker|speakers))?$', re.I)
_RE_VOL_UP = re.compile(r'^(?:turn\s+(?:the\s+)?volume\s+up|increase\s+(?:the\s+)?volume|volume\s+up|louder)$', re.I)
_RE_VOL_DOWN = re.compile(r'^(?:turn\s+(?:the\s+)?volume\s+down|decrease\s+(?:the\s+)?volume|lower\s+(?:the\s+)?volume|volume\s+down|quieter|softer)$', re.I)
_RE_VOL_SET = re.compile(r'^(?:set\s+(?:the\s+)?volume\s+to|volume)\s+(\d{1,3})(?:\s*(?:%|percent))?$', re.I)
_RE_SPOTIFY_PLAY = re.compile(r'^(?:play|search)\s+(.+?)\s+on\s+spotify$', re.I)

_RE_APP_OPEN = re.compile(r'^(?:open|launch|start)\s+([a-zA-Z0-9_\-\.\s]+)$', re.I)
_RE_TIME = re.compile(r'^(?:what\s+time\s+is\s+it|tell\s+me\s+the\s+time|current\s+time|what(?:\'s|\s+is)\s+the\s+time)$', re.I)
_RE_DATE = re.compile(r'^(?:what\s+date\s+is\s+it|what(?:\'s|\s+is)\s+today(?:\'s)?\s+date|today(?:\'s)?\s+date|what(?:\'s|\s+is)\s+the\s+date)$', re.I)
_RE_DAY = re.compile(r'^(?:what\s+day\s+is\s+it|what\s+day\s+of\s+the\s+week\s+is\s+it)$', re.I)

_RE_GREETING = re.compile(r'^(?:hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening)(?:\s+tilux|\s+assistant)?$', re.I)
_RE_IDENTITY = re.compile(r'^(?:who\s+are\s+you|what\s+are\s+you|what(?:\'s|\s+is)\s+your\s+name)$', re.I)
_RE_DISMISS = re.compile(r'^(?:stop|cancel|never\s*mind|dismiss|close|shut\s*up|quiet|exit)$', re.I)

# App alias mapping to ensure cross-platform resolution
_APP_ALIASES = {
    "spotify": "spotify",
    "chrome": "google-chrome",
    "google chrome": "google-chrome",
    "browser": "browser",
    "firefox": "firefox",
    "terminal": "terminal",
    "console": "terminal",
    "bash": "terminal",
    "calculator": "calculator",
    "calc": "calculator",
    "vs code": "code",
    "vscode": "code",
    "code": "code",
    "visual studio code": "code",
    "files": "files",
    "file manager": "files",
    "explorer": "files",
    "finder": "files",
    "nautilus": "files",
    "settings": "settings",
    "discord": "discord",
    "slack": "slack",
    "telegram": "telegram",
    "vlc": "vlc",
}

def reflex_route(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Checks if a user prompt can be handled deterministically via high-speed native reflex.
    Returns a dict with {"handled": True, "reply": ..., "sub_text": ..., "action": ...}
    or None if the prompt requires LLM reasoning.
    """
    if not prompt or not isinstance(prompt, str):
        return None
        
    clean = prompt.strip().rstrip('.!?')
    if not clean:
        return None

    # 1. Immediate Dismissal / Cancel
    if _RE_DISMISS.match(clean):
        return {
            "handled": True,
            "action": "dismiss",
            "reply": "",
            "sub_text": "Dismissed",
            "aborted": True
        }

    # 2. Media Controls (MPRIS2 / Win32 / AppleScript)
    if _RE_PAUSE.match(clean):
        res = OSProtocols.media_play_pause()
        return {
            "handled": True,
            "action": "media_pause",
            "reply": "Paused.",
            "sub_text": res.get("output", "Paused media")
        }

    if _RE_PLAY_RESUME.match(clean):
        res = OSProtocols.media_play_pause()
        return {
            "handled": True,
            "action": "media_play",
            "reply": "Playing.",
            "sub_text": res.get("output", "Resumed media")
        }

    if _RE_NEXT.match(clean):
        res = OSProtocols.media_next()
        return {
            "handled": True,
            "action": "media_next",
            "reply": "Next track.",
            "sub_text": res.get("output", "Skipped to next track")
        }

    if _RE_PREV.match(clean):
        res = OSProtocols.media_prev()
        return {
            "handled": True,
            "action": "media_prev",
            "reply": "Previous track.",
            "sub_text": res.get("output", "Returned to previous track")
        }

    if _RE_MUTE.match(clean):
        res = OSProtocols.media_mute()
        return {
            "handled": True,
            "action": "media_mute",
            "reply": "Muted audio.",
            "sub_text": res.get("output", "Toggled mute")
        }

    if _RE_VOL_UP.match(clean):
        res = OSProtocols.media_volume_up(10)
        return {
            "handled": True,
            "action": "media_volume_up",
            "reply": "Volume turned up.",
            "sub_text": res.get("output", "Volume increased")
        }

    if _RE_VOL_DOWN.match(clean):
        res = OSProtocols.media_volume_down(10)
        return {
            "handled": True,
            "action": "media_volume_down",
            "reply": "Volume turned down.",
            "sub_text": res.get("output", "Volume decreased")
        }

    vol_set_match = _RE_VOL_SET.match(clean)
    if vol_set_match:
        val = min(100, max(0, int(vol_set_match.group(1))))
        res = OSProtocols.media_set_volume(val)
        return {
            "handled": True,
            "action": "media_set_volume",
            "reply": f"Volume set to {val} percent.",
            "sub_text": res.get("output", f"Volume: {val}%")
        }

    spotify_match = _RE_SPOTIFY_PLAY.match(clean)
    if spotify_match:
        query = spotify_match.group(1).strip()
        res = OSProtocols.play_spotify(query)
        return {
            "handled": True,
            "action": "spotify_play",
            "reply": f"Playing {query} on Spotify.",
            "sub_text": res.get("output", f"Spotify: {query}")
        }

    # 3. Fast App Launching
    app_match = _RE_APP_OPEN.match(clean)
    if app_match:
        raw_app = app_match.group(1).lower().strip()
        # Look up mapped alias
        target_app = _APP_ALIASES.get(raw_app)
        if target_app:
            res = OSProtocols.open_app(target_app)
            pretty_name = raw_app.title()
            return {
                "handled": True,
                "action": f"launch_{target_app}",
                "reply": f"Opening {pretty_name}.",
                "sub_text": res.get("output", f"Launched {pretty_name}")
            }

    # 4. System Time / Date / Day
    if _RE_TIME.match(clean):
        now_str = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
        return {
            "handled": True,
            "action": "system_time",
            "reply": f"It's {now_str}.",
            "sub_text": f"Time: {now_str}"
        }

    if _RE_DATE.match(clean):
        now = datetime.datetime.now()
        day_num = now.day
        # Determine ordinal suffix (1st, 2nd, 3rd, 4th...)
        suffix = "th" if 11 <= day_num <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
        date_str = now.strftime(f"%A, %B {day_num}{suffix}, %Y")
        return {
            "handled": True,
            "action": "system_date",
            "reply": f"Today is {date_str}.",
            "sub_text": date_str
        }

    if _RE_DAY.match(clean):
        day_str = datetime.datetime.now().strftime("%A")
        return {
            "handled": True,
            "action": "system_day",
            "reply": f"Today is {day_str}.",
            "sub_text": f"Day: {day_str}"
        }

    # 5. Quick Greeting Reflex
    if _RE_GREETING.match(clean):
        hour = datetime.datetime.now().hour
        if hour < 12:
            greet = "Good morning! What are we working on?"
        elif hour < 17:
            greet = "Good afternoon! What's on your mind?"
        else:
            greet = "Good evening! Ready when you are."
        return {
            "handled": True,
            "action": "greeting",
            "reply": greet,
            "sub_text": "Ready"
        }

    # 6. Identity Reflex
    if _RE_IDENTITY.match(clean):
        return {
            "handled": True,
            "action": "identity",
            "reply": "I am Tilux ASM v1.0, your native desktop automation system. What can I automate for you?",
            "sub_text": "Tilux ASM v1.0"
        }

    return None
