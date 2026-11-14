import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("TILUX_USER_DATA_DIR") or BASE_DIR
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")

def load_memory() -> list:
    """Loads all saved facts/rules from memory."""
    target = MEMORY_FILE
    if not os.path.exists(target):
        cand = os.path.join(BASE_DIR, "memory.json")
        if os.path.exists(cand):
            target = cand
    if not os.path.exists(target):
        return []
    try:
        with open(target, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_fact(fact: str) -> str:
    """Saves a new fact/rule to memory."""
    facts = load_memory()
    if fact not in facts:
        facts.append(fact)
        with open(MEMORY_FILE, 'w') as f:
            json.dump(facts, f, indent=4)
        return f"Successfully remembered: {fact}"
    return "I already know that."

def forget_fact(fact: str) -> str:
    """Removes a fact from memory."""
    facts = load_memory()
    if fact in facts:
        facts.remove(fact)
        with open(MEMORY_FILE, 'w') as f:
            json.dump(facts, f, indent=4)
        return f"I have forgotten: {fact}"
    return "I don't have that in my memory."

get_facts = load_memory

