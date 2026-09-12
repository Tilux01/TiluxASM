import pyautogui
import pyperclip
import time
import subprocess
import re

# Open the page
subprocess.Popen(['xdg-open', 'https://www.linkedin.com/mynetwork/invitation-manager/'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(6) # wait for page to load

# Copy everything
pyautogui.hotkey('ctrl', 'a')
time.sleep(0.5)
pyautogui.hotkey('ctrl', 'c')
time.sleep(0.5)

# Read clipboard
text = pyperclip.paste()
lines = text.split('\n')
names = []

# Typical LinkedIn UI has the person's name followed by their headline, then mutual connections, then "Ignore" and "Accept" buttons
# A simple heuristic: look for "Accept" and the name is usually 2-4 lines above it.
for i, line in enumerate(lines):
    if line.strip() == "Accept":
        # The name is usually a few lines up, before "Connect", headline, etc.
        # Let's grab the 4 lines above it
        chunk = lines[max(0, i-6):i]
        names.append(chunk)

print("RAW CLIPBOARD SNIPPET (First 500 chars):", text[:500])
print("FOUND CHUNKS NEAR ACCEPT BUTTONS:")
for chunk in names:
    print("---")
    for c in chunk:
        if c.strip():
            print(c.strip())

