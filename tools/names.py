import json
import os
import gradio as gr
from openai import OpenAI
from utils.read import read_json
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
  # This is the default and can be omitted
  api_key=os.getenv("OPENAI"),
)

def generate_names(file_obj, amount):
  data = read_json(file_obj)
  environment_context = (
      f"Era: {data['era']}, "
      f"Time Period: {data['time_period']}, "
      f"Detail: {data['detail']}\n\n"
  )
  
  prompt = environment_context + "Given the json file describing an environment, create " + str(amount) + " unique names that don't repeat for NPCs in that environment. Output a list of these names in a json format." 

  chat_completion = client.chat.completions.create(
    response_format={ "type": "json_object" },
    messages=[
        {
            "role": "system",
            "content": "You are a creative team designing NPC characters. Given these personalities, choose 5, and output in a json",
        },
      {
          "role": "user",
          "content": prompt
      }

    ],
    model="gpt-3.5-turbo-0125",
  )

  print(chat_completion.choices[0].message.content)
  return chat_completion.choices[0].message.content
