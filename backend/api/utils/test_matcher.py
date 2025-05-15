import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to enable imports
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(parent_dir))

import logging
from api.utils.skill_course_matcher import load_skill_embeddings, match_course_to_skills, match_course_to_underpinning_knowledge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_load_embeddings():
    logger.info("Testing load_skill_embeddings function")
    embeddings = load_skill_embeddings()
    logger.info(f"Received {len(embeddings)} embeddings in test")
    return embeddings

def test_matching():
    logger.info("Testing course-skill matching")
    
    # Sample course text
    sample_course = """
    Introduction to Data Analytics: 
    This course covers fundamental concepts of data analytics including data collection, 
    cleaning, processing, and visualization. Students will learn basic statistical methods 
    and how to use tools like Python and SQL for data analysis.
    """
    
    # Test matching to skills
    logger.info("Testing matching to skills")
    skill_matches = match_course_to_skills(sample_course, top_n=3)
    logger.info(f"Found {len(skill_matches)} skill matches")
    for i, match in enumerate(skill_matches):
        logger.info(f"Match {i+1}: {match['skill']} (Score: {match['similarity']:.4f})")
    
    # Test matching to underpinning knowledge
    logger.info("Testing matching to underpinning knowledge")
    knowledge_matches = match_course_to_underpinning_knowledge(sample_course, top_n=3)
    logger.info(f"Found {len(knowledge_matches)} knowledge matches")
    for i, match in enumerate(knowledge_matches):
        logger.info(f"Match {i+1}: Knowledge from skill '{match['metadata'].get('skill_title', 'Unknown')}' (Score: {match['similarity']:.4f})")

if __name__ == "__main__":
    logger.info("Starting test script")
    embeddings = test_load_embeddings()
    
    if embeddings:
        test_matching()
    else:
        logger.error("No embeddings loaded, skipping matching tests")
    
    logger.info("Testing complete") 