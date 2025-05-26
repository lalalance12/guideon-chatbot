import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import json
import requests
import numpy as np
import traceback
import django

django.setup()

# --- Configuration ---
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "bge-m3"
OUTPUT_EMBEDDINGS_FILE = f"{BASE_DIR}/api/data/all_embeddings_data.json"

# Input data file paths
ESC_DATA_PATH = f"{BASE_DIR}/api/data/esc/esc_data.json"
FSC_DATA_PATH = f"{BASE_DIR}/api/data/fsc/processed_data.json"
ROLES_DATA_PATH = f"{BASE_DIR}/api/data/roles/processed_roles.json"
CAREER_MAP_PATH = f"{BASE_DIR}/api/data-sample/career_map.json"

# --- Global Lookups (to be populated in process_all_data) ---
CAREER_MAP_LOOKUP = {}
ROLES_DATA_LOOKUP = {}

# --- Helper Functions for Data Loading and Preparation ---
def load_roles_data(filepath):
    """Loads roles data from a JSON file."""
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Roles data file not found at {filepath}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from roles data file {filepath}")
    except Exception as e:
        print(f"Error loading roles data {filepath}: {e}")
    return None

def load_and_prepare_career_map_data(filepath):
    """Loads and prepares career map data into easily queryable lookup structures."""
    lookup = {"role_to_career_info": {}, "grade_to_info": {}, "domain_to_info": {}}
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        # Process jobGrades section
        for grade_item in data.get("jobGrades", []):
            grade_name = grade_item.get("grade")
            lookup["grade_to_info"][grade_name] = {"positions": []}
            for pos in grade_item.get("positions", []):
                pos_name = pos.get("name")
                career_info = {
                    "grade": grade_name,
                    "domain": pos.get("domain"),
                    "nextRoles": pos.get("nextRoles", [])
                }
                lookup["role_to_career_info"][pos_name] = career_info
                lookup["grade_to_info"][grade_name]["positions"].append(pos_name)

        # Process domains section
        for domain_item in data.get("domains", []):
            domain_name = domain_item.get("name")
            lookup["domain_to_info"][domain_name] = {"roles": []}
            for role_detail in domain_item.get("roles", []):
                role_name = role_detail.get("role")
                # Add or update role_to_career_info from domain perspective
                if role_name not in lookup["role_to_career_info"]:
                    lookup["role_to_career_info"][role_name] = {}
                lookup["role_to_career_info"][role_name].update({
                    "grade_from_domain": role_detail.get("grade"),
                    "domain_name": domain_name,
                    "nextGrade": role_detail.get("nextGrade")
                })
                lookup["domain_to_info"][domain_name]["roles"].append({
                    "role": role_name, 
                    "grade": role_detail.get("grade"), 
                    "nextGrade": role_detail.get("nextGrade")
                })
        
        print(f"Career Map Lookup prepared with {len(lookup['role_to_career_info'])} role mappings")
    except Exception as e:
        print(f"Error loading or preparing career map data from {filepath}: {e}")
    return lookup

def load_and_prepare_roles_data(filepath):
    """Loads and prepares roles data into easily queryable lookup structures."""
    lookup = {"role_title_to_details": {}}
    try:
        data = load_roles_data(filepath)
        if data and "roles" in data:
            for role in data.get("roles", []):
                title = role.get("job_title")
                if title:
                    description = role.get("description", "")
                    lookup["role_title_to_details"][title] = {
                        "description_snippet": (description[:150] + "...") if len(description) > 150 else description,
                        "key_tasks_count": len(role.get("key_tasks", [])),
                        "functional_skills": [{"skill": s.get("skill"), "level": s.get("level")} for s in role.get("functional_skills", [])],
                        "enabling_skills": [{"skill": s.get("skill"), "level": s.get("level")} for s in role.get("enabling_skills", [])],
                        "total_skills": len(role.get("functional_skills", [])) + len(role.get("enabling_skills", []))
                    }
        print(f"Roles Data Lookup prepared with {len(lookup['role_title_to_details'])} role details")
    except Exception as e:
        print(f"Error loading or preparing roles data from {filepath}: {e}")
    return lookup

def build_skill_to_roles_map(roles_data):
    """Builds a map from skill name to a list of roles requiring that skill."""
    skill_map = {}
    if not roles_data or "roles" not in roles_data:
        return skill_map

    for role in roles_data.get("roles", []):
        role_title = role.get("job_title")
        if not role_title:
            continue

        for fs_skill_info in role.get("functional_skills", []):
            skill_name = fs_skill_info.get("skill")
            skill_level = fs_skill_info.get("level")
            if skill_name:
                skill_map.setdefault(skill_name, {"roles": [], "type": "functional"})
                role_entry = {"role": role_title, "level": skill_level}
                if role_entry not in skill_map[skill_name]["roles"]:
                    skill_map[skill_name]["roles"].append(role_entry)

        for es_skill_info in role.get("enabling_skills", []):
            skill_name = es_skill_info.get("skill")
            skill_level = es_skill_info.get("level")
            if skill_name:
                skill_map.setdefault(skill_name, {"roles": [], "type": "enabling"})
                role_entry = {"role": role_title, "level": skill_level}
                if role_entry not in skill_map[skill_name]["roles"]:
                    skill_map[skill_name]["roles"].append(role_entry)
    return skill_map

# --- Embedding Generation ---
def generate_embeddings(text_chunks):
    """Generates embeddings for a list of text chunks using the specified Ollama model."""
    embeddings = []
    total_chunks = len(text_chunks)
    print(f"\nGenerating embeddings using model: {EMBEDDING_MODEL}")

    for i, chunk in enumerate(text_chunks):
        if not chunk or chunk.isspace():
            print(f"Skipping empty chunk {i+1}/{total_chunks}")
            embeddings.append([])
            continue

        print(f"Generating embedding for chunk {i+1}/{total_chunks}")
        payload = {
            "model": EMBEDDING_MODEL,
            "prompt": chunk
        }

        try:
            response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=120)
            response.raise_for_status()
            embedding_data = response.json()
            embedding = embedding_data.get("embedding", [])
            if not embedding:
                print(f"Warning: Received empty embedding for chunk {i+1}")
            embeddings.append(embedding)
        except requests.exceptions.RequestException as e:
            print(f"Error generating embedding for chunk {i+1}: {e}")
            embeddings.append([])
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response for chunk {i+1}: {e} - Response text: {response.text}")
            embeddings.append([])
        except Exception as e:
            print(f"An unexpected error occurred for chunk {i+1}: {e}")
            embeddings.append([])

    print(f"Finished generating embeddings for {len(embeddings)} chunks.")
    return embeddings

# --- Enhanced Data Processing Functions ---
def process_roles(filepath, career_map_lookup, skill_to_roles_map):
    """Processes roles data, adding career context and skill linkage."""
    print(f"\nProcessing Roles from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    try:
        data = load_roles_data(filepath)

        for role in data.get("roles", []):
            title = role.get("job_title", "Untitled Role")
            description = role.get("description", "No description")
            key_tasks_list = role.get("key_tasks", [])
            func_skills_list = role.get("functional_skills", [])
            enable_skills_list = role.get("enabling_skills", [])
            
            # Get career context
            career_info = career_map_lookup.get("role_to_career_info", {}).get(title, {})
            role_grade = career_info.get("grade", career_info.get("grade_from_domain", "N/A"))
            role_domain = career_info.get("domain", career_info.get("domain_name", "N/A"))
            next_roles_from_map = career_info.get("nextRoles", [])
            next_grade_from_map = career_info.get("nextGrade")
            
            # Prepare structured metadata for skills
            required_functional_skills_meta = [{"skill": s.get("skill"), "level": s.get("level")} for s in func_skills_list]
            required_enabling_skills_meta = [{"skill": s.get("skill"), "level": s.get("level")} for s in enable_skills_list]

            # Enhanced base metadata with career context
            base_meta = {
                "source_file": os.path.basename(filepath),
                "role_grade": role_grade,
                "role_domain": role_domain,
                "next_roles_from_career_map": next_roles_from_map,
                "next_grade_from_career_map": next_grade_from_map,
                "skills_count": len(func_skills_list) + len(enable_skills_list),
                "functional_skills_count": len(func_skills_list),
                "enabling_skills_count": len(enable_skills_list)
            }

            # Enhanced contextual title
            contextual_title = f"{title} (Grade: {role_grade}, Domain: {role_domain})"
            
            # Comprehensive role chunk with career context
            whole_role_text = f"# {contextual_title}\n\n"
            whole_role_text += f"## Description\n{description.strip()}\n\n"
            
            if next_roles_from_map:
                whole_role_text += f"## Career Progression\nThis role can typically lead to: {', '.join(next_roles_from_map)}.\n\n"
            if next_grade_from_map:
                whole_role_text += f"## Next Grade Level\nProgression can lead to the {next_grade_from_map} grade.\n\n"
            
            whole_role_text += f"## Key Tasks\n"
            for kt in key_tasks_list:
                function = kt.get("function", "").strip()
                tasks = kt.get("tasks", [])
                if function:
                    whole_role_text += f"### {function}\n"
                for task in tasks:
                    whole_role_text += f"- {task.strip()}\n"
                whole_role_text += "\n"
            
            whole_role_text += f"## Required Skills\n"
            whole_role_text += f"### Functional Skills ({len(func_skills_list)} required)\n"
            for skill_item in func_skills_list:
                whole_role_text += f"- {skill_item.get('skill')} (Level {skill_item.get('level')})\n"
            whole_role_text += f"\n### Enabling Skills ({len(enable_skills_list)} required)\n"
            for skill_item in enable_skills_list:
                whole_role_text += f"- {skill_item.get('skill')} ({skill_item.get('level')})\n"
            
            text_chunks.append(whole_role_text)
            chunk_metadata.append({
                "type": "whole_role",
                "title": title,
                "contextual_title": contextual_title,
                **base_meta,
                "description": description.strip(),
                "key_tasks": key_tasks_list,
                "required_functional_skills": required_functional_skills_meta,
                "required_enabling_skills": required_enabling_skills_meta,
            })
            
            # Enhanced role description chunk
            desc_chunk_text = f"Role: {contextual_title}\nDescription: {description.strip()}"
            if next_roles_from_map:
                desc_chunk_text += f"\nCareer Path: Can progress to {', '.join(next_roles_from_map)}"
            
            text_chunks.append(desc_chunk_text)
            chunk_metadata.append({
                "type": "role_description",
                "title": title,
                "contextual_title": contextual_title,
                **base_meta,
                "description": description.strip(),
            })

            # Enhanced skills requirement chunk
            if func_skills_list or enable_skills_list:
                skills_chunk_text = f"Skills required for {contextual_title}:\n\n"
                skills_chunk_text += f"Functional Skills ({len(func_skills_list)}):\n"
                for s in func_skills_list:
                    skills_chunk_text += f"- {s.get('skill')} at Level {s.get('level')}\n"
                skills_chunk_text += f"\nEnabling Skills ({len(enable_skills_list)}):\n"
                for s in enable_skills_list:
                    skills_chunk_text += f"- {s.get('skill')} at {s.get('level')} level\n"
                
                text_chunks.append(skills_chunk_text)
                chunk_metadata.append({
                    "type": "role_skills",
                    "title": title,
                    "contextual_title": contextual_title,
                    **base_meta,
                    "required_functional_skills": required_functional_skills_meta,
                    "required_enabling_skills": required_enabling_skills_meta,
                })

        print(f"Processed {len(chunk_metadata)} role chunks with career context.")
    except Exception as e:
        print(f"Error processing roles: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def process_enabling_skills(filepath, skill_to_roles_map):
    """Processes enabling skills data, adding enhanced roles information to metadata."""
    print(f"\nProcessing Enabling Skills from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            skill = item.get("enablingSkill", {})
            title = skill.get("title", "Untitled Skill")
            description = skill.get("description", "No description")
            code_prefix = skill.get("codePrefix", "")
            
            range_data = skill.get("rangeOfApplication", {})
            range_title = range_data.get("title", "Range of Application")
            range_items = range_data.get("items", [])
            
            valid_levels = [l for l in skill.get("proficiencyLevels", []) if l.get("description")]
            level_labels = [l.get("level") for l in valid_levels if l.get("level")]

            # Enhanced role usage information
            skill_usage = skill_to_roles_map.get(title, {"roles": [], "type": "enabling"})
            roles_using_skill = [r["role"] for r in skill_usage.get("roles", [])]
            role_level_requirements = skill_usage.get("roles", [])
            
            # Enhanced overview with richer context
            overview_text = f"# {title} (Enabling Skill)\n\n"
            overview_text += f"## Description\n{description}\n\n"
            
            if roles_using_skill:
                overview_text += f"## Used in {len(roles_using_skill)} Roles\n"
                overview_text += f"This enabling skill is required for the following roles:\n"
                for role_req in role_level_requirements:
                    overview_text += f"- {role_req['role']} (at {role_req['level']} level)\n"
                overview_text += "\n"
            
            if range_items:
                overview_text += f"## {range_title}\n"
                for r_item in range_items:
                    if r_item and not r_item.isspace():
                        overview_text += f"- {r_item.strip()}\n"
                overview_text += "\n"
            
            if level_labels:
                overview_text += f"## Available Proficiency Levels ({len(level_labels)})\n"
                overview_text += f"This enabling skill has the following levels: {', '.join(level_labels)}\n"
            
            text_chunks.append(overview_text)
            chunk_metadata.append({
                "type": "esc_complete_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_labels,
                "skill_category": "enabling",
                "used_in_roles": roles_using_skill,
                "role_level_requirements": role_level_requirements,
                "usage_count": len(roles_using_skill),
                "source_file": os.path.basename(filepath)
            })
            
            # Enhanced level-specific chunks
            for lvl in valid_levels:
                level_label = lvl.get("level")
                if not level_label:
                    continue
                
                level_desc = lvl.get("description", "")
                esc_code = lvl.get("escCode", "")
                knowledge_points = lvl.get("underpinningKnowledge", [])
                skill_applications = lvl.get("skillsApplication", [])
                
                level_text = f"# {title} - {level_label} Level (Enabling Skill)\n\n"
                if esc_code:
                    level_text += f"**Code:** {esc_code}\n\n"
                level_text += f"## Level Description\n{level_desc}\n\n"
                
                # Add roles context for this specific level
                roles_at_this_level = [r["role"] for r in role_level_requirements if r["level"] == level_label]
                if roles_at_this_level:
                    level_text += f"## Roles Requiring This Level\n"
                    level_text += f"The following roles require {title} at {level_label} level: {', '.join(roles_at_this_level)}\n\n"
                
                if knowledge_points:
                    level_text += f"## Underpinning Knowledge\nAt this level, you should know:\n"
                    for k in knowledge_points:
                        if k and not k.isspace():
                            level_text += f"- {k.strip()}\n"
                    level_text += "\n"
                if skill_applications:
                    level_text += f"## Skills Application\nAt this level, you should be able to:\n"
                    for sa in skill_applications:
                        if sa and not sa.isspace():
                            level_text += f"- {sa.strip()}\n"
                
                text_chunks.append(level_text)
                chunk_metadata.append({
                    "type": "esc_complete_level",
                    "title": f"{title} - {level_label} Level",
                    "skill": title,
                    "level": level_label,
                    "escCode": esc_code,
                    "skill_category": "enabling",
                    "used_in_roles": roles_using_skill,
                    "roles_at_this_level": roles_at_this_level,
                    "source_file": os.path.basename(filepath)
                })
        
        print(f"Processed {len(chunk_metadata)} enabling skill chunks with role context.")
    except Exception as e:
        print(f"Error processing enabling skills: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def process_functional_skills(filepath, skill_to_roles_map):
    """Processes functional skills data, adding enhanced roles information to metadata."""
    print(f"\nProcessing Functional Skills from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            skill = item.get("functionalSkill", {})
            title = skill.get("title", "Untitled Skill")
            description = skill.get("description", "No description")
            code_prefix = skill.get("codePrefix", "")
            
            range_data = skill.get("rangeOfApplication", {})
            range_title = range_data.get("title", "Range of Application")
            range_items = range_data.get("items", [])
            
            valid_levels = [l for l in skill.get("proficiencyLevels", []) if l.get("description")]
            level_numbers = [str(l.get("level")) for l in valid_levels if l.get("level")]

            # Enhanced role usage information
            skill_usage = skill_to_roles_map.get(title, {"roles": [], "type": "functional"})
            roles_using_skill = [r["role"] for r in skill_usage.get("roles", [])]
            role_level_requirements = skill_usage.get("roles", [])
            
            # Enhanced overview with richer context
            overview_text = f"# {title} (Functional Skill)\n\n"
            overview_text += f"## Description\n{description}\n\n"

            if roles_using_skill:
                overview_text += f"## Used in {len(roles_using_skill)} Roles\n"
                overview_text += f"This functional skill is required for the following roles:\n"
                for role_req in role_level_requirements:
                    overview_text += f"- {role_req['role']} (at Level {role_req['level']})\n"
                overview_text += "\n"

            if range_items:
                overview_text += f"## {range_title}\n"
                for r_item in range_items:
                    if r_item and not r_item.isspace():
                        overview_text += f"- {r_item.strip()}\n"
                overview_text += "\n"
            
            if level_numbers:
                overview_text += f"## Available Proficiency Levels ({len(level_numbers)})\n"
                overview_text += f"This skill has the following levels: {', '.join(level_numbers)}\n"
            
            text_chunks.append(overview_text)
            chunk_metadata.append({
                "type": "fs_complete_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_numbers,
                "skill_category": "functional",
                "used_in_roles": roles_using_skill,
                "role_level_requirements": role_level_requirements,
                "usage_count": len(roles_using_skill),
                "source_file": os.path.basename(filepath)
            })
            
            # Enhanced level-specific chunks
            for lvl in valid_levels:
                level_no = lvl.get("level")
                if not level_no:
                    continue
                
                level_desc = lvl.get("description", "")
                fsc_code = lvl.get("fscCode", "")
                knowledge_points = lvl.get("underpinningKnowledge", [])
                skill_applications = lvl.get("skillsApplication", [])
                
                level_text = f"# {title} - Level {level_no} (Functional Skill)\n\n"
                if fsc_code:
                    level_text += f"**Code:** {fsc_code}\n\n"
                level_text += f"## Level Description\n{level_desc}\n\n"
                
                # Add roles context for this specific level
                roles_at_this_level = [r["role"] for r in role_level_requirements if str(r["level"]) == f"Level {level_no}"]
                if roles_at_this_level:
                    level_text += f"## Roles Requiring This Level\n"
                    level_text += f"The following roles require {title} at Level {level_no}: {', '.join(roles_at_this_level)}\n\n"
                
                if knowledge_points:
                    level_text += f"## Underpinning Knowledge\nAt this level, you should know:\n"
                    for k in knowledge_points:
                        if k and not k.isspace():
                            level_text += f"- {k.strip()}\n"
                    level_text += "\n"
                if skill_applications:
                    level_text += f"## Skills Application\nAt this level, you should be able to:\n"
                    for sa in skill_applications:
                        if sa and not sa.isspace():
                            level_text += f"- {sa.strip()}\n"
                
                text_chunks.append(level_text)
                chunk_metadata.append({
                    "type": "fs_complete_level",
                    "title": f"{title} - Level {level_no}",
                    "skill": title,
                    "level": level_no,
                    "fscCode": fsc_code,
                    "skill_category": "functional",
                    "used_in_roles": roles_using_skill,
                    "roles_at_this_level": roles_at_this_level,
                    "source_file": os.path.basename(filepath)
                })
        
        print(f"Processed {len(chunk_metadata)} functional skill chunks with role context.")
    except Exception as e:
        print(f"Error processing functional skills: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def process_career_map(filepath, roles_data_lookup):
    """Processes career map data, linking to role details and creating progression chunks."""
    print(f"\nProcessing Career Map from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)

        # Enhanced overview
        domain_names = [d.get("name", "Unknown Domain") for d in data.get("domains", [])]
        grade_names = [g.get("grade", "Unknown Grade") for g in data.get("jobGrades", [])]
        overview_text = (
            f"# Analytics & AI Career Framework Overview\n\n"
            f"## Career Domains ({len(domain_names)})\n"
            f"Vertical specialization tracks: {', '.join(domain_names)}\n\n"
            f"## Job Grades ({len(grade_names)})\n"
            f"Horizontal progression levels: {', '.join(grade_names)}\n\n"
            f"This framework provides structured career progression paths in analytics and AI, "
            f"combining domain expertise with grade-level advancement."
        )
        text_chunks.append(overview_text)
        chunk_metadata.append({
            "type": "career_map_overview",
            "title": "Analytics & AI Career Framework Overview",
            "domains": domain_names,
            "job_grades": grade_names,
            "total_domains": len(domain_names),
            "total_grades": len(grade_names),
            "source_file": os.path.basename(filepath)
        })

        # Enhanced domain processing with role details
        for domain_item in data.get("domains", []):
            domain_name = domain_item.get("name", "Unknown Domain")
            roles_in_domain_text_list = []
            roles_in_domain_meta = []
            
            for role_info in domain_item.get("roles", []):
                grade = role_info.get("grade", "")
                role_name = role_info.get("role", "")
                next_grade = role_info.get("nextGrade")
                
                # Get detailed role information
                role_details = roles_data_lookup.get("role_title_to_details", {}).get(role_name, {})
                description_snippet = role_details.get("description_snippet", "")
                skills_count = role_details.get("total_skills", 0)
                
                entry_text = f"- {grade}: {role_name}"
                if description_snippet:
                    entry_text += f" - {description_snippet}"
                if skills_count > 0:
                    entry_text += f" (Requires {skills_count} skills)"
                if next_grade:
                    entry_text += f" → Next Grade: {next_grade}"
                
                roles_in_domain_text_list.append(entry_text)
                roles_in_domain_meta.append({
                    "grade": grade,
                    "role": role_name,
                    "nextGrade": next_grade,
                    "description_snippet": description_snippet,
                    "skills_count": skills_count
                })

            domain_text = f"# {domain_name} Domain\n\n"
            domain_text += f"## Career Progression in {domain_name}\n"
            domain_text += f"This domain contains {len(roles_in_domain_meta)} distinct roles across various grades:\n\n"
            domain_text += "\n".join(roles_in_domain_text_list)
            
            text_chunks.append(domain_text)
            chunk_metadata.append({
                "type": "career_map_domain",
                "title": f"Domain: {domain_name}",
                "domain_name": domain_name,
                "roles_in_domain": roles_in_domain_meta,
                "roles_count": len(roles_in_domain_meta),
                "source_file": os.path.basename(filepath)
            })
        
        # Enhanced job grades processing with progression paths
        for job_grade in data.get("jobGrades", []):
            grade_name = job_grade.get("grade", "Unknown Grade")
            positions_in_grade_meta = []
            positions_in_grade_text_list = []

            for position_info in job_grade.get("positions", []):
                pos_name = position_info.get("name", "Unknown Position")
                pos_domain = position_info.get("domain", "N/A")
                next_roles = position_info.get("nextRoles", [])
                
                # Get detailed role information
                role_details = roles_data_lookup.get("role_title_to_details", {}).get(pos_name, {})
                description_snippet = role_details.get("description_snippet", "")
                skills_count = role_details.get("total_skills", 0)
                
                position_text = f"- {pos_name}"
                if description_snippet:
                    position_text += f" - {description_snippet}"
                position_text += f" (Domain: {pos_domain}"
                if skills_count > 0:
                    position_text += f", {skills_count} skills required"
                position_text += ")"
                if next_roles:
                    position_text += f" → Can advance to: {', '.join(next_roles)}"
                
                positions_in_grade_text_list.append(position_text)
                positions_in_grade_meta.append({
                    "name": pos_name,
                    "domain": pos_domain,
                    "nextRoles": next_roles,
                    "description_snippet": description_snippet,
                    "skills_count": skills_count
                })

                # Create specific progression chunks for roles with next steps
                if next_roles:
                    prog_text = f"# Career Progression from {pos_name}\n\n"
                    prog_text += f"## Current Position\n"
                    prog_text += f"**Role:** {pos_name} ({grade_name} grade)\n"
                    prog_text += f"**Domain:** {pos_domain}\n"
                    if description_snippet:
                        prog_text += f"**Description:** {description_snippet}\n"
                    
                    prog_text += f"\n## Potential Next Roles ({len(next_roles)})\n"
                    prog_text += f"From {pos_name}, you can typically progress to:\n\n"
                    
                    for nr_title in next_roles:
                        nr_details = roles_data_lookup.get("role_title_to_details", {}).get(nr_title, {})
                        nr_snippet = nr_details.get("description_snippet", "")
                        nr_skills = nr_details.get("total_skills", 0)
                        prog_text += f"### {nr_title}\n"
                        if nr_snippet:
                            prog_text += f"{nr_snippet}\n"
                        if nr_skills > 0:
                            prog_text += f"*Requires {nr_skills} skills*\n"
                        prog_text += "\n"
                    
                    text_chunks.append(prog_text)
                    chunk_metadata.append({
                        "type": "career_progression_path",
                        "title": f"Progression Path from {pos_name}",
                        "source_role": pos_name,
                        "source_grade": grade_name,
                        "source_domain": pos_domain,
                        "target_next_roles": next_roles,
                        "progression_options": len(next_roles),
                        "source_file": os.path.basename(filepath)
                    })
            
            grade_text = f"# {grade_name} Grade Level\n\n"
            grade_text += f"## Positions at {grade_name} Level\n"
            grade_text += f"This grade level includes {len(positions_in_grade_meta)} distinct positions:\n\n"
            grade_text += "\n".join(positions_in_grade_text_list)
            
            text_chunks.append(grade_text)
            chunk_metadata.append({
                "type": "career_map_grade",
                "title": f"Job Grade: {grade_name}",
                "grade_name": grade_name,
                "positions_in_grade": positions_in_grade_meta,
                "positions_count": len(positions_in_grade_meta),
                "source_file": os.path.basename(filepath)
            })

        print(f"Processed {len(chunk_metadata)} career map chunks with role links and progression paths.")
    except Exception as e:
        print(f"Error processing career map: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

# --- Main Processing Orchestration ---
def process_all_data():
    """Loads data from all JSON files, processes them with interconnections, generates embeddings, and saves results."""
    global CAREER_MAP_LOOKUP, ROLES_DATA_LOOKUP

    all_text_chunks = []
    all_chunk_metadata = []

    # --- Pre-load and Prepare Lookups ---
    print("Preparing cross-file lookups for enhanced connectivity...")
    CAREER_MAP_LOOKUP = load_and_prepare_career_map_data(CAREER_MAP_PATH)
    ROLES_DATA_LOOKUP = load_and_prepare_roles_data(ROLES_DATA_PATH)
    
    # Load raw roles data for skill_to_roles_map
    roles_data_content = load_roles_data(ROLES_DATA_PATH)
    skill_to_roles_map = build_skill_to_roles_map(roles_data_content)
    if not skill_to_roles_map:
        print("Warning: Skill-to-roles map could not be built. Skills metadata will not include 'used_in_roles'.")
    else:
        print(f"Built skill-to-roles map with {len(skill_to_roles_map)} skills")
    print("Lookups prepared successfully.\n")

    # Process all data with enhanced connectivity
    processing_order = [
        (ROLES_DATA_PATH, "process_roles", lambda: process_roles(ROLES_DATA_PATH, CAREER_MAP_LOOKUP, skill_to_roles_map)),
        (ESC_DATA_PATH, "process_enabling_skills", lambda: process_enabling_skills(ESC_DATA_PATH, skill_to_roles_map)),
        (FSC_DATA_PATH, "process_functional_skills", lambda: process_functional_skills(FSC_DATA_PATH, skill_to_roles_map)),
        (CAREER_MAP_PATH, "process_career_map", lambda: process_career_map(CAREER_MAP_PATH, ROLES_DATA_LOOKUP))
    ]

    for filepath, process_name, process_func in processing_order:
        if os.path.exists(filepath):
            print(f"Processing {process_name}...")
            chunks, meta = process_func()
            all_text_chunks.extend(chunks)
            all_chunk_metadata.extend(meta)
        else:
            print(f"Warning: {process_name} input file not found, skipping: {filepath}")

    if not all_text_chunks:
        print("\nNo text chunks were generated. Exiting.")
        return

    print(f"\nTotal text chunks to embed: {len(all_text_chunks)}")
    # Verify metadata length
    if len(all_text_chunks) != len(all_chunk_metadata):
        print(f"CRITICAL ERROR: Mismatch between text chunks ({len(all_text_chunks)}) and metadata ({len(all_chunk_metadata)}) count.")
        return

    embeddings = generate_embeddings(all_text_chunks)

    results = []
    valid_embeddings_count = 0
    for i in range(len(all_text_chunks)):
        if i < len(embeddings) and embeddings[i] and i < len(all_chunk_metadata):
            embedding_list = embeddings[i].tolist() if isinstance(embeddings[i], np.ndarray) else embeddings[i]
            results.append({
                "text": all_text_chunks[i],
                "metadata": all_chunk_metadata[i],
                "embedding": embedding_list
            })
            valid_embeddings_count += 1
        else:
            print(f"Skipping result for chunk index {i} due to missing embedding or metadata.")

    if not results:
        print("\nNo valid embeddings were generated. Output file will not be created.")
        return

    output_dir = os.path.dirname(OUTPUT_EMBEDDINGS_FILE)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nEnsured output directory exists: {output_dir}")

    try:
        with open(OUTPUT_EMBEDDINGS_FILE, "w", encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nSuccessfully saved {valid_embeddings_count} enriched embeddings to: {OUTPUT_EMBEDDINGS_FILE}")
        
        # Print summary of chunk types created
        type_counts = {}
        for meta in all_chunk_metadata:
            chunk_type = meta.get("type", "unknown")
            type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        
        print("\nChunk type distribution:")
        for chunk_type, count in sorted(type_counts.items()):
            print(f"  - {chunk_type}: {count}")
            
    except IOError as e:
        print(f"Error saving embeddings file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving the file: {e}")

    return results

# --- Execution ---
if __name__ == "__main__":
    print("Starting enhanced JSON data processing with cross-file connectivity...")
    process_all_data()
    print("\nEnhanced embedding generation script finished.")