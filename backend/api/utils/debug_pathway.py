import os
import sys
import json

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
from generate_pathways import generate_learning_pathway

def debug_pipeline():
    print("=" * 60)
    print("DEBUGGING PATHWAY GENERATION PIPELINE")
    print("=" * 60)
    
    # 1. Check if data directory exists
    data_dir = "backend/api/data"
    print(f"\nChecking data directory: {os.path.abspath(data_dir)}")
    if os.path.exists(data_dir):
        print(f"✓ Data directory exists")
        print(f"Directory contents: {os.listdir(data_dir)}")
    else:
        print(f"✗ Data directory not found")
        os.makedirs(data_dir, exist_ok=True)
        print(f"  Created data directory at {data_dir}")
    
    # 2. Check Pathway model structure
    print("\nChecking Pathway model structure:")
    try:
        fields = [f.name for f in Pathway._meta.get_fields()]
        print(f"✓ Model fields: {fields}")
        
        # Get the count
        count = Pathway.objects.count()
        print(f"✓ Pathway count in database: {count}")
        
        if count > 0:
            # Print first record
            first = Pathway.objects.first()
            print(f"✓ First record attributes: {first.__dict__}")
        else:
            print("✗ No records in the Pathway table")
    except Exception as e:
        print(f"✗ Error checking model: {e}")
    
    # 3. Test generate_learning_pathway
    print("\nTesting pathway generation:")
    query = "AI engineering skills"
    try:
        result = generate_learning_pathway(query)
        
        # Print summary
        print(f"✓ Generated pathway for query: '{query}'")
        if "error" in result:
            print(f"✗ Error in result: {result['error']}")
        else:
            print(f"✓ Pathway length: {len(result['pathway'])}")
            print(f"✓ Context items: {len(result['context'])}")
        
        # Save the result
        output_path = os.path.join(data_dir, "debug_pathway.json")
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ Debug pathway saved to: {output_path}")
        
        # Verify the file was created
        if os.path.exists(output_path):
            print(f"✓ File created successfully ({os.path.getsize(output_path)} bytes)")
        else:
            print(f"✗ File creation failed")
    except Exception as e:
        print(f"✗ Error testing pathway generation: {e}")
    
    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    debug_pipeline()