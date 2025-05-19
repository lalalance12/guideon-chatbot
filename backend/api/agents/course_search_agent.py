import logging
import time
import random
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import os
import json
import numpy as np
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from .topic_extractor import TopicExtractor

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Initialize a user agent generator
ua = UserAgent()

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "bge-m3"

def get_headers() -> Dict[str, str]:
    """Generate random headers for each request to mimic different browsers."""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.classcentral.com/",
        "DNT": "1",
    }

# Path to your precomputed skill embeddings (update if needed)
SKILL_EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), '../data/courses/role_skill_knowledge_embeddings.json')

# Load skill embeddings once at module load
def load_skill_embeddings():
    logger.info(f"Loading skill embeddings from {SKILL_EMBEDDINGS_PATH}")
    with open(SKILL_EMBEDDINGS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logger.debug(f"Loaded {len(data)} skill embeddings.")
    return data

SKILL_EMBEDDINGS = load_skill_embeddings()

# Update the get_topic_from_query function

async def get_topic_from_query(query: str) -> str:
    """Extract the topic from the query using the TopicExtractor."""
    topic_extractor = TopicExtractor()
    topic = await topic_extractor.extract_topic(query)
    return topic


def match_query_to_skills_and_get_underpinning_knowledge(query: str):
    """Find the skill that has a skill_title that exactly matches the query and return its underpinning knowledge"""
    for item in SKILL_EMBEDDINGS:
        metadata = item.get("metadata", {})
        if metadata.get("skill_title", "") == query:
            # Extract underpinning knowledge if available
            knowledge = metadata.get("knowledge", [])
            return {
                "skill_title": metadata.get("skill_title", ""),
                "job_title": metadata.get("job_title", ""),
                "underpinning_knowledge": knowledge,
                "knowledge_count": metadata.get("knowledge_count", 0)
            }
    return None  # Return None if no matching skill is found

def get_embedding_for_text(text):
    logger.info(f"Generating embedding for text: {text[:60]}...")
    payload = {"model": EMBEDDING_MODEL, "prompt": text}
    try:
        response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=60)
        response.raise_for_status()
        embedding_data = response.json()
        embedding = embedding_data.get("embedding", [])
        logger.debug(f"Generated embedding of length {len(embedding)} for text.")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return []

def cosine_similarity(vec1, vec2):
    #logger.debug(f"Calculating cosine similarity.")
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    if v1.shape != v2.shape or v1.size == 0:
        logger.warning("Vectors have mismatched shapes or are empty.")
        return 0.0
    sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    #logger.debug(f"Cosine similarity: {sim}")
    return sim

def random_delay(min_sec: float = 1, max_sec: float = 3) -> None:
    """Pause execution for a random interval to avoid rate limits."""
    time.sleep(random.uniform(min_sec, max_sec))

def search_class_central(query: str) -> List[str]:
    """Search Class Central and return a list of course URLs."""
    base_url = "https://www.classcentral.com"
    search_url = f"{base_url}/search?q={quote_plus(query)}"
    try:
        random_delay()
        resp = requests.get(search_url, headers=get_headers(), timeout=10)
        resp.raise_for_status()

        if "Sorry, you have been blocked" in resp.text:
            logger.warning("Blocked by Class Central during search")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.find_all('a', {'class': 'color-charcoal course-name'})
        urls = []
        for card in cards[:10]:
            href = card.get('href')
            if href and '/course/' in href:
                full = href if href.startswith('http') else base_url + href
                urls.append(full)
        return list(dict.fromkeys(urls))  # dedupe

    except requests.RequestException as e:
        logger.error(f"Error searching Class Central: {e}")
        return []

def scrape_class_central(course_url: str, retries: int = 3) -> Optional[Dict[str, Any]]:
    """Scrape individual course details from a Class Central page."""
    for attempt in range(retries):
        try:
            random_delay(2, 4)
            resp = requests.get(course_url, headers=get_headers(), timeout=10)
            resp.raise_for_status()

            if "Sorry, you have been blocked" in resp.text:
                logger.warning(f"Blocked by Class Central scraping {course_url}")
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            title_tag = soup.find('h1', {
                'class': 'head-2 medium-up-head-1 small-down-margin-bottom-xsmall'
            })
            provider_tag = soup.find('a', {'class': 'text-1 link-gray-underline'})
            rating_span = soup.find('span', class_='cmpt-rating-xlarge')

            price_icon = soup.select_one('i.icon-dollar-charcoal.icon-medium.small-down-hidden') or \
            soup.select_one('i.icon-dollar-solid.icon-medium.small-down-hidden')

            if price_icon:
                if 'icon-dollar-charcoal' in price_icon['class']:
                    price = "Free"  # Free
                elif 'icon-dollar-solid' in price_icon['class']:
                    price = "Paid"  # Paid
            else:
                price = -1

            # Alternative approach - Just check if the string representation contains certain patterns
            if rating_span:
                all_icons = rating_span.find_all('i')
                logger.debug(f"Found {len(all_icons)} icons in rating span")
                
                full = []
                half = []
                
                for icon in all_icons:
                    icon_str = str(icon)
                    if 'icon-star' in icon_str and 'half' not in icon_str:
                        full.append(icon)
                    elif 'star-half' in icon_str or 'icon-star-half' in icon_str:
                        half.append(icon)
                
                logger.debug(f"Counted {len(full)} full stars and {len(half)} half stars")
            else:
                full = []
                half = []

            description_tag = soup.select_one(
                'div.wysiwyg.text-1.line-wide, div.truncatable-area.wysiwyg.text-1.line-wide'
            )

            return {
                'title': title_tag.text.strip() if title_tag else 'Unknown Title',
                'provider': provider_tag.text.strip() if provider_tag else 'Unknown Provider',
                'rating': len(full) + 0.5 * len(half),
                'price': price,
                'description': description_tag.text.strip() if description_tag else 'No description',
                'url': course_url
            }

        except requests.RequestException as e:
            logger.error(f"Error scraping {course_url} (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None

def match_course_description_to_underpinning_knowledge(description: str, underpinning_knowledge: list):
    """Match the course description to the underpinning knowledge using cosine similarity"""
    if not underpinning_knowledge:
        return 0
    
    # Get the embedding for the description
    description_embedding = get_embedding_for_text(description)
    if not description_embedding:
        logger.warning("Failed to generate embedding for course description")
        return 0
    
    # Calculate average similarity to all knowledge items
    similarities = []
    for knowledge_item in underpinning_knowledge:
        # Find the matching knowledge item in SKILL_EMBEDDINGS
        for item in SKILL_EMBEDDINGS:
            if (item.get("metadata", {}).get("type") == "underpinning_knowledge" and 
                knowledge_item in item.get("metadata", {}).get("knowledge", [])):
                knowledge_embedding = item.get("embedding", [])
                if knowledge_embedding:
                    sim = cosine_similarity(description_embedding, knowledge_embedding)
                    similarities.append(sim)
                break
    
    # Return average similarity if we have any valid comparisons
    if similarities:
        avg_similarity = sum(similarities) / len(similarities)
        logger.debug(f"Average similarity score: {avg_similarity:.4f}")
        return avg_similarity
    return 0

class CourseSearchAgent(BaseAgent):
    """Agent responsible for finding relevant courses based on user query."""

    # Minimum similarity threshold for considering a course relevant
    SIMILARITY_THRESHOLD = 0.58

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
    #        Check if we're receiving an extracted topic from the orchestrator
            extracted_topic = context.get("extracted_topic")
            
            if extracted_topic and extracted_topic != query:
                logger.info(f"Using extracted topic from orchestrator: '{extracted_topic}' (original query: '{query}')")
                topic = extracted_topic
            else:
                # Fall back to extracting the topic ourselves
                logger.info(f"No extracted topic in context, extracting from query: '{query}'")
                topic_extractor = TopicExtractor()
                topic = await topic_extractor.extract_topic(query)
                logger.info(f"Extracted topic: '{topic}'")
            
            # Log the processing of the query with the extracted topic
            logger.info(f"Processing query: '{query}' with topic: '{topic}'")
            
            # First, find the matching skill and its underpinning knowledge
            # Use the topic for matching instead of the raw query
            skill_match = match_query_to_skills_and_get_underpinning_knowledge(topic)
            has_skill_match = skill_match is not None
            
            if has_skill_match:
                logger.info(f"Found matching skill: {skill_match.get('skill_title')}")
                logger.debug(f"Underpinning knowledge items: {len(skill_match.get('underpinning_knowledge', []))}")
            else:
                logger.info(f"No matching skill found for topic '{topic}', will use direct title comparison")
            
            # If skill match is found, use underpinning knowledge for comparison
            # Otherwise, we'll directly compare with the query
            underpinning_knowledge = []
            if has_skill_match:
                underpinning_knowledge = skill_match.get('underpinning_knowledge', [])
            
            # Now search for relevant courses
            logger.info(f"Searching Class Central for courses about '{topic}'...")
            urls = search_class_central(topic)
            if not urls:
                logger.warning("No course URLs found from Class Central")
                return {
                    'found': False,
                    'reason': 'no_courses',
                    'message': 'No relevant courses found for this query.'
                }
            
            logger.info(f"Found {len(urls)} course URLs to process")

            all_courses = []

            # Scrape course info and calculate similarity
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing course {i}/{len(urls)}: {url}")
                info = scrape_class_central(url)
                if info:
                    logger.debug(f"Scraped course: {info.get('title')}")
                    
                    # If we have a skill match, compare course description with underpinning knowledge
                    if has_skill_match and underpinning_knowledge:
                        logger.debug("Calculating similarity with underpinning knowledge")
                        similarity = match_course_description_to_underpinning_knowledge(
                            info['description'], underpinning_knowledge
                        )
                        info['matched_skill'] = skill_match
                    else:
                        # Fallback: If no skill match, compare query with course title
                        logger.debug("Calculating direct similarity with course title")
                        query_embedding = get_embedding_for_text(query)
                        title_embedding = get_embedding_for_text(info['title'])
                        
                        if query_embedding and title_embedding:
                            similarity = cosine_similarity(query_embedding, title_embedding)
                            logger.debug(f"Title similarity score: {similarity:.4f}")
                        else:
                            logger.warning("Failed to generate embeddings for similarity comparison")
                            similarity = 0
                    
                    # Add similarity score to the course
                    info['similarity_score'] = similarity
                    if similarity >= self.SIMILARITY_THRESHOLD:
                        all_courses.append(info)
                        logger.debug(f"Course meets similarity threshold ({similarity:.4f} >= {self.SIMILARITY_THRESHOLD})")
                    else:
                        logger.debug(f"Course below similarity threshold ({similarity:.4f} < {self.SIMILARITY_THRESHOLD})")
                else:
                    logger.warning(f"Failed to scrape course from URL: {url}")
            
            logger.info(f"Successfully processed {len(all_courses)} courses above threshold")
            
            # Sort courses by similarity score (highest first)
            sorted_courses = sorted(all_courses, key=lambda x: x.get('similarity_score', 0), reverse=True)
            
            # Return top 3 courses (or fewer if less than 3 are found)
            top_courses = sorted_courses[:3]
            
            if top_courses:
                logger.info(f"Returning top {len(top_courses)} courses")
                for i, course in enumerate(top_courses, 1):
                    logger.debug(f"Top {i} course: {course.get('title')} (score: {course.get('similarity_score'):.4f})")
                
                result = {
                    'found': True,
                    'count': len(top_courses),
                    'courses': top_courses,
                }
                
                if has_skill_match:
                    result['matched_skill'] = skill_match
                else:
                    result['direct_query_match'] = True
                    result['message'] = 'No skill match found. Courses ranked by title similarity to query.'
                
                return result

            logger.warning("No courses met the relevance threshold")
            return {
                'found': False,
                'reason': 'no_matching_courses',
                'message': 'Found courses but none were relevant to the query.'
            }

        except Exception as e:
            logger.error(f"Error in course search agent: {e}", exc_info=True)
            return {
                'found': False,
                'reason': 'exception',
                'message': f'Error finding courses: {e}'
            }
