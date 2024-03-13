import json
import os

import gradio as gr
from openai import OpenAI

import example


client = OpenAI(
  # This is the default and can be omitted
  api_key=os.environ.get("OPENAI"),
)


def read_json(file_obj):
  try:
    # Load JSON file
    with open(file_obj.name, "r") as file:
      data = json.load(file)
    return data
  except Exception as e:
    return {"error": str(e)}

def character_generation(prompt, examples):

  # Add a prompt for the model to generate a new example
  prompt += "Create a new character profile that fits in this environment:"

  chat_completion = client.chat.completions.create(
    response_format={ "type": "json_object" },
    messages=[
        {
            "role": "system",
            "content": "You are a creative team designing NPC characters based upon a given environment prompt and output in a json format",
        },
      {
          "role": "user",
          "content": prompt
      }

    ],
    model="gpt-3.5-turbo-0125",
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

  # return [chat_completion.choices[0].message.content, generated_image.data[0].url]
  return chat_completion.choices[0].message.content

def instruction(file_obj):
  data = read_json(file_obj)
  environment_context = (
      f"Era: {data['era']}, "
      f"Time Period: {data['time_period']}, "
      f"Detail: {data['detail']}\n\n"
  )
  examples = example.examples

  prompt = environment_context + "\n\n".join([e["example"] for e in examples]) + "\n\n"

  charlist = []

  for x in range(10):
    character = character_generation(prompt,examples)
    charlist.append(character)

  

  with open('output.json', 'w') as outfile:
      json.dump(charlist, outfile)
  return charlist[0:3]


# Create Gradio Interface
demo = gr.Interface(fn=instruction,
                    inputs="file",
                    outputs=["json","json","json"],
                    title="JSON File Reader",
                    description="Upload a JSON file and see its contents.")

demo.launch(share=True)
