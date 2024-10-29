import os
import gradio as gr
import time
import json
from langchain_together import ChatTogether
from dotenv import load_dotenv
from tools.process_dialogue import process_dialogue
import chromadb
import uuid


chat = ChatTogether(
        model="meta-llama/Llama-3-8b-chat-hf",
        together_api_key = os.getenv("TOGETHER_API_KEY"),
)

environment_context = None
character_context = None

with open("JSONdata/prompt2.json", "r") as file:
    environment_context = json.load(file)

with open("JSONdata/KaiyaStarling.json", "r") as file:
    character_context = json.load(file)

persist_directory = "data"

client = chromadb.PersistentClient(path=persist_directory)


def npc_chat(message, history):
    initial_time = time.time()
    load_dotenv()

    # Initialize chromaDB

    character_name = character_context["name"]
    collection = client.get_or_create_collection(name=character_name.replace(" ", "_"))

    results = collection.query(
    query_texts=[message], # Chroma will embed this for you
    n_results=2 # how many results to return
    )

    print(results)

    #Create a character_description that ensures that the LLM only response to the confines of the character's background, skills, and secrets. 
    #Save previous messages using chromaDB
    system_prompt = f"""
    You are the character, {character_name}
    Your character description is as follows:\n\n {character_context}\n\n.
    Here is the environment where the character is from:
    \n\n {environment_context} \n\n
    The way you speak should be influenced by your personalities, which are listed here: {character_context['personalities']}.
    Your knowledge is limited to only what you know in background, skills, and secrets. Redirect if the player asks about something you don't know or answer with I don't know.
    
    Here is what we have said so far:

    History (Use for information, but vary responses somewhat):
    \n\n{history}\n\n

    From memory:
    {results}

    """

    user_msg = f"""
    The player said this: {message}\n
    """

    model_answer = None
    
    prompt = f"""
    <|begin_of_text|><|start_header_id|>system<|end_header_id|>

    { system_prompt }<|eot_id|><|start_header_id|>user<|end_header_id|>

    { user_msg }<|eot_id|><|start_header_id|>assistant<|end_header_id|>

    { model_answer }<|eot_id|>

    """



    output = chat.invoke(prompt)
    print(output)
    output = process_dialogue(output.content)
    # Generate UUID for the document

    collection.add(
    documents=[
            output,
        ],
    metadatas=[{"time": time.time()}],
    ids=[str(uuid.uuid4())]
    )


    t = f"Time taken: {time.time() - initial_time}"
    print(t)

    return t + "\n\n" + output.content


def shutdown():
    client.close()