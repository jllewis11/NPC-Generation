from app.generation import instruction
from app.npcchat import npc_chat, shutdown, initialize_clients
import gradio as gr
import asyncio
import atexit

# Pre-initialize clients for better performance
initialize_clients()

# Register cleanup function
atexit.register(shutdown)

# Async wrapper for the instruction function
async def async_instruction(file_obj, count):
    """Async wrapper for instruction function."""
    return await instruction(file_obj, count)

# Create optimized Gradio Interface with performance improvements
demo = gr.Interface(
    fn=async_instruction,
    inputs=[
        gr.File(
            label="JSON Environment File",
            file_types=[".json"],
            file_count="single"
        ),
        gr.Slider(
            minimum=1,
            maximum=20,  # Reduced from 50 to prevent overwhelming API calls
            value=1,
            step=1,
            label="Character Count",
            info="Choose between 1 and 20 characters"
        )
    ],
    outputs=[
        gr.JSON(
            label="Generated Characters & Relationships",
            show_label=True
        )
    ],
    title="🎭 NPC Character Generator",
    description="Upload a JSON environment file to generate NPCs with relationships. Optimized for performance with concurrent processing.",
    article="""
    ### Performance Features:
    - ⚡ Concurrent character generation
    - 🔄 Shared API client connections
    - 💾 Intelligent caching
    - 🎯 Rate limiting for stability
    """,
    theme="soft",  # Use a lighter theme for faster rendering
    allow_flagging="never",  # Disable flagging for performance
    analytics_enabled=False,  # Disable analytics for privacy and speed
)

# Alternative chat interface (optimized)
chat_demo = gr.ChatInterface(
    fn=npc_chat,
    title="💬 NPC Chat Interface",
    description="Chat with generated NPCs. Memory-enabled with ChromaDB.",
    theme="soft",
    retry_btn=None,  # Disable retry button for cleaner UI
    undo_btn=None,   # Disable undo button for cleaner UI
    clear_btn="🗑️ Clear Chat",
    analytics_enabled=False
)

# Combine interfaces in a tabbed layout for better organization
app = gr.TabbedInterface(
    [demo, chat_demo],
    ["Character Generator", "NPC Chat"],
    title="🎮 Advanced NPC System",
    theme="soft"
)

if __name__ == "__main__":
    # Launch with optimized settings
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,  # Set to True only if needed, as sharing can slow things down
        inbrowser=False,  # Prevent auto-opening browser for server deployments
        show_api=False,  # Disable API docs for faster startup
        quiet=False,  # Keep logging for debugging
        favicon_path=None,  # No custom favicon for faster loading
        ssl_verify=False,  # For development - set to True in production
        enable_queue=True,  # Enable queue for better handling of concurrent requests
        max_threads=10  # Limit threads to prevent overwhelming the server
    )