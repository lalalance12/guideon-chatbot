import os
import sys
import subprocess
import logging

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.conf import settings
from django.db import connection

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def reset_database():
    db_settings = settings.DATABASES['default']
    db_name = db_settings['NAME']
    
    logger.info(f"Database configuration:")
    logger.info(f" - Name: {db_name}")
    
    # Instead of dropping the whole database, drop all tables using Django's connection
    with connection.cursor() as cursor:
        logger.info("Dropping all tables...")
        cursor.execute("""
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """)
    
    # Run migrations to recreate tables
    logger.info("Running migrations...")
    os.chdir(project_root)
    subprocess.run("python manage.py migrate", shell=True)
    
    logger.info("Database reset complete!")

if __name__ == "__main__":
    reset_database()