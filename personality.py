from openai import OpenAI
import os

client = OpenAI(
  # This is the default and can be omitted
  api_key=os.environ.get("OPENAI"),
)

def read_personality_file():
    with open("personality.txt", "r") as f:
        personalities = f.read()
    return personalities

p = read_personality_file()

prompt = p + "Given the list of personalities above. Choose 5. Ensure that the personalities do not contradict each other. Output a list of 3 different groups of personality in a json format."

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
  model="gpt-4-0125-preview",
)

print(chat_completion.choices[0].message.content)