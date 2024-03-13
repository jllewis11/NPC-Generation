
Environment JSON
Era, Time period (description of the time period), (description of the species)

``` json
{
"era": "",
"time_period": "",
"detail": {
  "Environment": " ",
  "Social and Economic Aspects": "",
  "Livelihood": "",
  "Social Hierarchy": "",
  "Cultural Norms": "",
  "Natural Environment": "",
  "Political Climate": ""
  }
}
```

Example
```json
{
  "era":"United Roman Empire",
  "time_period":"27 BC–AD 395",
  "detail":"A senator during the United Roman Empire was a member of the Roman Senate, which was the highest governing body in Rome. Senators were chosen by the Roman censors, who were responsible for conducting a census of the Roman people every five years. To be eligible to become a senator, a person had to be at least 30 years old, have a good reputation, and possess a certain amount of wealth.Senators were elected for life, and their main responsibility was to advise the emperor on matters of state. They also had the power to pass laws, known as senatus consulta, and to try criminal cases. Senators were considered to be the elite of Roman society, and they were often wealthy landowners who held the highest social status.Senators were required to wear a distinctive dress, which included a toga praetexta, a purple-bordered toga that was worn by magistrates and priests. They also had the right to sit on a special bench in the Senate, known as the 'prohedria', which was reserved for the most important members of the Senate.Senators were expected to be well-versed in rhetoric and law, and they were often called upon to give speeches in the Senate. They were also expected to be loyal to the emperor and to support his policies. In return for their service, senators were granted certain privileges, such as the right to wear imperial robes and to receive special honors and awards.Overall, being a senator during the United Roman Empire was a position of great power and prestige, and it was considered to be one of the highest honors that a Roman citizen could achieve."
}
```





Create an {Environment} NPC backstory from the personality traits of {Big 5 personality traits}

Expand on description, what are we looking for?

JSON TEMPLATE

```json

{
  "name":"",
  "age": Int,
  "gender":"",
  "personalities":[],
  "appearance": {
    "description": "",
    "height": "",
    "weight": "",
    "hair": "",
    "eyes": ""
  },
  "background": {
    "hometown": "",
    "family": "",
    "motivation": ""
  },
  "skills": [],
  "secrets": []
}
```


JSON EXAMPLE OUTPUT

```json

{
  "name":"Mary",
  "age": 25,
  "gender":"female",
  "personalities":["friendly", "caring", "lazy", "toxic", "daring"],
  "appearance": {
  "description": "a bubbly and vivacious young woman with a mischievous grin and a wild mane of curly hair. She has a curvaceous figure and often wears bright and colorful clothing that accentuates her assets.",
  "height": "5'5",
  "weight": "120 lbs",
  "hair": "curly",
  "eyes": "piercing blue"
  },
  "background": {
  "hometown": "a small, secluded town on the outskirts of a dense forest",
  "family": "her parents were both skilled warriors who taught her everything they knew about combat and survival",
  "motivation": "to avenge her family's death and see the world beyond her own borders"
  },
  "skills": [
  "swordfighter",
  "manipulation"
  ],
  "secrets": [
  "she is toxic and can use her charm and wit to manipulate others to do her bidding",
  ]
}
```