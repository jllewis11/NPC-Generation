import os
import gradio as gr
import time
import json
import uuid
import functools
from typing import Dict, Any, List
from tools.process_dialogue import process_dialogue_optimized
from config import get_together_client, get_chroma_client, config

# Cache the chat client globally
chat = None
chroma_client = None
environment_context = None
character_context = None

def initialize_clients():
    """Initialize clients and load context data once."""
    global chat, chroma_client, environment_context, character_context
    
    if chat is None:
        chat = get_together_client()
    
    if chroma_client is None:
        chroma_client = get_chroma_client()
    
    if environment_context is None:
        environment_context = config.get_environment_context()
    
    if character_context is None:
        character_context = config.get_character_context()

# Pre-compile system prompt template for better performance
SYSTEM_PROMPT_TEMPLATE = """
You are the character, {character_name}
Your character description is as follows:

{character_context}

Here is the environment where the character is from:

{environment_context}

The way you speak should be influenced by your personalities, which are listed here: {personalities}.
Your knowledge is limited to only what you know in background, skills, and secrets. Redirect if the player asks about something you don't know or answer with I don't know.

Here is what we have said so far:

History (Use for information, but vary responses somewhat):

{history}

From memory:
{memory_results}
"""

USER_PROMPT_TEMPLATE = """
The player said this: {message}
"""

@functools.lru_cache(maxsize=32)
def get_collection(character_name: str):
    """Get or create collection for character with caching."""
    global chroma_client
    if chroma_client is None:
        initialize_clients()
    
    collection_name = character_name.replace(" ", "_").replace("-", "_")
    return chroma_client.get_or_create_collection(name=collection_name)

def npc_chat(message: str, history: List) -> str:
    """Optimized NPC chat with better caching and performance."""
    initial_time = time.time()
    
    # Initialize clients if not already done
    initialize_clients()
    
    try:
        character_name = character_context.get("name", "Unknown")
        personalities = character_context.get("personalities", [])
        
        # Get collection with caching
        collection = get_collection(character_name)

        # Query memory efficiently
        try:
            results = collection.query(
                query_texts=[message],
                n_results=2  # Reduced from potentially larger queries
            )
        except Exception as e:
            print(f"ChromaDB query failed: {e}")
            results = {"documents": []}

        # Build prompts using templates
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            character_name=character_name,
            character_context=character_context,
            environment_context=environment_context,
            personalities=personalities,
            history=history,
            memory_results=results
        )

        user_msg = USER_PROMPT_TEMPLATE.format(message=message)

        # Optimized prompt format
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

{user_msg}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

<|eot_id|>"""

        # Get response from model
        output = chat.invoke(prompt)
        
        if not output or not output.content:
            return "I'm sorry, I couldn't process that request."

        # Process dialogue optimally
        processed_output = process_dialogue_optimized(output.content)
        
        # Store in memory with error handling
        try:
            collection.add(
                documents=[processed_output],
                metadatas=[{"time": time.time()}],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            print(f"Failed to store in ChromaDB: {e}")

        elapsed_time = time.time() - initial_time
        print(f"Response time: {elapsed_time:.2f}s")

        return processed_output

    except Exception as e:
        print(f"Error in npc_chat: {e}")
        return f"I'm experiencing some technical difficulties. Error: {str(e)}"

def shutdown():
    """Optimized shutdown with proper client cleanup."""
    global chroma_client, chat
    try:
        if chroma_client:
            chroma_client.close()
            chroma_client = None
        # Note: Together client doesn't need explicit cleanup
        chat = None
    except Exception as e:
        print(f"Error during shutdown: {e}")