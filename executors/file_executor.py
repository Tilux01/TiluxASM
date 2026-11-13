import sys
import os
import json

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from os_protocols import OSProtocols

def run_file_task(data: dict) -> dict:
    """
    Executes file and code editor tasks using centralized native OS protocols.
    """
    action = data.get("action", "open").lower().strip()
    path = data.get("path", "").strip()
    
    if action == "open_code":
        res = OSProtocols.open_app("code", [path] if path else None)
    else:
        res = OSProtocols.open_url(path)

    return {
        "status": res.get("status", "success"),
        "os": res.get("os", ""),
        "action": action,
        "path": path,
        "output": res.get("output", "")
    }

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
