import logging
import time
import random
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import os
import requests
import json
import asyncio  # **ADD THIS IMPORT**
import re
import os
import json
import numpy as np
import requests
from .topic_extractor import TopicExtractor
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class CourseSearchAgent(BaseAgent):
    """Agent responsible for finding relevant courses based on user query."""

    # Configuration constants
    OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
    EMBEDDING_MODEL = "bge-m3"
    SKILL_EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), '../data/courses/role_skill_knowledge_embeddings.json')
    SIMILARITY_THRESHOLD = 0.58  # Default threshold for course relevance

    def __init__(self, llm=None):
        """Initialize the course search agent with an optional LLM."""
        super().__init__(llm=llm)
        self.ua = UserAgent()
        self.SKILL_EMBEDDINGS = self.load_skill_embeddings()

    def get_headers(self) -> Dict[str, str]:
        """Generate random headers for each request to mimic different browsers."""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.classcentral.com/",
            "DNT": "1",
        }

    # Load skill embeddings once at module load
    def load_skill_embeddings(self):
        logger.info(f"Loading skill embeddings from {self.SKILL_EMBEDDINGS_PATH}")
        with open(self.SKILL_EMBEDDINGS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"Loaded {len(data)} skill embeddings.")
        return data
    
    async def get_topic_from_query(self, query: str) -> str:
        """Extract the topic from the query using the TopicExtractor."""
        topic_extractor = TopicExtractor()
        topic = await topic_extractor.extract_topic(query)
        return topic

    def match_query_to_skills_and_get_underpinning_knowledge(self, query):
        """Find the skill that has a skill_title that matches the query(case-insensitive) and return its underpinning knowledge"""
        # Add validation to prevent the error
        if query is None:
            logger.warning("Received None as query in match_query_to_skills_and_get_underpinning_knowledge")
            return None
            
        if not isinstance(query, str):
            logger.warning(f"Expected string for query but got {type(query)} in match_query_to_skills_and_get_underpinning_knowledge")
            try:
                # Try to convert to string if possible
                query = str(query)
            except:
                return None
        
        # Now safe to proceed
        query_lower = query.lower() # Convert query to lowercase
        for item in self.SKILL_EMBEDDINGS:
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

    def get_embedding_for_text(self, text):
        logger.info(f"Generating embedding for text: {text[:60]}...")
        payload = {"model": self.EMBEDDING_MODEL, "prompt": text}
        try:
            response = requests.post(self.OLLAMA_EMBED_URL, json=payload, timeout=60)
            response.raise_for_status()
            embedding_data = response.json()
            embedding = embedding_data.get("embedding", [])
            logger.debug(f"Generated embedding of length {len(embedding)} for text.")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

    def cosine_similarity(self, vec1, vec2):
        #logger.debug(f"Calculating cosine similarity.")
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        if v1.shape != v2.shape or v1.size == 0:
            logger.warning("Vectors have mismatched shapes or are empty.")
            return 0.0
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        #logger.debug(f"Cosine similarity: {sim}")
        return sim

    def random_delay(self, min_sec: float = 1, max_sec: float = 3) -> None:
        """Pause execution for a random interval to avoid rate limits."""
        time.sleep(random.uniform(min_sec, max_sec))

    def search_class_central(self, query: str) -> List[str]:
        """Search Class Central and return a list of course URLs."""
        # Add validation
        if not isinstance(query, str):
            logger.warning(f"Expected string for query but got {type(query)}")
            query = str(query) if query is not None else ""
            
        base_url = "https://www.classcentral.com"
        search_url = f"{base_url}/search?q={quote_plus(query)}"
        try:
            self.random_delay()
            resp = requests.get(search_url, headers=self.get_headers(), timeout=10)
            resp.raise_for_status()

            if "Sorry, you have been blocked" in resp.text:
                logger.warning("Blocked by Class Central during search")
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.find_all('a', {'class': 'color-charcoal course-name'})
            urls = []
            for card in cards[:15]:
                href = card.get('href')
                if href and '/course/' in href:
                    full = href if href.startswith('http') else base_url + href
                    urls.append(full)
            return list(dict.fromkeys(urls))  # dedupe

        except requests.RequestException as e:
            logger.error(f"Error searching Class Central: {e}")
            return []

    def scrape_class_central(self, course_url: str, retries: int = 3) -> Optional[Dict[str, Any]]:
        """Scrape individual course details from a Class Central page."""
        for attempt in range(retries):
            try:
                self.random_delay(2, 4)
                resp = requests.get(course_url, headers=self.get_headers(), timeout=10)
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

    def match_course_description_to_underpinning_knowledge(self, description: str, underpinning_knowledge: list):
        """Match the course description to the underpinning knowledge using cosine similarity"""
        if not underpinning_knowledge:
            return 0
        
        # Get the embedding for the description
        description_embedding = self.get_embedding_for_text(description)
        if not description_embedding:
            logger.warning("Failed to generate embedding for course description")
            return 0
        
        # Calculate average similarity to all knowledge items
        similarities = []
        for knowledge_item in underpinning_knowledge:
            # Find the matching knowledge item in SKILL_EMBEDDINGS
            for item in self.SKILL_EMBEDDINGS:
                if (item.get("metadata", {}).get("type") == "underpinning_knowledge" and 
                    knowledge_item in item.get("metadata", {}).get("knowledge", [])):
                    knowledge_embedding = item.get("embedding", [])
                    if knowledge_embedding:
                        sim = self.cosine_similarity(description_embedding, knowledge_embedding)
                        similarities.append(sim)
                    break
        
        # Return average similarity if we have any valid comparisons
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            logger.debug(f"Average similarity score: {avg_similarity:.4f}")
            return avg_similarity
        return 0

    def get_skill_match_and_adjusted_threshold(self, topic: str):
        """Determine the skill match and adjust the threshold based on the topic."""
        # First, find the matching skill and its underpinning knowledge
        # Use the topic for matching instead of the raw query
        skill_match = self.match_query_to_skills_and_get_underpinning_knowledge(topic)
        has_skill_match = skill_match is not None
        
        # Initialize the threshold with the default value
        current_similarity_threshold = self.SIMILARITY_THRESHOLD
        
        if has_skill_match:
            logger.info(f"Found matching skill: {skill_match.get('skill_title')}")
            logger.debug(f"Underpinning knowledge items: {len(skill_match.get('underpinning_knowledge', []))}")
            current_similarity_threshold = 0.1 # Change threshold if skill match is found
            logger.info(f"Skill match found. Similarity threshold set to: {current_similarity_threshold}")
        else:
            logger.info(f"No matching skill found for topic '{topic}', will use direct title comparison. Threshold remains: {current_similarity_threshold}")

        return skill_match, current_similarity_threshold

    def _extract_flow_enhanced_topic(self, query: str, context: Dict[str, Any]) -> str:
        """**NEW: Extract topic with flow context awareness**"""
        
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        focus_role, focus_topic = self.get_focus_elements(context)
        
        # Check for flow-provided topic first
        if focus_topic:
            logger.info(f"[CourseSearchAgent] Using focus topic from flow: {focus_topic}")
            return focus_topic
            
        # Check for flow context topic
        flow_preserved_context = self.get_flow_preserved_context(context)
        if flow_preserved_context.get("search_topic"):
            return flow_preserved_context["search_topic"]
        
        # Check for extracted topic from context (orchestrator)
        extracted_topic_from_context = context.get("extracted_topic")
        if extracted_topic_from_context and extracted_topic_from_context != query:
            logger.info(f"[CourseSearchAgent] Using extracted topic from orchestrator: {extracted_topic_from_context}")
            return extracted_topic_from_context
        
        # **FIXED: Use the existing async method and handle it properly**
        logger.info(f"[CourseSearchAgent] Extracting topic from query: {query}")
        # Return a coroutine that will be awaited in the process method
        return asyncio.create_task(self.get_topic_from_query(query))
    
    async def _create_flow_enhanced_response(self, courses: List[Dict], context: Dict[str, Any], topic: str) -> Dict[str, Any]:
        """**NEW: Create enhanced response with flow context**"""
        
        flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
        focus_role, focus_topic = self.get_focus_elements(context)
        
        # Base response
        result = {
            'found': True,
            'count': len(courses),
            'courses': courses,
            'topic_searched': topic
        }
        
        # Add flow-enhanced messaging
        if focus_role:
            result['message'] = f"Found courses for '{topic}' that align with your interest in the {focus_role} role."
            result['career_context'] = focus_role
        elif flow_action == "course_search_with_context":
            result['message'] = f"Found courses for '{topic}' with PSF-AAI career pathway context."
            result['pathway_context'] = True
        else:
            result['message'] = f"Found relevant courses for '{topic}'."
        
        # Add connectivity suggestions if in enhanced flow
        if flow_context.get("include_skill_connections"):
            result['skill_connections_available'] = True
            result['suggestions'] = [
                f"Want to see how '{topic}' connects to PSF-AAI career roles?",
                "Explore skill requirements for specific positions",
                "Discover career progression paths using this skill"
            ]
        
        # Add flow metadata
        result = self.add_flow_metadata(result, context)
        
        return result

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Debug: Log the entire context to see what's being passed
            logger.info(f"CourseSearchAgent received context with keys: {list(context.keys())}")
            
            # Get user ID from context if available
            user_id = context.get("user_id")
            logger.info(f"CourseSearchAgent extracted user_id: {user_id}")
            
            # Initialize user preferences
            user_preferences = {
                "course_level": None,
                "programming_languages": [],
                "development_areas": []
            }
              # Retrieve user preferences if user_id is available
            if user_id:
                try:
                    # Use Django ORM with async support
                    from api.models import UserPreference
                    from django.db import transaction
                    from asgiref.sync import sync_to_async
                    
                    # Convert user_id to int if needed
                    if isinstance(user_id, str) and user_id.isdigit():
                        user_id = int(user_id)
                        logger.info(f"Converted user_id from string to int: {user_id}")
                    
                    # Create a sync function that can be called with sync_to_async
                    @sync_to_async
                    def get_user_preferences(user_id):
                        with transaction.atomic():
                            return UserPreference.objects.filter(user_id=user_id).first()
                    
                    # Get user preferences asynchronously
                    user_preference = await get_user_preferences(user_id)
                    
                    if user_preference:
                        user_preferences = {
                            "course_level": user_preference.course_level,
                            "programming_languages": user_preference.programming_languages,
                            "development_areas": user_preference.development_areas
                        }
                        logger.info(f"Retrieved user preferences for user {user_id}:")
                        logger.info(f"  - Course level: {user_preference.course_level}")
                        logger.info(f"  - Programming languages: {user_preference.programming_languages}")
                        logger.info(f"  - Development areas: {user_preference.development_areas}")
                    else:
                        logger.info(f"No preferences found for user {user_id}, using default values")
                        
                except Exception as e:
                    logger.error(f"Error retrieving user preferences: {e}", exc_info=True)
            else:
                logger.info("No user_id in context, proceeding without user preferences")

            logger.info(f"[CourseSearchAgent] Processing with flow context: {query[:60]}")
            
            # **NEW: Extract flow context**
            flow_context, flow_action, response_format, flow_state = self.get_flow_context(context)
            
            # **ENHANCED: Extract topic with flow awareness - FIXED ASYNC HANDLING**
            topic_result = self._extract_flow_enhanced_topic(query, context)
            
            # Handle the async topic extraction properly
            if asyncio.iscoroutine(topic_result) or isinstance(topic_result, asyncio.Task):
                topic = await topic_result
            else:
                topic = topic_result
            
            # Add safety check to ensure topic is a string
            if topic is not None and not isinstance(topic, str):
                logger.warning(f"Topic is not a string, converting from {type(topic)} to string")
                topic = str(topic)

            if not topic:
                return self._create_clarification_response(context)
            
            # **ENHANCED: Determine search strategy based on flow**
            skill_match, threshold = self.get_skill_match_and_adjusted_threshold(topic)
            
            # Apply flow-specific search enhancements
            if flow_action == "course_search_with_context":
                threshold = max(0.1, threshold - 0.05)  # More lenient for flow-driven searches
                
            logger.info(f"Effective topic for course search: '{topic}' (from query: '{query}')")

            # Check if the topic is empty (signaling a generic/unclear request)
            if not topic:
                logger.info(f"No specific topic extracted for query '{query}'. Clarification needed.")
                return self._create_clarification_response(context)
            
            # Log the processing of the query with the extracted topic
            logger.info(f"Processing query: '{query}' with specific topic: '{topic}'")
            
            # Determine skill match and adjusted threshold based on the topic
            skill_match, current_similarity_threshold = self.get_skill_match_and_adjusted_threshold(topic)
            has_skill_match = skill_match is not None
            
            # If skill match is found, use underpinning knowledge for comparison
            # Otherwise, we'll directly compare with the query
            underpinning_knowledge = []
            if has_skill_match:
                underpinning_knowledge = skill_match.get('underpinning_knowledge', [])
            
            # Now search for relevant courses
            logger.info(f"Searching Class Central for courses about '{topic}'...")
            urls = self.search_class_central(topic)
            if not urls:
                logger.warning("No course URLs found from Class Central")
                return {
                    'found': False,
                    'reason': 'no_courses',
                    'message': f"I couldn't find any courses related to '{topic}' on Class Central."
                }
            
            logger.info(f"Found {len(urls)} course URLs to process")

            all_courses = []

            # Scrape course info and calculate similarity
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing course {i}/{len(urls)}: {url}")
                info = self.scrape_class_central(url)
                if info:
                    logger.debug(f"Scraped course: {info.get('title')}")
                    similarity = 0.0 # Initialize similarity
                    
                    # If we have a skill match, compare course description with underpinning knowledge
                    if has_skill_match and underpinning_knowledge:
                        logger.debug("Calculating similarity with underpinning knowledge")
                        similarity = self.match_course_description_to_underpinning_knowledge(
                            info['description'], underpinning_knowledge
                        )
                        info['matched_skill'] = skill_match # Keep skill_match info
                    else:
                        # Fallback: If no skill match, compare query (or topic) with course title
                        logger.debug(f"Calculating direct similarity between topic '{topic}' and course title '{info['title']}'")
                        # Use topic for embedding comparison if no skill match
                        topic_embedding = self.get_embedding_for_text(topic) 
                        title_embedding = self.get_embedding_for_text(info['title'])
                        
                        if topic_embedding and title_embedding:
                            similarity = self.cosine_similarity(topic_embedding, title_embedding)
                            logger.debug(f"Title similarity score: {similarity:.4f}")
                        else:
                            logger.warning("Failed to generate embeddings for title similarity comparison")
                            similarity = 0.0 # Ensure similarity is float
                    
                    # Add similarity score to the course
                    info['similarity_score'] = similarity
                    if similarity >= current_similarity_threshold: # Use the dynamic threshold
                        all_courses.append(info)
                        logger.debug(f"Course '{info.get('title')}' meets similarity threshold ({similarity:.4f} >= {current_similarity_threshold})")
                    else:
                        logger.debug(f"Course '{info.get('title')}' below similarity threshold ({similarity:.4f} < {current_similarity_threshold})")
                else:
                    logger.warning(f"Failed to scrape course from URL: {url}")
            
            logger.info(f"Successfully processed {len(all_courses)} courses above threshold")
              # After scraping all courses but before returning results, filter based on user preferences
            if all_courses:
                logger.info(f"Starting preference filtering with {len(all_courses)} courses")
                logger.info(f"User preferences: {user_preferences}")
                
                # Instead of filtering out courses, let's score them based on preference matches
                # This way we prioritize courses that match preferences but still show others if needed
                for course in all_courses:
                    preference_score = 0
                    matches = []
                    logger.debug(f"Evaluating course: {course.get('title', 'Unknown')}")
                    
                    # Filter by course level if specified
                    if user_preferences["course_level"] and user_preferences["course_level"] != "all":
                        if "level" in course and course["level"] == user_preferences["course_level"]:
                            preference_score += 3  # Highest priority
                            matches.append(f"level: {course.get('level')}")
                            logger.debug(f"Course '{course.get('title')}' matches preferred level: {user_preferences['course_level']}")
                    
                    # Filter by programming languages if specified
                    if user_preferences["programming_languages"]:
                        matching_langs = []
                        for lang in user_preferences["programming_languages"]:
                            if (lang.lower() in course.get('title', '').lower() or 
                                lang.lower() in course.get('description', '').lower()):
                                matching_langs.append(lang)
                        
                        if matching_langs:
                            preference_score += 2  # Medium priority
                            matches.append(f"languages: {', '.join(matching_langs)}")
                            logger.debug(f"Course '{course.get('title')}' matches preferred languages: {', '.join(matching_langs)}")
                    
                    # Filter by development areas if specified
                    if user_preferences["development_areas"]:
                        matching_areas = []
                        for area in user_preferences["development_areas"]:
                            if (area.lower() in course.get('title', '').lower() or 
                                area.lower() in course.get('description', '').lower()):
                                matching_areas.append(area)
                        
                        if matching_areas:
                            preference_score += 1  # Lower priority
                            matches.append(f"areas: {', '.join(matching_areas)}")
                            logger.debug(f"Course '{course.get('title')}' matches preferred development areas: {', '.join(matching_areas)}")
                    
                    # Store the preference score and match details in the course object
                    course['preference_score'] = preference_score
                    course['preference_matches'] = matches
                    
                    logger.debug(f"Course '{course.get('title')}' preference score: {preference_score}, matches: {matches}")
                
                # If we have user preferences, adjust the sorting to consider both similarity and preferences
                has_preferences = (user_preferences["course_level"] and user_preferences["course_level"] != "all") or \
                                 user_preferences["programming_languages"] or \
                                 user_preferences["development_areas"]
                
                if has_preferences and user_id:
                    # Sort by a combined score of similarity and preference matches
                    # This ensures courses matching preferences are prioritized but still relevant
                    logger.info("Applying preference-based sorting")
                    sorted_courses = sorted(
                        all_courses, 
                        key=lambda x: (x.get('preference_score', 0) * 0.5 + x.get('similarity_score', 0)), 
                        reverse=True
                    )
                    
                    # Log how preferences affected the sorting
                    logger.info(f"Courses re-ordered based on user preferences")
                    for i, course in enumerate(sorted_courses[:5], 1):
                        logger.debug(f"Course {i}: '{course.get('title')}' - similarity: {course.get('similarity_score', 0):.2f}, preference score: {course.get('preference_score', 0)}")
                else:
                    # Fall back to sorting just by similarity if no preferences are set
                    sorted_courses = sorted(all_courses, key=lambda x: x.get('similarity_score', 0.0), reverse=True)
                    logger.info("No preference filtering applied - using similarity-only sorting")
            else:
                # No courses to filter
                sorted_courses = []

            # Step 1: Get the top courses, prioritizing those matching preferences
            # First, get courses with preference matches (if any)
            preference_matched_courses = [c for c in sorted_courses if c.get('preference_score', 0) > 0]
            regular_courses = [c for c in sorted_courses if c.get('preference_score', 0) == 0]
            
            # Ensure we include at least 3 courses, with preference for those matching user preferences
            if len(preference_matched_courses) >= 3:
                # If we have enough preference-matched courses, use those first
                top_courses = preference_matched_courses[:3]
                logger.info(f"Selected top 3 courses based on preferences and similarity")
            else:
                # If not enough preference-matched courses, supplement with highest similarity courses
                top_courses = preference_matched_courses + regular_courses[:max(3 - len(preference_matched_courses), 0)]
                logger.info(f"Selected {len(preference_matched_courses)} preference-matched courses and {min(3 - len(preference_matched_courses), len(regular_courses))} additional courses")

            # Step 2: Count how many paid courses are in the top selection
            paid_in_top = [c for c in top_courses if c.get('price', '').lower() == 'paid']
            num_paid = len(paid_in_top)

            # Step 3: For each paid course, add a free course with preference for preference-matched free courses
            extra_free_courses = []
            if num_paid > 0:
                free_preference_matched = [c for c in preference_matched_courses 
                                         if c.get('price', '').lower() == 'free' and c not in top_courses]
                free_regular = [c for c in regular_courses 
                              if c.get('price', '').lower() == 'free' and c not in top_courses]
                
                # Try to select free courses that match preferences first
                if len(free_preference_matched) >= num_paid:
                    extra_free_courses = free_preference_matched[:num_paid]
                else:
                    # If not enough preference-matched free courses, supplement with regular free courses
                    extra_free_courses = free_preference_matched + free_regular[:max(num_paid - len(free_preference_matched), 0)]
                
                logger.info(f"Added {len(extra_free_courses)} free courses to complement paid courses")

            # Step 4: Combine the results
            final_courses = top_courses + extra_free_courses

            # Remove duplicates by URL unless description is different
            seen = set()
            descriptions = set()
            unique_final_courses = []
            for course in final_courses:
                url = course.get('url')
                desc = course.get('description', '').strip()
                # Allow duplicates if description is the same
                if url in seen and desc not in descriptions:
                    continue
                unique_final_courses.append(course)
                seen.add(url)
                descriptions.add(desc)

            final_courses = unique_final_courses

            # Store in context for follow-up reference
            if final_courses:
                context['last_courses'] = final_courses
            
            if final_courses:
                logger.info(f"Returning top {len(final_courses)} courses")
                for i_course, course in enumerate(final_courses, 1):
                    logger.debug(f"Top {i_course} course: {course.get('title')} (score: {course.get('similarity_score'):.4f})")
                
                # **ENHANCED: Use flow-enhanced response creation**
                return await self._create_flow_enhanced_response(final_courses, context, topic)

            logger.warning(f"No courses met the relevance threshold of {current_similarity_threshold} for topic '{topic}'")
            # Provide a more informative message if no courses meet the threshold
            reason_message = f"I found some courses related to '{topic}', but none seemed relevant enough after detailed review."

            result = {
                'found': False,
                'reason': 'no_matching_courses_above_threshold',
                'message': reason_message
            }
            
            return self.add_flow_metadata(result, context)

        except Exception as e:
            logger.error(f"Error in course search agent: {e}", exc_info=True)
            result = {
                'found': False,
                'reason': 'exception',
                'message': f'An error occurred while trying to find courses: {str(e)}'
            }
            return self.add_flow_metadata(result, context)

    def _create_clarification_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """**NEW: Create clarification response with flow context**"""
        
        flow_context, flow_action, _, _ = self.get_flow_context(context)
        focus_role, _ = self.get_focus_elements(context)
        
        message = "What specific topic would you like to learn about?"
        
        # Add context-aware suggestions
        suggestions = []
        if focus_role:
            message = f"What specific skills would you like to develop for the {focus_role} role?"
            suggestions = [
                f"Technical skills for {focus_role}",
                f"Programming languages for {focus_role}",
                f"Tools and technologies for {focus_role}"
            ]
        elif flow_action == "clarify_course_topic_with_suggestions":
            suggestions = [
                "Data Analysis", "Machine Learning", "Python Programming",
                "Data Visualization", "SQL", "Statistics", "AI/Deep Learning"
            ]
        
        result = {
            'found': False,
            'reason': 'clarification_needed',
            'message': message,
            'needs_clarification': True
        }
        
        if suggestions:
            result['clarification_options'] = suggestions
        
        return self.add_flow_metadata(result, context)

    def _create_no_results_response(self, topic: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """**NEW: Create no results response with flow context**"""
        result = {
            'found': False,
            'reason': 'no_courses',
            'message': f"I couldn't find any courses related to '{topic}' on Class Central."
        }
        return self.add_flow_metadata(result, context)

    def _create_error_response(self, error_message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """**NEW: Create error response with flow context**"""
        result = {
            'found': False,
            'reason': 'exception',
            'message': f'An error occurred while trying to find courses: {error_message}'
        }
        return self.add_flow_metadata(result, context)

    # ... rest of the existing methods remain unchanged ...
