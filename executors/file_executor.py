import sys
import json
import subprocess

def run_file_task(data: dict) -> dict:
    import platform
    os_type = platform.system()
    action = data.get("action", "open").lower()
    path = data.get("path", "")
    
    if action == "open_code":
        cmd = f"code '{path}' & disown"
    else:
        if os_type == "Linux":
            cmd = f"xdg-open '{path}' & disown"
        elif os_type == "Darwin": # macOS
            cmd = f"open '{path}'"
        else: # Windows
            cmd = f"cmd /c start '' '{path}'"

    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return {"status": "success", "action": action, "path": path}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            payload = json.loads(sys.argv[1])
        except Exception:
            payload = {}
    else:
        payload = {}
        
    output = run_file_task(payload)
    print(json.dumps(output))
