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

    def sync_host_state(self, host_id, pair_token, tunnel_url, pc_name=None, wake_token=None):
        if not host_id:
            return False
            
        endpoint = f"{self.db_url}/hosts/{host_id}.json"
        payload = {
            "host_id": host_id,
            "pair_token": pair_token or "",
            "wake_token": wake_token or "",
            "tunnel_url": tunnel_url or "",
            "local_url": tunnel_url or "",
            "is_online": True,
            "last_seen": int(time.time()),
            "pc_name": pc_name or os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "Tilux-PC"
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(endpoint, data=data, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 204):
                    self.last_synced_url = tunnel_url
                    # print(f"[Firebase Sync] Host state synced for [{host_id}]: {tunnel_url}")
                    
                    return True
        except Exception as e:
            # print(f"[Firebase Sync Error] {e}")
            return False

    def sync_settings(self, host_id, settings):
        if not host_id or not settings:
            return False
        try:
            endpoint = f"{self.db_url}/hosts/{host_id}/settings.json"
            data = json.dumps(settings).encode('utf-8')
            req = urllib.request.Request(endpoint, data=data, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False

    def sync_usage_and_billing(self, host_id, usage_data):
        if not usage_data or not isinstance(usage_data, dict):
            return False
        try:
            if host_id:
                endpoint = f"{self.db_url}/hosts/{host_id}/usage.json"
                data = json.dumps(usage_data).encode('utf-8')
                req = urllib.request.Request(endpoint, data=data, method='PATCH')
                req.add_header('Content-Type', 'application/json')
                urllib.request.urlopen(req, timeout=5)

            user_slug = self._sanitize_user_id(self.active_user)
            user_endpoint = f"{self.db_url}/users/{user_slug}/billing.json"
            data_user = json.dumps(usage_data).encode('utf-8')
            req_u = urllib.request.Request(user_endpoint, data=data_user, method='PATCH')
            req_u.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req_u, timeout=5)
            # print(f"[Firebase Sync] Usage & Billing synced to Firebase: {usage_data.get('total_tokens', 0)} tokens")
            return True
        except Exception as e:
            # print(f"[Firebase Usage Sync Error] {e}")
            return False

    def fetch_usage_and_billing(self, host_id):
        try:
            # Prefer pulling directly from the host's usage node if available
            if host_id:
                endpoint = f"{self.db_url}/hosts/{host_id}/usage.json"
                req = urllib.request.Request(endpoint, method='GET')
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode('utf-8'))
                        if data and isinstance(data, dict):
                            return data
            
            # Fallback to user node
            user_slug = self._sanitize_user_id(self.active_user)
            user_endpoint = f"{self.db_url}/users/{user_slug}/billing.json"
            req_u = urllib.request.Request(user_endpoint, method='GET')
            with urllib.request.urlopen(req_u, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data and isinstance(data, dict):
                        return data
        except Exception as e:
            pass
        return None

    def sync_tunnel_url(self, tunnel_url, user_id=None, auth_token=None, pairing_token=None, host_id=None):
        if host_id:
            return self.sync_host_state(host_id, pairing_token, tunnel_url)
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
                    # print(f"[Firebase Sync] Device state synced to Firebase: {tunnel_url}")
                    return True
        except Exception as e:
            # print(f"[Firebase Sync Error] {e}")
            return False

    def start_heartbeat_loop(self, get_tunnel_func, get_host_info_func=None, interval=15):
        def loop():
            while True:
                try:
                    current_url = get_tunnel_func()
                    if get_host_info_func:
                        info = get_host_info_func()
                        host_id = info[0]
                        pair_token = info[1]
                        pc_name = info[2]
                        wake_token = info[3] if len(info) > 3 else None
                        self.sync_host_state(host_id, pair_token, current_url, pc_name, wake_token)
                    else:
                        self.sync_tunnel_url(current_url)
                except Exception as e:
                    # print(f"[Firebase Watchdog Error] {e}")
                    pass
                time.sleep(interval)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return t

firebase_sync = FirebaseSync()
