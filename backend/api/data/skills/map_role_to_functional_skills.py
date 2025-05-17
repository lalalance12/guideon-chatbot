import json

# Load functional skills data
with open('c:/Users/Nasvil/Desktop/guideon-chatbot/backend/api/data/fsc/processed_data.json', 'r', encoding='utf-8') as f:
    fsc_data = json.load(f)

# Build a mapping from title to aggregated underpinning knowledge
fsc_map = {}
for item in fsc_data:
    skill = item.get('functionalSkill', {})
    title = skill.get('title')
    # Aggregate underpinning knowledge from all proficiency levels
    underpinning_knowledge_set = set()
    for level in skill.get('proficiencyLevels', []):
        for uk in level.get('underpinningKnowledge', []):
            underpinning_knowledge_set.add(uk)
    underpinning_knowledge = list(underpinning_knowledge_set) if underpinning_knowledge_set else None
    if title:
        fsc_map[title] = {
            'title': title,
            'underpinning_knowledge': underpinning_knowledge
        }

# Load roles data
with open('c:/Users/Nasvil/Desktop/guideon-chatbot/backend/api/data/roles/processed_roles.json', 'r', encoding='utf-8') as f:
    roles_data = json.load(f)

output = []
for role in roles_data.get('roles', []):
    job_title = role.get('job_title')
    functional_skills = role.get('functional_skills', [])
    mapped_skills = []
    for skill in functional_skills:
        # Skill can be a dict with 'skill' key or just a string
        skill_title = skill.get('skill') if isinstance(skill, dict) else skill
        if skill_title and skill_title in fsc_map:
            mapped_skills.append(fsc_map[skill_title])
    output.append({
        'job_title': job_title,
        'functional_skills': mapped_skills
    })

# Save the output
with open('c:/Users/Nasvil/Desktop/guideon-chatbot/backend/api/data/skills/role_skill_knowledge.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('Mapping complete. Output saved to role_skill_mapping.json')
