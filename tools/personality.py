import os
import random
import json


def read_personality():
  p = ""
  with open("personality.txt", "r") as f:
    p = f.read()

  with open(
      os.path.join(os.path.dirname(__file__), "../data/polar_opposites.json"),
      "r") as json_file:
    polar_opposites = json.load(json_file)
  p = p.replace("\n", " ").split()

  personality_list = random.sample(p, 5)
  isReady = False
  while not isReady:

    for i, personality in enumerate(personality_list):
      if polar_opposites.get(personality) in personality_list:
        personality_list[i] = random.choice(p)

    if not any(
        polar_opposites.get(x) in personality_list for x in personality_list):
      isReady = True
      break

  return personality_list
