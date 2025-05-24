import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import json
import traceback
import django

django.setup()

# Import the models *after* Django setup
from api.models import KnowledgeChunk, KnowledgeSource

# --- Configuration ---
# Use the same output file name as defined in generate_embeddings.py
INPUT_EMBEDDINGS_FILE = BASE_DIR / "api" / "data" / "all_embeddings_data.json"

def determine_section_type(metadata):
    """Determine which section of the PSF-AAI document this chunk belongs to"""
    chunk_type = metadata.get("type", "unknown")
    skill_category = metadata.get("skill_category", "")
    
    # More specific matching for functional skills
    if chunk_type.startswith("fs_") or skill_category == "functional":
        return "functional_skills"
    # More specific matching for enabling skills
    elif chunk_type.startswith("esc_") or chunk_type == "enabling_skill" or skill_category == "enabling":
        return "enabling_skills"
    # More specific matching for roles
    elif chunk_type.startswith("role_") or chunk_type == "whole_role":
        return "job_roles"
    # More specific matching for career map
    elif chunk_type.startswith("career_map"):
        return "career_map"
    else:
        return "general"

def store_embeddings_from_json(input_path=INPUT_EMBEDDINGS_FILE):
    """Loads embeddings from a JSON file and stores them in the database."""
    print(f"\nAttempting to load embeddings from: {input_path}")

    if not os.path.exists(input_path):
        print(f"Error: Embeddings JSON file not found at {input_path}")
        return

    try:
        with open(input_path, "r", encoding='utf-8') as f:
            embeddings_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {input_path}: {e}")
        return
    except Exception as e:
        print(f"Error reading file {input_path}: {e}")
        return

    if not embeddings_data:
        print("No embeddings data found in the file.")
        return

    print(f"Found {len(embeddings_data)} items in the embeddings file.")

    # Clear existing knowledge chunks before adding new ones
    try:
        print("Clearing existing KnowledgeChunk data from the database...")
        count, _ = KnowledgeChunk.objects.all().delete()
        print(f"Deleted {count} existing KnowledgeChunk objects.")
    except Exception as e:
        print(f"Error clearing existing KnowledgeChunk data: {e}")

    # Create a single PSF-AAI source
    psf_source, created = KnowledgeSource.objects.get_or_create(
        name="Philippine Skills Framework for Analytics and AI",
        source_type="framework_document",
        defaults={
            "metadata": {
                "description": "Comprehensive skills framework for analytics and AI roles in the Philippines",
                "publication_date": "2023",
                "publisher": "DOST-PCIEERD and Analytics Association of the Philippines"
            }
        }
    )
    
    if created:
        print(f"Created PSF-AAI source record")
    else:
        print(f"Using existing PSF-AAI source record")

    # Store new embeddings
    print("Storing new embeddings into the database...")
    stored_count = 0
    skipped_count = 0
    error_count = 0
    section_counts = {
        "functional_skills": 0,
        "enabling_skills": 0,
        "job_roles": 0,
        "career_map": 0,
        "general": 0
    }

    for i, item in enumerate(embeddings_data):
        try:
            text = item.get("text")
            embedding_list = item.get("embedding")
            metadata = item.get("metadata", {})
            
            # Skip if missing essential data
            if not text or not embedding_list or not isinstance(embedding_list, list):
                print(f"Skipping item {i+1} due to missing text or invalid embedding format.")
                skipped_count += 1
                continue
            
            # Determine section type and add to metadata
            section_type = determine_section_type(metadata)
            metadata["psf_section"] = section_type
            section_counts[section_type] += 1
            
            # Create the knowledge chunk
            chunk = KnowledgeChunk.objects.create(
                text=text,
                embedding=embedding_list,
                metadata=metadata,
                source=psf_source
            )
            
            stored_count += 1
            if stored_count % 100 == 0:
                print(f"Processed {stored_count} knowledge chunks...")
                
        except Exception as e:
            print(f"Error processing item {i+1}: {e}")
            traceback.print_exc()
            error_count += 1

    print(f"\nEmbedding storage summary:")
    print(f"Successfully stored {stored_count} knowledge chunks")
    print(f"Content breakdown by section:")
    for section, count in section_counts.items():
        if count > 0:
            print(f"  - {section}: {count} chunks")
    print(f"Skipped {skipped_count} items due to missing data")
    print(f"Encountered {error_count} errors during processing")

if __name__ == "__main__":
    print("Starting embedding storage process...")
    store_embeddings_from_json()
    print("\nEmbedding storage process completed.")