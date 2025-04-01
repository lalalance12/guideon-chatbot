from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import time
import random
from fake_useragent import UserAgent
from agno.agent.agent import Agent
from agno.models.ollama import Ollama
from typing import List, Dict, Optional

# Initialize User Agent
ua = UserAgent()
ollama_llm = Ollama(id="deepseek-r1:8b")

class CourseSearchAPI(APIView):
    def get_headers(self):
        return {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.classcentral.com/",
            "DNT": "1",
        }
    
    def random_delay(self, min_sec=1, max_sec=3):
        time.sleep(random.uniform(min_sec, max_sec))
    
    def parse_natural_language(self, user_query: str) -> Dict[str, str]:
        prompt = {"content": f"""
        Extract main subject and filters from this query: "{user_query}"
        Return JSON: {"query": "main term", "filters": {"language": "python"}}
        """}
        
        try:
            response = ollama_llm.invoke([prompt])
            return response.json()
        except Exception as e:
            return {"query": user_query, "filters": None}
    
    def search_class_central(self, search_query: Dict[str, str]) -> List[str]:
        base_url = "https://www.classcentral.com"
        query = quote_plus(search_query["query"])
        search_url = f"{base_url}/search?q={query}"
        
        try:
            self.random_delay()
            response = requests.get(search_url, headers=self.get_headers())
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            course_cards = soup.find_all('a', {'class': 'color-charcoal course-name'})
            
            return [base_url + card['href'] for card in course_cards[:10] if '/course/' in card['href']]
        except requests.exceptions.RequestException:
            return []
    
    def scrape_course_details(self, course_url: str) -> Optional[Dict[str, str]]:
        try:
            self.random_delay()
            response = requests.get(course_url, headers=self.get_headers())
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.find('h1', {'class': 'head-2'}).text.strip()
            provider = soup.find('a', {'class': 'text-1'}).text.strip()
            rating = soup.find('span', {'class': 'text-3'}).text.strip()
            
            return {"title": title, "provider": provider, "rating": rating, "url": course_url}
        except requests.exceptions.RequestException:
            return None
    
    def post(self, request):
        user_query = request.data.get("query", "")
        if not user_query:
            return Response({"error": "No query provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        search_query = self.parse_natural_language(user_query)
        course_links = self.search_class_central(search_query)
        
        if not course_links:
            return Response({"message": "No courses found."}, status=status.HTTP_404_NOT_FOUND)
        
        courses = [self.scrape_course_details(url) for url in course_links if url]
        return Response({"courses": [course for course in courses if course]}, status=status.HTTP_200_OK)
