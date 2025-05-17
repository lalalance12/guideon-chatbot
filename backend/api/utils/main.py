import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.backend.settings')

from backend.api.utils.generate_embeddings import process_all_data
from backend.api.utils.setup_db import setup_database
from backend.api.utils.store_embeddings import store_embeddings_from_json
import django

django.setup()

def run_embedding_pipeline():
    """Runs the pipeline to generate and store embeddings from JSON data."""
    print("=" * 50)
    print("Starting Skills Framework Embedding Pipeline (JSON Data)")
    print("Using bge-m3 model")
    print("=" * 50)

    output_embeddings_file = f"{BASE_DIR}/api/data/all_embeddings_data.json"
    os.makedirs(os.path.dirname(output_embeddings_file), exist_ok=True)


    print("\nStep 1: Setting up PostgreSQL database with pgvector...")
    try:
        setup_database()
        print("Database setup checked/completed.")
    except Exception as e:
        print(f"Error during database setup: {e}")
        # Decide whether to stop or continue
        # return # Stop if DB setup fails

    print("\nStep 2: Processing JSON files and generating embeddings with bge-m3...")
    try:
        process_all_data() # This function now handles processing and saving to JSON
        print("Embedding generation completed.")
    except Exception as e:
        print(f"Error during embedding generation: {e}")
        # return # Stop if embedding generation fails

    print("\nStep 3: Storing embeddings in the database...")
    try:
        store_embeddings_from_json() # This function loads from the JSON and stores
        print("Embeddings stored in database.")
    except Exception as e:
        print(f"Error during embedding storage: {e}")

    # Step 4: Querying (Keep commented out as requested)
    # print("\nStep 4: Testing vector search (Example)...")
    # try:
    #     test_query = "What skills are needed for a Data Analyst?"
    #     results = search_similar_content(test_query)
    #     if isinstance(results, dict) and "error" in results:
    #          print(f"Error testing search: {results['error']}")
    #     elif not results:
    #          print(f"No results found for query: '{test_query}'")
    #     else:
    #          print(f"Found {len(results)} results for query: '{test_query}'")
    #          # print(results[0]) # Optionally print the top result
    # except Exception as e:
    #     print(f"Error during search test: {e}")


    print("\n" + "=" * 50)
    print("Embedding Pipeline completed!")
    print("=" * 50)

if __name__ == "__main__":
    run_embedding_pipeline()
