import json
import functools
from typing import Dict, Any, Union
import os

@functools.lru_cache(maxsize=32)
def read_json_cached(file_path: str, file_mtime: float) -> Dict[str, Any]:
    """Cached JSON reading with file modification time as cache key."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON format: {str(e)}"}
    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except PermissionError:
        return {"error": f"Permission denied: {file_path}"}
    except Exception as e:
        return {"error": f"Unexpected error reading file: {str(e)}"}

def read_json(file_obj) -> Dict[str, Any]:
    """Optimized JSON reading with caching and better error handling."""
    try:
        # Handle different input types
        if hasattr(file_obj, 'name'):
            file_path = file_obj.name
        elif isinstance(file_obj, str):
            file_path = file_obj
        else:
            return {"error": "Invalid file object provided"}
        
        # Check if file exists and get modification time for cache invalidation
        if not os.path.exists(file_path):
            return {"error": f"File does not exist: {file_path}"}
        
        file_mtime = os.path.getmtime(file_path)
        
        # Use cached version if available
        result = read_json_cached(file_path, file_mtime)
        
        # Validate that we have required fields for the application
        if "error" not in result:
            required_fields = ["era", "time_period", "detail"]
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                return {
                    "error": f"Missing required fields: {missing_fields}",
                    "data": result
                }
        
        return result
        
    except Exception as e:
        return {"error": f"Failed to process file: {str(e)}"}