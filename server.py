import os
import sys

# Configure Playwright browsers path if compiled with Nuitka
if "__compiled__" in globals():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_dir, "playwright_browsers")

import credentials
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import threading
import logging
import psutil
import subprocess
from brain import Brain
from voice import speak, listen
from memory import load_memory


# Werkzeug logging enabled for debugging
log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)

app = Flask(__name__)
CORS(app) # Allow cross-origin requests from the Electron app

brain = Brain()
from history_manager import history_manager

import json
import os


SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "tts_enabled": True,
    "tts_voice": "en-GB-SoniaNeural",
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
    firebase_sync.sync_settings(HOST_ID, data)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/splash")
def splash():
    return render_template("splash.html")

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

@app.route("/api/clear_user_session", methods=["POST"])
def clear_user_session():
    try:
        if os.path.exists("user_personal.json"):
            os.remove("user_personal.json")
        save_settings(DEFAULT_SETTINGS)
        return jsonify({"status": "success", "message": "User session erased"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/sync_user_personal", methods=["POST"])
def sync_user_personal():
    try:
        data = request.json or {}
        with open("user_personal.json", "w") as f:
            json.dump(data, f, indent=4)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/file", methods=["GET"])
def serve_file():
    file_path = request.args.get("path", "").strip()
    if not file_path:
        return jsonify({"error": "No file path provided"}), 400
    
    if file_path.startswith("file://"):
        file_path = file_path[7:]
        
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
        
    if os.path.exists(file_path) and os.path.isfile(file_path):
        as_attachment = request.args.get("download", "0") == "1"
        res = send_file(file_path, as_attachment=as_attachment)
        res.headers["Access-Control-Allow-Origin"] = "*"
        res.headers["Bypass-Tunnel-Reminder"] = "true"
        return res
    else:
        return jsonify({"error": f"File not found: {file_path}"}), 404



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

def stop_audio_process():
    import platform
    if platform.system() == "Windows":
        subprocess.run("taskkill /F /IM ffplay.exe /T 2>NUL || exit /b 0", shell=True)
    else:
        subprocess.run("killall ffplay 2>/dev/null || true", shell=True)

@app.route("/api/stop", methods=["POST"])
def stop_generation():
    brain.abort_flag = True
    brain.is_processing = False
    brain.current_status = "Idle"
    brain.current_events = []
    stop_audio_process()
    return jsonify({"status": "stopped"})



@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(history_manager.list_sessions())

@app.route("/api/history/<session_id>", methods=["GET"])
def get_history_session(session_id):
    sess = history_manager.get_session(session_id)
    if not sess:
        return jsonify({"error": "Session not found"}), 404
    history_manager.current_session_id = session_id
    brain.load_session_history(sess.get("messages", []))
    return jsonify(sess)

@app.route("/api/history/new", methods=["POST"])
def new_history_session():
    new_id = history_manager.start_new_session()
    brain.clear_history()
    return jsonify({"status": "success", "session_id": new_id})

@app.route("/api/history/<session_id>", methods=["DELETE"])
def delete_history_session(session_id):
    history_manager.delete_session(session_id)
    brain.clear_history()
    return jsonify({"status": "success"})


def sync_brain_session(session_id):
    if not session_id:
        session_id = history_manager.start_new_session()
        brain.clear_history()
    else:
        history_manager.current_session_id = session_id
        sess = history_manager.get_session(session_id)
        if sess:
            brain.load_session_history(sess.get("messages", []))
        else:
            brain.clear_history()
    return session_id

@app.route("/api/chat", methods=["POST"])
def chat():
    stop_audio_process()
    if request.is_json:
        user_text = request.json.get("text", "").strip()
        session_id = request.json.get("session_id")
        attachments = []
    else:
        user_text = request.form.get("text", "").strip()
        session_id = request.form.get("session_id")
        attachments = request.files.getlist("attachments")
        
    if not user_text and not attachments:
        return jsonify({"error": "No input provided"}), 400

    from usage_tracker import usage_tracker
    if not usage_tracker.can_generate():
        return jsonify({"error": "You've exhausted your tokens and your wallet balance is empty. Please click 'Wallet Top-Up' to add funds and continue using Tilux ASM."}), 402

    session_id = sync_brain_session(session_id)
        
    import os, uuid
    from werkzeug.utils import secure_filename
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    saved_files = []
    attachment_urls = []
    for f in attachments:
        if f.filename:
            filename = secure_filename(f.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(uploads_dir, unique_name)
            f.save(filepath)
            saved_files.append(filepath)
            attachment_urls.append(f"/static/uploads/{unique_name}")
            
    sid = history_manager.add_message(session_id, "User", user_text, attachments=attachment_urls)

    try:
        reply_data = brain.process_input(user_text, attachments=saved_files, session_id=sid)
    except Exception as e:
        reply_data = {"reply": "Task failed: " + str(e), "events": []}
        
    reply_text = reply_data.get("reply", "").replace("—", "-")
    history_manager.add_message(sid, "AI", reply_text, events=reply_data.get("events", []))
    reply_data["session_id"] = sid
    threading.Thread(target=speak, args=(reply_text,), daemon=True).start()
    return jsonify(reply_data)


@app.route("/api/voice", methods=["POST"])
def voice():
    stop_audio_process()
    text = listen()
    if not text:
        return jsonify({"error": "Did not catch that. Please try again."}), 400
        
    reply_data = brain.process_input(text, session_id=history_manager.current_session_id)
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

import socket
import qrcode
import base64
from io import BytesIO
from flask_socketio import SocketIO, emit

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10000000
)


import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST_ID_FILE = os.path.join(BASE_DIR, "host_id.txt")
PAIR_TOKEN_FILE = os.path.join(BASE_DIR, "pair_token.txt")
def get_or_create_host_id():
    env_id = os.getenv("TILUX_HOST_ID")
    if env_id:
        return env_id.strip()
    if os.path.exists(HOST_ID_FILE):
        try:
            with open(HOST_ID_FILE, "r") as f:
                h_id = f.read().strip()
                if h_id:
                    return h_id
        except Exception:
            pass
    new_id = "tilux_host_" + os.urandom(6).hex()
    try:
        with open(HOST_ID_FILE, "w") as f:
            f.write(new_id)
    except Exception as e:
        print(f"[Warning] Could not save host ID: {e}")
    return new_id

def get_or_create_pair_token():
    env_token = os.getenv("REMOTE_PAIR_TOKEN")
    if env_token:
        return env_token.strip()
    
    if os.path.exists(PAIR_TOKEN_FILE):
        try:
            with open(PAIR_TOKEN_FILE, "r") as f:
                token = f.read().strip()
                if token:
                    return token
        except Exception:
            pass
            
    new_token = "tilux_pair_" + os.urandom(6).hex()
    try:
        with open(PAIR_TOKEN_FILE, "w") as f:
            f.write(new_token)
    except Exception as e:
        print(f"[Warning] Could not save pair token to file: {e}")
    return new_token

HOST_ID = get_or_create_host_id()
PAIR_TOKEN = get_or_create_pair_token()
WAKE_TOKEN = "wake_" + os.urandom(6).hex()

def get_host_info():
    return HOST_ID, PAIR_TOKEN, socket.gethostname() or "Tilux-PC", WAKE_TOKEN

@app.route("/api/host_info", methods=["GET"])
def get_host_info_api():
    return jsonify({
        "host_id": HOST_ID,
        "pair_token": PAIR_TOKEN,
        "wake_token": WAKE_TOKEN,
        "url": get_public_url(),
        "pc_name": socket.gethostname() or "Tilux-PC"
    })

@app.route("/api/regenerate_pair_token", methods=["POST"])
def regenerate_pair_token():
    global PAIR_TOKEN
    new_token = "tilux_pair_" + os.urandom(6).hex()
    PAIR_TOKEN = new_token
    try:
        with open(PAIR_TOKEN_FILE, "w") as f:
            f.write(new_token)
    except Exception as e:
        print(f"[Warning] Could not update pair_token.txt: {e}")
    
    pub_url = get_public_url()
    firebase_sync.sync_host_state(HOST_ID, PAIR_TOKEN, pub_url, wake_token=WAKE_TOKEN)
    return jsonify({
        "status": "success",
        "host_id": HOST_ID,
        "pair_token": PAIR_TOKEN
    })

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_public_url():
    if os.getenv("TILUX_TUNNEL_URL"):
        return os.getenv("TILUX_TUNNEL_URL")
    ip = get_local_ip()
    return f"http://{ip}:8932"


@app.route("/api/qr_pair", methods=["GET"])
def get_qr_pair():
    ip = get_local_ip()
    public_url = get_public_url()
    
    payload = {
        "host_id": HOST_ID,
        "token": PAIR_TOKEN,
        "url": public_url,
        "pc_name": socket.gethostname() or "Tilux-PC"
    }
    
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return jsonify({
        "qr_image": f"data:image/png;base64,{qr_b64}",
        "host_id": HOST_ID,
        "token": PAIR_TOKEN,
        "url": public_url,
        "ip": ip
    })

@socketio.on("connect")
def handle_connect():
    emit("status", {"message": "Connected to Tilux Remote Gateway"})

@socketio.on("pair_device")
def handle_pair(data):
    token = data.get("token") if isinstance(data, dict) else data
    if token == PAIR_TOKEN:
        emit("paired", {"status": "success", "pc_name": socket.gethostname(), "host_id": HOST_ID})
    else:
        emit("paired", {"status": "unauthorized"})

@socketio.on("send_prompt")
def handle_remote_prompt(data):
    prompt_text = data.get("text", "")
    token = data.get("token", "")
    session_id = data.get("session_id")
    raw_attachments = data.get("attachments", [])
    if token != PAIR_TOKEN:
        emit("error", {"message": "Unauthorized remote device"})
        return
        
    client_sid = request.sid
    
    session_id = sync_brain_session(session_id)
    brain.abort_flag = False
    sid = history_manager.add_message(session_id, "User", prompt_text)

    def run_task():
        socketio.emit("agent_status", {"status": "Thinking..."}, to=client_sid)
        saved_files = []
        if raw_attachments:
            import os, uuid, base64
            temp_dir = "/tmp/tilux_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            for item in raw_attachments:
                try:
                    name = item.get("name", "file.png")
                    b64_str = item.get("b64", "")
                    if "," in b64_str:
                        b64_str = b64_str.split(",", 1)[1]
                    file_data = base64.b64decode(b64_str)
                    filepath = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{name}")
                    with open(filepath, "wb") as f:
                        f.write(file_data)
                    saved_files.append(filepath)
                except Exception as e:
                    print(f"[Remote Attachment Save Error] {e}")
                    
        try:
            result = brain.process_input(prompt_text, attachments=saved_files)
        except Exception as e:
            result = {"reply": "Remote task failed: " + str(e), "events": []}
        
        history_manager.add_message(sid, "AI", result.get("reply", ""), events=result.get("events", []))
        result["session_id"] = sid
        result["requested_by"] = client_sid
        socketio.emit("agent_reply", result)
        socketio.emit("history_list", history_manager.list_sessions())
        
    threading.Thread(target=run_task, daemon=True).start()

@socketio.on("stop_task")
def handle_stop_remote_task():
    was_processing = brain.is_processing
    brain.abort_flag = True
    brain.is_processing = False
    brain.current_status = "Idle"
    brain.current_events = []
    stop_audio_process()
    if not was_processing:
        socketio.emit("agent_reply", {"reply": "Task stopped by user.", "events": []})

@socketio.on("get_history")
def handle_get_history():
    emit("history_list", history_manager.list_sessions())

@socketio.on("load_session")
def handle_load_session(data):
    sess_id = data.get("id") if isinstance(data, dict) else data
    sess = history_manager.get_session(sess_id)
    if sess:
        history_manager.current_session_id = sess_id
        brain.load_session_history(sess.get("messages", []))
        emit("session_loaded", sess)

@socketio.on("new_chat")
def handle_new_chat():
    new_id = history_manager.start_new_session()
    brain.clear_history()
    emit("new_chat_started", {"session_id": new_id})
    emit("history_list", history_manager.list_sessions())

@socketio.on("delete_session")
def handle_delete_session(data):
    sess_id = data.get("id") if isinstance(data, dict) else data
    history_manager.delete_session(sess_id)
    emit("history_list", history_manager.list_sessions())

@app.route("/api/kill_audio", methods=["POST"])
def kill_audio():
    stop_audio_process()
    return jsonify({"status": "success"})

from voice import generate_audio_buffer
from flask import send_file
import io

@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json() or {}
    text = data.get("text", "")
    voice = data.get("voiceName", "en-US-AriaNeural")
    speed = data.get("speed", "+20%")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    audio_bytes = generate_audio_buffer(text, voice, speed)
    if not audio_bytes:
        return jsonify({"error": "Failed to generate TTS audio"}), 500
        
    return send_file(io.BytesIO(audio_bytes), mimetype="audio/mpeg")

def on_brain_event_update(events, status, session_id=None):
    socketio.emit("agent_events", {"events": events, "status": status, "session_id": session_id})

brain.on_event_update = on_brain_event_update


from firebase_sync import firebase_sync

from usage_tracker import usage_tracker

@app.route("/api/firebase_config", methods=["GET"])
def get_firebase_config():
    return jsonify({
        "apiKey": "AIzaSyAQ1ffdL36D8Bw3xA4fOj1boPJlqhPR4p4",
        "authDomain": "tiluxasm.firebaseapp.com",
        "databaseURL": "https://tiluxasm-default-rtdb.firebaseio.com",
        "projectId": "tiluxasm",
        "storageBucket": "tiluxasm.firebasestorage.app",
        "messagingSenderId": "686558431377",
        "appId": "1:686558431377:web:64786056989860a2039730",
        "measurementId": "G-Q7Y0B754HX"
    })

@app.route("/api/billing_status", methods=["GET"])
def get_billing_status_api():
    return jsonify(usage_tracker.get_summary())

import urllib.request
import urllib.parse
import uuid

@app.route("/api/payment/config", methods=["GET"])
def get_payment_config():
    return jsonify({
        "paystack_public_key": credentials.get_credential("PAYSTACK_PUBLIC_KEY"),
        "flutterwave_public_key": credentials.get_credential("FLUTTERWAVE_PUBLIC_KEY")
    })

@app.route("/api/payment/initialize", methods=["POST"])
def initialize_payment():
    try:
        data = request.json or {}
        gateway = data.get("gateway", "paystack").lower()
        amount_usd = float(data.get("amount_usd", 10.0))
        email = data.get("email", "user@mail.com").strip() or "user@mail.com"
        currency = data.get("currency", "USD").upper()
        
        reference = f"tilux_{gateway}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        # We use a reliable HTTPS URL to bypass Paystack's live mode strict HTTPS callback requirement. 
        # The frontend JS polls the verify endpoint and automatically closes the window upon success anyway.
        callback_url = "https://paystack.com"
            
        proxy_url = os.getenv("TILUX_PROXY_URL", "https://tilux-proxy.vercel.app")
        
        req = urllib.request.Request(
            f"{proxy_url}/api/v1/payment/initialize",
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode('utf-8'))
                return jsonify(res_json), resp.status
        except urllib.error.HTTPError as ex:
            return jsonify(json.loads(ex.read().decode('utf-8'))), ex.code

        return jsonify({"status": "error", "message": "Unsupported payment gateway"}), 400


    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/payment/verify", methods=["POST"])
def verify_payment():
    try:
        data = request.json or {}
        gateway = data.get("gateway", "paystack").lower()
        reference = data.get("reference", "")
        amount_usd = float(data.get("amount_usd", 10.0))

        if not reference:
            return jsonify({"status": "error", "message": "Missing payment reference"}), 400

        verified = False
        proxy_url = os.getenv("TILUX_PROXY_URL", "https://tilux-proxy.vercel.app")
        
        req = urllib.request.Request(
            f"{proxy_url}/api/v1/payment/verify",
            data=json.dumps(data).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode('utf-8'))
                if res_json.get("status") == "success":
                    verified = True
        except urllib.error.HTTPError:
            pass

        if verified:
            summary = usage_tracker.add_funds(amount_usd, gateway, reference)
            return jsonify({"status": "success", "message": f"Payment verified. ${amount_usd:.2f} USD added.", "billing": summary})
        else:
            return jsonify({"status": "pending", "message": "Transaction unverified or pending."}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": f"Verification failed: {str(e)}"}), 500

@app.route("/api/payment/callback", methods=["GET"])
def payment_callback():
    gateway = request.args.get("gateway", "paystack")
    reference = request.args.get("reference", "")
    amount_usd = float(request.args.get("amount_usd", 10.0))
    
    usage_tracker.add_funds(amount_usd, gateway, reference)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Payment Successful - Tilux ASM</title>
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #09090b; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: #18181b; border: 1px solid rgba(168,85,247,0.3); border-radius: 16px; padding: 40px; text-align: center; max-width: 400px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }}
            .icon {{ font-size: 50px; color: #10b981; margin-bottom: 20px; }}
            h1 {{ font-size: 24px; margin-bottom: 10px; color: #a855f7; }}
            p {{ font-size: 14px; color: #a1a1aa; margin-bottom: 25px; }}
            .btn {{ background: linear-gradient(135deg, #a855f7, #6366f1); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✓</div>
            <h1>Top-Up Successful!</h1>
            <p>${amount_usd:.2f} USD has been added to your Tilux Wallet via {gateway.capitalize()}.</p>
            <button class="btn" onclick="window.close()">Close Window</button>
        </div>
    </body>
    </html>
    """
    return Response(html, mimetype="text/html")

@socketio.on("get_billing_status")
def handle_get_billing_status():
    emit("token_usage_update", usage_tracker.get_summary())

from tunnel_manager import tunnel_manager

if __name__ == "__main__":
    try:
        from autostart import enable_autostart
        enable_autostart()
    except Exception:
        pass
        
    try:
        from mac_permissions import request_mac_permissions
        request_mac_permissions()
    except Exception:
        pass

    psutil.cpu_percent(interval=0.1)
    usage_tracker.socketio = socketio
    tunnel_manager.start_tunnel(get_host_info)
    firebase_sync.start_heartbeat_loop(get_public_url, get_host_info)
    
    settings = load_settings()
    firebase_sync.sync_settings(HOST_ID, settings)
    
    print(f"Tilux UI Server & Gateway starting for Host [{HOST_ID}] at http://0.0.0.0:8932", flush=True)

    socketio.run(app, host="0.0.0.0", port=8932, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
