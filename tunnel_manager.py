import subprocess
import threading
import re
import os
import sys
import time
import shutil
import platform
from cloud_bridge import cloud_bridge

def _is_executable_valid(path: str) -> bool:
    """Verifies that the candidate file exists, is non-truncated (>= 15MB), and runs --version successfully."""
    if not path or not os.path.exists(path) or not os.path.isfile(path):
        return False
    try:
        if os.path.getsize(path) < 15 * 1024 * 1024:
            return False
    except Exception:
        return False
    if platform.system() != "Windows":
        try:
            os.chmod(path, 0o755)
        except Exception:
            pass
        if platform.system() == "Darwin":
            try:
                subprocess.run(["xattr", "-d", "com.apple.quarantine", path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
    try:
        res = subprocess.run([path, "--version"], capture_output=True, timeout=5)
        return res.returncode == 0
    except Exception:
        return False

class TunnelManager:
    def __init__(self, port=8932):
        self.port = port
        self.tunnel_url = None
        self.process = None
        self.cf_cmd = None
        self.get_host_info_func = None

    def _get_cloudflared_command(self) -> str:
        if self.cf_cmd and (_is_executable_valid(self.cf_cmd) or "npx" in os.path.basename(self.cf_cmd).lower()):
            return self.cf_cmd

        is_win = platform.system() == "Windows"
        is_mac = platform.system() == "Darwin"
        exe_name = "cloudflared.exe" if is_win else "cloudflared"

        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data = os.environ.get("TILUX_USER_DATA_DIR")
        res_dir = os.environ.get("TILUX_RESOURCES_DIR")
        parent_dir = os.path.dirname(base_dir)

        candidates = []
        # 1. System PATH
        cf_path = shutil.which("cloudflared")
        if cf_path:
            candidates.append(cf_path)

        # 2. OS-specific standard installation locations
        if is_mac:
            candidates.extend([
                "/opt/homebrew/bin/cloudflared",
                "/usr/local/bin/cloudflared",
                "/opt/local/bin/cloudflared"
            ])
        elif is_win:
            candidates.extend([
                r"C:\Program Files\cloudflared\cloudflared.exe",
                r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
            ])

        # 3. Application package & persistent cache locations
        if user_data:
            candidates.append(os.path.join(user_data, exe_name))
        if res_dir:
            candidates.append(os.path.join(res_dir, exe_name))
            candidates.append(os.path.join(res_dir, "backend", exe_name))
        candidates.append(os.path.join(base_dir, exe_name))
        candidates.append(os.path.join(parent_dir, exe_name))
        candidates.append(os.path.join(parent_dir, "backend", exe_name))
        candidates.append(os.path.expanduser(f"~/.cache/tilux/{exe_name}"))

        for cand in candidates:
            if cand and os.path.exists(cand):
                if _is_executable_valid(cand):
                    self.cf_cmd = cand
                    return cand
                else:
                    # File exists but is corrupt/truncated; purge it so it doesn't block re-download
                    try:
                        if os.path.isfile(cand):
                            os.remove(cand)
                    except Exception:
                        pass

        # 4. Standalone binary download with verified atomic writes
        print(f"[Tunnel Manager] cloudflared not found. Downloading official Cloudflare Tunnel binary...", flush=True)
        try:
            import urllib.request
            target_dir = user_data if user_data and os.path.exists(user_data) else os.path.expanduser("~/.cache/tilux")
            if not os.access(target_dir, os.W_OK):
                target_dir = os.path.expanduser("~/.cache/tilux")
            os.makedirs(target_dir, exist_ok=True)

            target_file = os.path.join(target_dir, exe_name)
            tmp_download = target_file + f".tmp_{os.getpid()}"

            if is_win:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=45) as resp, open(tmp_download, 'wb') as f:
                    shutil.copyfileobj(resp, f)
                if _is_executable_valid(tmp_download):
                    os.replace(tmp_download, target_file)
                    print(f"[Tunnel Manager] Successfully installed cloudflared to: {target_file}", flush=True)
                    self.cf_cmd = target_file
                    return target_file
                else:
                    try: os.remove(tmp_download)
                    except Exception: pass
            elif is_mac:
                import tarfile
                arch = "arm64" if platform.machine().lower() in ["arm64", "aarch64"] else "amd64"
                url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-{arch}.tgz"
                tgz_tmp = os.path.join(target_dir, f"cf_{os.getpid()}.tgz")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=45) as resp, open(tgz_tmp, 'wb') as f:
                    shutil.copyfileobj(resp, f)
                with tarfile.open(tgz_tmp, "r:gz") as tar:
                    tar.extractall(path=target_dir)
                try: os.remove(tgz_tmp)
                except Exception: pass

                extracted = os.path.join(target_dir, "cloudflared")
                if _is_executable_valid(extracted):
                    print(f"[Tunnel Manager] Successfully installed cloudflared to: {extracted}", flush=True)
                    self.cf_cmd = extracted
                    return extracted
            else:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=45) as resp, open(tmp_download, 'wb') as f:
                    shutil.copyfileobj(resp, f)
                os.chmod(tmp_download, 0o755)
                if _is_executable_valid(tmp_download):
                    os.replace(tmp_download, target_file)
                    print(f"[Tunnel Manager] Successfully installed cloudflared to: {target_file}", flush=True)
                    self.cf_cmd = target_file
                    return target_file
                else:
                    try: os.remove(tmp_download)
                    except Exception: pass
        except Exception as e:
            print(f"[Tunnel Manager] Binary download notice: {e}. Checking npx fallback...", flush=True)

        # 5. Fallback to npx
        npx_bin = shutil.which("npx")
        if npx_bin:
            self.cf_cmd = npx_bin
            return npx_bin

        return "cloudflared"

    def start_tunnel(self, get_host_info_func=None):
        self.get_host_info_func = get_host_info_func
        def _run():
            retry_delay = 5
            attempt_count = 0
            while True:
                last_err = ""
                connected = False
                try:
                    # Terminate any orphan cloudflared instances first to avoid duplicate tunnel collisions
                    try:
                        if platform.system() == "Windows":
                            subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            subprocess.run(["pkill", "-f", "cloudflared tunnel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

                    cf_cmd = self._get_cloudflared_command()
                    # Start with standard zero-config parameters. If repeatedly failing, toggle http2
                    extra_flags = ["--no-autoupdate", "--metrics", "127.0.0.1:0"]
                    if attempt_count >= 2:
                        extra_flags = ["--protocol", "http2"] + extra_flags

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
                                attempt_count = 0
                                connected = True
                                last_err = ""
                                if self.get_host_info_func:
                                    try:
                                        info = self.get_host_info_func()
                                        host_id = info[0]
                                        pair_token = info[1]
                                        pc_name = info[2]
                                        wake_token = info[3] if len(info) > 3 else None
                                        cloud_bridge.sync_host_state(host_id, pair_token, url, pc_name, wake_token)
                                    except Exception as se:
                                        print(f"[Tunnel Manager] Cloud sync error: {se}")
                                else:
                                    cloud_bridge.sync_tunnel_url(url)
                        elif not connected and any(k in line_str.lower() for k in ["429", "rate limit", "error=", "failed to dial", "status 5"]):
                            if not any(ign in line_str.lower() for ign in ["icmp proxy", "config.yml", "no file", "buffer size", "ping_group_range"]):
                                last_err = line_str

                    self.process.wait()
                except Exception as e:
                    last_err = str(e)

                os.environ.pop("TILUX_TUNNEL_URL", None)
                self.tunnel_url = None
                attempt_count += 1

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
