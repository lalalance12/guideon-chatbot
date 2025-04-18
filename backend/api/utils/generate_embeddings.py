# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\utils\generate_embeddings.py
import json
import requests
import numpy as np
import os

# --- Configuration ---
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "bge-m3"  # Ensure this is bge-m3
OUTPUT_EMBEDDINGS_FILE = "backend/api/data/all_embeddings_data.json" # Consistent output file

# Input data file paths
ESC_DATA_PATH = "backend/api/data/esc/esc_data.json"
FSC_DATA_PATH = "backend/api/data/fsc/processed_data.json"
ROLES_DATA_PATH = "backend/api/data/roles/processed_roles.json"
CAREER_MAP_PATH = "backend/api/data-sample/career_map.json" # Using sample path provided

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
    """Processes enabling skills data from esc_data.json."""
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

            skill_text = f"Enabling Skill: {title}\nDescription: {description}"
            text_chunks.append(skill_text)
            chunk_metadata.append({
                "type": "enabling_skill",
                "title": title,
                "codePrefix": code_prefix,
                "source_file": os.path.basename(filepath)
            })

        print(f"Processed {len(chunk_metadata)} enabling skill chunks.")
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return text_chunks, chunk_metadata

def process_functional_skills(filepath):
    """Processes functional skills data from processed_data.json."""
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

            skill_text = f"Functional Skill: {title}\nDescription: {description}"
            text_chunks.append(skill_text)
            chunk_metadata.append({
                "type": "functional_skill",
                "title": title,
                "codePrefix": code_prefix,
                "source_file": os.path.basename(filepath)
            })
        print(f"Processed {len(chunk_metadata)} functional skill chunks.")
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return text_chunks, chunk_metadata

def process_roles(filepath):
    """Processes roles data from processed_roles.json."""
    print(f"\nProcessing Roles from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)

        roles = data.get("roles", [])
        for role in roles:
            title = role.get("job_title", "Untitled Role")
            description = role.get("description", "No description")
            key_tasks_list = role.get("key_tasks", [])
            # Handle potential nested structure if 'function' and 'tasks' exist
            key_tasks_formatted = []
            if key_tasks_list and isinstance(key_tasks_list[0], dict): # Check if tasks are dicts
                 for kt in key_tasks_list:
                     fn = kt.get("function", "")
                     if fn: key_tasks_formatted.append(f"• {fn}")
                     for t in kt.get("tasks", []):
                         key_tasks_formatted.append(f"    – {t}")
            elif key_tasks_list: # Assume list of strings
                key_tasks_formatted = [f"- {t}" for t in key_tasks_list if isinstance(t, str)]

            key_tasks = "\n".join(key_tasks_formatted)
            perf_expectations = "\n".join([f"- {p}" for p in role.get("performance_expectations", []) if isinstance(p, str)])

            # Handle skills which might be strings or dicts
            func_skills_list = role.get("functional_skills", [])
            if func_skills_list and isinstance(func_skills_list[0], dict):
                func_skills = ", ".join(f"{s.get('skill', '')} (Level {s.get('level', 'N/A')})" for s in func_skills_list)
            else:
                func_skills = ", ".join([s for s in func_skills_list if isinstance(s, str)])

            enabling_skills_list = role.get("enabling_skills", [])
            if enabling_skills_list and isinstance(enabling_skills_list[0], dict):
                 enabling_skills = ", ".join(f"{s.get('skill', '')} (Level {s.get('level', 'N/A')})" for s in enabling_skills_list)
            else:
                enabling_skills = ", ".join([s for s in enabling_skills_list if isinstance(s, str)])


            role_text = (
                f"Job Role: {title}\n\n"
                f"Description:\n{description}\n\n"
                f"Key Tasks:\n{key_tasks if key_tasks else 'N/A'}\n\n"
                f"Performance Expectations:\n{perf_expectations if perf_expectations else 'N/A'}\n\n"
                f"Functional Skills: {func_skills if func_skills else 'N/A'}\n"
                f"Enabling Skills: {enabling_skills if enabling_skills else 'N/A'}"
            )
            text_chunks.append(role_text)
            chunk_metadata.append({
                "type": "role",
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
