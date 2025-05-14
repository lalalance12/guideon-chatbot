import json
import requests
from collections import defaultdict

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

results = []
print("Skill titles to query:", skill_titles)

for skill in skill_titles:
    print(f"Querying for skill: '{skill}'")
    resp = requests.post(
        'http://127.0.0.1:8000/api/course-search/',
        json={'query': skill}
    )
    print(f"Status code: {resp.status_code}")
    print(f"Response: {resp.text}")
    if resp.status_code != 200:
        continue
    courses = resp.json().get('courses', [])[:3]
    course_info = []
    for course in courses:
        print(f"Added course '{course.get('title')}' for skill '{skill}'")
        course_info.append({
            "course_title": course.get("title"),
            "course_provider": course.get("provider"),
            "course_rating": course.get("rating"),
            "course_description": course.get("description"),
            "price": course.get("price"),
            "course_url": course.get("url"),
        })
    results.append({
        "skill": skill,
        "course_info": course_info
    })

# Save to JSON
with open(r'c:\Users\Nasvil\Desktop\guideon-chatbot\backend\api\data\roles\skill_courses.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)