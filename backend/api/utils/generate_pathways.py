import os
import sys
import requests
import json
import numpy as np

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from .query_vectors import search_similar_content, create_fallback_content

def generate_learning_pathway(query_text):
    """
    Generate a personalized learning pathway based on user query
    using vector search and Llama 3.1
    """
    # Step 1: Search for relevant content using vector similarity
    print(f"Searching for content related to: {query_text}")
    try:
        similar_content = search_similar_content(query_text, limit=5)
        
        # If we got an error dictionary instead of a list, use fallback
        if isinstance(similar_content, dict) and "error" in similar_content:
            print(f"Search returned error: {similar_content['error']}, using fallback content")
            similar_content = create_fallback_content(query_text)
    except Exception as e:
        print(f"Exception during search: {e}, using fallback content")
        similar_content = create_fallback_content(query_text)
    
    # Step 2: Format the content as context for the LLM
    context = "Information about Philippines Skills Framework for Analytics and AI:\n\n"
    
    for item in similar_content:
        metadata = item.get("metadata", {})
        if metadata.get("type") == "pathway":
            context += f"PATHWAY: {metadata.get('title', 'Unnamed Pathway')}\n{item['text']}\n\n"
        elif metadata.get("type") == "subsection":
            context += f"SUBSECTION: {metadata.get('title', 'Unnamed Section')} (Part of {metadata.get('parent', 'Unknown')})\n{item['text']}\n\n"
        else:
            context += f"CONTENT: {metadata.get('title', 'Relevant Information')}\n{item['text']}\n\n"
    
    # Step 3: Create prompt for Llama 3.1
    prompt = f"""
Based on the following information from the Philippines Skills Framework for Analytics and AI, 
create a personalized learning pathway or roadmap for someone interested in: "{query_text}".

Include:
1. Relevant skills to develop
2. Suggested learning progression
3. Potential job roles to target
4. Key competencies needed

CONTEXT INFORMATION:
{context}

Please format your response as a clear, structured learning pathway.
"""
    
    # Step 4: Call Llama 3.1 with the prompt
    print("Generating learning pathway with Llama 3.1...")
    
    try:
        # Try to call Llama 3.1
        response = call_llama_model(prompt)
        pathway_content = response
    except Exception as e:
        print(f"Error calling Llama 3.1: {e}, using fallback response")
        # If Llama call fails, use the fallback response
        pathway_content = generate_fallback_response(query_text)
    
    # Create the result object
    result = {
        "query": query_text,
        "pathway": pathway_content,
        "context": similar_content
    }
    
    # Save the result to file
    # save_pathway_to_file(result)
    
    return result

def call_llama_model(prompt):
    """Call the Llama 3.1 model via Ollama API"""
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": "llama3.1",
        "prompt": prompt,
        "stream": False
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        return result.get("response", "Could not generate pathway")
    else:
        print(f"Error calling Llama 3.1: {response.text}")
        raise Exception(f"Failed to generate pathway: {response.status_code}")

# def save_pathway_to_file(result):
#     """Save the generated pathway to a file"""
#     # Create the data directory if it doesn't exist
#     data_dir = os.path.abspath("backend/api/data")
#     os.makedirs(data_dir, exist_ok=True)
    
#     # Full path to the output file
#     output_path = os.path.join(data_dir, "sample_pathway.json")
    
#     print(f"Saving pathway to: {output_path}")
    
#     try:
#         with open(output_path, "w", encoding="utf-8") as f:
#             json.dump(result, f, indent=2, ensure_ascii=False)
        
#         if os.path.exists(output_path):
#             file_size = os.path.getsize(output_path)
#             print(f"File saved successfully: {output_path} ({file_size} bytes)")
#         else:
#             print(f"Error: File not created at {output_path}")
#     except Exception as e:
#         print(f"Exception saving file: {e}")
        
#         # Try alternate approach with absolute path
#         try:
#             alt_path = os.path.join(os.getcwd(), "backend", "api", "data", "sample_pathway.json")
#             print(f"Trying alternate path: {alt_path}")
            
#             os.makedirs(os.path.dirname(alt_path), exist_ok=True)
#             with open(alt_path, "w", encoding="utf-8") as f:
#                 json.dump(result, f, indent=2, ensure_ascii=False)
                
#             if os.path.exists(alt_path):
#                 print(f"File saved to alternate path: {alt_path}")
#         except Exception as e2:
#             print(f"Failed with alternate path too: {e2}")

def create_fallback_content(query_text):
    """Create fallback content when no search results are available"""
    # AI/ML related queries fallback content
    if any(term in query_text.lower() for term in ["ai", "machine learning", "artificial intelligence", "ml"]):
        return [
            {
                "text": "AI Engineering typically requires skills in machine learning algorithms, data preprocessing, model development, MLOps, and deployment techniques. Key competencies include Python programming, understanding of neural networks, and knowledge of frameworks like TensorFlow and PyTorch.",
                "metadata": {
                    "type": "text_match",
                    "title": "AI Engineering Skills"
                }
            },
            {
                "text": "Career progression in AI often involves starting as a Junior AI Engineer, then moving to AI Engineer, Senior AI Engineer, and eventually AI Architect or AI Research Scientist positions.",
                "metadata": {
                    "type": "text_match",
                    "title": "AI Career Progression"
                }
            }
        ]
    # Data Science related queries fallback content
    elif any(term in query_text.lower() for term in ["data science", "data scientist", "analytics"]):
        return [
            {
                "text": "Data Scientists need skills in statistical analysis, machine learning, data visualization, and domain knowledge. They should be proficient in Python, R, SQL, and tools like Tableau or PowerBI.",
                "metadata": {
                    "type": "text_match",
                    "title": "Data Science Skills"
                }
            },
            {
                "text": "Career paths in data science typically start with Data Analyst roles, progressing to Junior Data Scientist, Data Scientist, Senior Data Scientist, and then to Lead Data Scientist or Data Science Manager.",
                "metadata": {
                    "type": "text_match",
                    "title": "Data Science Career Path"
                }
            }
        ]
    # General tech fallback
    else:
        return [
            {
                "text": "Technology careers in analytics and AI require a foundation in programming, mathematics, and domain knowledge. Key technical skills include Python, SQL, cloud technologies, and data structures.",
                "metadata": {
                    "type": "text_match",
                    "title": "Tech Career Foundations"
                }
            },
            {
                "text": "Career progression in tech usually involves moving from junior roles to senior positions, then to lead or architect roles, and potentially into management or executive positions.",
                "metadata": {
                    "type": "text_match",
                    "title": "Tech Career Progression"
                }
            }
        ]

def generate_fallback_response(query_text):
    """Generate a fallback response when the LLM API is unavailable"""
    # AI/ML related queries
    if any(term in query_text.lower() for term in ["ai", "artificial intelligence", "machine learning"]):
        return """
# AI Engineering Learning Pathway

## 1. Relevant Skills to Develop
- Python programming (advanced level)
- Machine learning algorithms and frameworks
- Deep learning and neural networks
- Data preprocessing and feature engineering
- MLOps and deployment practices
- Cloud platforms (AWS, Azure, or GCP)

## 2. Suggested Learning Progression
1. **Foundation Phase** (3-6 months)
   - Master Python programming
   - Learn data structures and algorithms
   - Study statistics and probability
   - Complete basic ML courses

2. **Technical Development Phase** (6-12 months)
   - Deep dive into ML frameworks (TensorFlow, PyTorch)
   - Study deep learning architectures
   - Learn data engineering principles
   - Practice with real-world datasets

3. **Specialization Phase** (6-12 months)
   - Focus on a specific AI domain (NLP, Computer Vision, etc.)
   - Master deployment and MLOps
   - Build a portfolio of projects
   - Contribute to open source

## 3. Potential Job Roles to Target
- Junior AI Engineer
- Machine Learning Engineer
- AI Application Developer
- MLOps Engineer
- Senior AI Engineer (with experience)
- AI Research Engineer

## 4. Key Competencies Needed
- Analytical thinking and problem-solving
- Continuous learning mindset
- Attention to detail
- Collaborative teamwork
- Communication of technical concepts
- Research and experimentation skills
"""
    # Data Science related queries
    elif any(term in query_text.lower() for term in ["data science", "data scientist", "analytics"]):
        return """
# Data Science Career Pathway

## 1. Relevant Skills to Develop
- Statistical analysis and mathematics
- Python and R programming
- SQL and database knowledge
- Data visualization techniques
- Machine learning algorithms
- Domain expertise in your industry
- Data storytelling and communication

## 2. Suggested Learning Progression
1. **Foundation Building** (3-6 months)
   - Master Python programming
   - Learn statistics and probability
   - Develop SQL database skills
   - Study data visualization techniques

2. **Technical Enhancement** (6-12 months)
   - Advanced statistical methods
   - Machine learning algorithms
   - Feature engineering practices
   - Working with big data technologies

3. **Specialization** (6-12 months)
   - Focus on industry-specific applications
   - Advanced ML or deep learning
   - Build a portfolio of projects
   - Develop business acumen

## 3. Potential Job Roles to Target
- Data Analyst (entry point)
- Junior Data Scientist
- Data Scientist
- Senior Data Scientist
- Lead Data Scientist
- Data Science Manager

## 4. Key Competencies Needed
- Critical thinking and problem-solving
- Communication and presentation skills
- Business understanding
- Intellectual curiosity
- Teamwork and collaboration
- Attention to detail
"""
    # General career path
    else:
        return """
# Analytics and AI Career Pathway

## 1. Relevant Skills to Develop
- Programming fundamentals (Python, R)
- Data handling and processing
- Statistical analysis
- Machine learning basics
- Domain knowledge in your target industry
- Communication and presentation skills

## 2. Suggested Learning Progression
1. **Technical Foundation** (3-6 months)
   - Learn programming fundamentals
   - Study data structures and algorithms
   - Develop database and SQL skills
   - Basic statistics and visualization

2. **Analytical Skills Development** (6-12 months)
   - Advanced data analysis techniques
   - Basic machine learning algorithms
   - Data visualization and storytelling
   - Industry-specific knowledge

3. **Specialization Phase** (ongoing)
   - Focus on specific technologies or domains
   - Develop expertise in chosen area
   - Build portfolio of relevant projects
   - Networking and professional development

## 3. Potential Job Roles to Target
- Data Analyst
- Business Intelligence Analyst
- Analytics Specialist
- Junior Data Scientist
- Machine Learning Engineer
- AI Application Developer

## 4. Key Competencies Needed
- Analytical thinking
- Problem-solving ability
- Attention to detail
- Continuous learning mindset
- Communication skills
- Business acumen
"""

if __name__ == "__main__":
    # Test with single query
    query = "What skills do I need for AI engineering?"
    result = generate_learning_pathway(query)
    
    print("\n" + "="*80)
    print(f"QUERY: {query}")
    print("="*80)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(result["pathway"])
    print("="*80 + "\n")