import os
import sys
import django

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Add backend directory to Python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.backend.settings')

# Initialize Django v
django.setup()

from django.conf import settings

def get_db_connection_params():
    """Get database connection parameters from Django settings"""
    return {
        'host': settings.DATABASES['default']['HOST'],
        'user': settings.DATABASES['default']['USER'],
        'password': settings.DATABASES['default']['PASSWORD'],
        'database': settings.DATABASES['default']['NAME'],
        'port': settings.DATABASES['default']['PORT'],
    }