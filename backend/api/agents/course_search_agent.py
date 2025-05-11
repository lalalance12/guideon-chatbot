import logging
import time
import random
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from .base_agent import BaseAgent
from ..utils.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

# Initialize a user agent generator
ua = UserAgent()


def get_headers() -> Dict[str, str]:
    """Generate random headers for each request to mimic different browsers."""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.classcentral.com/",
        "DNT": "1",
    }


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

            # parse stars
            full = rating_span.find_all('i', class_='icon-star') if rating_span else []
            half = rating_span.find_all('i', class_='icon-star-half') if rating_span else []

            description_tag = soup.select_one(
                'div.wysiwyg.text-1.line-wide, div.truncatable-area.wysiwyg.text-1.line-wide'
            )

            return {
                'title': title_tag.text.strip() if title_tag else 'Unknown Title',
                'provider': provider_tag.text.strip() if provider_tag else 'Unknown Provider',
                'rating': len(full) + 0.5 * len(half),
                'description': description_tag.text.strip() if description_tag else 'No description',
                'url': course_url
            }

        except requests.RequestException as e:
            logger.error(f"Error scraping {course_url} (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None


class CourseSearchAgent(BaseAgent):
    """Agent responsible for finding relevant courses based on user query."""

    async def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get('intent')
        if intent not in [QueryIntent.EDUCATION_ADVICE, QueryIntent.SKILL_PROGRESSION]:
            return {
                'found': False,
                'reason': 'not_education_intent',
                'message': 'No course search performed for this query type.'
            }

        try:
            # Perform live search
            urls = search_class_central(query)
            if not urls:
                return {
                    'found': False,
                    'reason': 'no_courses',
                    'message': 'No relevant courses found for this query.'
                }

            courses = []
            for url in urls:
                info = scrape_class_central(url)
                if info:
                    courses.append(info)

            return {
                'found': bool(courses),
                'count': len(courses),
                'courses': courses
            }

        except Exception as e:
            logger.error(f"Error in course search agent: {e}")
            return {
                'found': False,
                'reason': 'exception',
                'message': f'Error finding courses: {e}'
            }
