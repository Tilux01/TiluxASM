import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

models = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "z-ai/glm-5.2:free"
]

for m in models:
    print(f"Testing {m}...")
    try:
        response = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
        print("  SUCCESS!")
        break
    except Exception as e:
        print("  ERROR:", str(e))
