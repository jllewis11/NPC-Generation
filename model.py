from langchain.pydantic_v1 import BaseModel, Field
from typing import List


class Envrionment(BaseModel):
  era: str = Field(description="distinct period in history with unique events")
  time_period: str = Field(description="starting and ending year of era")
  detail: str = Field(
      description="specific detail about how people lived in the era")


class NPC(BaseModel):
  name: str = Field(description="name of the NPC")
  age: int = Field(description="age of the NPC")
  gender: str = Field(description="gender of the NPC")
  personalities: List[str] = Field(
      description="list of 5 main personality traits of the NPC")
  appearance: dict[str, str] = Field(
      description="description of the NPC's appearance")
  background: dict[str, str] = Field(description="background of the NPC")
  skills: List[str] = Field(description="list of skills the NPC has")
  secrets: List[str] = Field(description="list of secrets the NPC has")
