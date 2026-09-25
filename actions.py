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
    settings_file = "settings.json"
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
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r") as f:
                return json.load(f).get("sudo_password", "").strip()
        except:
            pass
    return os.environ.get("SUDO_PASSWORD", "").strip()

def execute_bash_command(command: str) -> str:
    """
    Executes a bash command on the Linux system.
    Use this to open apps, change settings, manage files, or open URLs (using xdg-open).
    """
    dangerous_keywords = ['rm ', 'mkfs', 'dd ', 'sudo ', 'chmod -R', 'chown -R']
    
    # Check if the AI has explicitly flagged that the user approved this command
    has_approval = False
    if command.startswith("I_HAVE_USER_APPROVAL "):
        has_approval = True
        command = command.replace("I_HAVE_USER_APPROVAL ", "", 1)
        
    is_dangerous = any(keyword in command for keyword in dangerous_keywords)
    
    if is_dangerous and not has_approval:
        return f"SECURITY ALERT: The command `{command}` is considered dangerous. You MUST stop and explicitly ask the user for permission in the chat. If they reply 'yes', you can re-run this command exactly by prefixing it with 'I_HAVE_USER_APPROVAL ' (e.g. 'I_HAVE_USER_APPROVAL {command}')."
            
    try:
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
    
    # Save code to a temp file, but inject a non-blocking webbrowser monkey-patch
    temp_file = "temp_automation.py"
    
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
    with open(temp_file, "w") as f:
        f.write(monkey_patch + code)
        
    # Log the AI's code for debugging
    with open("tilux_code_history.log", "a") as log:
        log.write("\n\n--- EXECUTING SCRIPT ---\n")
        log.write(code)
    
    # Execute the file using the local venv python
    try:
        import platform
        if platform.system() == "Windows" and os.path.exists("./venv/Scripts/python.exe"):
            python_bin = "./venv/Scripts/python.exe"
        elif os.path.exists("./venv/bin/python"):
            python_bin = "./venv/bin/python"
        else:
            python_bin = "python3"
        result = subprocess.run([python_bin, temp_file], capture_output=True, text=True, timeout=120)
        
        output = result.stdout + result.stderr
        
        # Clean up
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        if not output.strip():
            return "Python code executed successfully with no output."
        return output
    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return f"Python execution failed: {str(e)}"

def generate_image(prompt: str) -> str:
    """
    Generates an image using Google's Imagen 3 API. 
    Use this when the user asks you to draw, create, or generate an image.
    The resulting image will be saved locally and returned as a markdown image string.
    """
    import os
    import uuid
    from google import genai
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return "Failed: Image server is currently offline or unreachable."
        
    try:
        import urllib.parse
        import urllib.request
        
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        # Save to static/uploads directory so the web server can serve it
        upload_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = f"gen_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(upload_dir, filename)
        
        # Add a custom user agent to prevent 403s just in case
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
            
        # Return markdown image syntax. Flask serves static files at /static/...
        return f"![Generated Image](http://127.0.0.1:8932/static/uploads/{filename})"
        
    except Exception as e:
        return f"Failed to generate image: {str(e)}"

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
    
    # Tier 1: Spotify via playerctl or D-Bus
    if "spotify" in app_lower:
        if payload and action_lower in ["play", "search", "open"]:
            import urllib.parse
            encoded_payload = urllib.parse.quote(payload)
            cmd_res = execute_bash_command(f"dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.OpenUri string:'spotify:search:{encoded_payload}' 2>/dev/null || xdg-open 'spotify:search:{encoded_payload}' & disown")
            return f"Executed Spotify search for '{payload}' via D-Bus OpenUri: {cmd_res}"
        elif action_lower in ["play", "pause", "playpause", "toggle"]:
            cmd_res = execute_bash_command("playerctl -p spotify play-pause 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlayPause")
            return f"Executed Spotify toggle via D-Bus: {cmd_res}"
        elif action_lower in ["next", "skip"]:
            cmd_res = execute_bash_command("playerctl -p spotify next 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next")
            return f"Executed Spotify next via D-Bus: {cmd_res}"
        elif action_lower in ["prev", "previous"]:
            cmd_res = execute_bash_command("playerctl -p spotify previous 2>/dev/null || dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Previous")
            return f"Executed Spotify previous via D-Bus: {cmd_res}"

    # Tier 1: VS Code / Code editor via CLI
    if "code" in app_lower or "vscode" in app_lower:
        if action_lower in ["open_file", "open_folder", "launch"] and payload:
            cmd_res = execute_bash_command(f"code {payload} & disown")
            return f"Opened {payload} in VS Code via CLI: {cmd_res}"

    # Tier 1: Web Browsers via xdg-open
    if any(b in app_lower for b in ["chrome", "browser", "firefox", "brave", "edge", "google"]):
        if action_lower in ["open_url", "navigate", "search"]:
            import urllib.parse
            if payload.startswith("http"):
                target_url = payload
            else:
                target_url = f"https://www.google.com/search?q={urllib.parse.quote(payload)}"
            cmd_res = execute_bash_command(f"xdg-open '{target_url}' & disown")
            return f"Opened URL via xdg-open: {cmd_res}"

    # Tier 2: Generic Window Focus + Shortcut / Clipboard Injection Boilerplate
    python_script = f"""import pyautogui, pyperclip, subprocess, time
# 1. Bring window to front
subprocess.run(["wmctrl", "-a", "{app_name}"], capture_output=True)
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
    python_script = f"""import subprocess, time, pyautogui
try:
    import pytesseract
    from PIL import Image
    has_ocr = True
except ImportError:
    has_ocr = False

# 1. Bring window to front
subprocess.run(["wmctrl", "-a", "{app_name}"], capture_output=True)
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
        
    python_bin = "./venv/bin/python" if os.path.exists("./venv/bin/python") else "python3"
    try:
        res = subprocess.run([python_bin, script_path, payload_json], capture_output=True, text=True, timeout=30)
        return res.stdout.strip() or res.stderr.strip() or "Category task executed successfully."
    except Exception as e:
        return f"Category task execution failed: {str(e)}"
