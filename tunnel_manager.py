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
            
        # 2. Check local directories & resources
        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data = os.environ.get("TILUX_USER_DATA_DIR")
        res_dir = os.environ.get("TILUX_RESOURCES_DIR")
        is_win = platform.system() == "Windows"
        exe_name = "cloudflared.exe" if is_win else "cloudflared"
        
        candidates = [
            os.path.join(base_dir, exe_name),
        ]
        if user_data:
            candidates.insert(0, os.path.join(user_data, exe_name))
        if res_dir:
            candidates.insert(0, os.path.join(res_dir, exe_name))
            candidates.insert(0, os.path.join(res_dir, "backend", exe_name))
        parent_dir = os.path.dirname(base_dir)
        candidates.append(os.path.join(parent_dir, exe_name))
        candidates.append(os.path.join(parent_dir, "backend", exe_name))
        candidates.append(os.path.expanduser(f"~/.cache/tilux/{exe_name}"))
            
        for cand in candidates:
            if cand and os.path.exists(cand) and os.path.isfile(cand):
                return cand
                
        # 3. Direct standalone single binary download (fast, reliable, zero-dependency)
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
                urllib.request.urlretrieve(url, target_file)
            elif platform.system() == "Darwin":
                import tarfile
                arch = "arm64" if platform.machine().lower() in ["arm64", "aarch64"] else "amd64"
                url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-{arch}.tgz"
                tgz_path = os.path.join(target_dir, "cf.tgz")
                urllib.request.urlretrieve(url, tgz_path)
                with tarfile.open(tgz_path, "r:gz") as tar:
                    tar.extractall(path=target_dir)
                if os.path.exists(tgz_path):
                    os.remove(tgz_path)
            else:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                urllib.request.urlretrieve(url, target_file)
                
            if not is_win and os.path.exists(target_file):
                os.chmod(target_file, 0o755)
            print(f"[Tunnel Manager] Successfully installed cloudflared to: {target_file}")
            return target_file
        except Exception as e:
            print(f"[Tunnel Manager] Auto-download notice: {e}. Checking npx fallback...")

        # 4. Fallback to npx if binary download fails
        npx_bin = shutil.which("npx")
        if npx_bin:
            return npx_bin
            
        return "cloudflared"

    def start_tunnel(self, get_host_info_func=None):
        self.get_host_info_func = get_host_info_func
        def _run():
            retry_delay = 5
            while True:
                last_err = ""
                connected = False
                try:
                    import shutil, platform
                    # Terminate any orphan cloudflared instances first to avoid duplicate tunnel collisions
                    try:
                        if platform.system() == "Windows":
                            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            subprocess.run(["pkill", "-f", "cloudflared tunnel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

                    cf_cmd = self._get_cloudflared_command()
                    extra_flags = ["--protocol", "http2", "--no-autoupdate", "--metrics", "127.0.0.1:0"]
                    use_shell = False
                    if "npx" in os.path.basename(cf_cmd).lower():
                        cmd_list = [cf_cmd, "--yes", "cloudflared", "tunnel"] + extra_flags + ["--url", f"http://127.0.0.1:{self.port}"]
                        if platform.system() == "Windows":
                            use_shell = True
                    else:
                        cmd_list = [cf_cmd, "tunnel"] + extra_flags + ["--url", f"http://127.0.0.1:{self.port}"]

                    print(f"[Tunnel Manager] Connecting Secure Remote Tunnel on port {self.port}...", flush=True)
                    popen_kwargs = {
                        "stdout": subprocess.PIPE,
                        "stderr": subprocess.STDOUT,
                        "text": True,
                        "bufsize": 1,
                        "shell": use_shell
                    }
                    if platform.system() == "Windows" and not use_shell:
                        popen_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
                    spawn_cmd = subprocess.list2cmdline(cmd_list) if (use_shell and platform.system() == "Windows") else cmd_list
                    self.process = subprocess.Popen(spawn_cmd, **popen_kwargs)
                    
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
                                print(f"[Tunnel Manager] 🚀 Secure Remote Tunnel URL established: {url}", flush=True)
                                retry_delay = 5  # Reset backoff on success
                                connected = True
                                if self.get_host_info_func:
                                    info = self.get_host_info_func()
                                    host_id = info[0]
                                    pair_token = info[1]
                                    pc_name = info[2]
                                    wake_token = info[3] if len(info) > 3 else None
                                    cloud_bridge.sync_host_state(host_id, pair_token, url, pc_name, wake_token)
                                else:
                                    cloud_bridge.sync_tunnel_url(url)
                        elif any(k in line_str.lower() for k in ["429", "rate limit", "error", "failed", "status 5"]):
                            last_err = line_str

                    self.process.wait()
                except Exception as e:
                    last_err = str(e)
                
                os.environ.pop("TILUX_TUNNEL_URL", None)
                self.tunnel_url = None
                
                # If rate-limited (429), use 60s cooldown so Cloudflare's rate limit window can clear
                if "429" in last_err.lower() or "rate" in last_err.lower():
                    retry_delay = 60
                    print(f"[Tunnel Manager] Cloudflare quick tunnel rate-limited (HTTP 429). Cooling down for {retry_delay}s...", flush=True)
                else:
                    retry_delay = min(retry_delay * 2 if not connected else 5, 60)
                    if last_err:
                        print(f"[Tunnel Manager] Notice: {last_err}. Reconnecting in {retry_delay}s...", flush=True)
                    else:
                        print(f"[Tunnel Manager] Tunnel closed. Reconnecting in {retry_delay}s...", flush=True)
                
                time.sleep(retry_delay)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

tunnel_manager = TunnelManager()
