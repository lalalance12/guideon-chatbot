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
    """Find the skill that has a skill_title that matches the query (case-insensitive) and return its underpinning knowledge"""
    query_lower = query.lower() # Convert query to lowercase
    for item in SKILL_EMBEDDINGS:
        metadata = item.get("metadata", {})
        skill_title_lower = metadata.get("skill_title", "").lower() # Convert skill_title to lowercase
        if skill_title_lower == query_lower: # Compare lowercase versions
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
                if 'icon-star-empty' not in icon_str:  # Skip empty stars
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
        """Process a query to find relevant learning resources."""
        logger.info(f"Processing course search query: {query[:60]}...")
        start_time = time.time()
        
        # Set up topic extractor if not already done
        if not hasattr(self, 'topic_extractor'):
            self.topic_extractor = TopicExtractor()
        
        # Extract topic from query using context-aware extraction
        topic_result = await self.topic_extractor.extract_topic(query, context)
        
        # Check if we got multiple topics (list) or a single topic (string)
        if isinstance(topic_result, list):
            logger.info(f"Multiple topics found in context: {topic_result}")
            # Return the multiple topics for the flow to handle clarification
            return {
                "found": False,
                "multiple_topics": topic_result,
                "needs_clarification": True,
                "processing_time": time.time() - start_time
            }
        
        # Set topic from either extraction or context
        topic = topic_result
        flow_context = context.get("flow", {})
        
        # If topic is provided in flow context, use that instead
        if flow_context.get("topic"):
            topic = flow_context.get("topic")
            logger.info(f"Using topic from flow context: {topic}")
        
        # If we still don't have a clear topic, return needs_clarification
        if not topic or len(topic.strip()) < 2:
            logger.info("No clear topic identified, requesting clarification")
            return {
                "found": False,
                "needs_clarification": True,
                "processing_time": time.time() - start_time
            }
        
        # Now search for courses using the identified topic
        logger.info(f"Searching for courses on topic: {topic}")
        
        # Try to find matching skills knowledge
        underpinning_knowledge = match_query_to_skills_and_get_underpinning_knowledge(topic)
        
        # Search on Class Central
        search_urls = search_class_central(topic)
        
        if not search_urls:
            logger.warning(f"No courses found for '{topic}'")
            return {
                "found": False,
                "topic": topic,
                "processing_time": time.time() - start_time
            }
        
        # Scrape course details
        courses = []
        for url in search_urls[:5]:  # Limit to top 5 for performance
            try:
                course_data = scrape_class_central(url)
                if course_data:
                    # Calculate relevance score if we have underpinning knowledge
                    if underpinning_knowledge:
                        relevance = match_course_description_to_underpinning_knowledge(
                            course_data["description"], underpinning_knowledge
                        )
                        course_data["relevance_score"] = relevance
                    else:
                        course_data["relevance_score"] = 0.5  # Default mid-score
                    
                    courses.append(course_data)
            except Exception as e:
                logger.error(f"Error scraping course details: {e}")
        
        # Sort by relevance score
        courses.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Filter out courses with low relevance
        relevant_courses = [c for c in courses if c.get("relevance_score", 0) >= self.SIMILARITY_THRESHOLD]
        
        if not relevant_courses:
            logger.info(f"Found {len(courses)} courses but none met relevance threshold")
            # If we found courses but none are relevant enough, return some anyway
            if courses:
                return {
                    "found": True,
                    "topic": topic,
                    "courses": courses[:3],  # Return top 3 even if below threshold
                    "processing_time": time.time() - start_time
                }
            else:
                return {
                    "found": False,
                    "topic": topic,
                    "processing_time": time.time() - start_time
                }
        
        logger.info(f"Found {len(relevant_courses)} relevant courses for '{topic}'")
        return {
            "found": True,
            "topic": topic,
            "courses": relevant_courses,
            "processing_time": time.time() - start_time
        }
