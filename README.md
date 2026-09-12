# Tilux ASM

> **An autonomous cross-platform AI agent framework for system automation, web interaction, desktop software control, and task planning.**

---

## Overview

**Tilux ASM** is an intelligent automation platform engineered to execute multi-step user tasks across web browsers, native desktop applications, and operating system environments. Powered by natural language planning and robust action handlers, **Tilux ASM** acts as a virtual desktop assistant capable of parsing complex instructions, automating browser workflows, handling file operations, and executing shell scripts across Linux, Windows, and macOS.

---

## Key Features

- **Cross-Platform System Automation:** Interacts with native operating system applications, file managers, and system processes across Linux, Windows, and macOS.
- **Autonomous Task Planning:** Breaks down complex, multi-step natural language instructions into ordered system execution steps.
- **Web & Native Desktop Control:** Combines web DOM automation with native desktop GUI controls for seamless interaction between web browsers and desktop software.
- **Speech Recognition & Voice Commands:** Supports voice instruction input and speech response synthesis for hands-free system operation.
- **Persistent Agent Memory:** Maintains task history, user context, and action logs across sessions to optimize repeated task execution.
- **Web Dashboard & Remote Interface:** Features a web management portal for real-time task monitoring, agent status tracking, and manual intervention.

---

## Architecture & Tech Stack

- **Core Agent Engine:** Python 3, Async Task Planner, Custom Action Dispatcher (`brain.py`, `actions.py`, `main.py`)
- **Backend API & Web Server:** Python Flask / FastAPI (`server.py`)
- **Speech & Voice Processing:** Python SpeechRecognition & Text-To-Speech (TTS) Modules (`voice.py`)
- **Web Frontend:** HTML5, CSS3, JavaScript, WebSockets / REST API (`frontend/`, `static/`, `templates/`)
- **System Integration:** Subprocess execution, OS API bindings, cross-platform shell commands

---

## Repository Structure

```
Tilux ASM/
├── main.py              # Application entry point and main agent control loop
├── brain.py             # Task planning engine and LLM integration
├── actions.py           # System action handlers (browser, GUI, file system)
├── voice.py             # Speech recognition and voice interaction module
├── server.py            # Local backend server interface
├── install.py           # Environment setup and dependency installer
├── requirements.txt     # Python dependencies
├── templates/           # Web dashboard HTML templates
├── static/              # Frontend static assets (CSS, JS, images)
└── frontend/            # UI components and client interface
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- Linux, macOS, or Windows
- Microphone and speakers (optional, for voice interaction)

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Tilux01/TiluxASM.git
   cd TiluxASM
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration:**
   - Configure your API keys in `.env` (if applicable) and configure your system preferences.

5. **Run the Application:**
   ```bash
   python3 main.py
   # Or start the web server interface:
   python3 server.py
   ```

---

## Author

* **Adekola Israel** ([@Tilux01](https://github.com/Tilux01))
* **Portfolio:** [portfolio-jet-phi-32.vercel.app](https://portfolio-jet-phi-32.vercel.app/)
* **LinkedIn:** [Adekola Israel](https://www.linkedin.com/in/israel-adekola-a873872)

---

## License

This project is open-source and available under the [MIT License](LICENSE).
