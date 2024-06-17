## Initial Setup and Character Creation

- Edit character json to include era and more detail on appearance (skin color).
- Generate multiple people in one go.
- Ensure personalities do not contradict each other. Randomly choose using random.randint() 5 and cross reference them to conflicting personalities. If any conflicts are found, then pick more.
- Determine if the prompt for name needs to say randomized because we see Lucius a lot.

## Social Network and Hierarchy

- Create connections between NPCs.
- Redo social hierarchy because it is reading emperor first.
- Create a social graph using a reputation scale between -1, 1.
- Explore using Neo4j, vector databases or traditional SQL for social network graphs.

## Environment and Interaction

- Edit the prompt.json to be more about environment.
- Revised character messaging prompt. It is working but the output is not as expected. Need to take a look at gradio again maybe (5/13).
- Finished working on character messaging and prompting (5/20).

## Technical Implementation

- Finish creating coroutines, still need to check the speed.
- Consider moving the generations to a serverless function backend.
- Implement Networkx with gradio output.
- Create two separate gradios: one for character generation, and the other for chat interface.
- Use RAG to load in the character, and inference using togetherai.
- Find a way to combine both gradios into one. Similar to this, where the run generation button will activate the second portion for chat interface.
- Implement ChromaDB for chat history, including long term memory and short term memory.

Reference Links

Langchain Integration
Langchain Use Cases