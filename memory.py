import json
import os

MEMORY_FILE = "memory.json"

def load_memory() -> list:
    """Loads all saved facts/rules from memory."""
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, 'r') as f:
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
