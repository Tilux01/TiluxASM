import os
import json
import time
import threading

# Pricing rates (2.5x DeepSeek V3/R1 rate)
RATE_INPUT_PER_1M = 0.35
RATE_OUTPUT_PER_1M = 0.70

# 24-Hour Free Trial Duration in Seconds (86,400s)
FREE_TRIAL_DURATION_SEC = 24 * 3600

class UsageTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.socketio = None
        self.host_id = None
        # Minimal in-memory cache to prevent blocking UI excessively, 
        # but ALWAYS fetched fresh on critical operations.
        self._cached_stats = None
        self._last_fetch_time = 0

    def _default_stats(self):
        now = int(time.time())
        return {
            "account_created_at": now,
            "trial_ends_at": now + FREE_TRIAL_DURATION_SEC,
            "wallet_balance_usd": 5.00,  # Default starting balance after trial
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "payment_history": [],
            "last_updated": now
        }

    def _fetch_realtime_stats(self):
        """Always pulls the absolute latest from Firebase."""
        if not self.host_id:
            return self._cached_stats or self._default_stats()
            
        try:
            from firebase_sync import firebase_sync
            cloud_data = firebase_sync.fetch_usage_and_billing(self.host_id)
            if cloud_data:
                # Ensure all keys exist
                defaults = self._default_stats()
                for k, v in defaults.items():
                    if k not in cloud_data:
                        cloud_data[k] = v
                self._cached_stats = cloud_data
                self._last_fetch_time = time.time()
                return cloud_data
        except Exception as e:
            pass
            
        return self._cached_stats or self._default_stats()

    def _save_realtime_stats(self, data):
        """Pushes directly to Firebase and updates memory cache. No local file."""
        self._cached_stats = data
        self._last_fetch_time = time.time()
        if self.host_id:
            def _push():
                try:
                    from firebase_sync import firebase_sync
                    firebase_sync.sync_usage_and_billing(self.host_id, data)
                except Exception:
                    pass
            threading.Thread(target=_push, daemon=True).start()

    def can_generate(self):
        with self.lock:
            stats = self._fetch_realtime_stats()
            now = int(time.time())
            trial_ends = stats.get("trial_ends_at", 0)
            if now < trial_ends:
                return True
            return stats.get("wallet_balance_usd", 0.0) > 0.001

    def get_summary(self):
        with self.lock:
            stats = self._fetch_realtime_stats()
            now = int(time.time())
            trial_ends = stats.get("trial_ends_at", 0)
            is_trial = now < trial_ends
            remaining_sec = max(0, trial_ends - now)
            hours_left = round(remaining_sec / 3600.0, 1)

            return {
                "account_created_at": stats.get("account_created_at", now),
                "trial_ends_at": trial_ends,
                "is_free_trial": is_trial,
                "remaining_trial_hours": hours_left,
                "remaining_trial_seconds": remaining_sec,
                "wallet_balance_usd": round(stats.get("wallet_balance_usd", 0.0), 4),
                "total_input_tokens": stats.get("total_input_tokens", 0),
                "total_output_tokens": stats.get("total_output_tokens", 0),
                "total_tokens": stats.get("total_tokens", 0),
                "total_cost_usd": round(stats.get("total_cost_usd", 0.0), 6),
                "payment_history": stats.get("payment_history", []),
                "last_updated": stats.get("last_updated", now)
            }

    def record_usage(self, input_tokens: int, output_tokens: int):
        if input_tokens <= 0 and output_tokens <= 0:
            return self.get_summary()

        with self.lock:
            stats = self._fetch_realtime_stats()
            now = int(time.time())
            input_tokens = max(0, int(input_tokens))
            output_tokens = max(0, int(output_tokens))
            total_turn_tokens = input_tokens + output_tokens

            turn_input_cost = (input_tokens / 1_000_000.0) * RATE_INPUT_PER_1M
            turn_output_cost = (output_tokens / 1_000_000.0) * RATE_OUTPUT_PER_1M
            turn_total_cost = turn_input_cost + turn_output_cost

            is_trial = now < stats.get("trial_ends_at", 0)

            stats["total_input_tokens"] += input_tokens
            stats["total_output_tokens"] += output_tokens
            stats["total_tokens"] += total_turn_tokens
            stats["total_cost_usd"] += turn_total_cost
            stats["last_updated"] = now

            if not is_trial:
                current_wallet = stats.get("wallet_balance_usd", 0.0)
                new_wallet = max(0.0, current_wallet - turn_total_cost)
                stats["wallet_balance_usd"] = round(new_wallet, 6)

            self._save_realtime_stats(stats)

        summary = self.get_summary()
        self.broadcast_and_sync(summary)
        return summary

    def add_funds(self, amount_usd: float, gateway: str, reference: str):
        if amount_usd <= 0 or not reference:
            return self.get_summary()

        with self.lock:
            stats = self._fetch_realtime_stats()
            history = stats.get("payment_history", [])
            for item in history:
                if item.get("reference") == reference:
                    return self.get_summary()

            now = int(time.time())
            current_wallet = stats.get("wallet_balance_usd", 0.0)
            stats["wallet_balance_usd"] = round(current_wallet + float(amount_usd), 4)

            history.append({
                "timestamp": now,
                "amount_usd": float(amount_usd),
                "gateway": gateway,
                "reference": reference,
                "status": "success"
            })
            stats["payment_history"] = history
            stats["last_updated"] = now
            
            self._save_realtime_stats(stats)

        summary = self.get_summary()
        self.broadcast_and_sync(summary)
        return summary

    def broadcast_and_sync(self, summary=None):
        if summary is None:
            summary = self.get_summary()
        if self.socketio:
            try:
                self.socketio.emit("token_usage_update", summary)
            except Exception as e:
                pass

    def sync_from_cloud(self, host_id):
        # Kept for compatibility if called externally, though _fetch_realtime_stats covers it
        self.host_id = host_id
        self._fetch_realtime_stats()

usage_tracker = UsageTracker()
