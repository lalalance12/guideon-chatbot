import json
import requests
import numpy as np
import os

def generate_embeddings(text_chunks):
    embeddings = []
    
    # Ollama API endpoint for embeddings
    url = "http://localhost:11434/api/embeddings"
    
    for i, chunk in enumerate(text_chunks):
        print(f"Generating embedding for chunk {i+1}/{len(text_chunks)}")
        payload = {
            "model": "llama3.1",
            "prompt": chunk
        }
        
        try:
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                embedding_data = response.json()
                embedding = embedding_data.get("embedding", [])
                embeddings.append(embedding)
            else:
                print(f"Error generating embedding: {response.text}")
                embeddings.append([])
        except Exception as e:
            print(f"Exception while generating embedding: {e}")
            embeddings.append([])
    
    return embeddings

def process_pathways():
    input_path = "backend/api/data/extracted_pathways.json"
    
    if not os.path.exists(input_path):
        print(f"Error: Extracted pathways file not found at {input_path}")
        return []
    
    with open(input_path, "r") as f:
        data = json.load(f)
    
    # Extract the career map from the new structure
    career_map = data.get("career_map", {})
    roles = career_map.get("roles", [])
    
    if not roles:
        print("Warning: No roles found in the career map")
    
    text_chunks = []
    chunk_metadata = []
    
    # Add overall career map info
    overview = f"Analytics & Artificial Intelligence Career Map\n"
    overview += f"Vertical Tracks: {', '.join(career_map.get('vertical_tracks', []))}\n"
    overview += f"Job Grades: {', '.join(career_map.get('horizontal_job_grades', []))}"
    
    text_chunks.append(overview)
    chunk_metadata.append({
        "type": "overview",
        "title": "Career Map Overview"
    })
    
    # Process each role
    for role in roles:
        # Main role info
        role_text = f"Title: {role['title']}\n\n"
        role_text += f"Description: {role['description']}\n\n"
        role_text += f"Critical Work Functions: {role['critical_work_functions']}\n\n"
        role_text += f"Performance Expectations: {role['performance_expectations']}"
        
        text_chunks.append(role_text)
        chunk_metadata.append({
            "type": "role",
            "title": role['title']
        })
        
        # Skills as separate chunks
        skills_text = f"Skills for {role['title']}:\n\n"
        skills_text += "Functional Skills:\n"
        for skill in role['skills_and_competencies'].get('functional', []):
            skills_text += f"• {skill}\n"
        
        skills_text += "\nEnabling Skills:\n"
        for skill in role['skills_and_competencies'].get('enabling', []):
            skills_text += f"• {skill}\n"
        
        text_chunks.append(skills_text)
        chunk_metadata.append({
            "type": "skills",
            "title": f"Skills for {role['title']}",
            "parent": role['title']
        })
    
    print(f"Generating embeddings for {len(text_chunks)} text chunks")
    embeddings = generate_embeddings(text_chunks)
    
    results = []
    for i in range(len(text_chunks)):
        if embeddings[i]:
            results.append({
                "text": text_chunks[i],
                "metadata": chunk_metadata[i],
                "embedding": embeddings[i]
            })
    
    output_path = "backend/api/data/embeddings_data.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Generated {len(results)} embeddings")
    return results

if __name__ == "__main__":
    process_pathways()