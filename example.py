examples = [
  {
    "example":""" name: ,
    age: 0,
    gender: ,
    personalities: [],
    appearance: {
      description: ,
      height: ,
      weight: ,
      hair: ,
      eyes: 
    },
    background: {
      hometown: ,
      family: ,
      motivation: 
    },
    skills: [],
    secrets: [] """
  },
  {
    "example":"""name: Mary,
    age: 25,
    gender: female,
    "personalities": ["friendly", "caring", "lazy", "toxic", "daring"],
    appearance: {
      description: a bubbly and vivacious young woman with a mischievous grin and a wild mane of curly hair. She has a curvaceous figure and often wears bright and colorful clothing that accentuates her assets.,
      height: 5'5,
      weight: 120 lbs,
      hair: curly,
      eyes: piercing blue
    },
    background: {
      hometown: a small, secluded town on the outskirts of a dense forest,
      family: her parents were both skilled warriors who taught her everything they knew about combat and survival,
      motivation: to avenge her family's death and see the world beyond her own borders
    },
    skills: [
      swordfighter,
      manipulation
    ],
    secrets: [
      she is toxic and can use her charm and wit to manipulate others to do her bidding
    ]"""
  },
  {
    "example": """name: Lyrion,
    age: 28,
    gender: Male,
    personalities: [
      "Introspective",
      "Compassionate",
      "Curious",
      "Diplomatic"
    ],
    "appearance": {
      "description": "Lyrion has a slender, elegant physique typical of a Zythorian, with shimmering, iridescent scales that change colors reflecting his mood. His scales predominantly exhibit shades of serene blues and vibrant greens.",
      "height": "7'2\"",
      "weight": "Light for human standards due to Zythorian physiology",
      "hair": "None, typical of Zythorians",
      "eyes": "Large, luminescent, star-like silver"
    },
    "background": {
      "hometown": "Eclipsion, a luminous city near Zytheria's equatorial region",
      "family": "Part of a respected lineage known for their roles as ambassadors and scholars",
      "motivation": "To establish peaceful and enlightening interstellar relations and to learn about human cultures and technologies"
    },
    "skills": [
      "Advanced telepathic communication",
      "Environmental energy manipulation",
      "Deep knowledge of Zytherian history and culture",
      "Adept at diplomatic negotiations"
    ],
    "secrets": [
      "Unbeknownst to most, Lyrion possesses an ancient Zytherian artifact that enhances telepathic abilities",
      "Harbors a deep-seated curiosity about Earth's oceans, stemming from Zytherian legends of ancient sea-like environments on their own planet"
    ]"""
  },
  {
    "example": """name: Elena Rivera,
    age: 28,
    gender: Female,
    personalities: [Intelligent, Resourceful, Compassionate, Determined],
    appearance: {
      description: Elena has an athletic build, with a confident posture.,
      height: 5'7",
      weight: 140 lbs,
      hair: Long, wavy dark brown hair,
      eyes: Hazel
    },
    background: {
      hometown: Santa Fe, New Mexico,
      family: Only child, raised by a single mother who is a renowned botanist,
      motivation: Elena is driven by a desire to make a significant contribution to environmental conservation, inspired by her mother's dedication to botany.
    },
    skills: [Expert in environmental science, Skilled in wilderness survival, Fluent in Spanish and English, Trained in basic first aid],
    secrets: [Elena discovered an unknown plant species but hasn't disclosed it yet due to potential threats from pharmaceutical companies]"""
  }
]

edge_list = {
  "edge_list": {
    "relationships": [
      {
        "from": "Zyra Kintar",
        "to": "Kael Thorne",
        "description": "Zyra admires Kael's charisma and shares his passion for uncovering Nova Terra's mysteries. They often collaborate on eco-friendly projects and shared exploration endeavors.",
        "weight": 0.7
      },
      {
        "from": "Zyra Kintar",
        "to": "Kalen Taros",
        "description": "Zyra finds Kalen's skepticism valuable but feels frustrated by his distrust of corporate interests, which sometimes puts them at odds during discussions about their future missions.",
        "weight": -0.2
      },
      {
        "from": "Zyra Kintar",
        "to": "Varek Fionis",
        "description": "Varek and Zyra share a close bond, supporting each other's dreams of merging exploration with conservation. They often brainstorm innovative eco-projects together.",
        "weight": 0.8
      },
      {
        "from": "Kael Thorne",
        "to": "Varek Fionis",
        "description": "Kael respects Varek's expertise in geological surveying; however, Varek's cautious nature sometimes clashes with Kael's more adventurous approach.",
        "weight": 0.3
      },
      {
        "from": "Kael Thorne",
        "to": "Kalen Taros",
        "description": "Kalen often critiques Kael's idealistic views on trade, leading to heated debates. There is a mutual respect underneath their disagreements.",
        "weight": 0.1
      },
      {
        "from": "Kael Thorne",
        "to": "Zyra Kintar",
        "description": "Kael and Zyra have an easygoing friendship built on shared values of exploration and environmentalism, often conveying ideas through creative mediums.",
        "weight": 0.6
      },
      {
        "from": "Varek Fionis",
        "to": "Kalen Taros",
        "description": "Varek appreciates Kalen's insights into corporate corruption, though he worries that Kalen's approach may be too harsh for effective change.",
        "weight": 0.4
      },
      {
        "from": "Varek Fionis",
        "to": "Kael Thorne",
        "description": "The two have a professional relationship, often collaborating on projects, but differ in tactics on how to achieve their societal goals, leading to tension.",
        "weight": 0.2
      },
      {
        "from": "Kalen Taros",
        "to": "Zyra Kintar",
        "description": "Kalen is protective of Zyra due to her idealism and expression of vulnerability, which leads to a brother-sister-like dynamic where he often looks out for her.",
        "weight": 0.5
      },
      {
        "from": "Kalen Taros",
        "to": "Varek Fionis",
        "description": "Kalen feels a connection with Varek due to their shared skepticism toward corporations, yet Kalen finds Varek's cautious nature slow and stifling.",
        "weight": -0.1
      },
      {
        "from": "Varek Fionis",
        "to": "Kael Thorne",
        "description": "Varek sees Kael's vibrant personality as both refreshing and reckless, often finding himself mediating between Kael's daring plans and the potential consequences.",
        "weight": -0.3
      }
    ]
  }
} 
