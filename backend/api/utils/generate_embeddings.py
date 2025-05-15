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
EMBEDDING_MODEL = "bge-m3"  # Ensure this is bge-m3
OUTPUT_EMBEDDINGS_FILE = f"{BASE_DIR}/api/data/all_embeddings_data.json" # Consistent output file

# Input data file paths
ESC_DATA_PATH = f"{BASE_DIR}/api/data/esc/esc_data.json"
FSC_DATA_PATH = f"{BASE_DIR}/api/data/fsc/processed_data.json"
ROLES_DATA_PATH = f"{BASE_DIR}/api/data/roles/processed_roles.json"
CAREER_MAP_PATH = f"{BASE_DIR}/api/data-sample/career_map.json" # Using sample path provided

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
        # Use 'prompt' for newer Ollama versions, 'input' might be for older ones or specific models
        # Check Ollama API documentation if unsure. 'prompt' is common.
        payload = {
            "model": EMBEDDING_MODEL,
            "prompt": chunk
        }

        try:
            # Increased timeout for potentially longer embedding generation
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
# (process_enabling_skills, process_functional_skills, process_roles, process_career_map functions remain as previously defined)
def process_enabling_skills(filepath):
    """Processes enabling skills data with organized chunking for better retrieval and search."""
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
            
            # Get range of application data
            range_data = skill.get("rangeOfApplication", {})
            range_title = range_data.get("title", "Range of Application")
            range_items = range_data.get("items", [])
            
            # Get valid levels data
            valid_levels = [l for l in skill.get("proficiencyLevels", []) if l.get("description")]
            level_labels = [l.get("level") for l in valid_levels if l.get("level")]
            
            # 1. COMPREHENSIVE SKILL OVERVIEW WITH RANGE OF APPLICATION
            overview_text = f"# {title}\n\n"
            overview_text += f"## Description\n{description}\n\n"
            
            # Add range of application if available
            if range_items:
                overview_text += f"## {range_title}\n"
                for item in range_items:
                    if item and not item.isspace():
                        overview_text += f"- {item.strip()}\n"
                overview_text += "\n"
            
            # Add available levels summary
            if level_labels:
                overview_text += f"## Available Proficiency Levels\n"
                overview_text += f"This enabling skill has {len(level_labels)} defined proficiency levels: {', '.join(level_labels)}\n"
            
            # Add the comprehensive overview chunk
            text_chunks.append(overview_text)
            chunk_metadata.append({
                "type": "esc_complete_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_labels,
                "skill_category": "enabling"
            })
            
            # 2. COMPLETE LEVEL INFORMATION (one chunk per level with all details)
            for lvl in valid_levels:
                level_label = lvl.get("level")
                if not level_label:
                    continue
                
                level_desc = lvl.get("description", "")
                esc_code = lvl.get("escCode", "")
                knowledge_points = lvl.get("underpinningKnowledge", [])
                skill_applications = lvl.get("skillsApplication", [])
                
                # Create comprehensive level chunk
                level_text = f"# {title} - {level_label} Level\n\n"
                if esc_code:
                    level_text += f"**Code:** {esc_code}\n\n"
                
                # Add level description
                level_text += f"## Level Description\n{level_desc}\n\n"
                
                # Add knowledge requirements
                if knowledge_points:
                    level_text += f"## Underpinning Knowledge\nAt this level, you should know:\n"
                    for k in knowledge_points:
                        if k and not k.isspace():
                            level_text += f"- {k.strip()}\n"
                    level_text += "\n"
                
                # Add skill applications
                if skill_applications:
                    level_text += f"## Skills Application\nAt this level, you should be able to:\n"
                    for sa in skill_applications:
                        if sa and not sa.isspace():
                            level_text += f"- {sa.strip()}\n"
                
                # Add the comprehensive level chunk
                text_chunks.append(level_text)
                chunk_metadata.append({
                    "type": "esc_complete_level",
                    "title": f"{title} - {level_label} Level",
                    "skill": title,
                    "level": level_label,
                    "escCode": esc_code,
                    "skill_category": "enabling"
                })
            
            # 3. Keep original overview chunk for backward compatibility
            # Basic skill overview (without range)
            basic_overview = f"Enabling Skill: {title}\nDescription: {description}\nLevels: {', '.join(level_labels)}"
            text_chunks.append(basic_overview)
            chunk_metadata.append({
                "type": "enabling_skill",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_labels,
                "skill_category": "enabling"
            })
            
            # Range of application as separate chunk (if available)
            if range_items:
                range_text = f"{title} - Contexts of Application\n\nThis skill can be applied in the following contexts:\n"
                range_text += "\n".join([f"• {item.strip()}" for item in range_items if item and not item.isspace()])
                
                text_chunks.append(range_text)
                chunk_metadata.append({
                    "type": "esc_range",
                    "title": f"{title} - Contexts of Application",
                    "skill": title,
                    "skill_category": "enabling"
                })
        
        print(f"Processed {len(chunk_metadata)} enabling skill chunks.")
    except Exception as e:
        print(f"Error processing enabling skills: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def process_functional_skills(filepath):
    """Processes functional skills data with organized chunking for better retrieval and search."""
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
            
            # Get range of application data
            range_data = skill.get("rangeOfApplication", {})
            range_title = range_data.get("title", "Range of Application")
            range_items = range_data.get("items", [])
            
            # Get valid levels data
            valid_levels = [l for l in skill.get("proficiencyLevels", []) if l.get("description")]
            level_numbers = [str(l.get("level")) for l in valid_levels if l.get("level")]
            
            # 1. COMPREHENSIVE SKILL OVERVIEW WITH RANGE OF APPLICATION
            overview_text = f"# {title}\n\n"
            overview_text += f"## Description\n{description}\n\n"
            
            # Add range of application if available
            if range_items:
                overview_text += f"## {range_title}\n"
                for item in range_items:
                    if item and not item.isspace():
                        overview_text += f"- {item.strip()}\n"
                overview_text += "\n"
            
            # Add available levels summary
            if level_numbers:
                overview_text += f"## Available Proficiency Levels\n"
                overview_text += f"This skill has {len(level_numbers)} defined proficiency levels: {', '.join(level_numbers)}\n"
            
            # Add the comprehensive overview chunk
            text_chunks.append(overview_text)
            chunk_metadata.append({
                "type": "fs_complete_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_numbers,
                "skill_category": "functional"
            })
            
            # 2. COMPLETE LEVEL INFORMATION (one chunk per level with all details)
            for lvl in valid_levels:
                level_no = lvl.get("level")
                if not level_no:
                    continue
                
                level_desc = lvl.get("description", "")
                fsc_code = lvl.get("fscCode", "")
                knowledge_points = lvl.get("underpinningKnowledge", [])
                skill_applications = lvl.get("skillsApplication", [])
                
                # Create comprehensive level chunk
                level_text = f"# {title} - Level {level_no}\n\n"
                if fsc_code:
                    level_text += f"**Code:** {fsc_code}\n\n"
                
                # Add level description
                level_text += f"## Level Description\n{level_desc}\n\n"
                
                # Add knowledge requirements
                if knowledge_points:
                    level_text += f"## Underpinning Knowledge\nAt this level, you should know:\n"
                    for k in knowledge_points:
                        if k and not k.isspace():
                            level_text += f"- {k.strip()}\n"
                    level_text += "\n"
                
                # Add skill applications
                if skill_applications:
                    level_text += f"## Skills Application\nAt this level, you should be able to:\n"
                    for sa in skill_applications:
                        if sa and not sa.isspace():
                            level_text += f"- {sa.strip()}\n"
                
                # Add the comprehensive level chunk
                text_chunks.append(level_text)
                chunk_metadata.append({
                    "type": "fs_complete_level",
                    "title": f"{title} - Level {level_no}",
                    "skill": title,
                    "level": level_no,
                    "fscCode": fsc_code,
                    "skill_category": "functional"
                })
            
            # 3. Keep original overview and range chunks for specific searches
            # Basic skill overview (without range)
            basic_overview = f"Functional Skill: {title}\nDescription: {description}\nLevels: {', '.join(level_numbers)}"
            text_chunks.append(basic_overview)
            chunk_metadata.append({
                "type": "fs_overview",
                "title": title,
                "skill": title,
                "codePrefix": code_prefix,
                "available_levels": level_numbers,
                "skill_category": "functional"
            })
            
            # Range of application as separate chunk (if available)
            if range_items:
                range_text = f"{title} - Contexts of Application\n\nThis skill can be applied in the following contexts:\n"
                range_text += "\n".join([f"• {item.strip()}" for item in range_items if item and not item.isspace()])
                
                text_chunks.append(range_text)
                chunk_metadata.append({
                    "type": "fs_range",
                    "title": f"{title} - Contexts of Application",
                    "skill": title,
                    "skill_category": "functional"
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
            # Intentionally ignoring performance expectations as requested
            func_skills_list = role.get("functional_skills", [])
            enable_skills_list = role.get("enabling_skills", [])
            
            # Create a comprehensive "whole role" chunk with all information
            whole_role_text = f"# {title}\n\n"
            whole_role_text += f"## Description\n{description.strip()}\n\n"
            
            # Add key tasks section
            whole_role_text += f"## Key Tasks\n"
            for kt in key_tasks_list:
                function = kt.get("function", "").strip()
                tasks = kt.get("tasks", [])
                if function:
                    whole_role_text += f"### {function}\n"
                for task in tasks:
                    whole_role_text += f"- {task.strip()}\n"
                whole_role_text += "\n"
            
            # Add functional skills section
            whole_role_text += f"## Functional Skills Required\n"
            for skill in func_skills_list:
                whole_role_text += f"- {skill.get('skill')} (Level {skill.get('level')})\n"
            whole_role_text += "\n"
            
            # Add enabling skills section
            whole_role_text += f"## Enabling Skills Required\n"
            for skill in enable_skills_list:
                whole_role_text += f"- {skill.get('skill')} (Level {skill.get('level')})\n"
            
            # Add this comprehensive chunk
            text_chunks.append(whole_role_text)
            chunk_metadata.append({
                "type": "whole_role",
                "title": title,
                "source_file": os.path.basename(filepath)
            })
            
            # Keep the existing granular chunks for specific queries
            # 1) Role description chunk
            desc_chunk = f"What does a {title} do?\nDescription: {description.strip()}"
            text_chunks.append(desc_chunk)
            chunk_metadata.append({
                "type": "role_description",
                "title": title,
                "source_file": os.path.basename(filepath)
            })

            # 2) Key tasks chunk(s)
            if key_tasks_list:
                tasks_text = []
                for kt in key_tasks_list:
                    fn = kt.get("function", "")
                    if fn:
                        tasks_text.append(f"• {fn.strip()}")
                    for t in kt.get("tasks", []):
                        tasks_text.append(f"    – {t.strip()}")
                tasks_chunk = f"Key tasks for {title}:\n" + "\n".join(tasks_text)
                text_chunks.append(tasks_chunk)
                chunk_metadata.append({
                    "type": "role_tasks",
                    "title": title,
                    "source_file": os.path.basename(filepath)
                })

            # 3) Skills needed chunk
            func_skills = ", ".join(
                f"{s.get('skill')} (Level {s.get('level')})" for s in func_skills_list
            )
            enable_skills = ", ".join(
                f"{s.get('skill')} (Level {s.get('level')})" for s in enable_skills_list
            )
            skills_chunk = (
                f"What skills does a {title} need?\n"
                f"Functional Skills: {func_skills or 'N/A'}\n"
                f"Enabling Skills: {enable_skills or 'N/A'}"
            )
            text_chunks.append(skills_chunk)
            chunk_metadata.append({
                "type": "role_skills",
                "title": title,
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

        # Overview Chunk
        domains = [d.get("name", "Unknown Domain") for d in data.get("domains", [])]
        grades = [g.get("grade", "Unknown Grade") for g in data.get("jobGrades", [])]
        overview_text = (
            f"Career Map Overview\n\n"
            f"Domains/Vertical Tracks: {', '.join(domains)}\n"
            f"Job Grades/Horizontal Levels: {', '.join(grades)}"
        )
        text_chunks.append(overview_text)
        chunk_metadata.append({
            "type": "career_map_overview",
            "title": "Career Map Overview",
            "source_file": os.path.basename(filepath)
        })

        # Domain-specific Chunks
        for domain in data.get("domains", []):
            domain_name = domain.get("name", "Unknown Domain")
            roles_in_domain = []
            for role_info in domain.get("roles", []):
                grade = role_info.get("grade", "")
                role_name = role_info.get("role", "")
                if grade and role_name:
                    roles_in_domain.append(f"- {grade}: {role_name}")

            domain_text = f"Career Domain: {domain_name}\nRoles:\n" + "\n".join(roles_in_domain)
            text_chunks.append(domain_text)
            chunk_metadata.append({
                "type": "career_map_domain",
                "title": f"Domain: {domain_name}",
                "domain": domain_name,
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

    # Define processing functions and their corresponding file paths
    file_processors = {
        ESC_DATA_PATH: process_enabling_skills,
        FSC_DATA_PATH: process_functional_skills,
        ROLES_DATA_PATH: process_roles,
        CAREER_MAP_PATH: process_career_map
    }

    # Process each file type
    for file_path, process_func in file_processors.items():
         if os.path.exists(file_path):
             chunks, meta = process_func(file_path)
             all_text_chunks.extend(chunks)
             all_chunk_metadata.extend(meta)
         else:
             print(f"Warning: Input file not found, skipping: {file_path}")


    if not all_text_chunks:
        print("\nNo text chunks were generated. Exiting.")
        return

    print(f"\nTotal text chunks to embed: {len(all_text_chunks)}")

    # Generate embeddings for all combined chunks
    embeddings = generate_embeddings(all_text_chunks)

    # Combine chunks, metadata, and embeddings
    results = []
    valid_embeddings_count = 0
    for i in range(len(all_text_chunks)):
        # Ensure embedding is not empty and metadata exists
        if i < len(embeddings) and embeddings[i] and i < len(all_chunk_metadata):
            # Convert numpy array to list if necessary (Ollama usually returns list)
            embedding_list = embeddings[i].tolist() if isinstance(embeddings[i], np.ndarray) else embeddings[i]
            results.append({
                "text": all_text_chunks[i],
                "metadata": all_chunk_metadata[i],
                "embedding": embedding_list # Store as list
            })
            valid_embeddings_count += 1
        else:
            print(f"Skipping result for chunk {i+1} due to missing embedding or metadata.")

    if not results:
        print("\nNo valid embeddings were generated. Output file will not be created.")
        return

    # Ensure output directory exists
    output_dir = os.path.dirname(OUTPUT_EMBEDDINGS_FILE)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nEnsured output directory exists: {output_dir}")

    # Save results to JSON file
    try:
        with open(OUTPUT_EMBEDDINGS_FILE, "w", encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nSuccessfully saved {valid_embeddings_count} embeddings to: {OUTPUT_EMBEDDINGS_FILE}")
    except IOError as e:
        print(f"Error saving embeddings file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving the file: {e}")

    return results # Return results for potential chaining

# --- Execution ---
if __name__ == "__main__":
    print("Starting JSON data processing and BGE-M3 embedding generation...")
    process_all_data()
    print("\nEmbedding generation script finished.")
