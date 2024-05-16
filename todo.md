- Edit character json to include era and more detail on appearance (skin color)
- 

- Social Network graphs
- Creating connections between NPCs
- Neo4j, maybe vector databases or traditional sql 

- Edited the prompt.json to be more about environment
- Making sure personalities do not contradict each other.
- Generating multiple people in one go.


- Figure out if the prompt for name needs to say randomized because we see lucius a lot :(


- Redo social hiearchy because it is reading emperor first

DOuble check
- Randomly choose using random.randint() 5 and cross referencing them to conflicting personalities. IF any  x are found, then pick x more.


- Social graph using reputation scale between -1, 1


- Finished creating coroutines, still need to check the speed.
- POssibly moving the generations to a serverless function backend

- Networkx with gradio output

- Create two separate gradios one for character generation, and the other for chatinterface
- use RAG to load in the character, and inference using togetherai

- find a way to combine both into one gradio
  - Similar to this https://huggingface.co/spaces/One-2-3-45/One-2-3-45
  - Where the run generation button will activate the second portion for chatinterface

- Implement chromaDB for chathistory
  - Long Term memory and short term memory 



5/13 
- Revised character messaging prompt. It is working but the output is not as expected.
- Need to take a look at gradio again maybe.




Links
https://python.langchain.com/docs/integrations/llms/together
https://python.langchain.com/docs/use_cases/data_generation