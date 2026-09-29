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

You can compile Tilux ASM into a standalone desktop installer (`.exe`, `.AppImage`, `.dmg`) using the included Nuitka and Electron Builders!

### Build the Desktop Application:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Tilux01/TiluxASM.git
   cd TiluxASM
   ```

2. **Run the Nuitka Compiler (Linux/Mac/Windows):**
   *(Note: This translates the Python Brain into C code and compiles it into an unbreakable binary.)*
   ```bash
   pip install -r requirements.txt
   python build_nuitka.py
   ```

3. **Package the Electron UI:**
   ```bash
   cd tilux-client
   npm install
   npm run dist
   ```

*(Alternatively, you can just push to the `master` branch and GitHub Actions will automatically build the Windows, Linux, and Mac installers for you!)*

---

## Author

* **Adekola Israel** ([@Tilux01](https://github.com/Tilux01))
* **Portfolio:** [portfolio-jet-phi-32.vercel.app](https://portfolio-jet-phi-32.vercel.app/)
* **LinkedIn:** [Adekola Israel](https://www.linkedin.com/in/israel-adekola-a873872)

---

## License

This project is open-source and available under the [MIT License](LICENSE).
