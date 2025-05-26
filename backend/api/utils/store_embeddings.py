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
INPUT_EMBEDDINGS_FILE = BASE_DIR / "api" / "data" / "all_embeddings_data.json"

def determine_section_type(metadata):
    """Enhanced section type determination leveraging enriched metadata"""
    chunk_type = metadata.get("type", "unknown")
    skill_category = metadata.get("skill_category", "")
    
    # Enhanced functional skills detection
    if (chunk_type.startswith("fs_") or 
        skill_category == "functional" or
        chunk_type == "functional_skill"):
        return "functional_skills"
    
    # Enhanced enabling skills detection
    elif (chunk_type.startswith("esc_") or 
          skill_category == "enabling" or
          chunk_type == "enabling_skill"):
        return "enabling_skills"
    
    # Enhanced roles detection
    elif (chunk_type.startswith("role_") or 
          chunk_type == "whole_role" or
          metadata.get("job_title")):
        return "job_roles"
    
    # Enhanced career map detection
    elif (chunk_type.startswith("career_map") or 
          chunk_type == "career_progression_path" or
          metadata.get("domain_name") or
          metadata.get("grade_name") or
          metadata.get("next_roles_from_career_map")):
        return "career_map"
    
    # General/overview content
    else:
        return "general"

def enrich_metadata_for_search(metadata):
    """Add search-friendly fields to metadata"""
    # Create searchable text fields from metadata
    searchable_fields = []
    
    # Add role-related searchable terms
    if metadata.get("role_grade"):
        searchable_fields.append(f"grade_{metadata['role_grade'].lower().replace(' ', '_')}")
    
    if metadata.get("role_domain"):
        searchable_fields.append(f"domain_{metadata['role_domain'].lower().replace(' ', '_')}")
    
    # Add skill-related searchable terms
    if metadata.get("skill_category"):
        searchable_fields.append(f"skill_type_{metadata['skill_category']}")
    
    # Add progression-related terms
    if metadata.get("next_roles_from_career_map"):
        searchable_fields.extend([f"leads_to_{role.lower().replace(' ', '_')}" 
                                for role in metadata["next_roles_from_career_map"]])
    
    # Add connectivity indicators
    connectivity_score = 0
    if metadata.get("used_in_roles"):
        connectivity_score += len(metadata["used_in_roles"])
    if metadata.get("next_roles_from_career_map"):
        connectivity_score += len(metadata["next_roles_from_career_map"])
    if metadata.get("role_level_requirements"):
        connectivity_score += len(metadata["role_level_requirements"])
    
    # Add enriched fields
    metadata["searchable_tags"] = searchable_fields
    metadata["connectivity_score"] = connectivity_score
    metadata["has_career_progression"] = bool(metadata.get("next_roles_from_career_map") or 
                                            metadata.get("nextGrade"))
    metadata["has_role_connections"] = bool(metadata.get("used_in_roles") or 
                                          metadata.get("roles_at_this_level"))
    
    return metadata

def store_embeddings_from_json(input_path=INPUT_EMBEDDINGS_FILE):
    """Enhanced embeddings storage with connectivity metadata"""
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

    # Clear existing knowledge chunks
    try:
        print("Clearing existing KnowledgeChunk data from the database...")
        count, _ = KnowledgeChunk.objects.all().delete()
        print(f"Deleted {count} existing KnowledgeChunk objects.")
    except Exception as e:
        print(f"Error clearing existing KnowledgeChunk data: {e}")

    # Create PSF-AAI source
    psf_source, created = KnowledgeSource.objects.get_or_create(
        name="Philippine Skills Framework for Analytics and AI",
        source_type="framework_document",
        defaults={
            "metadata": {
                "description": "Comprehensive skills framework with enhanced connectivity",
                "publication_date": "2023",
                "publisher": "DOST-PCIEERD and Analytics Association of the Philippines",
                "features": ["career_progression", "skill_connections", "role_mappings"]
            }
        }
    )
    
    if created:
        print(f"Created PSF-AAI source record with enhanced metadata")
    else:
        print(f"Using existing PSF-AAI source record")

    # Enhanced storage with connectivity analysis
    print("Storing enriched embeddings with connectivity metadata...")
    stored_count = 0
    skipped_count = 0
    error_count = 0
    
    # Enhanced section tracking
    section_counts = {
        "functional_skills": 0,
        "enabling_skills": 0,
        "job_roles": 0,
        "career_map": 0,
        "general": 0
    }
    
    # Connectivity analysis
    connectivity_stats = {
        "chunks_with_role_connections": 0,
        "chunks_with_career_progression": 0,
        "chunks_with_skill_mappings": 0,
        "high_connectivity_chunks": 0  # connectivity_score > 3
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
            
            # Enhanced metadata processing
            section_type = determine_section_type(metadata)
            metadata["psf_section"] = section_type
            metadata = enrich_metadata_for_search(metadata)
            
            # Update statistics
            section_counts[section_type] += 1
            
            if metadata.get("has_role_connections"):
                connectivity_stats["chunks_with_role_connections"] += 1
            if metadata.get("has_career_progression"):
                connectivity_stats["chunks_with_career_progression"] += 1
            if metadata.get("role_level_requirements") or metadata.get("used_in_roles"):
                connectivity_stats["chunks_with_skill_mappings"] += 1
            if metadata.get("connectivity_score", 0) > 3:
                connectivity_stats["high_connectivity_chunks"] += 1
            
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

    print(f"\nEnhanced embedding storage summary:")
    print(f"Successfully stored {stored_count} knowledge chunks with connectivity metadata")
    print(f"\nContent breakdown by section:")
    for section, count in section_counts.items():
        if count > 0:
            print(f"  - {section}: {count} chunks")
    
    print(f"\nConnectivity analysis:")
    for stat_name, count in connectivity_stats.items():
        percentage = (count / stored_count * 100) if stored_count > 0 else 0
        print(f"  - {stat_name.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
    
    print(f"\nSkipped {skipped_count} items due to missing data")
    print(f"Encountered {error_count} errors during processing")

if __name__ == "__main__":
    print("Starting enhanced embedding storage process...")
    store_embeddings_from_json()
    print("\nEnhanced embedding storage process completed.")