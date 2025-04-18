import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import time
import random
from fake_useragent import UserAgent

# Initialize a user agent generator
ua = UserAgent()

def get_headers():
    """Generate random headers for each request"""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.classcentral.com/",
        "DNT": "1",
    }

def random_delay(min_sec=1, max_sec=3):
    """Wait for a random interval between requests"""
    time.sleep(random.uniform(min_sec, max_sec))

def search_class_central(query):
    """Search Class Central directly using their API endpoint"""
    base_url = "https://www.classcentral.com"
    search_url = f"{base_url}/search?q={quote_plus(query)}"
    
    try:
        random_delay()
        response = requests.get(search_url, headers=get_headers())
        response.raise_for_status()
        
        # Check if we got blocked
        if "Sorry, you have been blocked" in response.text:
            return {"error": "Blocked by Class Central. Please try again later."}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        course_cards = soup.find_all('a', {'class': 'color-charcoal course-name'})
        
        course_links = []
        for card in course_cards[:10]:
            href = card.get('href')
            if href and '/course/' in href:
                full_url = f"{base_url}{href}" if not href.startswith('http') else href
                course_links.append(full_url)
        
        return list(set(course_links))  # Remove duplicates
    
    except requests.exceptions.RequestException as e:
        return {"error": f"Error searching Class Central: {str(e)}"}

def scrape_class_central(course_url, retries=3):
    """Scrape course details from a Class Central course page with retries"""
    for attempt in range(retries):
        try:
            random_delay()
            response = requests.get(course_url, headers=get_headers())
            response.raise_for_status()
            
            # Check if we got blocked
            if "Sorry, you have been blocked" in response.text:
                if attempt < retries - 1:
                    time.sleep((attempt + 1) * 5)  # Increasing delay
                    continue
                else:
                    return {"error": "Failed after multiple attempts. You may be blocked."}
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract course title
            title_tag = soup.find('h1', {'class': 'head-2 medium-up-head-1 small-down-margin-bottom-xsmall'})
            title = title_tag.text.strip() if title_tag else "Unknown Title"
            
            # Extract provider (university/platform)
            provider_tag = soup.find('a', {'class': 'text-1 link-gray-underline'})
            provider = provider_tag.text.strip() if provider_tag else "Unknown Provider"
            
            rating_span = soup.find('span', class_='cmpt-rating-xlarge')
            full_stars = rating_span.find_all('i', class_='icon-star') if rating_span else []
            half_stars = rating_span.find_all('i', class_='icon-star-half') if rating_span else []

            rating = len(full_stars) + 0.5 * len(half_stars)

            description_tag = soup.select_one('div.wysiwyg.text-1.line-wide, div.truncatable-area.wysiwyg.text-1.line-wide')
            description = description_tag.text.strip() if description_tag else "No description"
            
            return {
                "title": title,
                "provider": provider,
                "rating": rating,
                "description": description,
                "url": course_url
            }
        
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 2)  # Exponential backoff
                continue
            else:
                return {"error": f"Failed to scrape course after {retries} attempts: {str(e)}"}

def get_courses(query):
    """Main function to search and display courses"""
    course_links = search_class_central(query)
    
    if isinstance(course_links, dict) and "error" in course_links:
        return course_links
    
    if course_links:
        courses = []
        for course_url in course_links:
            course_info = scrape_class_central(course_url)
            if isinstance(course_info, dict) and "error" not in course_info:
                courses.append(course_info)
            time.sleep(random.uniform(2, 4))
        
        return {"courses": courses}
    else:
        return {"error": "No courses found. Try a different search term."}