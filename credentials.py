import os
import keyring

SERVICE_NAME = "TiluxASM"

KEYS_DEF = {
    "DEEPSEEK_API_KEY": "your_deepseek_key_here",
    "GEMINI_API_KEY": "your_gemini_key_here",
    "OPENROUTER_API_KEY": "your_openrouter_key_here",
    "GROQ_API_KEY": "your_groq_key_here",
    "QWEN_API_KEY": "your_qwen_key_here"
}

def init_vault_credentials():
    """Initializes keys into local OS Keyring vault on system boot / setup."""
    for key_name, default_val in KEYS_DEF.items():
        try:
            current = keyring.get_password(SERVICE_NAME, key_name)
            if not current:
                env_val = os.getenv(key_name) or default_val
                if env_val:
                    keyring.set_password(SERVICE_NAME, key_name, env_val)
        except Exception as e:
            print(f"[Credentials Vault Notice] {key_name}: {e}")

def get_credential(key_name: str, fallback: str = "") -> str:
    """Retrieves secret credential from OS Keyring vault with fallback."""
    try:
        val = keyring.get_password(SERVICE_NAME, key_name)
        if val:
            return val
    except Exception:
        pass
    env_val = os.getenv(key_name)
    if env_val:
        return env_val
    return KEYS_DEF.get(key_name, fallback)

def load_credentials_into_env():
    init_vault_credentials()
    for key_name in KEYS_DEF.keys():
        val = get_credential(key_name)
        if val:
            os.environ[key_name] = val

load_credentials_into_env()
