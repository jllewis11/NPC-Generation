import json
import os

import gradio as gr
from openai import OpenAI

import example
import asyncio
from utils.read import read_json
from tools.personality import read_personality
from tools.names import generate_names
from dotenv import load_dotenv




async def character_generation(prompt, examples, name):
  load_dotenv()
  client = OpenAI(
  # This is the default and can be omitted
  api_key=os.getenv("OPENAI_API_KEY"), )

  # Add a prompt for the model to generate a new example
  prompt += "Create a new character profile that fits in this environment with the following personality " + str(
      read_personality) + " and this name " + name

  print(prompt)

  chat_completion = client.chat.completions.create(
      response_format={"type": "json_object"},
      messages=[{
          "role":
          "system",
          "content":
          "You are a creative team designing NPC characters based upon a given environment prompt and output in a json format",
      }, {
          "role": "user",
          "content": prompt
      }],
      model="gpt-4o-mini-2024-07-18",
  )
  chat = ""
  character = dict()
  if chat_completion.choices[0].message.content is not None:
    temp = json.loads(chat_completion.choices[0].message.content)
    character["name"] = temp["name"]
    character["age"] = temp["age"]
    character["gender"] = temp["gender"]
    character["personalities"] = temp["personalities"]
    character["appearance"] = temp["appearance"]
    character["background"] = temp["background"]
    chat = str(character)

  # generated_image = client.images.generate(
  #   model="dall-e-2",
  #   prompt=chat,
  #   n=1,
  #   size="1024x1024"
  # )

  print(type(chat_completion.choices[0].message.content))
  print(chat_completion)
  final = chat_completion.choices[0].message.content
  # return [chat_completion.choices[0].message.content, generated_image.data[0].url]
  return "" if final is None else final

async def relationship_generation(prompt,characters):
  load_dotenv()
  client = OpenAI(
  # This is the default and can be omitted
  api_key=os.getenv("OPENAI_API_KEY"), )

  # Add a prompt for the model to generate a new example
  prompt += " Given a list of characters, generate a edge list of relationships between them with a backstory and a description of the relationship. Add a weight to each relationship between -1 and 1. Have a good mix between positive and negative relationships. This is the list of characters: " + str(characters)

  print(prompt)

  chat_completion = client.chat.completions.create(
      response_format={"type": "json_object"},
      messages=[{
          "role":
          "system",
          "content":
          "You are a creative team designing NPC characters based upon a given environment prompt and output in a json format",
      }, {
          "role": "user",
          "content": prompt
      }],
      model="gpt-4o-mini-2024-07-18",
  )
  if chat_completion.choices[0].message.content is not None:
    temp = json.loads(chat_completion.choices[0].message.content)

  print(type(chat_completion.choices[0].message.content))
  print(chat_completion)
  final = chat_completion.choices[0].message.content
  # return [chat_completion.choices[0].message.content, generated_image.data[0].url]
  return "" if final is None else final



async def instruction(file_obj, amount):
  amount = int(amount)
  data = read_json(file_obj)
  environment_context = (f"Era: {data['era']}, "
                         f"Time Period: {data['time_period']}, "
                         f"Detail: {data['detail']}\n\n")
  examples = example.examples

  prompt = environment_context + "\n\n".join([e["example"]
                                              for e in examples]) + "\n\n"

  tasks = set()

  names = generate_names(file_obj, amount)
  for x in range(amount):

    task = asyncio.create_task(character_generation(prompt, examples, names[x]))
    tasks.add(task)


  await asyncio.gather(*tasks)

  results = [json.loads(task.result()) for task in tasks]
  
  # Format the results as a list of JSON objects
  formatted_results = json.dumps(results, indent=2)

  # Write the formatted results to output.json in the main project folder
  output_file = os.path.join(os.getcwd(), 'output.json')
  with open(output_file, 'w') as outfile:
      outfile.write(formatted_results)

  data = read_json(file_obj)
  environment_context = (f"Era: {data['era']}, "
                         f"Time Period: {data['time_period']}, "
                         f"Detail: {data['detail']}\n\n")


  prompt = environment_context 

  edge_list = await relationship_generation(prompt,results)
  #combine results and edgelist together
  combined_results = {
      "characters": results,
      "edge_list": edge_list
  }

  return combined_results