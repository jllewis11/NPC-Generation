import os
import gradio as gr

import json
from langchain_together import Together
from dotenv import load_dotenv

def json_to_string(json_data):
    def process_dict(dictionary):
        result = ""
        for key, value in dictionary.items():
            if isinstance(value, dict):
                result += f"\n- {key}:\n" + process_dict(value)
            elif isinstance(value, list):
                result += f"\n- {key}:\n" + process_list(value)
            else:
                result += f"\n- {key}: {value}"
        return result

    def process_list(lst):
        result = ""
        for item in lst:
            result += f"  - {item}\n"
        return result

    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    return process_dict(json_data)


def response(message, history):
    load_dotenv()

    chat = Together(
        model="meta-llama/Llama-3-8b-chat-hf",
        temperature= 0.7,
        max_tokens= 2048,
        top_p= 0.7,
        top_k= 50,
        repetition_penalty= 1.0,
        together_api_key=os.getenv("TOGETHER_API_KEY"),
    )

    environment_context = None
    character_context = None
    character_name = "Kaiya Starling"

  


    with open("data/prompt2.json", "r") as file:
        environment_context = json_to_string(json.load(file))

    with open("data/KaiyaStarling.json", "r") as file:
        character_context = json_to_string(json.load(file))

    #Create a character_description that ensures that the LLM only response to the confines of the character's background, skills, and secrets. 

    #Save previous messages using chromaDB

    
    prompt = f"""
    <|begin_of_text|>
    You are the character, {character_name}. Your character description is as follows: {character_context}.
    Here is the environment where the character is from: {environment_context}.
    Your knowledge is limited to only what you know in background, skills, and secrets. Redirect if the player asks about something you don't know or answer with "I don't know."

    {{"response": "{message}"}}
    <|end_of_text|>
    """


    print(prompt)
    output = chat.invoke(prompt)
    print(output)

    return output


