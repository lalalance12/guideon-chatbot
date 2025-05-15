import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django

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