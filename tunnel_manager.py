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

    def start_tunnel(self):
        def _run():
            while True:
                try:
                    cmd = f"npx localtunnel --port {self.port}"
                    print(f"[Tunnel Manager] Spawning localtunnel on port {self.port}...")
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
                        print(f"[Localtunnel Output] {line_str}")
                        match = re.search(r'https://[^\s]+', line_str)
                        if match:
                            url = match.group(0)
                            self.tunnel_url = url
                            os.environ["TILUX_TUNNEL_URL"] = url
                            print(f"[Tunnel Manager] ✅ Live Tunnel URL established: {url}")
                            firebase_sync.sync_tunnel_url(url)
                            
                    self.process.wait()
                except Exception as e:
                    print(f"[Tunnel Manager Error] {e}")
                
                print("[Tunnel Manager] Localtunnel process exited. Reconnecting in 5 seconds...")
                time.sleep(5)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

tunnel_manager = TunnelManager()
