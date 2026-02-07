"""
Simple test script for the FastAPI endpoints.
Run this after starting the API locally or after deploying to Modal.
"""
import requests
import json

# Change this to your Modal URL or localhost
BASE_URL = "http://localhost:8000"  # For local testing
# BASE_URL = "https://your-app-name--fastapi-app.modal.run"  # For Modal deployment


def test_health():
    """Test the health check endpoint."""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_chat():
    """Test the chat endpoint."""
    print("Testing /chat endpoint...")
    
    # First message
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "Hello! Tell me about yourself.",
            "history": []
        }
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    print()
    
    # Second message with history
    history = [
        ["Hello! Tell me about yourself.", result["response"]]
    ]
    
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": "What are your skills?",
            "history": history
        }
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    print()


def test_clear_history():
    """Test the clear history endpoint."""
    print("Testing /clear-history endpoint...")
    response = requests.post(f"{BASE_URL}/clear-history")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("NPC Dialogue Generation API Test Script")
    print("=" * 60)
    print()
    
    try:
        test_health()
        test_chat()
        test_clear_history()
        print("All tests completed!")
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {BASE_URL}")
        print("Make sure the API is running locally or update BASE_URL for Modal deployment.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

