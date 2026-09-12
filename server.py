from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import threading
import logging
import psutil
import subprocess
from brain import Brain
from voice import speak, listen
from memory import load_memory

# Disable Flask logging spam
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app) # Allow cross-origin requests from the Electron app

brain = Brain()

import json
import os


SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "tts_enabled": True,
    "tts_voice": "en-US-AriaNeural",
    "tts_speed": "+20%",
    "ai_tone": "Sassy Gen-Z",
    "setup_complete": False,
    "api_key": ""
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(DEFAULT_SETTINGS, f)
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return DEFAULT_SETTINGS

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": getattr(brain, "current_status", "Thinking..."),
        "events": getattr(brain, "current_events", [])
    })

@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    if request.method == "GET":
        return jsonify(load_settings())
    else:
        new_settings = request.json
        save_settings(new_settings)
        return jsonify({"status": "success"})

from flask import Response

@app.route("/api/install", methods=["GET"])
def install_system():
    def generate():
        import subprocess, sys, os
        python_bin = sys.executable
        if os.path.exists("./venv/bin/python"):
            python_bin = "./venv/bin/python"
        
        process = subprocess.Popen([python_bin, "install.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            yield f"data: {line}\n\n"
        process.stdout.close()
        process.wait()
        
        # Once complete, automatically set setup_complete to True
        settings = load_settings()
        settings["setup_complete"] = True
        save_settings(settings)
        
        yield "data: [INSTALL_COMPLETE]\n\n"
        
    return Response(generate(), mimetype='text/event-stream')

@app.route("/api/stop", methods=["POST"])
def stop_generation():
    brain.abort_flag = True
    return jsonify({"status": "stopped"})

@app.route("/api/chat", methods=["POST"])
def chat():
    if request.is_json:
        user_text = request.json.get("text", "").strip()
        attachments = []
    else:
        user_text = request.form.get("text", "").strip()
        attachments = request.files.getlist("attachments")
        
    if not user_text and not attachments:
        return jsonify({"error": "No input provided"}), 400
        
    import os, uuid
    from werkzeug.utils import secure_filename
    temp_dir = "/tmp/tilux_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    
    saved_files = []
    for f in attachments:
        if f.filename:
            filename = secure_filename(f.filename)
            filepath = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{filename}")
            f.save(filepath)
            saved_files.append(filepath)
            
    reply_data = brain.process_input(user_text, attachments=saved_files)
    reply_text = reply_data.get("reply", "").replace("—", "-")
    steps = reply_data.get("steps", [])
    
    threading.Thread(target=speak, args=(reply_text,), daemon=True).start()
    return jsonify({"reply": reply_text, "steps": steps, "events": getattr(brain, "current_events", [])})

@app.route("/api/voice", methods=["POST"])
def voice():
    text = listen()
    if not text:
        return jsonify({"error": "Did not catch that. Please try again."}), 400
        
    reply_data = brain.process_input(text)
    reply_text = reply_data.get("reply", "").replace("—", "-")
    steps = reply_data.get("steps", [])
    
    threading.Thread(target=speak, args=(reply_text,), daemon=True).start()
    return jsonify({"text": text, "reply": reply_text, "steps": steps, "events": getattr(brain, "current_events", [])})

import time

last_net_io = psutil.net_io_counters()
last_net_time = time.time()

@app.route("/api/system", methods=["GET"])
def get_system_stats():
    global last_net_io, last_net_time
    
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    swap = psutil.swap_memory().percent
    
    current_net_io = psutil.net_io_counters()
    current_time = time.time()
    time_delta = current_time - last_net_time
    
    if time_delta > 0:
        download_speed = (current_net_io.bytes_recv - last_net_io.bytes_recv) / time_delta
        upload_speed = (current_net_io.bytes_sent - last_net_io.bytes_sent) / time_delta
    else:
        download_speed = 0
        upload_speed = 0
        
    last_net_io = current_net_io
    last_net_time = current_time
    
    def format_bytes(b):
        if b < 1024: return f"{b:.0f} B/s"
        elif b < 1024**2: return f"{b/1024:.1f} KB/s"
        else: return f"{b/(1024**2):.1f} MB/s"

    # Get top 5 processes by CPU usage using bash ps command
    try:
        ps_output = subprocess.check_output("ps -eo comm,%cpu,%mem --sort=-%cpu | head -n 6", shell=True).decode('utf-8')
        lines = ps_output.strip().split('\n')[1:] # Skip header
        top_processes = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                name = " ".join(parts[:-2])
                top_processes.append({"name": name, "cpu": parts[-2], "mem": parts[-1]})
    except Exception as e:
        top_processes = [{"name": "Error fetching", "cpu": "0", "mem": "0"}]

    return jsonify({
        "cpu": cpu, 
        "ram": ram,
        "swap": swap,
        "download": format_bytes(download_speed),
        "upload": format_bytes(upload_speed),
        "top_processes": top_processes
    })

@app.route("/api/trigger", methods=["POST"])
def trigger_action():
    action = request.json.get("action")
    if action == "browser":
        subprocess.Popen("xdg-open https://google.com", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "calculator":
        subprocess.Popen("gnome-calculator", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "music":
        # Launch youtube music in background via play_music wrapper
        subprocess.Popen('./venv/bin/python play_music.py "top hits" &', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return jsonify({"status": "success"})

@app.route("/api/kill_audio", methods=["POST"])
def kill_audio():
    subprocess.run("killall ffplay", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"status": "success"})

if __name__ == "__main__":
    # Pre-warm psutil cpu_percent
    psutil.cpu_percent(interval=0.1)
    print("Tilux UI Server starting at http://localhost:8932")
    app.run(debug=True, port=8932, use_reloader=False)
