import os
import sys
from pathlib import Path
import json
import logging

# --- Django setup ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from api.models import Course

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COURSES_JSON_PATH = BASE_DIR / 'api' / 'data' / 'courses' / 'skill_courses.json'

def store_courses_from_json(input_path=COURSES_JSON_PATH):
    logger.info(f"Attempting to load courses from: {input_path}")
    if not os.path.exists(input_path):
        logger.error(f"Courses JSON file not found at {input_path}")
        return
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} skill entries from JSON.")
    created_count = 0
    for skill_entry in data:
        skill = skill_entry['skill']
        logger.info(f"Processing skill: {skill}")
        for course in skill_entry['course_info']:
            logger.info(f"  Adding course: {course['course_title']}")
            Course.objects.create(
                title=course['course_title'],
                provider=course['course_provider'],
                url=course['course_url'],
                description=course.get('course_description', ''),
                price=course.get('price', 'Free'),
                rating=course.get('course_rating'),
                matching_skill=skill,
                metadata={},  # or add more info if needed
            )
            created_count += 1
    logger.info(f"Successfully created {created_count} Course objects.")

if __name__ == "__main__":
    logger.info("Starting course storage process...")
    store_courses_from_json()
    logger.info("Course storage process completed.")