#!/usr/bin/env python3
"""
Tilux Server & App Cross-Platform Restart & Launcher Script
Supported OS: Linux, Windows, macOS

Functions:
1. Cleanly terminates running Tilux server instances and frees port 8932.
2. Updates and registers the system boot autostart entry for the active directory.
3. Restarts the Python server process detached.
4. Restarts the main desktop app (Electron) if requested.
"""

import os
import sys
import time
import socket
import signal
import platform
import argparse
import subprocess

PORT = 8932

def is_port_in_use(port=PORT) -> bool:
    """Checks if a TCP port is currently open and bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (socket.error, OSError):
            return False

def wait_for_port_free(port=PORT, timeout=6.0) -> bool:
    """Waits until the specified TCP port is completely released."""
    start = time.time()
    while time.time() - start < timeout:
        if not is_port_in_use(port):
            # Double check with a test bind
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(("0.0.0.0", port))
                return True
            except OSError:
                pass
        time.sleep(0.2)
    return not is_port_in_use(port)

def kill_process_by_pid(pid: int):
    """Safely terminates a process across Windows, Linux, and macOS."""
    if not pid or pid <= 0 or pid == os.getpid():
        return
    try:
        if platform.system().lower() == "windows":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    except Exception as e:
        print(f"[Restart] Notice terminating PID {pid}: {e}")

def kill_port_owner(port=PORT):
    """Kills any process currently listening on port 8932 across all operating systems."""
    sys_type = platform.system().lower()
    
    if "windows" in sys_type:
        try:
            out = subprocess.check_output('netstat -ano -p tcp | findstr :' + str(port), shell=True).decode(errors="ignore")
            for line in out.strip().split("\n"):
                parts = line.strip().split()
                if len(parts) >= 5 and "LISTENING" in line.upper():
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        print(f"[Restart] Killing Windows PID holding port {port}: {pid}")
                        subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    elif "linux" in sys_type or "darwin" in sys_type:
        # Try fuser first (Linux)
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        # Try lsof (macOS / Linux fallback)
        try:
            out = subprocess.check_output(["lsof", "-ti", f":{port}"]).decode(errors="ignore")
            for pid in out.strip().split():
                if pid.isdigit() and int(pid) != os.getpid():
                    print(f"[Restart] Killing Unix PID holding port {port}: {pid}")
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except OSError:
                        pass
        except Exception:
            pass

def kill_desktop_app():
    """Terminates any active Electron desktop instances for Tilux."""
    sys_type = platform.system().lower()
    print("[Restart] Terminating active desktop app instances...")
    if "windows" in sys_type:
        try:
            subprocess.run(["taskkill", "/F", "/IM", "Tilux.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "electron.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        try:
            # Terminate electron processes associated with tilux-client
            subprocess.run(["pkill", "-f", "tilux-client"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-f", "electron.*tilux-client"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def find_python_executable(app_dir: str) -> str:
    """Finds the best python binary (venv, bundled runtime, or system)."""
    sys_type = platform.system().lower()
    if "windows" in sys_type:
        candidates = [
            os.path.join(app_dir, "runtime", "python.exe"),
            os.path.join(app_dir, "venv", "Scripts", "python.exe"),
            sys.executable
        ]
    else:
        candidates = [
            os.path.join(app_dir, "runtime", "bin", "python3"),
            os.path.join(app_dir, "runtime", "bin", "python"),
            os.path.join(app_dir, "venv", "bin", "python"),
            os.path.join(app_dir, "venv", "bin", "python3"),
            sys.executable
        ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)
    return sys.executable or "python3"

def launch_server_detached(app_dir: str, python_exe: str) -> bool:
    """Spawns server.py as a fully detached background process."""
    server_script = os.path.join(app_dir, "server.py")
    if not os.path.exists(server_script):
        print(f"[Restart] Error: server.py not found in {app_dir}")
        return False
        
    sys_type = platform.system().lower()
    print(f"[Restart] Launching server: {python_exe} {server_script} (CWD: {app_dir})")
    
    try:
        if "windows" in sys_type:
            subprocess.Popen(
                [python_exe, server_script],
                cwd=app_dir,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
        else:
            subprocess.Popen(
                [python_exe, server_script],
                cwd=app_dir,
                start_new_session=True,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
        print("[Restart] Detached server process successfully spawned.")
        return True
    except Exception as e:
        print(f"[Restart] Error spawning server: {e}")
        return False

def launch_desktop_app_detached(app_dir: str) -> bool:
    """Spawns the Electron desktop app detached."""
    import json
    sys_type = platform.system().lower()
    settings_file = os.path.join(app_dir, "settings.json")
    frontend_exe = "npm"
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                s = json.load(f)
                frontend_exe = s.get("frontend_executable", "npm")
        except Exception:
            pass

    client_dir = os.path.join(app_dir, "tilux-client")
    print(f"[Restart] Launching desktop app via '{frontend_exe}'...")

    try:
        if frontend_exe == "npm" or not os.path.isabs(frontend_exe):
            # Development mode: npm start inside tilux-client
            if not os.path.exists(client_dir):
                return False
            cmd = ["npm", "start"] if "windows" not in sys_type else ["npm.cmd", "start"]
            if "windows" in sys_type:
                subprocess.Popen(
                    cmd,
                    cwd=client_dir,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    close_fds=True,
                    shell=True
                )
            else:
                subprocess.Popen(
                    cmd,
                    cwd=client_dir,
                    start_new_session=True,
                    close_fds=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        elif os.path.exists(frontend_exe):
            # Packaged executable
            if "windows" in sys_type:
                subprocess.Popen(
                    [frontend_exe],
                    cwd=os.path.dirname(frontend_exe),
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    close_fds=True
                )
            else:
                subprocess.Popen(
                    [frontend_exe],
                    cwd=os.path.dirname(frontend_exe),
                    start_new_session=True,
                    close_fds=True
                )
        print("[Restart] Desktop app successfully launched.")
        return True
    except Exception as e:
        print(f"[Restart] Could not launch desktop app: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Tilux Server & App Cross-Platform Restart Helper")
    parser.add_argument("--kill-pid", type=int, default=0, help="PID of the old server process to kill")
    parser.add_argument("--app-dir", type=str, default="", help="Directory containing server.py")
    parser.add_argument("--restart-app", action="store_true", help="Also restart the desktop Electron app")
    parser.add_argument("--update-autostart", action="store_true", default=True, help="Update system boot autostart entry")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait before killing")
    args = parser.parse_args()

    app_dir = args.app_dir or os.path.dirname(os.path.abspath(__file__))
    
    print(f"\n==============================================")
    print(f"  Tilux Cross-Platform Server & App Restart   ")
    print(f"  OS: {platform.system()} ({platform.machine()})")
    print(f"  Directory: {app_dir}")
    print(f"==============================================\n")

    if not args.no_wait:
        # Give the initiating HTTP request a moment to respond to the client
        time.sleep(0.4)

    # 1. Kill old server PID if provided
    if args.kill_pid and args.kill_pid > 0:
        print(f"[Restart] Terminating target server PID {args.kill_pid}...")
        kill_process_by_pid(args.kill_pid)

    # 2. Terminate any remaining process occupying port 8932
    print(f"[Restart] Clearing port {PORT} across all processes...")
    kill_port_owner(PORT)

    # 3. If desktop app restart requested, terminate existing Electron instances
    if args.restart_app:
        kill_desktop_app()

    # 4. Wait for port 8932 to be completely free
    freed = wait_for_port_free(PORT, timeout=5.0)
    if not freed:
        print(f"[Restart] Warning: Port {PORT} still appears busy. Forcing additional cleanup...")
        kill_port_owner(PORT)
        wait_for_port_free(PORT, timeout=2.0)

    # 5. Refresh system boot autostart configuration for active directory
    if args.update_autostart:
        try:
            sys.path.insert(0, app_dir)
            from autostart import enable_autostart
            boot_path = enable_autostart(app_dir)
            if boot_path:
                print(f"[Restart] Boot autostart registered from active directory: {boot_path}")
        except Exception as e:
            print(f"[Restart] Autostart update notice: {e}")

    # 6. Locate python binary and start server detached
    python_exe = find_python_executable(app_dir)
    server_ok = launch_server_detached(app_dir, python_exe)

    # 7. Optionally restart main desktop app
    if args.restart_app:
        time.sleep(0.6)
        launch_desktop_app_detached(app_dir)

    print("\n[Restart] Restart procedure complete!\n")

if __name__ == "__main__":
    main()
