import os
import sys

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from extract_pathways import extract_pathways_from_pdf
from generate_embeddings import process_pathways
from setup_db import setup_database
from store_embeddings import store_embeddings
from generate_pathways import generate_learning_pathway

def run_pipeline():
    print("=" * 50)
    print("Starting Philippine Skills Framework Processing Pipeline")
    print("=" * 50)
    
    print("\nStep 1: Setting up PostgreSQL database with pgvector...")
    setup_database()
    
    print("\nStep 2: Extracting pathways from the Philippine Skills Framework PDF...")
    extract_pathways_from_pdf()
    
    print("\nStep 3: Generating embeddings with Llama 3.1...")
    process_pathways()
    
    print("\nStep 4: Storing embeddings in the database...")
    store_embeddings()
    
    print("\nStep 5: Testing pathway generation with Llama 3.1...")
    test_query = "What skills do I need for AI engineering?"
    result = generate_learning_pathway(test_query)
    
    if "error" in result:
        print(f"Error testing pathway generation: {result['error']}")
    else:
        print(f"Successfully generated pathway for: '{test_query}'")
        # print(f"Saved sample pathway to: backend/api/data/sample_pathway.json")
    
    print("\n" + "=" * 50)
    print("Pipeline completed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    os.makedirs("backend/api/data", exist_ok=True)
    run_pipeline()