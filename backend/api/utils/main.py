# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\utils\main.py
import os
import sys

# Add project root and backend directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../..'))
backend_dir = os.path.abspath(os.path.join(current_dir, '../..'))

if project_root not in sys.path:
    sys.path.append(project_root)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Import necessary functions AFTER path setup
# Note: Adjusted import paths assuming 'utils' is a package within 'api'
try:
    from backend.api.utils.generate_embeddings import process_all_data
    from backend.api.utils.setup_db import setup_database
    from backend.api.utils.store_embeddings import store_embeddings_from_json
    # from backend.api.utils.query_vectors import search_similar_content # Keep commented for now
    # from backend.api.utils.generate_pathways import generate_learning_pathway # Keep commented for now
except ImportError as e:
     print(f"Error importing modules: {e}")
     print("Ensure the script is run from the correct directory or PYTHONPATH is set.")
     sys.exit(1)


def run_embedding_pipeline():
    """Runs the pipeline to generate and store embeddings from JSON data."""
    print("=" * 50)
    print("Starting Skills Framework Embedding Pipeline (JSON Data)")
    print("Using bge-m3 model")
    print("=" * 50)

    # Ensure data directories exist (optional, but good practice)
    os.makedirs("backend/api/data/esc", exist_ok=True)
    os.makedirs("backend/api/data/fsc", exist_ok=True)
    os.makedirs("backend/api/data/roles", exist_ok=True)
    # Ensure the directory for the output embeddings file exists
    output_embeddings_file = "backend/api/data/all_embeddings_data.json"
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
