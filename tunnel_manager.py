import subprocess
import threading
import re
import os
import time
from cloud_bridge import cloud_bridge

class TunnelManager:
    def __init__(self, port=8932):
        self.port = port
        self.tunnel_url = None
        self.process = None

    def _get_cloudflared_command(self):
        import shutil, platform, os
        # 1. Check if cloudflared is installed in system PATH
        cf_bin = shutil.which("cloudflared")
        if cf_bin:
            return cf_bin
            
        # 2. Check local directories
        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data = os.environ.get("TILUX_USER_DATA_DIR")
        is_win = platform.system() == "Windows"
        exe_name = "cloudflared.exe" if is_win else "cloudflared"
        
        candidates = [
            os.path.join(base_dir, exe_name),
        ]
        if user_data:
            candidates.insert(0, os.path.join(user_data, exe_name))
            
        for cand in candidates:
            if os.path.exists(cand) and os.path.isfile(cand):
                return cand
                
        # 3. Check if npx is available
        if shutil.which("npx"):
            return "npx --yes cloudflared"
            
        # 4. If neither exists, auto-download standalone single binary
        print(f"[Tunnel Manager] cloudflared not found. Downloading official Cloudflare Tunnel binary...")
        try:
            import urllib.request
            target_dir = user_data if user_data and os.path.exists(user_data) else base_dir
            if not os.access(target_dir, os.W_OK):
                target_dir = os.path.expanduser("~/.cache/tilux")
                os.makedirs(target_dir, exist_ok=True)
            target_file = os.path.join(target_dir, exe_name)
            
            if is_win:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
            elif platform.system() == "Darwin":
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
            else:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                
            urllib.request.urlretrieve(url, target_file)
            if not is_win:
                os.chmod(target_file, 0o755)
            print(f"[Tunnel Manager] Successfully installed cloudflared to: {target_file}")
            return target_file
        except Exception as e:
            print(f"[Tunnel Manager] Auto-download error: {e}. Falling back to npx.")
            return "npx --yes cloudflared"

    def start_tunnel(self, get_host_info_func=None):
        self.get_host_info_func = get_host_info_func
        def _run():
            while True:
                try:
                    import shutil
                    stdbuf_prefix = "stdbuf -oL -eL " if shutil.which("stdbuf") else ""
                    cf_cmd = self._get_cloudflared_command()
                    cmd = f"{stdbuf_prefix}{cf_cmd} tunnel --url http://localhost:{self.port}"
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
                                    cloud_bridge.sync_host_state(host_id, pair_token, url, pc_name, wake_token)
                                else:
                                    cloud_bridge.sync_tunnel_url(url)
                                
                    self.process.wait()
                except Exception as e:
                    print(f"[Tunnel Manager Error] {e}", flush=True)
                
                print("[Tunnel Manager] Secure Tunnel process exited. Reconnecting in 3 seconds...", flush=True)
                time.sleep(3)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

tunnel_manager = TunnelManager()
