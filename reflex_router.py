"""
Tilux Reflex Fast-Path Router
Executes deterministic local OS and media actions in < 50ms with ZERO LLM latency and ZERO token burn.
Security-conscious: Only safe, read-only or explicit UI/media actions are handled here.
Everything else falls through to the full LLM brain.
"""

import re
import datetime
import platform
import os
import sys
from typing import Optional, Dict, Any

_parent_dir = os.path.dirname(os.path.abspath(__file__))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    from os_protocols import OSProtocols
except ImportError:
    try:
        from os_protocol import OSProtocols
    except ImportError:
        OSProtocols = None

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

_RE_APP_OPEN = re.compile(r'^(?:open\s+up|open|launch|start)\s+([a-zA-Z0-9_\-\.\s]+)$', re.I)
_RE_TIME = re.compile(r'^(?:what\s+time\s+is\s+it|tell\s+me\s+the\s+time|current\s+time|what(?:\'s|\s+is)\s+the\s+time)$', re.I)
_RE_DATE = re.compile(r'^(?:what\s+date\s+is\s+it|what(?:\'s|\s+is)\s+today(?:\'s)?\s+date|today(?:\'s)?\s+date|what(?:\'s|\s+is)\s+the\s+date)$', re.I)
_RE_DAY = re.compile(r'^(?:what\s+day\s+is\s+it|what\s+day\s+of\s+the\s+week\s+is\s+it)$', re.I)

_RE_GREETING = re.compile(r'^(?:hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening)(?:\s+tilux|\s+assistant)?$', re.I)
_RE_IDENTITY = re.compile(r'^(?:who\s+are\s+you|what\s+are\s+you|what(?:\'s|\s+is)\s+your\s+name)$', re.I)
_RE_EMERGENCY_STOP = re.compile(r'^(?:stop|cancel|shut\s*up|quiet|be\s+quiet|silence)$', re.I)
_RE_BATTERY = re.compile(r'^(?:what(?:\'s|\s+is)\s+(?:the\s+)?battery(?:\s+level|\s+percentage|\s+status)?|battery(?:\s+percentage|\s+level|\s+status)?|how\s+much\s+battery(?:\s+do\s+i\s+have)?)$', re.I)
_RE_SYS_STATS = re.compile(r'^(?:system\s+stats|cpu\s+usage|ram\s+usage|memory\s+usage|system\s+performance|how\s+much\s+(?:ram|memory)\s+(?:is\s+free|used)?)$', re.I)
_RE_DISK = re.compile(r'^(?:disk\s+space|storage|free\s+space|how\s+much\s+(?:disk\s+space|storage)\s+(?:is\s+left|free)?)$', re.I)
_RE_SCREENSHOT = re.compile(r'^(?:take\s+(?:a\s+)?screenshot|screenshot|screen\s+capture|capture\s+(?:the\s+)?screen)$', re.I)
_RE_LOCK = re.compile(r'^(?:lock\s+(?:the\s+)?(?:screen|computer|pc)|lock\s+my\s+screen)$', re.I)
_RE_MATH = re.compile(r'^(?:what(?:\'s|\s+is)|calculate|compute)\s+([\d\.\s\+\-\*\/\(\)\%\^]+|\d+(?:\.\d+)?\s*%\s*of\s*\d+(?:\.\d+)?)$', re.I)

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
    "figma": "figma",
    "notion": "notion",
    "obsidian": "obsidian",
    "postman": "postman",
    "docker": "docker",
    "steam": "steam",
    "zoom": "zoom",
    "whatsapp": "whatsapp",
    "obs": "obs",
    "blender": "blender",
    "gimp": "gimp",
}

_SITE_SHORTCUTS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://www.github.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "netflix": "https://www.netflix.com",
    "chatgpt": "https://chatgpt.com",
    "gmail": "https://mail.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "tiktok": "https://www.tiktok.com",
    "maps": "https://maps.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "drive": "https://drive.google.com",
    "translate": "https://translate.google.com",
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

    # 1. Immediate Emergency Stop / Silence
    if _RE_EMERGENCY_STOP.match(clean):
        return {
            "handled": True,
            "action": "dismiss",
            "reply": "",
            "sub_text": "Stopped",
            "aborted": True,
            "close_voice_assistant": True
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

    # 3. Web Search Reflex (Google / Search for)
    if re.match(r'^(?:web\s+search|search\s+the\s+web|open\s+(?:the\s+)?browser(?:\s+to\s+search(?:\s+the\s+web)?)?)$', clean, re.I):
        res = OSProtocols.open_url("https://www.google.com")
        return {
            "handled": True,
            "action": "web_search",
            "reply": "Opening browser for web search.",
            "sub_text": "Opened Google"
        }

    search_match = re.match(r'^(?:search\s+(?:for\s+)?|google\s+)(.+)$', clean, re.I)
    if search_match:
        q = search_match.group(1).strip()
        import urllib.parse
        target_url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
        res = OSProtocols.open_url(target_url)
        return {
            "handled": True,
            "action": "web_search",
            "reply": f"Searching Google for {q}.",
            "sub_text": f"Google: {q}"
        }

    # 4. Workspace Chatbox Fast-Path
    if re.search(r'^(?:open|show|launch|start)\s+(?:the\s+)?(?:workspace\s+(?:chatbox|chat\s*box|chatbot|chat)|workspace|chatbox|chat\s*box)$', clean, re.I):
        try:
            import server
            server.trigger_open_chat("")
            return {
                "handled": True,
                "action": "open_workspace_chatbox",
                "reply": "Opening the workspace chatbox.",
                "sub_text": "Opening Workspace..."
            }
        except Exception as e:
            print(f"[Reflex] Error triggering open chat: {e}")

    # 5. Universal App Launching & Website Opening
    app_match = _RE_APP_OPEN.match(clean)
    if app_match:
        raw_target = app_match.group(1).strip()
        # Clean leading 'the ' or 'a ' if present: e.g. "open the chrome" -> "chrome"
        raw_target = re.sub(r'^(?:the|a|an)\s+', '', raw_target, flags=re.I).strip()
        words = raw_target.lower().split()
        
        # Guard: App names are concise (<= 3 words) and should not contain conversational pronouns/filler
        CONVERSATIONAL_WORDS = {"i", "you", "we", "me", "my", "your", "said", "say", "saying", "tell", "told", "ask", "asked", "here", "there", "is", "was", "are", "were", "what", "how", "why", "where", "who", "when", "can", "could", "should", "would", "please", "help", "work", "that", "this"}
        
        if len(words) <= 3 and not any(w in CONVERSATIONAL_WORDS for w in words) and not re.search(r'[;&|><`$\n]', raw_target):
            target_lower = raw_target.lower()
            
            # 5a. Is it a well-known site shortcut or URL?
            if target_lower in _SITE_SHORTCUTS or "." in target_lower or target_lower.startswith("http"):
                if target_lower in _SITE_SHORTCUTS:
                    target_url = _SITE_SHORTCUTS[target_lower]
                elif target_lower.startswith("http://") or target_lower.startswith("https://"):
                    target_url = target_lower
                else:
                    target_url = f"https://{target_lower}"
                res = OSProtocols.open_url(target_url)
                if res.get("status") == "success":
                    pretty_name = target_lower.replace("https://", "").replace("http://", "").replace("www.", "").split(".")[0].title()
                    return {
                        "handled": True,
                        "action": "open_url",
                        "reply": f"Opening {pretty_name}.",
                        "sub_text": res.get("output", f"Opened {target_url}")
                    }

            # 5b. Universal App Launch
            raw_app = re.sub(r'\s+(?:app|application)$', '', target_lower).strip()
            target_app = _APP_ALIASES.get(raw_app, raw_app)
            res = OSProtocols.open_app(target_app)
            # Only treat as handled if OS confirmed the app was successfully found and launched!
            if res.get("status") == "success":
                pretty_name = raw_app.title()
                return {
                    "handled": True,
                    "action": f"launch_{target_app}",
                    "reply": f"Opening {pretty_name}.",
                    "sub_text": res.get("output", f"Launched {pretty_name}")
                }
            else:
                print(f"[Reflex] App '{target_app}' not found on system. Falling through to LLM.")

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

    # 7. Battery Status
    if _RE_BATTERY.match(clean):
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt:
                pct = int(batt.percent)
                status = "charging" if batt.power_plugged else "on battery"
                return {
                    "handled": True,
                    "action": "battery_status",
                    "reply": f"Battery is at {pct}% ({status}).",
                    "sub_text": f"Battery: {pct}% ({status})"
                }
            else:
                return {
                    "handled": True,
                    "action": "battery_status",
                    "reply": "No battery detected (desktop AC power).",
                    "sub_text": "AC Power"
                }
        except Exception:
            pass

    # 8. CPU & RAM System Stats
    if _RE_SYS_STATS.match(clean):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.04)
            mem = psutil.virtual_memory()
            avail_gb = mem.available / (1024**3)
            return {
                "handled": True,
                "action": "system_stats",
                "reply": f"CPU usage is {cpu:.0f}%, RAM usage is {mem.percent:.0f}% ({avail_gb:.1f} GB available).",
                "sub_text": f"CPU: {cpu:.0f}% | RAM: {mem.percent:.0f}%"
            }
        except Exception:
            pass

    # 9. Free Disk Space
    if _RE_DISK.match(clean):
        try:
            import shutil
            total, used, free = shutil.disk_usage(os.path.expanduser("~"))
            free_gb = free / (1024**3)
            return {
                "handled": True,
                "action": "disk_space",
                "reply": f"You have {free_gb:.1f} GB of free storage space available.",
                "sub_text": f"Free: {free_gb:.1f} GB"
            }
        except Exception:
            pass

    # 10. Instant Screenshot
    if _RE_SCREENSHOT.match(clean):
        try:
            from actions import take_screenshot
            path = take_screenshot()
            fname = os.path.basename(path) if path else "screenshot"
            return {
                "handled": True,
                "action": "take_screenshot",
                "reply": "Screenshot captured and saved to Pictures.",
                "sub_text": f"Screenshot: {fname}"
            }
        except Exception as e:
            print(f"[Reflex] Screenshot notice: {e}")

    # 11. Lock Screen
    if _RE_LOCK.match(clean):
        try:
            import platform, subprocess
            sys_name = platform.system()
            if sys_name == "Windows":
                subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            elif sys_name == "Darwin":
                subprocess.Popen("osascript -e 'tell application \"System Events\" to keystroke \"q\" using {control down, command down}' 2>/dev/null || pmset displaysleepnow", shell=True)
            else:
                subprocess.Popen("loginctl lock-session 2>/dev/null || xdg-screensaver lock 2>/dev/null || gnome-screensaver-command -l 2>/dev/null || true", shell=True)
            return {
                "handled": True,
                "action": "lock_screen",
                "reply": "Screen locked.",
                "sub_text": "Locked workstation"
            }
        except Exception as e:
            print(f"[Reflex] Lock screen notice: {e}")

    # 12. Safe Deterministic Math Calculator (< 1ms, zero hallucination)
    math_match = _RE_MATH.match(clean)
    if math_match:
        expr = math_match.group(1).strip()
        if re.match(r'^[\d\.\s\+\-\*\/\(\)\%\^]+$', expr) or re.match(r'^\d+(?:\.\d+)?\s*%\s*of\s*\d+(?:\.\d+)?$', expr, re.I):
            try:
                expr_calc = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)', r'(\1 / 100.0 * \2)', expr, flags=re.I)
                expr_calc = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1 / 100.0)', expr_calc)
                expr_calc = expr_calc.replace('^', '**')
                code = compile(expr_calc, "<math>", "eval")
                if not code.co_names:
                    val = eval(code, {"__builtins__": {}}, {})
                    if isinstance(val, (int, float)):
                        fmt_val = f"{val:,.4f}".rstrip('0').rstrip('.') if isinstance(val, float) else f"{val:,}"
                        return {
                            "handled": True,
                            "action": "quick_math",
                            "reply": f"The answer is {fmt_val}.",
                            "sub_text": f"{expr} = {fmt_val}"
                        }
            except Exception:
                pass

    return None
