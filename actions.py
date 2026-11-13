import subprocess
from memory import save_fact, forget_fact

def save_to_memory(fact_or_rule: str) -> str:
    """
    Saves a rule, preference, or fact about the user to long-term memory.
    Use this when the user tells you to remember something or gives you a new rule.
    """
    return save_fact(fact_or_rule)

def remove_from_memory(fact_or_rule: str) -> str:
    """
    Removes a rule or fact from memory if the user tells you to forget it.
    """
    return forget_fact(fact_or_rule)

def update_settings(ai_tone: str = None, tts_enabled: bool = None, tts_voice: str = None, tts_speed: str = None, sudo_password: str = None) -> str:
    """
    Updates the Tilux app settings in settings.json dynamically.
    Use this when the user asks to change the AI tone, enable/disable voice, change TTS voice or speed, or update sudo password.
    """
    import json, os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.environ.get("TILUX_USER_DATA_DIR") or base_dir
    settings_file = os.path.join(data_dir, "settings.json")
    if not os.path.exists(settings_file):
        cand = os.path.join(base_dir, "settings.json")
        if os.path.exists(cand):
            try:
                import shutil
                shutil.copy2(cand, settings_file)
            except Exception:
                pass
    data = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                data = json.load(f)
        except:
            pass
            
    updated = []
    if ai_tone is not None:
        data["ai_tone"] = ai_tone
        updated.append(f"AI Tone set to '{ai_tone}'")
    if tts_enabled is not None:
        data["tts_enabled"] = tts_enabled
        updated.append(f"TTS Enabled set to {tts_enabled}")
    if tts_voice is not None:
        data["tts_voice"] = tts_voice
        updated.append(f"TTS Voice set to '{tts_voice}'")
    if tts_speed is not None:
        data["tts_speed"] = tts_speed
        updated.append(f"TTS Speed set to '{tts_speed}'")
    if sudo_password is not None:
        data["sudo_password"] = sudo_password
        updated.append("Sudo Password updated")
        
    with open(settings_file, "w") as f:
        json.dump(data, f, indent=4)
        
    return "Settings updated successfully: " + ", ".join(updated)


def get_sudo_password():
    import json, os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.environ.get("TILUX_USER_DATA_DIR") or base_dir
    for cand in [os.path.join(data_dir, "settings.json"), os.path.join(base_dir, "settings.json")]:
        if os.path.exists(cand):
            try:
                with open(cand, "r") as f:
                    return json.load(f).get("sudo_password", "").strip()
            except:
                pass
    return os.environ.get("SUDO_PASSWORD", "").strip()

def execute_bash_command(command: str) -> str:
    """
    Executes a system shell command (PowerShell on Windows, bash on Linux/macOS).
    Use this to open apps, manage files, or inspect system state.
    """
    dangerous_keywords = ['rm ', 'mkfs', 'dd ', 'sudo ', 'chmod -R', 'chown -R']
    
    # Check God Mode state
    import json, os, platform
    god_mode = False
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r") as f:
                god_mode = json.load(f).get("god_mode", False)
        except: pass
        
    # Check if the AI has explicitly flagged that the user approved this command
    has_approval = False
    if command.startswith("I_HAVE_USER_APPROVAL ") or god_mode:
        has_approval = True
        command = command.replace("I_HAVE_USER_APPROVAL ", "", 1)
        
    is_dangerous = any(keyword in command for keyword in dangerous_keywords)
    
    if is_dangerous and not has_approval:
        return f"SECURITY ALERT: The command `{command}` is considered dangerous. You MUST stop and explicitly ask the user for permission in the chat. If they reply 'yes', you can re-run this command exactly by prefixing it with 'I_HAVE_USER_APPROVAL ' (e.g. 'I_HAVE_USER_APPROVAL {command}')."
            
    try:
        if platform.system() == "Windows":
            from os_protocols import WindowsProtocol
            return WindowsProtocol.execute_command(command)

        # Properly detach background tasks so they don't block or die on script exit
        if command.strip().endswith("&"):
            cmd_clean = command.strip()[:-1].strip()
            subprocess.Popen(cmd_clean, shell=True, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "App launched successfully in the background."
            
        is_sudo = "sudo " in command or command.startswith("sudo") or "pkexec " in command
        sudo_pass = get_sudo_password()

        if is_sudo:
            if command.startswith("pkexec "):
                command = command.replace("pkexec ", "sudo ", 1)
            
            if sudo_pass:
                if not command.startswith("sudo -S"):
                    if "sudo " in command:
                        cmd_parts = command.split("sudo ", 1)
                        command = f"{cmd_parts[0]}sudo -S -p '' {cmd_parts[1]}"
                    else:
                        command = f"sudo -S -p '' {command}"
                
                result = subprocess.run(
                    command,
                    shell=True,
                    input=f"{sudo_pass}\n",
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120
                )
            else:
                return (
                    "AUTHENTICATION REQUIRED: This command requires administrator (sudo) privileges, "
                    "but no PC Sudo Password is set in Tilux Settings. "
                    "Please ask the user to enter their PC Sudo Password in Settings or via the Remote Auth prompt."
                )
        else:
            result = subprocess.run(command, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)

        output = result.stdout + result.stderr
        
        import re
        # Strip massive base64 or encoded strings to prevent token bloat
        output = re.sub(r'[A-Za-z0-9+/=]{2000,}', '[BASE64_MEDIA_DATA_REMOVED]', output)
        
        if len(output) > 40000:
            output = output[:40000] + "\n\n... [OUTPUT TRUNCATED BY SYSTEM TO PREVENT TOKEN OVERFLOW]"
            
        if not output.strip():
            return "Command executed successfully."
        return output
    except Exception as e:
        return f"Failed to execute command: {str(e)}"

def execute_python_code(code: str) -> str:
    """
    Executes a snippet of Python code by saving it to a temporary file and running it.
    This gives the AI ultimate power to use PyAutoGUI, requests, selenium, etc.
    """
    import os
    import sys
    import tempfile
    import uuid
    import subprocess
    import re

    # Save code to a temp file in the OS temp directory to avoid CWD permission errors
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, f"tilux_auto_{uuid.uuid4().hex[:8]}.py")

    monkey_patch = """import webbrowser, subprocess, platform
def _mock_open(url, *args, **kwargs):
    os_name = platform.system()
    if os_name == "Windows":
        cmd = ['cmd', '/c', 'start', url]
    elif os_name == "Darwin":
        cmd = ['open', url]
    else:
        cmd = ['xdg-open', url]
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True
webbrowser.open = _mock_open
webbrowser.open_new = _mock_open
webbrowser.open_new_tab = _mock_open

"""
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(monkey_patch + code)
    except Exception as e:
        return f"Failed to write automation script: {e}"

    # Log the AI's code for debugging into user data or temp directory
    log_dir = os.environ.get("TILUX_USER_DATA_DIR") or temp_dir
    log_path = os.path.join(log_dir, "tilux_code_history.log")
    try:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write("\n\n--- EXECUTING SCRIPT ---\n")
            log.write(code)
    except Exception:
        pass

    # Execute using the currently active Python executable (bundled runtime or venv)
    try:
        python_bin = sys.executable if sys.executable else "python3"
        base_dir = os.path.dirname(os.path.abspath(__file__))
        env = os.environ.copy()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{base_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = base_dir

        result = subprocess.run([python_bin, temp_file], capture_output=True, text=True, timeout=120, env=env)
        output = result.stdout + result.stderr

        output = re.sub(r'[A-Za-z0-9+/=]{2000,}', '[BASE64_MEDIA_DATA_REMOVED]', output)
        if len(output) > 40000:
            output = output[:40000] + "\n\n... [OUTPUT TRUNCATED BY SYSTEM TO PREVENT TOKEN OVERFLOW]"

        if not output.strip():
            return "Python code executed successfully with no output."
        return output
    except Exception as e:
        return f"Python execution failed: {str(e)}"
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

def generate_image(prompt: str) -> str:
    """
    Generates an image using NanoGPT Qwen WAN 2.7 Image model (wan2.7-image).
    The resulting image is saved locally in static/uploads and returned as a markdown image string.
    Collects 1.3x cost and token usage from user wallet.
    """
    import os
    import json
    import uuid
    import base64
    import urllib.request
    try:
        from vault import get_credential
        import vault as credentials
    except ImportError:
        try:
            from credentials import get_credential
            import credentials
        except ImportError:
            get_credential = lambda k: os.getenv(k)
            credentials = None

    proxy_url = os.getenv("TILUX_PROXY_URL", "https://tilux-proxy.vercel.app").rstrip("/")
    direct_key = get_credential("NANOGPT_API_KEY") or get_credential("GEMINI_API_KEY") or os.getenv("NANOGPT_API_KEY") or os.getenv("GEMINI_API_KEY")

    payload = {
        "model": "wan2.7-image",
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1
    }
    data = json.dumps(payload).encode("utf-8")

    # 1. Try secure proxy endpoint first
    res_data = None
    try:
        client_secret = (credentials.get_credential("TILUX_CLIENT_SECRET") if credentials and hasattr(credentials, "get_credential") else None) or os.getenv("TILUX_CLIENT_SECRET", "tilux_sec_994b7e8832a1df04")
        proxy_endpoint = f"{proxy_url}/api/v1/images/generations"
        req = urllib.request.Request(
            proxy_endpoint,
            data=data,
            headers={
                "Authorization": f"Bearer {direct_key or client_secret}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
    except Exception as proxy_err:
        print(f"[Image Gen] Proxy generation notice: {proxy_err}")
        # 2. Fallback to direct NanoGPT if user provided a local API key
        if direct_key:
            try:
                direct_url = "https://nano-gpt.com/api/v1/images/generations"
                req = urllib.request.Request(
                    direct_url,
                    data=data,
                    headers={
                        "Authorization": f"Bearer {direct_key}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except Exception as direct_err:
                return f"Failed: Image generation failed ({direct_err})."
        else:
            return "Failed: Image server is currently unreachable or at capacity. Please try again later."

    if not res_data:
        return "Failed: No response from image generation service."

    try:
        raw_cost = res_data.get("cost", 0.03)
        img_items = res_data.get("data", [])
        if not img_items:
            return "Failed: No image data returned from image server."

        upload_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"gen_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(upload_dir, filename)

        first = img_items[0]
        if "b64_json" in first:
            b64_str = first["b64_json"]
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(b64_str))
        elif "url" in first:
            urllib.request.urlretrieve(first["url"], filepath)
        else:
            return "Failed: Unrecognized image data format."

        # Collect 1.3x of token/cost from user
        try:
            from usage_tracker import usage_tracker
            usage_tracker.record_image_usage(raw_cost=raw_cost, multiplier=1.3)
        except Exception:
            pass

        tunnel_base = os.getenv("TILUX_TUNNEL_URL", "http://127.0.0.1:8932").rstrip("/")
        return f"![Generated Image]({tunnel_base}/static/uploads/{filename})"

    except Exception as e:
        return f"Failed: Error processing generated image: {str(e)}"

def _local_remove_background(image_path_or_url: str, output_path: str) -> str:
    """Internal smart local fallback to extract clean transparent PNG from studio/gradient backgrounds."""
    from PIL import Image
    import numpy as np
    import urllib.request

    if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
        req = urllib.request.Request(image_path_or_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            im = Image.open(resp)
            im.load()
    else:
        im = Image.open(image_path_or_url)
        im.load()

    im = im.convert("RGBA")
    w, h = im.size

    step_w = max(1, w // 25)
    step_h = max(1, h // 25)
    samples = []
    for x in range(0, w, step_w):
        samples.append(im.getpixel((x, 0)))
        samples.append(im.getpixel((x, h - 1)))
    for y in range(0, h, step_h):
        samples.append(im.getpixel((0, y)))
        samples.append(im.getpixel((w - 1, y)))

    bg_r = sum(c[0] for c in samples) / float(len(samples))
    bg_g = sum(c[1] for c in samples) / float(len(samples))
    bg_b = sum(c[2] for c in samples) / float(len(samples))

    arr = np.array(im, dtype=np.float32)
    dist = np.sqrt((arr[:, :, 0] - bg_r)**2 + (arr[:, :, 1] - bg_g)**2 + (arr[:, :, 2] - bg_b)**2)

    low_thresh = 28.0
    high_thresh = 58.0
    alpha = np.clip((dist - low_thresh) / (high_thresh - low_thresh) * 255.0, 0, 255).astype(np.uint8)

    arr[:, :, 3] = alpha
    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    result.save(output_path, "PNG")
    return output_path

def remove_image_background(image_path_or_url: str, output_path: str = None) -> str:
    """
    Removes the background from an image to produce a clean transparent PNG asset.
    Saves the clean transparent PNG locally and returns the local file path.
    """
    import os
    import uuid
    import urllib.request
    try:
        from vault import get_credential
    except ImportError:
        try:
            from credentials import get_credential
        except ImportError:
            get_credential = lambda k: os.getenv(k)

    if not output_path:
        upload_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        output_path = os.path.join(upload_dir, f"nobg_{uuid.uuid4().hex[:8]}.png")

    accounts = []
    u1 = get_credential("CLOUDINARY_URL_1") or os.getenv("CLOUDINARY_URL_1")
    u2 = get_credential("CLOUDINARY_URL_2") or os.getenv("CLOUDINARY_URL_2")
    if u1: accounts.append(u1)
    if u2: accounts.append(u2)

    c1_name = get_credential("CLOUDINARY_CLOUD_NAME_1") or os.getenv("CLOUDINARY_CLOUD_NAME_1")
    c1_key = get_credential("CLOUDINARY_API_KEY_1") or os.getenv("CLOUDINARY_API_KEY_1")
    c1_sec = get_credential("CLOUDINARY_API_SECRET_1") or os.getenv("CLOUDINARY_API_SECRET_1")
    if c1_name and c1_key and c1_sec:
        accounts.append(f"cloudinary://{c1_key}:{c1_sec}@{c1_name}")

    c2_name = get_credential("CLOUDINARY_CLOUD_NAME_2") or os.getenv("CLOUDINARY_CLOUD_NAME_2")
    c2_key = get_credential("CLOUDINARY_API_KEY_2") or os.getenv("CLOUDINARY_API_KEY_2")
    c2_sec = get_credential("CLOUDINARY_API_SECRET_2") or os.getenv("CLOUDINARY_API_SECRET_2")
    if c2_name and c2_key and c2_sec:
        accounts.append(f"cloudinary://{c2_key}:{c2_sec}@{c2_name}")

    # If cloud accounts are configured, attempt online asset processing
    if accounts:
        try:
            import cloudinary
            import cloudinary.uploader
            for acc in accounts:
                try:
                    cloudinary.config(cloudinary_url=acc)
                    res = cloudinary.uploader.upload(
                        image_path_or_url,
                        background_removal="cloudinary_ai"
                    )
                    clean_url = res.get("secure_url") or res.get("url")
                    if clean_url:
                        urllib.request.urlretrieve(clean_url, output_path)
                        return output_path
                except Exception:
                    continue
        except Exception:
            pass

    # Seamless high-precision local fallback
    try:
        return _local_remove_background(image_path_or_url, output_path)
    except Exception as e:
        return f"Failed: Unable to process image cutout: {str(e)}"

def log_failed_action(action_description: str, reason: str) -> str:
    """
    Logs a failed action pattern or dead-end command to persistent memory
    so the AI does not repeat the same mistake in future sessions.
    """
    fact = f"[FAILED ROUTE]: Do not use '{action_description}' - Reason: {reason}"
    return save_fact(fact)

def smart_action_router(app_name: str, action: str, payload: str = "") -> str:
    """
    Determines and executes the fastest, most reliable execution route for an application task.
    Priority Hierarchy:
      Tier 1: CLI / D-Bus / API (Instant background execution)
      Tier 2: Window Focus + Native Keyboard Shortcut + Clipboard Injection
      Tier 3: Fallback warning for manual visual OCR
    """
    app_lower = app_name.lower().strip()
    action_lower = action.lower().strip()
    
    from os_protocols import OSProtocols

    # Media & Spotify via Native OS Protocols
    if any(m in app_lower for m in ["spotify", "music", "media", "player"]):
        if payload and action_lower in ["play", "search", "open"]:
            res = OSProtocols.play_spotify(payload)
            return res.get("output", f"Playing '{payload}' on Spotify.")
        elif action_lower in ["next", "skip"]:
            res = OSProtocols.media_next()
            return res.get("output", "Skipped to next track.")
        elif action_lower in ["prev", "previous"]:
            res = OSProtocols.media_prev()
            return res.get("output", "Returned to previous track.")
        elif action_lower in ["volume", "set_volume"]:
            raw_v = "".join(c for c in payload if c.isdigit()) or "80"
            res = OSProtocols.media_set_volume(int(raw_v))
            return res.get("output", f"Set volume to {raw_v}%.")
        else:
            res = OSProtocols.media_play_pause()
            return res.get("output", "Toggled media playback.")

    # Code Editor / VS Code
    if "code" in app_lower or "vscode" in app_lower:
        if action_lower in ["open_file", "open_folder", "launch"] and payload:
            res = OSProtocols.open_app("code", [payload])
            return res.get("output", f"Opened {payload} in VS Code.")

    # Web Browsers via Cross-Platform Opener
    if any(b in app_lower for b in ["chrome", "browser", "firefox", "brave", "edge", "google"]):
        if action_lower in ["open_url", "navigate", "search"]:
            target_url = payload if payload.startswith("http") else f"https://www.google.com/search?q={urllib.parse.quote(payload)}"
            res = OSProtocols.open_url(target_url)
            return res.get("output", f"Opened URL: {target_url}")

    # Direct App Launching
    if action_lower in ["launch", "open", "start"]:
        res = OSProtocols.open_app(app_name, [payload] if payload else None)
        return res.get("output", f"Launched {app_name}.")

    # Direct Window Focus
    if action_lower in ["focus", "activate", "switch_to"]:
        res = OSProtocols.focus_window(app_name)
        if res.get("status") == "success":
            return res.get("output", f"Focused {app_name}.")

    # Tier 2: Generic Window Focus + Shortcut / Clipboard Injection Boilerplate
    python_script = f"""import pyautogui, pyperclip, subprocess, time, platform
sys_name = platform.system()
if sys_name == "Linux":
    subprocess.run(["wmctrl", "-a", "{app_name}"], capture_output=True)
elif sys_name == "Darwin":
    subprocess.run(["osascript", "-e", 'tell application "{app_name}" to activate'], capture_output=True)
elif sys_name == "Windows":
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("{app_name}")
        if wins: wins[0].activate()
    except Exception:
        pass
time.sleep(0.3)
"""
    if payload:
        python_script += f"""
# 2. Clipboard injection for payload
pyperclip.copy("{payload}")
pyautogui.hotkey('ctrl', 'v')
"""
    if "submit" in action_lower or "search" in action_lower:
        python_script += "pyautogui.press('enter')\n"

    exec_res = execute_python_code(python_script)
    return f"Executed Tier 2 Focus & Shortcut sequence for {app_name}: {exec_res}"

def execute_batched_perception_action(app_name: str, expected_text: str, action_keys: str = "enter") -> str:
    """
    Executes a combined Perception-Action cycle in a single local Python loop without LLM round trips:
    1. Brings target app to focus.
    2. Takes a local screenshot and checks for expected_text using pytesseract OCR.
    3. If text is found (or after timeout), fires action_keys immediately.
    """
    python_script = f"""import subprocess, time, pyautogui, platform, os
try:
    import pytesseract
    from PIL import Image
    if platform.system() == "Windows":
        win_tess = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        if os.path.exists(win_tess):
            pytesseract.pytesseract.tesseract_cmd = win_tess
    has_ocr = True
except ImportError:
    has_ocr = False

# 1. Bring window to front
sys_name = platform.system()
if sys_name == "Linux":
    subprocess.run(["wmctrl", "-a", "{app_name}"], capture_output=True)
elif sys_name == "Darwin":
    subprocess.run(["osascript", "-e", 'tell application "{app_name}" to activate'], capture_output=True)
elif sys_name == "Windows":
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle("{app_name}")
        if wins: wins[0].activate()
    except Exception:
        pass
time.sleep(0.3)

found = False
start_time = time.time()
max_wait = 5.0 # seconds

# 2. Local perception loop
if has_ocr and "{expected_text}":
    try:
        import mss
        with mss.MSS() as sct:
            while time.time() - start_time < max_wait:
                sct_img = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                text = pytesseract.image_to_string(img)
                if "{expected_text}".lower() in text.lower():
                    found = True
                    break
                time.sleep(0.8)
    except Exception:
        pass

# 3. Fire action keystrokes
keys = "{action_keys}".split(",")
for k in keys:
    k = k.strip()
    if "+" in k:
        combo = k.split("+")
        pyautogui.hotkey(*combo)
    else:
        pyautogui.press(k)
    time.sleep(0.1)

print(f"Batched action completed for {app_name}. OCR Text Found: {{found}}")
"""
    return execute_python_code(python_script)

def execute_category_task(category: str, payload_json: str = "{}") -> str:
    """
    Executes a category task directly via dedicated executor scripts (messaging, media, file).
    This bypasses LLM multi-turn reasoning loops and completes routine tasks in 1 turn.
    """
    import os, json
    cat_clean = category.lower().strip()
    exec_dir = os.path.join(os.path.dirname(__file__), "executors")
    
    script_map = {
        "messaging": "messaging_executor.py",
        "chat": "messaging_executor.py",
        "whatsapp": "messaging_executor.py",
        "media": "media_executor.py",
        "music": "media_executor.py",
        "spotify": "media_executor.py",
        "file": "file_executor.py",
        "code": "file_executor.py"
    }
    
    script_name = script_map.get(cat_clean, "messaging_executor.py")
    script_path = os.path.join(exec_dir, script_name)
    
    if not os.path.exists(script_path):
        return f"Error: Category executor script {script_name} not found."
        
    python_bin = sys.executable if sys.executable else ("./venv/bin/python" if os.path.exists("./venv/bin/python") else "python3")
    try:
        res = subprocess.run([python_bin, script_path, payload_json], capture_output=True, text=True, timeout=30)
        return res.stdout.strip() or res.stderr.strip() or "Category task executed successfully."
    except Exception as e:
        return f"Category task execution failed: {str(e)}"
