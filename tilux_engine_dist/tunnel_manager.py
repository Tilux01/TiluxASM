import subprocess
import threading
import re
import os
import time
from firebase_sync import firebase_sync

class TunnelManager:
    def __init__(self, port=8932):
        self.port = port
        self.tunnel_url = None
        self.process = None

    def start_tunnel(self, get_host_info_func=None):
        self.get_host_info_func = get_host_info_func
        def _run():
            while True:
                try:
                    import shutil
                    stdbuf_prefix = "stdbuf -oL -eL " if shutil.which("stdbuf") else ""
                    cmd = f"{stdbuf_prefix}npx --yes cloudflared tunnel --url http://localhost:{self.port}"
                    print(f"[Tunnel Manager] Spawning Secure High-Speed Tunnel on port {self.port}...", flush=True)
                    self.process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    
                    for line in iter(self.process.stdout.readline, ''):
                        if not line:
                            break
                        line_str = line.strip()
                        if "trycloudflare.com" in line_str:
                            match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line_str)
                            if match:
                                url = match.group(0)
                                self.tunnel_url = url
                                os.environ["TILUX_TUNNEL_URL"] = url
                                print(f"[Tunnel Manager] 🚀 Secure High-Speed Tunnel URL established: {url}", flush=True)
                                if self.get_host_info_func:
                                    info = self.get_host_info_func()
                                    host_id = info[0]
                                    pair_token = info[1]
                                    pc_name = info[2]
                                    wake_token = info[3] if len(info) > 3 else None
                                    firebase_sync.sync_host_state(host_id, pair_token, url, pc_name, wake_token)
                                else:
                                    firebase_sync.sync_tunnel_url(url)
                                
                    self.process.wait()
                except Exception as e:
                    print(f"[Tunnel Manager Error] {e}", flush=True)
                
                print("[Tunnel Manager] Secure Tunnel process exited. Reconnecting in 3 seconds...", flush=True)
                time.sleep(3)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

tunnel_manager = TunnelManager()
