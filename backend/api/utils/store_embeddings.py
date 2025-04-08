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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from api.models import Pathway

def store_embeddings():
    """Store embeddings in the database"""
    # Load the embeddings from the file
    input_path = "backend/api/data/generated_embeddings.json"
    
    if not os.path.exists(input_path):
        print(f"Error: Generated embeddings file not found at {input_path}")
        return
    
    with open(input_path, "r") as f:
        embeddings_data = json.load(f)
    
    # Check if there are any embeddings to store
    if not embeddings_data:
        print("No embeddings to store")
        return
    
    # Clear existing pathways
    Pathway.objects.all().delete()
    
    # Store embeddings in the database
    for item in embeddings_data:
        text = item["text"]
        embedding = np.array(item["embedding"])
        metadata = item["metadata"]
        
        # Create Pathway object with the correct field mapping
        Pathway.objects.create(
            text=text,
            embedding=embedding,
            metadata=metadata
        )
    
    print(f"Stored {len(embeddings_data)} embeddings in the database")

if __name__ == "__main__":
    store_embeddings()