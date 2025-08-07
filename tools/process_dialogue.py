import json
import os
import functools
from config import get_openai_client

example = """I'm so glad you asked! As an adventurous soul, I've had the privilege of exploring many incredible places on Nova Terra. One of my absolute favorites is the Crystal Caves of Zha'thik. The luminescent crystals that line the caverns are truly breathtaking, and the ancient alien carvings on the walls are a testament to the planet's rich history. It's a place that never fails to leave me in awe.

Another spot that holds a special place in my heart is the Skyforest of Elyria. The towering trees, infused with a soft, ethereal glow, stretch towards the sky like nature's own cathedral. The forest is home to a diverse array of flora and fauna, and I've had the privilege of encountering some truly remarkable creatures during my travels here.

Of course, there are countless other wonders to discover on Nova Terra, and I'm always excited to explore new places and uncover their secrets. What about you, have you had a chance to explore any of these amazing destinations?"""

# Optimized system prompt
SYSTEM_PROMPT = "You are a data engineer processing dialogue from a NPC. Given the dialogue, take the most important parts, and summarize in a json format. Use one word to describe the general idea as the key, and more detail as the value."

@functools.lru_cache(maxsize=64)
def process_dialogue_cached(dialogue_hash: str, dialogue: str) -> str:
    """Cached version of dialogue processing to avoid redundant API calls."""
    client = get_openai_client()
    
    prompt = f"Set this paragraph into important bullet points: {dialogue}"

    try:
        chat_completion = client.chat.completions.create(
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="gpt-3.5-turbo-0125",
        )

        result = chat_completion.choices[0].message.content
        return result if result else "{}"
        
    except Exception as e:
        print(f"Error in process_dialogue: {e}")
        return json.dumps({"error": f"Processing failed: {str(e)}"})

def process_dialogue_optimized(dialogue: str) -> str:
    """Optimized dialogue processing with caching and shared client."""
    # Create a hash of the dialogue for caching
    dialogue_hash = str(hash(dialogue))
    return process_dialogue_cached(dialogue_hash, dialogue)

# Keep original function for backwards compatibility
def process_dialogue(dialogue: str) -> str:
    """Original function kept for backwards compatibility."""
    return process_dialogue_optimized(dialogue)