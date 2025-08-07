import json
import os
import gradio as gr
from utils.read import read_json

# Keep the original function for backwards compatibility
def generate_names(file_obj, amount):
    from config import get_openai_client
    client = get_openai_client()
    return generate_names_optimized(file_obj, amount, client)

def generate_names_optimized(file_obj, amount, client):
    """Optimized name generation using shared client."""
    try:
        data = read_json(file_obj)
        environment_context = (
            f"Era: {data['era']}, "
            f"Time Period: {data['time_period']}, "
            f"Detail: {data['detail']}\n\n"
        )
        
        prompt = f"{environment_context}Given the json file describing an environment, create {amount} unique names for NPCs in that environment. Output a list of these names in a json format."

        chat_completion = client.chat.completions.create(
            response_format={ "type": "json_object" },
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative team designing NPC characters. Given an environment description, generate unique names that fit the setting. Output as a JSON array with a 'names' field.",
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="gpt-3.5-turbo-0125",
        )

        content = chat_completion.choices[0].message.content
        if not content:
            return [f"Character_{i}" for i in range(amount)]  # Fallback names
            
        result = json.loads(content)
        names = result.get('names', [])
        
        # Ensure we have enough names
        while len(names) < amount:
            names.append(f"Character_{len(names)}")
            
        return names[:amount]  # Return exactly the requested amount
        
    except Exception as e:
        print(f"Error in name generation: {e}")
        # Return fallback names
        return [f"Character_{i}" for i in range(amount)]
