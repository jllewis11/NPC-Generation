from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
  # This is the default and can be omitted
  api_key=os.getenv("OPENAI"),
)

def read_personality_file():
    with open("personality.txt", "r") as f:
        personalities = f.read()
    return personalities

p = read_personality_file()

prompt = p + "Given the list of personalities above. Create a dictionary JSON that lists the keys and values of personalities that are polar opposites and cannot be together in a group of personalities."

chat_completion = client.chat.completions.create(
  response_format={ "type": "json_object" },
  messages=[
      {
          "role": "system",
          "content": "You are a creative team designing NPC characters.",
      },
    {
        "role": "user",
        "content": prompt
    }

  ],
  model="gpt-3.5-turbo-0125",
)

print(chat_completion.choices[0].message.content)

#Save to json file
import json
with open('polar_opposites.json', 'w') as f:
    json.dump(chat_completion.choices[0].message.content, f, indent=4)