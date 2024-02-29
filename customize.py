import gradio as gr


def display(stuff):
  return f"""{stuff}"""


def read_personality_file():
  f = open("personality.txt", "r")
  personalities = []
  for line in f:
    line = line[:-1]
    personalities.append(line)
  return personalities


personalities = read_personality_file()


demo = gr.Interface(display, [
  gr.Textbox(label="Era", info="distinct period in history with unique events"),
  gr.Textbox(label="Time Period", info="starting and ending year of era"),
  gr.Textbox(label="Detail", info="specific detail about how people lived in the era"),
  gr.Dropdown(personalities,
              multiselect=True,
              label="Activity",
              info="Pick at least 5 main personalities")
],
  outputs="text")