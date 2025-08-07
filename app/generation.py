import json
import os
import asyncio
from typing import List, Dict, Any
import gradio as gr

import example
from utils.read import read_json
from tools.personality import read_personality
from tools.names import generate_names_optimized
from config import get_openai_client

# Pre-compile frequently used strings
SYSTEM_PROMPTS = {
    "character": "You are a creative team designing NPC characters based upon a given environment prompt and output in a json format",
    "relationship": "You are a creative team designing NPC characters based upon a given environment prompt and output in a json format where the relationships are listed in an array"
}

async def character_generation(prompt: str, name: str, client) -> str:
    """Optimized character generation with shared client and better error handling."""
    try:
        # Add a prompt for the model to generate a new example
        full_prompt = f"{prompt}Create a new character profile that fits in this environment with the following personality {read_personality()} and this name {name}"

        chat_completion = await asyncio.create_task(
            asyncio.to_thread(
                client.chat.completions.create,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "system",
                    "content": SYSTEM_PROMPTS["character"]
                }, {
                    "role": "user",
                    "content": full_prompt
                }],
                model="gpt-4o-mini-2024-07-18",
            )
        )
        
        if chat_completion.choices[0].message.content is None:
            return "{}"
            
        # Parse and validate the response
        content = chat_completion.choices[0].message.content
        temp = json.loads(content)
        
        # Structure the character data consistently
        character = {
            "name": temp.get("name", name),
            "age": temp.get("age", 0),
            "gender": temp.get("gender", ""),
            "personalities": temp.get("personalities", []),
            "appearance": temp.get("appearance", {}),
            "background": temp.get("background", {})
        }
        
        return json.dumps(character)
        
    except Exception as e:
        print(f"Error in character generation: {e}")
        return json.dumps({"name": name, "error": str(e)})

async def relationship_generation(prompt: str, examples: List[Dict], characters: List[Dict], client) -> List[Dict]:
    """Optimized relationship generation with better error handling."""
    try:
        full_prompt = f"{prompt} Given a list of characters, generate a edge list of relationships between them with a backstory and a description of the relationship. Add a weight to each relationship between -1 and 1. Have a good mix between positive and negative relationships. This is the list of characters: {characters}\n\n Generate following the examples from below: {examples}"

        chat_completion = await asyncio.create_task(
            asyncio.to_thread(
                client.chat.completions.create,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "system",
                    "content": SYSTEM_PROMPTS["relationship"]
                }, {
                    "role": "user",
                    "content": full_prompt
                }],
                model="gpt-4o-mini-2024-07-18",
            )
        )

        if chat_completion.choices[0].message.content is None:
            return []
            
        content = chat_completion.choices[0].message.content
        
        # Optimize file writing with async
        await asyncio.create_task(
            asyncio.to_thread(
                write_json_file,
                'output-edgelist.json',
                content
            )
        )

        final = json.loads(content)
        relationships = []

        if "edge_list" in final and "relationships" in final["edge_list"]:
            for rel in final["edge_list"]["relationships"]:
                relationships.append({
                    "from": rel.get("from", ""),
                    "to": rel.get("to", ""),
                    "description": rel.get("description", ""),
                    "weight": rel.get("weight", 0)
                })

        return relationships
        
    except Exception as e:
        print(f"Error in relationship generation: {e}")
        return []

def write_json_file(filename: str, content: str) -> None:
    """Helper function for writing JSON files."""
    output_file = os.path.join(os.getcwd(), filename)
    with open(output_file, 'w') as outfile:
        outfile.write(json.dumps(json.loads(content), indent=2))

async def instruction(file_obj, amount: int) -> Dict[str, Any]:
    """Optimized main instruction function with better concurrency and error handling."""
    amount = int(amount)
    
    # Use shared client instance
    client = get_openai_client()
    
    # Read file once and cache
    try:
        data = read_json(file_obj)
        environment_context = (f"Era: {data['era']}, "
                             f"Time Period: {data['time_period']}, "
                             f"Detail: {data['detail']}\n\n")
    except Exception as e:
        return {"error": f"Failed to read input file: {str(e)}"}

    examples = example.examples
    prompt = environment_context + "\n\n".join([e["example"] for e in examples]) + "\n\n"

    try:
        # Generate names first (this is synchronous but fast)
        names = generate_names_optimized(file_obj, amount, client)
        
        # Create character generation tasks with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent API calls
        
        async def bounded_character_generation(prompt_text, name):
            async with semaphore:
                return await character_generation(prompt_text, name, client)
        
        # Create and execute character generation tasks
        character_tasks = [
            bounded_character_generation(prompt, names[x])
            for x in range(amount)
        ]
        
        character_results = await asyncio.gather(*character_tasks, return_exceptions=True)
        
        # Filter out exceptions and parse results
        results = []
        for result in character_results:
            if isinstance(result, Exception):
                print(f"Character generation failed: {result}")
                continue
            try:
                results.append(json.loads(result))
            except json.JSONDecodeError as e:
                print(f"Failed to parse character result: {e}")
                continue

        if not results:
            return {"error": "No characters were successfully generated"}

        # Write characters to file asynchronously
        await asyncio.create_task(
            asyncio.to_thread(
                write_json_file,
                'output.json',
                json.dumps(results)
            )
        )

        # Generate relationships
        edge_list = await relationship_generation(environment_context, example.edge_list, results, client)

        # Combine results
        combined_results = {
            "characters": results,
            "edge_list": edge_list
        }

        return combined_results
        
    except Exception as e:
        return {"error": f"Generation failed: {str(e)}"}