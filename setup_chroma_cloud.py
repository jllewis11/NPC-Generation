"""
Script to initialize ChromaDB Cloud collection for NPC chat.
Run this once to set up the collection in your ChromaDB Cloud database.
"""
import os
from dotenv import load_dotenv
import chromadb
import json

# Load environment variables
load_dotenv()

# Get ChromaDB Cloud credentials
chroma_api_key = os.getenv("CHROMA_API_KEY")
chroma_tenant = os.getenv("CHROMA_TENANT")
chroma_database = os.getenv("CHROMA_DATABASE")

if not chroma_api_key or not chroma_tenant:
    print("Error: CHROMA_API_KEY and CHROMA_TENANT must be set in .env file")
    exit(1)

if not chroma_database:
    print("Error: CHROMA_DATABASE must be set in .env file")
    exit(1)

# Load character data to get the character name
try:
    with open("JSONData/KaiyaStarling.json", "r") as file:
        character_context = json.load(file)
        character_name = character_context.get("name", "Kaiya_Starling")
except Exception as e:
    print(f"Warning: Could not load character file, using default name: {e}")
    character_name = "Kaiya_Starling"

# Collection name is character name with spaces replaced by underscores
collection_name = character_name.replace(" ", "_")

print(f"Connecting to ChromaDB Cloud...")
print(f"  Database: {chroma_database}")
print(f"  Tenant: {chroma_tenant}")
print(f"  Collection: {collection_name}")

try:
    # Initialize ChromaDB Cloud client
    client = chromadb.CloudClient(
        api_key=chroma_api_key,
        tenant=chroma_tenant,
        database=chroma_database
    )
    
    print("\n✓ Successfully connected to ChromaDB Cloud")
    
    # Get or create the collection
    # This will create the collection if it doesn't exist
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": f"Conversation history for {character_name}"}
    )
    
    print(f"✓ Collection '{collection_name}' is ready")
    print(f"  Collection ID: {collection.id if hasattr(collection, 'id') else 'N/A'}")
    
    # Check if collection has any existing documents
    count = collection.count()
    print(f"  Current document count: {count}")
    
    if count > 0:
        print(f"\n⚠ Collection already has {count} documents")
    else:
        print(f"\n✓ Collection is empty and ready to use")
    
    print("\n" + "="*60)
    print("Setup complete! Your ChromaDB Cloud collection is ready.")
    print("="*60)
    
except Exception as e:
    print(f"\n✗ Error setting up ChromaDB Cloud: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

