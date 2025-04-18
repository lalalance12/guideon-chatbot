# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\utils\store_embeddings.py
import json
import os
import sys
import numpy as np

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.backend.settings')
import django
django.setup()

# Import the model *after* Django setup
from api.models import Pathway # Assuming Pathway model has a VectorField named 'embedding'

# --- Configuration ---
# Use the same output file name as defined in generate_embeddings.py
INPUT_EMBEDDINGS_FILE = "backend/api/data/all_embeddings_data.json"

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

    # Clear existing pathways before adding new ones
    try:
        print("Clearing existing Pathway data from the database...")
        count, _ = Pathway.objects.all().delete()
        print(f"Deleted {count} existing Pathway objects.")
    except Exception as e:
        print(f"Error clearing existing Pathway data: {e}")
        # Decide if you want to proceed or stop if clearing fails
        # return

    # Store new embeddings
    print("Storing new embeddings into the database...")
    stored_count = 0
    skipped_count = 0
    pathway_objects = []
    for i, item in enumerate(embeddings_data):
        text = item.get("text")
        embedding_list = item.get("embedding")
        metadata = item.get("metadata", {}) # Default to empty dict if missing

        if text and embedding_list and isinstance(embedding_list, list):
            try:
                # Convert list to numpy array for pgvector compatibility if needed,
                # but pgvector often handles lists directly. Check your model field definition.
                # embedding_vector = np.array(embedding_list)

                # Create Pathway object (use list directly if VectorField accepts it)
                pathway_objects.append(
                    Pathway(
                        text=text,
                        embedding=embedding_list, # Store the list
                        metadata=metadata
                    )
                )
                stored_count += 1
            except Exception as e:
                 print(f"Error preparing Pathway object for item {i+1}: {e}")
                 skipped_count += 1
        else:
            print(f"Skipping item {i+1} due to missing text or invalid embedding format.")
            skipped_count += 1

    # Bulk create for efficiency
    if pathway_objects:
        try:
            Pathway.objects.bulk_create(pathway_objects)
            print(f"Successfully stored {stored_count} new embeddings in the database.")
        except Exception as e:
            print(f"Error during bulk creation of Pathway objects: {e}")
    else:
        print("No valid Pathway objects were prepared for storage.")

    if skipped_count > 0:
         print(f"Skipped {skipped_count} items due to errors or missing data.")


if __name__ == "__main__":
    print("Starting embedding storage process...")
    store_embeddings_from_json()
    print("\nEmbedding storage script finished.")