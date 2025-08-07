"""
Performance-optimized configuration and caching module.
Centralizes API clients, environment loading, and expensive operations.
"""
import os
import json
import functools
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI
from langchain_together import ChatTogether
import chromadb

# Load environment variables once at module level
load_dotenv()

class Config:
    """Centralized configuration with lazy loading and caching."""
    
    def __init__(self):
        self._openai_client: Optional[OpenAI] = None
        self._together_client: Optional[ChatTogether] = None
        self._chroma_client: Optional[chromadb.PersistentClient] = None
        self._personality_data: Optional[list] = None
        self._polar_opposites: Optional[Dict] = None
        self._environment_context: Optional[Dict] = None
        self._character_context: Optional[Dict] = None
        
    @property
    def openai_client(self) -> OpenAI:
        """Lazy-loaded OpenAI client."""
        if self._openai_client is None:
            self._openai_client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
        return self._openai_client
    
    @property
    def together_client(self) -> ChatTogether:
        """Lazy-loaded Together client."""
        if self._together_client is None:
            self._together_client = ChatTogether(
                model="meta-llama/Llama-3-8b-chat-hf",
                together_api_key=os.getenv("TOGETHER_API_KEY"),
            )
        return self._together_client
    
    @property
    def chroma_client(self) -> chromadb.PersistentClient:
        """Lazy-loaded ChromaDB client."""
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(path="data")
        return self._chroma_client
    
    @functools.lru_cache(maxsize=1)
    def get_personality_data(self) -> list:
        """Cached personality data loading."""
        if self._personality_data is None:
            with open("personality.txt", "r") as f:
                content = f.read()
            self._personality_data = content.replace("\n", " ").split()
        return self._personality_data
    
    @functools.lru_cache(maxsize=1)
    def get_polar_opposites(self) -> Dict:
        """Cached polar opposites data loading."""
        if self._polar_opposites is None:
            with open("data/polar_opposites.json", "r") as json_file:
                self._polar_opposites = json.load(json_file)
        return self._polar_opposites
    
    @functools.lru_cache(maxsize=1)
    def get_environment_context(self) -> Dict:
        """Cached environment context loading."""
        if self._environment_context is None:
            try:
                with open("JSONdata/prompt2.json", "r") as file:
                    self._environment_context = json.load(file)
            except FileNotFoundError:
                self._environment_context = {}
        return self._environment_context
    
    @functools.lru_cache(maxsize=1)
    def get_character_context(self) -> Dict:
        """Cached character context loading."""
        if self._character_context is None:
            try:
                with open("JSONdata/KaiyaStarling.json", "r") as file:
                    self._character_context = json.load(file)
            except FileNotFoundError:
                self._character_context = {}
        return self._character_context

# Global configuration instance
config = Config()

# Utility functions for backwards compatibility
def get_openai_client() -> OpenAI:
    """Get the shared OpenAI client."""
    return config.openai_client

def get_together_client() -> ChatTogether:
    """Get the shared Together client."""
    return config.together_client

def get_chroma_client() -> chromadb.PersistentClient:
    """Get the shared ChromaDB client."""
    return config.chroma_client