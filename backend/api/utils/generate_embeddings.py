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

# --- Helper function to load roles data ---
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
            if skill_name:
                skill_map.setdefault(skill_name, {"roles": [], "type": "functional"})
                if role_title not in skill_map[skill_name]["roles"]:
                    skill_map[skill_name]["roles"].append(role_title)

        for es_skill_info in role.get("enabling_skills", []):
            skill_name = es_skill_info.get("skill")
            if skill_name:
                skill_map.setdefault(skill_name, {"roles": [], "type": "enabling"})
                if role_title not in skill_map[skill_name]["roles"]:
                    skill_map[skill_name]["roles"].append(role_title)
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

# --- Data Processing Functions ---
def process_enabling_skills(filepath, skill_to_roles_map):
    """Processes enabling skills data, adding roles information to metadata."""
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

            roles_using_skill = skill_to_roles_map.get(title, {}).get("roles", [])
            
            overview_text = f"# {title}\n\n"
            overview_text += f"## Description\n{description}\n\n"
            if roles_using_skill:
                overview_text += f"## Used in Roles\nThis skill is typically required for roles such as: {', '.join(roles_using_skill)}.\n\n"
            
            if range_items:
                overview_text += f"## {range_title}\n"
                for r_item in range_items:
                    if r_item and not r_item.isspace():
                        overview_text += f"- {r_item.strip()}\n"
                overview_text += "\n"
            
            if level_labels:
                overview_text += f"## Available Proficiency Levels\n"
                overview_text += f"This enabling skill has {len(level_labels)} defined proficiency levels: {', '.join(level_labels)}\n"
            
            text_chunks.append(overview_text)
            chunk_metadata.append({
                "type": "esc_complete_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_labels,
                "skill_category": "enabling",
                "used_in_roles": roles_using_skill
            })
            
            for lvl in valid_levels:
                level_label = lvl.get("level")
                if not level_label:
                    continue
                
                level_desc = lvl.get("description", "")
                esc_code = lvl.get("escCode", "")
                knowledge_points = lvl.get("underpinningKnowledge", [])
                skill_applications = lvl.get("skillsApplication", [])
                
                level_text = f"# {title} - {level_label} Level\n\n"
                if esc_code:
                    level_text += f"**Code:** {esc_code}\n\n"
                level_text += f"## Level Description\n{level_desc}\n\n"
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
                    "used_in_roles": roles_using_skill # Also add to level specific chunk
                })
            
            basic_overview = f"Enabling Skill: {title}\nDescription: {description}\nLevels: {', '.join(level_labels)}"
            if roles_using_skill:
                basic_overview += f"\nUsed in roles: {', '.join(roles_using_skill)}"
            text_chunks.append(basic_overview)
            chunk_metadata.append({
                "type": "enabling_skill",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_labels,
                "skill_category": "enabling",
                "used_in_roles": roles_using_skill
            })
            
            if range_items:
                range_text = f"{title} - Contexts of Application\n\nThis skill can be applied in the following contexts:\n"
                range_text += "\n".join([f"• {r_item.strip()}" for r_item in range_items if r_item and not r_item.isspace()])
                text_chunks.append(range_text)
                chunk_metadata.append({
                    "type": "esc_range",
                    "title": f"{title} - Contexts of Application",
                    "skill": title,
                    "skill_category": "enabling",
                    "used_in_roles": roles_using_skill
                })
        
        print(f"Processed {len(chunk_metadata)} enabling skill chunks.")
    except Exception as e:
        print(f"Error processing enabling skills: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def process_functional_skills(filepath, skill_to_roles_map):
    """Processes functional skills data, adding roles information to metadata."""
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

            roles_using_skill = skill_to_roles_map.get(title, {}).get("roles", [])
            
            overview_text = f"# {title}\n\n"
            overview_text += f"## Description\n{description}\n\n"
            if roles_using_skill:
                overview_text += f"## Used in Roles\nThis skill is typically required for roles such as: {', '.join(roles_using_skill)}.\n\n"

            if range_items:
                overview_text += f"## {range_title}\n"
                for r_item in range_items:
                    if r_item and not r_item.isspace():
                        overview_text += f"- {r_item.strip()}\n"
                overview_text += "\n"
            
            if level_numbers:
                overview_text += f"## Available Proficiency Levels\n"
                overview_text += f"This skill has {len(level_numbers)} defined proficiency levels: {', '.join(level_numbers)}\n"
            
            text_chunks.append(overview_text)
            chunk_metadata.append({
                "type": "fs_complete_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_numbers,
                "skill_category": "functional",
                "used_in_roles": roles_using_skill
            })
            
            for lvl in valid_levels:
                level_no = lvl.get("level")
                if not level_no:
                    continue
                
                level_desc = lvl.get("description", "")
                fsc_code = lvl.get("fscCode", "")
                knowledge_points = lvl.get("underpinningKnowledge", [])
                skill_applications = lvl.get("skillsApplication", [])
                
                level_text = f"# {title} - Level {level_no}\n\n"
                if fsc_code:
                    level_text += f"**Code:** {fsc_code}\n\n"
                level_text += f"## Level Description\n{level_desc}\n\n"
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
                    "used_in_roles": roles_using_skill # Also add to level specific chunk
                })
            
            basic_overview = f"Functional Skill: {title}\nDescription: {description}\nLevels: {', '.join(level_numbers)}"
            if roles_using_skill:
                basic_overview += f"\nUsed in roles: {', '.join(roles_using_skill)}"
            text_chunks.append(basic_overview)
            chunk_metadata.append({
                "type": "fs_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_numbers,
                "skill_category": "functional",
                "used_in_roles": roles_using_skill
            })
            
            if range_items:
                range_text = f"{title} - Contexts of Application\n\nThis skill can be applied in the following contexts:\n"
                range_text += "\n".join([f"• {r_item.strip()}" for r_item in range_items if r_item and not r_item.isspace()])
                text_chunks.append(range_text)
                chunk_metadata.append({
                    "type": "fs_range",
                    "title": f"{title} - Contexts of Application",
                    "skill": title,
                    "skill_category": "functional",
                    "used_in_roles": roles_using_skill
                })
        
        print(f"Processed {len(chunk_metadata)} functional skill chunks.")
    except Exception as e:
        print(f"Error processing functional skills: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def process_roles(filepath):
    """Processes roles data from processed_roles.json, splitting each role into multiple semantic chunks for better matching."""
    print(f"\nProcessing Roles from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)

        for role in data.get("roles", []):
            title = role.get("job_title", "Untitled Role")
            description = role.get("description", "No description")
            key_tasks_list = role.get("key_tasks", [])
            func_skills_list = role.get("functional_skills", [])
            enable_skills_list = role.get("enabling_skills", [])
            
            # Prepare structured metadata for skills to be stored with the role
            required_functional_skills_meta = [{"skill": s.get("skill"), "level": s.get("level")} for s in func_skills_list]
            required_enabling_skills_meta = [{"skill": s.get("skill"), "level": s.get("level")} for s in enable_skills_list]

            whole_role_text = f"# {title}\n\n"
            whole_role_text += f"## Description\n{description.strip()}\n\n"
            
            whole_role_text += f"## Key Tasks\n"
            for kt in key_tasks_list:
                function = kt.get("function", "").strip()
                tasks = kt.get("tasks", [])
                if function:
                    whole_role_text += f"### {function}\n"
                for task in tasks:
                    whole_role_text += f"- {task.strip()}\n"
                whole_role_text += "\n"
            
            whole_role_text += f"## Functional Skills Required\n"
            for skill_item in func_skills_list:
                whole_role_text += f"- {skill_item.get('skill')} (Level {skill_item.get('level')})\n"
            whole_role_text += "\n"
            
            whole_role_text += f"## Enabling Skills Required\n"
            for skill_item in enable_skills_list:
                whole_role_text += f"- {skill_item.get('skill')} (Level {skill_item.get('level')})\n"
            
            text_chunks.append(whole_role_text)
            chunk_metadata.append({
                "type": "whole_role",
                "title": title,
                "description": description.strip(),
                "key_tasks": key_tasks_list, # Store structured tasks
                "required_functional_skills": required_functional_skills_meta,
                "required_enabling_skills": required_enabling_skills_meta,
                "source_file": os.path.basename(filepath)
            })
            
            desc_chunk = f"What does a {title} do?\nDescription: {description.strip()}"
            text_chunks.append(desc_chunk)
            chunk_metadata.append({
                "type": "role_description",
                "title": title,
                "description": description.strip(),
                "source_file": os.path.basename(filepath)
            })

            if key_tasks_list:
                tasks_text_list = []
                for kt_item in key_tasks_list:
                    fn = kt_item.get("function", "")
                    if fn:
                        tasks_text_list.append(f"• {fn.strip()}")
                    for t in kt_item.get("tasks", []):
                        tasks_text_list.append(f"    – {t.strip()}")
                tasks_chunk_text = f"Key tasks for {title}:\n" + "\n".join(tasks_text_list)
                text_chunks.append(tasks_chunk_text)
                chunk_metadata.append({
                    "type": "role_tasks",
                    "title": title,
                    "key_tasks": key_tasks_list, # Store structured tasks
                    "source_file": os.path.basename(filepath)
                })

            func_skills_str = ", ".join(
                f"{s.get('skill')} (Level {s.get('level')})" for s in func_skills_list
            )
            enable_skills_str = ", ".join(
                f"{s.get('skill')} (Level {s.get('level')})" for s in enable_skills_list
            )
            skills_chunk_text = (
                f"What skills does a {title} need?\n"
                f"Functional Skills: {func_skills_str or 'N/A'}\n"
                f"Enabling Skills: {enable_skills_str or 'N/A'}"
            )
            text_chunks.append(skills_chunk_text)
            chunk_metadata.append({
                "type": "role_skills",
                "title": title,
                "required_functional_skills": required_functional_skills_meta,
                "required_enabling_skills": required_enabling_skills_meta,
                "source_file": os.path.basename(filepath)
            })

        print(f"Processed {len(chunk_metadata)} role chunks.")
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return text_chunks, chunk_metadata


def process_career_map(filepath):
    """Processes career map data from career_map.json."""
    print(f"\nProcessing Career Map from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)

        domain_names = [d.get("name", "Unknown Domain") for d in data.get("domains", [])]
        grade_names = [g.get("grade", "Unknown Grade") for g in data.get("jobGrades", [])]
        overview_text = (
            f"Career Map Overview\n\n"
            f"Domains/Vertical Tracks: {', '.join(domain_names)}\n"
            f"Job Grades/Horizontal Levels: {', '.join(grade_names)}"
        )
        text_chunks.append(overview_text)
        chunk_metadata.append({
            "type": "career_map_overview",
            "title": "Career Map Overview",
            "domains": domain_names,
            "job_grades": grade_names,
            "source_file": os.path.basename(filepath)
        })

        for domain_item in data.get("domains", []):
            domain_name = domain_item.get("name", "Unknown Domain")
            roles_in_domain_text_list = []
            roles_in_domain_meta = []
            for role_info in domain_item.get("roles", []):
                grade = role_info.get("grade", "")
                role_name = role_info.get("role", "")
                if grade and role_name:
                    roles_in_domain_text_list.append(f"- {grade}: {role_name}")
                    roles_in_domain_meta.append({"grade": grade, "role": role_name})

            domain_text = f"Career Domain: {domain_name}\nRoles:\n" + "\n".join(roles_in_domain_text_list)
            text_chunks.append(domain_text)
            chunk_metadata.append({
                "type": "career_map_domain",
                "title": f"Domain: {domain_name}",
                "domain_name": domain_name,
                "roles_in_domain": roles_in_domain_meta,
                "source_file": os.path.basename(filepath)
            })
        
        for job_grade in data.get("jobGrades", []):
            grade_name = job_grade.get("grade", "Unknown Grade")
            positions_in_grade_meta = []
            positions_in_grade_text_list = []

            for position_info in job_grade.get("positions", []):
                pos_name = position_info.get("name", "Unknown Position")
                pos_domain = position_info.get("domain", "N/A")
                next_roles = position_info.get("nextRoles", [])
                
                positions_in_grade_text_list.append(f"- {pos_name} (Domain: {pos_domain}, Next Roles: {', '.join(next_roles) if next_roles else 'N/A'})")
                positions_in_grade_meta.append({
                    "name": pos_name,
                    "domain": pos_domain,
                    "nextRoles": next_roles
                })
            
            grade_text = f"Job Grade: {grade_name}\nPositions:\n" + "\n".join(positions_in_grade_text_list)
            text_chunks.append(grade_text)
            chunk_metadata.append({
                "type": "career_map_grade",
                "title": f"Job Grade: {grade_name}",
                "grade_name": grade_name,
                "positions_in_grade": positions_in_grade_meta,
                "source_file": os.path.basename(filepath)
            })

        print(f"Processed {len(chunk_metadata)} career map chunks.")
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return text_chunks, chunk_metadata


# --- Main Processing Orchestration ---
def process_all_data():
    """Loads data from all JSON files, processes them, generates embeddings, and saves the results."""
    all_text_chunks = []
    all_chunk_metadata = []

    # First, load roles data and build the skill-to-roles map
    roles_data_content = load_roles_data(ROLES_DATA_PATH)
    skill_to_roles_map = build_skill_to_roles_map(roles_data_content)
    if not skill_to_roles_map:
        print("Warning: Skill-to-roles map could not be built. Skills metadata will not include 'used_in_roles'.")


    # Define processing functions and their corresponding file paths
    # Note: Roles are processed first, though the map is built from its raw data.
    # The skill processors now take the skill_to_roles_map.
    
    # Process Roles (doesn't need the map itself, but its data is used to build the map)
    if os.path.exists(ROLES_DATA_PATH):
        chunks, meta = process_roles(ROLES_DATA_PATH)
        all_text_chunks.extend(chunks)
        all_chunk_metadata.extend(meta)
    else:
        print(f"Warning: Roles input file not found, skipping: {ROLES_DATA_PATH}")

    # Process Enabling Skills
    if os.path.exists(ESC_DATA_PATH):
        chunks, meta = process_enabling_skills(ESC_DATA_PATH, skill_to_roles_map)
        all_text_chunks.extend(chunks)
        all_chunk_metadata.extend(meta)
    else:
        print(f"Warning: Enabling skills input file not found, skipping: {ESC_DATA_PATH}")

    # Process Functional Skills
    if os.path.exists(FSC_DATA_PATH):
        chunks, meta = process_functional_skills(FSC_DATA_PATH, skill_to_roles_map)
        all_text_chunks.extend(chunks)
        all_chunk_metadata.extend(meta)
    else:
        print(f"Warning: Functional skills input file not found, skipping: {FSC_DATA_PATH}")

    # Process Career Map
    if os.path.exists(CAREER_MAP_PATH):
        chunks, meta = process_career_map(CAREER_MAP_PATH)
        all_text_chunks.extend(chunks)
        all_chunk_metadata.extend(meta)
    else:
        print(f"Warning: Career map input file not found, skipping: {CAREER_MAP_PATH}")


    if not all_text_chunks:
        print("\nNo text chunks were generated. Exiting.")
        return

    print(f"\nTotal text chunks to embed: {len(all_text_chunks)}")

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
            print(f"Skipping result for chunk {i+1} due to missing embedding or metadata.")

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
        print(f"\nSuccessfully saved {valid_embeddings_count} embeddings to: {OUTPUT_EMBEDDINGS_FILE}")
    except IOError as e:
        print(f"Error saving embeddings file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving the file: {e}")

    return results

# --- Execution ---
if __name__ == "__main__":
    print("Starting JSON data processing and BGE-M3 embedding generation...")
    process_all_data()
    print("\nEmbedding generation script finished.")