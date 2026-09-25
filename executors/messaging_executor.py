import sys
import json
import time
import os
import subprocess

FAILURE_LOG = "failure_log.json"

def log_failure(step: str, error: str, context: dict):
    entry = {
        "timestamp": time.time(),
        "step": step,
        "error": error,
        "context": context
    }
    logs = []
    if os.path.exists(FAILURE_LOG):
        try:
            with open(FAILURE_LOG, "r") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    logs.append(entry)
    with open(FAILURE_LOG, "w") as f:
        json.dump(logs, f, indent=4)

def run_messaging_task(data: dict) -> dict:
    contact = data.get("contact", "")
    message = data.get("message", "")
    app = data.get("app", "whatsapp").lower()
    
    context = {"contact": contact, "message": message, "app": app}
    
    # Layer 0: OS Ground-Truth Window Query (Cross-Platform)
    import platform
    os_type = platform.system()
    try:
        window_found = False
        if os_type == "Linux":
            cmd = "xdotool search --onlyvisible --class 'Whatsapp' 2>/dev/null || wmctrl -l | grep -i whatsapp"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.stdout.strip():
                window_found = True
            if not window_found:
                subprocess.Popen(["xdg-open", "https://web.whatsapp.com"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
            subprocess.run(["wmctrl", "-a", "WhatsApp"], capture_output=True)
        elif os_type == "Darwin": # macOS
            subprocess.Popen(["open", "https://web.whatsapp.com"], start_new_session=True)
            time.sleep(2)
            subprocess.run(["osascript", "-e", 'tell application "WhatsApp" to activate'], capture_output=True)
        elif os_type == "Windows": # Windows
            subprocess.Popen(["cmd", "/c", "start", "https://web.whatsapp.com"], shell=True)
            time.sleep(2)
        time.sleep(0.3)
    except Exception as e:
        log_failure("layer_0_ground_truth", str(e), context)
        return {"status": "error", "message": f"Ground truth focus failed: {str(e)}"}
    
    # Layer 1: In-Process OCR Perception Check
    has_ocr = False
    try:
        import pytesseract
        import mss
        from PIL import Image
        has_ocr = True
    except ImportError:
        has_ocr = False
        
    if has_ocr:
        ocr_start = time.time()
        loaded = False
        try:
            with mss.MSS() as sct:
                while time.time() - ocr_start < 4.0:
                    sct_img = sct.grab(sct.monitors[0])
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    text = pytesseract.image_to_string(img).lower()
                    if "search" in text or "chats" in text or "message" in text:
                        loaded = True
                        break
                    time.sleep(0.8)
        except Exception:
            pass
            
    # Layer 2: Action - CDP / Clipboard & Keystrokes
    # Try CDP injection first if port 9222 is active (Wayland proof)
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:9222/json/version", timeout=1) as resp:
            if resp.status == 200:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    b = p.chromium.connect_over_cdp("http://localhost:9222")
                    ctx = b.contexts[0]
                    pg = [p_item for p_item in ctx.pages if "whatsapp" in p_item.url.lower()]
                    pg = pg[0] if pg else (ctx.pages[0] if ctx.pages else b.new_page())
                    pg.bring_to_front()
                    time.sleep(0.5)
                    
                    # 1. Search for contact
                    search_box = pg.locator('div[contenteditable="true"][data-tab="3"], input[aria-label*="Search"]').first
                    if search_box.is_visible():
                        search_box.click()
                        search_box.fill(contact)
                        time.sleep(0.8)
                        pg.keyboard.press("Enter")
                        time.sleep(1.0)
                    else:
                        pg.keyboard.press("Control+Alt+/")
                        time.sleep(0.3)
                        pg.keyboard.type(contact)
                        pg.keyboard.press("Enter")
                        time.sleep(1.0)
                        
                    # 2. Type & send message in message composer
                    msg_box = pg.locator('div[contenteditable="true"][data-tab="10"], div[title*="Type a message"]').first
                    if msg_box.is_visible():
                        msg_box.click()
                        # Use evaluate to safely inject multi-line text into React contenteditable
                        pg.evaluate("""([text]) => {
                            const el = document.querySelector('div[contenteditable="true"][data-tab="10"]') || document.querySelector('div[title*="Type a message"]');
                            if (el) {
                                el.focus();
                                document.execCommand('insertText', false, text);
                            }
                        }""", [message])
                        time.sleep(0.5)
                        pg.keyboard.press("Enter")
                    else:
                        pg.keyboard.type(message)
                        pg.keyboard.press("Enter")
                        
                    return {"status": "success", "message": f"Successfully sent message to {contact} via Wayland CDP"}
    except Exception as e:
        pass

    try:
        import pyautogui
        import pyperclip
        
        pyautogui.hotkey('ctrl', 'alt', '/')
        time.sleep(0.2)
        
        pyperclip.copy(contact)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(0.5)
        
        pyperclip.copy(message)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)
        pyautogui.press('enter')
        
        return {"status": "success", "message": f"Successfully sent message to {contact}"}
    except Exception as e:
        import pyperclip
        pyperclip.copy(message)
        log_failure("layer_2_action", str(e), context)
        return {"status": "error", "message": f"Action failed: {str(e)}. Message text has been copied to your clipboard!"}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            payload = json.loads(sys.argv[1])
        except Exception:
            payload = {}
    else:
        payload = {}
        
    output = run_messaging_task(payload)
    print(json.dumps(output))
