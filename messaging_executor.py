#!/usr/bin/env python3
"""
messaging_executor.py  --  Category-bound executor (PROOF OF CONCEPT)
Tilux dev spec: collapse "decide -> perceive -> act" into "classify -> execute".

Design contract
---------------
1. ONE process per task. No model round-trips on the happy path.
2. Ground truth = instant OS queries (xdotool / wmctrl). Never a cache.
3. Perception + action in the SAME script (batch perception, per roadmap P2).
4. Every failure appended to failure_log.json (persistent logging, roadmap P3).
5. Executor is dumb + deterministic. The model only classifies intent and
   handles exceptions -- it is NOT in the execution loop.

Invocation (from the AI layer, detached):
    python3 messaging_executor.py '{"contact":"mine","message":"I am late"}'
"""
import os, sys, json, time, subprocess
from datetime import datetime

# Executor is launched detached; make sure it owns a display context.
os.environ.setdefault("DISPLAY", ":0")

# ---------------- Config (data, not decisions) ----------------
APP_ID        = "WebApp-Whatsapp4319"
LAUNCH_CMD    = (
    'microsoft-edge-stable --app="https://web.whatsapp.com/" '
    '--class=WebApp-Whatsapp4319 --name=WebApp-Whatsapp4319 '
    '--user-data-dir=/home/tilux/.local/share/ice/profiles/Whatsapp4319'
)
WINDOW_HINTS  = ("whatsapp",)
LOAD_MARKERS  = ("search", "chats", "type a message")  # OCR says "UI ready"
LOAD_TIMEOUT  = 20      # seconds to wait for UI
SEC_SETTLE    = 0.4     # small settle between keystrokes
LOG_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failure_log.json")


# ---------------- Layer 0: OS ground truth (5 ms, $0, no model) ----------------
def sh(cmd, timeout=5):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()

def window_id(app_id):
    """Ground-truth: does a window with this class exist? Returns id or ''."""
    ids = sh(["xdotool", "search", "--class", app_id])
    return ids.splitlines()[0] if ids else ""

def active_window_title():
    return sh(["xdotool", "getactivewindow", "getwindowname"]).lower()

def is_focused(app_id):
    return app_id.lower() in active_window_title()

def launch_app():
    subprocess.Popen(["bash", "-lc", f"nohup {LAUNCH_CMD} >/dev/null 2>&1 & disown"])

def focus_window(wid):
    for _ in range(3):
        sh(["xdotool", "windowactivate", "--sync", wid])
        sh(["wmctrl", "-i", "-a", wid])
        time.sleep(0.4)
        if is_focused(APP_ID):
            return True
    return False


# ---------------- Layer 1: Perception (batch, in-process) ----------------
def read_screen():
    import pyautogui, pytesseract
    return pytesseract.image_to_string(pyautogui.screenshot()).lower()

def wait_for_ui(markers, timeout=LOAD_TIMEOUT):
    """OCR poll loop. Batch perception lives here -- check AND act in one process."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            txt = read_screen()
        except Exception:
            time.sleep(1.0); continue
        if any(m in txt for m in markers):
            return True
        time.sleep(1.5)
    return False


# ---------------- Layer 2: Action (keyboard shortcuts + clipboard) ----------------
def paste_text(text):
    import pyperclip, pyautogui
    pyperclip.copy(text)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")

def send_message(contact, message):
    import pyautogui
    # WhatsApp Desktop search shortcut
    pyautogui.hotkey("ctrl", "alt", "/"); time.sleep(SEC_SETTLE)
    paste_text(contact);                    time.sleep(SEC_SETTLE)
    pyautogui.press("enter");               time.sleep(0.8)   # open the chat
    paste_text(message);                    time.sleep(SEC_SETTLE)
    pyautogui.press("enter")


# ---------------- Layer 3: Persistent failure logging (roadmap P3) ----------------
def log_failure(step, error, context):
    entry = {"ts": datetime.now().isoformat(), "category": "messaging",
             "step": step, "error": str(error), "context": context}
    try:
        data = json.load(open(LOG_PATH)) if os.path.exists(LOG_PATH) else []
    except Exception:
        data = []
    data.append(entry)
    json.dump(data, open(LOG_PATH, "w"), indent=2)


# ---------------- Orchestrator: classify -> execute ----------------
def execute(task):
    contact, message = task["contact"], task["message"]

    # ground truth, no cache
    wid = window_id(APP_ID)
    if not wid:
        launch_app()
        for _ in range(10):
            time.sleep(1.0)
            wid = window_id(APP_ID)
            if wid: break
    if not wid:
        log_failure("launch", "window never appeared", task)
        return {"ok": False, "reason": "app_not_up"}

    if not focus_window(wid):
        log_failure("focus", "could not focus window", {"wid": wid, **task})
        return {"ok": False, "reason": "focus_failed"}

    if not wait_for_ui(LOAD_MARKERS):
        log_failure("load", "UI markers not detected", {"wid": wid, **task})
        return {"ok": False, "reason": "ui_not_ready"}

    try:
        send_message(contact, message)
    except Exception as e:
        log_failure("send", e, task)
        return {"ok": False, "reason": "send_error", "error": str(e)}

    return {"ok": True, "contact": contact}


if __name__ == "__main__":
    task = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"contact": "mine", "message": "test"}
    print(json.dumps(execute(task)))
