import os
import keyring

SERVICE_NAME = "TiluxASM"

KEYS_DEF = {}

def init_vault_credentials():
    """Initializes keys into local OS Keyring vault on system boot / setup."""
    for key_name, default_val in KEYS_DEF.items():
        try:
            current = keyring.get_password(SERVICE_NAME, key_name)
            if not current and default_val and not default_val.startswith("your_"):
                env_val = os.getenv(key_name) or default_val
                if env_val and not env_val.startswith("your_"):
                    keyring.set_password(SERVICE_NAME, key_name, env_val)
        except Exception as e:
            print(f"[Credentials Vault Notice] {key_name}: {e}")

def get_credential(key_name: str, fallback: str = "") -> str:
    """Retrieves secret credential from OS Keyring vault with fallback."""
    try:
        val = keyring.get_password(SERVICE_NAME, key_name)
        if val and not val.startswith("your_"):
            return val
    except Exception:
        pass
    env_val = os.getenv(key_name)
    if env_val and not env_val.startswith("your_"):
        return env_val
    def_val = KEYS_DEF.get(key_name, fallback)
    return def_val if def_val and not def_val.startswith("your_") else fallback

def load_credentials_into_env():
    init_vault_credentials()
    for key_name in KEYS_DEF.keys():
        val = get_credential(key_name)
        if val:
            os.environ[key_name] = val

load_credentials_into_env()
