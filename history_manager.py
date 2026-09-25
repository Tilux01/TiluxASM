import os
import json
import time
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "chat_sessions.json")

class HistoryManager:
    def __init__(self, filepath=HISTORY_FILE):
        self.filepath = filepath
        self.sessions = self._load()
        self.current_session_id = None

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[HistoryManager Load Error] {e}")
        return []

    def _save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[HistoryManager Save Error] {e}")

    def list_sessions(self):
        result = []
        for s in self.sessions:
            result.append({
                "id": s["id"],
                "title": s.get("title", "New Conversation"),
                "timestamp": s.get("timestamp", ""),
                "message_count": len(s.get("messages", []))
            })
        result.sort(key=lambda x: x["id"], reverse=True)
        return result

    def get_session(self, session_id):
        for s in self.sessions:
            if s["id"] == session_id:
                return s
        return None

    def start_new_session(self):
        new_id = f"session_{int(time.time() * 1000)}"
        self.current_session_id = new_id
        return new_id

    def _generate_title_from_text(self, text):
        if not text:
            return "New Conversation"
        import re
        # Remove attached file blocks, image tags, and HTML tags
        clean = re.sub(r'--- Attached File:.*?---', '', text, flags=re.DOTALL)
        clean = re.sub(r'\[Image uploaded:.*?\]', '', clean)
        clean = re.sub(r'<[^>]+>', '', clean)
        clean = clean.strip()
        if not clean:
            return "Attachment / Image"
            
        first_line = clean.split('\n')[0].strip()
        if len(first_line) <= 35:
            return first_line.capitalize()
            
        # Clean trim to nearest word boundary under 35 chars
        trimmed = first_line[:35]
        last_space = trimmed.rfind(' ')
        if last_space > 10:
            trimmed = trimmed[:last_space]
        return (trimmed + "...").capitalize()

    def add_message(self, session_id, sender, text, events=None):
        if not session_id:
            session_id = self.start_new_session()
            
        session = self.get_session(session_id)
        now_str = datetime.datetime.now().strftime("%b %d, %H:%M")
        
        if not session:
            title = self._generate_title_from_text(text) if sender == "User" else "New Conversation"
            session = {
                "id": session_id,
                "title": title,
                "timestamp": now_str,
                "messages": []
            }
            self.sessions.append(session)
        else:
            if (session.get("title") == "New Conversation" or not session.get("title")) and sender == "User":
                session["title"] = self._generate_title_from_text(text)
            session["timestamp"] = now_str
            
        msg = {
            "sender": sender,
            "text": text,
            "timestamp": time.strftime("%H:%M"),
            "events": events or []
        }
        session["messages"].append(msg)
        self._save()
        return session_id

    def delete_session(self, session_id):
        self.sessions = [s for s in self.sessions if s["id"] != session_id]
        if self.current_session_id == session_id:
            self.current_session_id = None
        self._save()
        return True

history_manager = HistoryManager()
