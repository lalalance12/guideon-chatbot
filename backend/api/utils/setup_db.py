import os
import sys
import django

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
django.setup()

def setup_database():
    """
    No need to create the extension manually as we're now using 
    Django migrations to set up pgvector
    """
    from django.core.management import call_command
    
    print("Running migrations to ensure database is set up...")
    call_command('migrate')
    print("Migrations completed successfully")

if __name__ == "__main__":
    setup_database()