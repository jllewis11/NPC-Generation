from app.generation import instruction
from app.npcchat import npc_chat, shutdown
import gradio as gr



# Create Gradio Interface
demo = gr.Interface(fn=instruction,
                    inputs=[
                        "file",
                        gr.Slider(1,
                                  50,
                                  value=1,
                                  label="Count",
                                  info="Choose between 1 and 20")
                    ],
                    outputs=["json"],
                    title="JSON File Reader",
                    description="Upload a JSON file and see its contents.")

demo.launch(share=True)





# demo = gr.ChatInterface(fn=npc_chat)

if __name__ == "__main__":
  demo.launch()

  # Capture shutdown signals
  demo.close(shutdown)