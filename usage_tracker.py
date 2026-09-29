import os
import json
import time
import threading

USAGE_FILE = "usage_stats.json"

# Pricing rates (2.5x DeepSeek V3/R1 rate)
# Input: $0.35 per 1M tokens ($0.00035 per 1K)
# Output: $0.70 per 1M tokens ($0.00070 per 1K)
RATE_INPUT_PER_1M = 0.35
RATE_OUTPUT_PER_1M = 0.70

# 24-Hour Free Trial Duration in Seconds (86,400s)
FREE_TRIAL_DURATION_SEC = 24 * 3600

class UsageTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.stats = self._load_stats()
        self.socketio = None

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

    def _load_stats(self):
        if not os.path.exists(USAGE_FILE):
            default_data = self._default_stats()
            self._save_stats_file(default_data)
            return default_data
        try:
            with open(USAGE_FILE, "r") as f:
                data = json.load(f)
                # Ensure all key fields exist
                defaults = self._default_stats()
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            print(f"[UsageTracker Load Error] {e}")
            return self._default_stats()

    def _save_stats_file(self, data):
        try:
            with open(USAGE_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[UsageTracker Save Error] {e}")

    def is_free_trial_active(self):
        with self.lock:
            now = int(time.time())
            trial_ends = self.stats.get("trial_ends_at", 0)
            return now < trial_ends

    def get_remaining_trial_seconds(self):
        with self.lock:
            now = int(time.time())
            trial_ends = self.stats.get("trial_ends_at", 0)
            remaining = trial_ends - now
            return max(0, remaining)

    def can_generate(self):
        with self.lock:
            now = int(time.time())
            trial_ends = self.stats.get("trial_ends_at", 0)
            is_trial = now < trial_ends
            if is_trial:
                return True
            wallet = self.stats.get("wallet_balance_usd", 0.0)
            return wallet > 0.001  # Need at least a fraction of a cent to start a generation

    def record_usage(self, input_tokens: int, output_tokens: int):
        """Calculates input & output tokens, applies 2x DeepSeek rate, checks trial/wallet, and syncs."""
        if input_tokens <= 0 and output_tokens <= 0:
            return self.get_summary()

        with self.lock:
            now = int(time.time())
            input_tokens = max(0, int(input_tokens))
            output_tokens = max(0, int(output_tokens))
            total_turn_tokens = input_tokens + output_tokens

            # Calculate cost at 2x DeepSeek rate
            turn_input_cost = (input_tokens / 1_000_000.0) * RATE_INPUT_PER_1M
            turn_output_cost = (output_tokens / 1_000_000.0) * RATE_OUTPUT_PER_1M
            turn_total_cost = turn_input_cost + turn_output_cost

            # Check 24-hour trial status
            trial_ends = self.stats.get("trial_ends_at", 0)
            is_trial = now < trial_ends

            # Update token counts
            self.stats["total_input_tokens"] += input_tokens
            self.stats["total_output_tokens"] += output_tokens
            self.stats["total_tokens"] += total_turn_tokens
            self.stats["total_cost_usd"] += turn_total_cost
            self.stats["last_updated"] = now

            # If trial has expired, deduct cost from wallet balance
            if not is_trial:
                current_wallet = self.stats.get("wallet_balance_usd", 0.0)
                new_wallet = max(0.0, current_wallet - turn_total_cost)
                self.stats["wallet_balance_usd"] = round(new_wallet, 6)

            self._save_stats_file(self.stats)

        summary = self.get_summary()
        self.broadcast_and_sync(summary)
        return summary

    def add_funds(self, amount_usd: float, gateway: str, reference: str):
        """Adds funded balance to wallet upon successful Paystack or Flutterwave payment. Idempotent by reference."""
        if amount_usd <= 0 or not reference:
            return self.get_summary()

        with self.lock:
            history = self.stats.get("payment_history", [])
            # Prevent duplicate crediting for identical reference
            for item in history:
                if item.get("reference") == reference:
                    return self.get_summary()

            now = int(time.time())
            current_wallet = self.stats.get("wallet_balance_usd", 0.0)
            new_wallet = current_wallet + float(amount_usd)
            self.stats["wallet_balance_usd"] = round(new_wallet, 4)

            history.append({
                "timestamp": now,
                "amount_usd": float(amount_usd),
                "gateway": gateway,
                "reference": reference,
                "status": "success"
            })
            self.stats["payment_history"] = history
            self.stats["last_updated"] = now
            self._save_stats_file(self.stats)

        summary = self.get_summary()
        self.broadcast_and_sync(summary)
        return summary

    def get_summary(self):
        with self.lock:
            now = int(time.time())
            trial_ends = self.stats.get("trial_ends_at", 0)
            is_trial = now < trial_ends
            remaining_sec = max(0, trial_ends - now)
            hours_left = round(remaining_sec / 3600.0, 1)

            return {
                "account_created_at": self.stats.get("account_created_at", now),
                "trial_ends_at": trial_ends,
                "is_free_trial": is_trial,
                "remaining_trial_hours": hours_left,
                "remaining_trial_seconds": remaining_sec,
                "wallet_balance_usd": round(self.stats.get("wallet_balance_usd", 0.0), 4),
                "total_input_tokens": self.stats.get("total_input_tokens", 0),
                "total_output_tokens": self.stats.get("total_output_tokens", 0),
                "total_tokens": self.stats.get("total_tokens", 0),
                "total_cost_usd": round(self.stats.get("total_cost_usd", 0.0), 6),
                "payment_history": self.stats.get("payment_history", []),
                "last_updated": self.stats.get("last_updated", now)
            }

    def broadcast_and_sync(self, summary=None):
        if summary is None:
            summary = self.get_summary()

        # Emit SocketIO event if socketio is attached
        if self.socketio:
            try:
                self.socketio.emit("token_usage_update", summary)
            except Exception as e:
                print(f"[UsageTracker SocketIO Error] {e}")

        # Sync to Firebase RTDB asynchronously
        def _sync():
            try:
                from firebase_sync import firebase_sync
                from server import HOST_ID
                firebase_sync.sync_usage_and_billing(HOST_ID, summary)
            except Exception as e:
                pass

        threading.Thread(target=_sync, daemon=True).start()

usage_tracker = UsageTracker()
