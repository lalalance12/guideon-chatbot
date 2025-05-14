from agno.agent import Agent, RunResponse
from agno.models.ollama import Ollama
import json
import requests
from collections import defaultdict

agent = Agent(
    model=Ollama(id="llama3.2"),
    markdown=True
)

# Load skill titles from the embeddings file
with open(r'c:\Users\Nasvil\Desktop\guideon-chatbot\backend\api\data\roles\sample_role_skill_embeddings_bge_m3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

skill_titles = set()
for entry in data:
    meta = entry.get('metadata', {})
    if meta.get('type') == 'skill_title':
        skill_titles.add(meta.get('title'))
    elif meta.get('skill_title'):
        skill_titles.add(meta.get('skill_title'))

prompt = (
    f"Generate at least 3 possible courses for each of the following skills in {skill_titles}."
    "just give me a list of the course titles"
    "Format as a JSON array."
  )

print(f"Courses for {skill_titles}:")
response = agent.run(prompt)

# If response is a RunResponse object, get the text
if hasattr(response, 'text'):
    response_text = response.text
else:
    response_text = str(response)

with open(r'c:\Users\Nasvil\Desktop\guideon-chatbot\backend\api\utils\courses_for_skills.txt', 'w', encoding='utf-8') as f:
    f.write(response_text)