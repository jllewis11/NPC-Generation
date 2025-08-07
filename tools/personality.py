import os
import random
import json
import functools
from config import config

@functools.lru_cache(maxsize=128)
def read_personality():
    """Optimized personality generation with caching and improved logic."""
    # Use cached data from config
    personality_words = config.get_personality_data()
    polar_opposites = config.get_polar_opposites()
    
    # More efficient personality generation
    max_attempts = 10
    for attempt in range(max_attempts):
        personality_list = random.sample(personality_words, min(5, len(personality_words)))
        
        # Check for polar opposites more efficiently
        has_conflicts = any(
            polar_opposites.get(personality) in personality_list 
            for personality in personality_list
        )
        
        if not has_conflicts:
            return personality_list
    
    # If we can't find a non-conflicting set, just return a random sample
    # and filter out one of any conflicting pairs
    personality_list = random.sample(personality_words, min(5, len(personality_words)))
    
    # Remove conflicts by keeping only the first occurrence
    seen_opposites = set()
    filtered_list = []
    
    for personality in personality_list:
        opposite = polar_opposites.get(personality)
        if opposite not in seen_opposites and personality not in seen_opposites:
            filtered_list.append(personality)
            seen_opposites.add(personality)
            if opposite:
                seen_opposites.add(opposite)
    
    # Fill up to 5 if we removed too many
    while len(filtered_list) < 5 and len(filtered_list) < len(personality_words):
        candidate = random.choice(personality_words)
        if candidate not in filtered_list and candidate not in seen_opposites:
            filtered_list.append(candidate)
            opposite = polar_opposites.get(candidate)
            if opposite:
                seen_opposites.add(opposite)
    
    return filtered_list
