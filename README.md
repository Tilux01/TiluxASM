# Tilux ASM

---

## Overview

**Tilux ASM** isn't just a chatbot, it is an immensely powerful, fully autonomous desktop AI agent that takes complete control of your operating system to execute complex workflows. Powered by advanced natural language planning and robust action handlers, Tilux ASM acts as your virtual software engineer, data analyst, and personal assistant. 

Whether you need to write and execute code, deeply research topics across the web, manipulate the file system, or control native desktop applications, Tilux ASM autonomously plans and executes every step until the goal is achieved.

---

## Limitless Capabilities

- **Deep System & Terminal Control:** Tilux doesn't just give you code; it executes it. It seamlessly controls your bash/cmd terminal to install packages, run scripts, modify system configurations, and parse error logs to debug its own mistakes.
- **Autonomous Web Browsing (Playwright):** Tilux can invisibly spawn Chromium browsers to scrape websites, extract complex data, bypass captchas, and analyze web DOMs, all without manual intervention.
- **Remote Mobile Control:** Control your PC from anywhere in the world. Using the [Tilux ASM Web Remote](https://tilux-asm.vercel.app), you can text or speak commands into your phone, and watch as your PC executes the tasks and streams the live results directly back to your mobile screen.
- **Advanced State Memory:** Tilux remembers your past sessions, system states, and preferences. It writes its own context files to disk so it can resume massive projects exactly where it left off.
- **Voice Synthesis (Edge TTS):** Complete hands-free mode. Speak naturally to the AI, and it will respond with ultra-realistic, low-latency synthesized speech as it works.

---

## The Mobile Web Remote

You don't need to be at your desk to control your PC. Tilux ASM features a beautiful, ultra-responsive mobile interface hosted directly on the cloud.

**Access the Remote Here:** [https://tilux-asm.vercel.app](https://tilux-asm.vercel.app)

**How it works:**
1. Your PC backend spins up a secure remote tunnel.
2. You open the web link on your phone, scan the QR code (or enter your pair token), and you instantly have a live connection to your PC's terminal and AI brain.
3. Any command you send from your phone is executed natively on your Desktop.

---

## Architecture & Tech Stack

- **Core Agent Engine:** Python 3, Async Task Planner, Custom Action Dispatcher (`brain.py`, `actions.py`)
- **Backend API & Web Server:** Flask SocketIO (`server.py`)
- **Browser Automation:** Microsoft Playwright
- **Desktop Client:** ElectronJS, Node.js

---

## Installation & Setup

### System Prerequisites (Windows / Linux / macOS)
1. **Python 3.11 or 3.12 (64-bit Strictly Required):**
   - Download from [python.org](https://www.python.org/downloads/).
   - ⚠️ **Windows Notice:** When installing Python, you **MUST check the box: "Add python.exe to PATH"**.
   - Make sure you install the **64-bit** version (AI speech and PyTorch models do not support 32-bit).
2. **Node.js (v18 or v20+):**
   - Download from [nodejs.org](https://nodejs.org/).
3. **Microsoft Visual C++ Redistributable (Windows Only):**
   - Install the x64 C++ runtime from [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe) (needed for AI inference).
4. **Optional Media Tools (Windows):**
   - In PowerShell / Terminal: `winget install Gyan.FFmpeg UB-Mannheim.TesseractOCR`
   - *(Tilux ASM includes automatic fallbacks if FFmpeg or Tesseract are not installed).*

---

### Step-by-Step Installation:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Tilux01/TiluxASM.git
   cd TiluxASM
   ```

2. **Run the Diagnostic Tool (Windows Environment Test):**
   On Windows, simply double-click **`diagnose_windows.bat`** (or run `python diagnose_windows.py`).
   This tests your Python version, PATH, 64-bit mode, C++ runtimes, and dependencies in 5 seconds!

3. **Install Dependencies & Offline AI Models:**
   ```bash
   python install.py
   ```
   *(This automatically creates a virtual environment, installs all Python packages with automatic fallbacks, and downloads the required offline AI engines).*

4. **Launch the Desktop Client:**
   ```bash
   cd tilux-client
   npm install
   npm start
   ```

5. **Build Standalone Desktop Installers (`.exe`, `.AppImage`, `.dmg`):**
   ```bash
   cd tilux-client
   npm run build:win      # For Windows NSIS installer (.exe)
   npm run build:linux    # For Linux AppImage / deb / pacman
   npm run build:mac      # For macOS DMG
   ```
   *(Installers will be generated in `tilux-client/dist/`)*

---

## Author

* **Tilux** ([@Tilux01](https://github.com/Tilux01)) — Adekola Israel, Software Engineer in Ogbomoso (SQI College of ICT graduate)
* **Portfolio:** [portfolio-jet-phi-32.vercel.app](https://portfolio-jet-phi-32.vercel.app/)
* **LinkedIn:** [Adekola Israel](https://www.linkedin.com/in/israel-adekola-a873872)

---

## License

This project is open-source and available under the [MIT License](LICENSE).
