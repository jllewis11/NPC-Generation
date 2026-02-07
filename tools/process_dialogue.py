import json
import os
from openai import OpenAI
from dotenv import load_dotenv



example = """I'm so glad you asked! As an adventurous soul, I've had the privilege of exploring many incredible places on Nova Terra. One of my absolute favorites is the Crystal Caves of Zha'thik. The luminescent crystals that line the caverns are truly breathtaking, and the ancient alien carvings on the walls are a testament to the planet's rich history. It's a place that never fails to leave me in awe.

Another spot that holds a special place in my heart is the Skyforest of Elyria. The towering trees, infused with a soft, ethereal glow, stretch towards the sky like nature's own cathedral. The forest is home to a diverse array of flora and fauna, and I've had the privilege of encountering some truly remarkable creatures during my travels here.

Of course, there are countless other wonders to discover on Nova Terra, and I'm always excited to explore new places and uncover their secrets. What about you, have you had a chance to explore any of these amazing destinations?"""


def process_dialogue(dialogue):
  load_dotenv()
  client = OpenAI(
    # This is the default and can be omitted
    api_key=os.getenv("OPENAI_API_KEY"),
  )
  
  
  
  prompt = "Set this paragraph into important bullet points" + example

  chat_completion = client.chat.completions.create(
    response_format={ "type": "json_object" },
    messages=[
        {
            "role": "system",
            "content": "You are a data engineer processing dialogue from a NPC. Given the dialogue, take the most important parts, and summarize in a json format. Use one word to describe the general idea as the key, and more detail as the value.",
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

process_dialogue(example)