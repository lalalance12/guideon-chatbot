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
EMBEDDING_MODEL = "bge-m3"  # Using BGE-M3 embedding model

# File paths
ROLE_SKILL_DESCRIPTION_PATH = f"{BASE_DIR}/api/data/skills/role_skill_description.json"
ROLE_SKILL_KNOWLEDGE_PATH = f"{BASE_DIR}/api/data/skills/role_skill_knowledge.json"
OUTPUT_DESCRIPTION_EMBEDDINGS_FILE = f"{BASE_DIR}/api/data/courses/role_skill_description_embeddings.json"
OUTPUT_KNOWLEDGE_EMBEDDINGS_FILE = f"{BASE_DIR}/api/data/courses/role_skill_knowledge_embeddings.json"

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

def process_skills_with_knowledge(filepath):
    """Process skills and their underpinning knowledge together for embedding generation."""
    print(f"\nProcessing Skills and Knowledge from: {filepath}")
    text_chunks = []
    chunk_metadata = []
    
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        title_count = 0
        knowledge_count = 0
        
        # This file contains job roles with functional skills, each with underpinning knowledge
        for role_entry in data:
            job_title = role_entry.get("job_title", "Unknown Role")
            skills = role_entry.get("functional_skills", [])
            
            for skill in skills:
                title = skill.get("title", "Untitled Skill")
                knowledge_points = skill.get("underpinning_knowledge", [])
                
                # Add the skill title as a chunk
                title_text = f"{title}"
                text_chunks.append(title_text)
                chunk_metadata.append({
                    "type": "skill_title",
                    "job_title": job_title,
                    "title": title
                })
                title_count += 1
                
                # Process underpinning knowledge if available
                if knowledge_points:
                    valid_points = [p.strip() for p in knowledge_points if p and not p.isspace()]
                    
                    if valid_points:
                        # Join knowledge points with spaces instead of numbered list
                        knowledge_text = "Underpinning Knowledge for " + title + ":\n"
                        
                        text_chunks.append(knowledge_text)
                        chunk_metadata.append({
                            "type": "underpinning_knowledge",
                            "job_title": job_title,
                            "skill_title": title,
                            "knowledge": valid_points,
                            "knowledge_count": len(valid_points)
                        })
                        knowledge_count += 1
        
        print(f"Processed {title_count} skill titles and {knowledge_count} knowledge chunks.")
    except Exception as e:
        print(f"Error processing skills and knowledge: {e}")
        traceback.print_exc()
    
    return text_chunks, chunk_metadata

def save_embeddings(text_chunks, chunk_metadata, embeddings, output_file):
    """Save embeddings to a specified output file."""
    # Combine chunks, metadata, and embeddings
    results = []
    valid_embeddings_count = 0
    
    for i in range(len(text_chunks)):
        # Ensure embedding is not empty and metadata exists
        if i < len(embeddings) and embeddings[i] and i < len(chunk_metadata):
            # Convert numpy array to list if necessary
            embedding_list = embeddings[i].tolist() if isinstance(embeddings[i], np.ndarray) else embeddings[i]
            results.append({
                "text": text_chunks[i],
                "metadata": chunk_metadata[i],
                "embedding": embedding_list
            })
            valid_embeddings_count += 1
        else:
            print(f"Skipping result for chunk {i+1} due to missing embedding or metadata.")
    
    if not results:
        print("\nNo valid embeddings were generated. Output file will not be created.")
        return 0
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\nEnsured output directory exists: {output_dir}")
    
    # Save results to JSON file
    try:
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"\nSuccessfully saved {valid_embeddings_count} embeddings to: {output_file}")
    except IOError as e:
        print(f"Error saving embeddings file: {e}")
        return 0
    except Exception as e:
        print(f"An unexpected error occurred while saving the file: {e}")
        return 0
    
    return valid_embeddings_count

def process_data():
    """Main function to process role skill data and generate embeddings."""
    print("Starting data processing and embedding generation...")
    
    # Process skills and their knowledge together
    print("\n--- PROCESSING SKILLS AND KNOWLEDGE ---")
    all_text_chunks, all_chunk_metadata = process_skills_with_knowledge(ROLE_SKILL_KNOWLEDGE_PATH)
    
    # Calculate and display total chunks before generating embeddings
    print(f"\n=== SUMMARY BEFORE EMBEDDING ===")
    title_count = sum(1 for meta in all_chunk_metadata if meta["type"] == "skill_title")
    knowledge_count = sum(1 for meta in all_chunk_metadata if meta["type"] == "underpinning_knowledge")
    print(f"Skill title chunks: {title_count}")
    print(f"Skill knowledge chunks: {knowledge_count}")
    print(f"Total chunks to be embedded: {len(all_text_chunks)}")
    print(f"===========================")
    
    # Generate embeddings for all chunks and save to one file
    total_count = 0
    if all_text_chunks:
        print(f"\nGenerating embeddings for {len(all_text_chunks)} total chunks...")
        all_embeddings = generate_embeddings(all_text_chunks)
        total_count = save_embeddings(all_text_chunks, all_chunk_metadata, all_embeddings, OUTPUT_KNOWLEDGE_EMBEDDINGS_FILE)
    else:
        print("\nNo chunks were generated.")
    
    return total_count

if __name__ == "__main__":
    total_count = process_data()
    print(f"\nEmbedding generation finished. Processed {total_count} total chunks (titles and knowledge).")
