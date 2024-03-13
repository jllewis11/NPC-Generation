import json

def read_json(file_obj):
  try:
    # Load JSON file
    with open(file_obj.name, "r") as file:
      data = json.load(file)
    return data
  except Exception as e:
    return {"error": str(e)}