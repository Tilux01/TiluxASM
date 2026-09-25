import os
import time
import json
import urllib.request
import urllib.parse
import threading

FIREBASE_DB_URL = "https://tiluxasm-default-rtdb.firebaseio.com"

class FirebaseSync:
    def __init__(self, db_url=FIREBASE_DB_URL):
        self.db_url = db_url.rstrip('/')
        self.last_synced_url = None
        self.active_user = os.getenv("TILUX_USER_ID", "default_user")
        self.brain_ref = None

    def _sanitize_user_id(self, user_id):
        return user_id.replace('.', '_').replace('@', '_at_').replace('$', '_').replace('#', '_').replace('[', '_').replace(']', '_')

    def sync_tunnel_url(self, tunnel_url, user_id=None, auth_token=None, pairing_token=None):
        if user_id:
            self.active_user = user_id

        user_slug = self._sanitize_user_id(self.active_user)
        endpoint = f"{self.db_url}/users/{user_slug}/device.json"
        
        if auth_token:
            endpoint += f"?auth={auth_token}"

        payload = {
            "tunnel_url": tunnel_url or "",
            "local_url": tunnel_url or "",
            "is_online": True,
            "last_seen": int(time.time()),
            "pc_name": os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "Tilux-PC"
        }
        if pairing_token:
            payload["pairing_token"] = pairing_token

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(endpoint, data=data, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 204):
                    self.last_synced_url = tunnel_url
                    print(f"[Firebase Sync] Device state synced to Firebase: {tunnel_url}")
                    return True
        except Exception as e:
            print(f"[Firebase Sync Error] {e}")
            return False



    def start_heartbeat_loop(self, get_tunnel_func, user_id=None, interval=15):
        def loop():
            while True:
                try:
                    current_url = get_tunnel_func()
                    self.sync_tunnel_url(current_url, user_id=user_id)
                except Exception as e:
                    print(f"[Firebase Watchdog Error] {e}")
                time.sleep(interval)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return t

firebase_sync = FirebaseSync()
