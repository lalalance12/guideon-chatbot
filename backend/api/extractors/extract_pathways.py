import json
import os
from markitdown import MarkItDown
import re

def extract_pathways_from_pdf():
    """Extract career map data from PDF using MarkItDown with improved structure"""
    # Initialize markitdown with the correct PDF path
    pdf_path = "backend/sample-role.pdf"
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return {}
    
    print(f"Processing PDF: {pdf_path}")
    
    # Use MarkItDown to convert PDF to structured markdown
    md = MarkItDown(enable_plugins=False)
    result = md.convert(pdf_path)
    markdown_content = result.text_content
    
    # Save the raw markdown for reference
    os.makedirs("backend/api/data", exist_ok=True)
    with open("backend/api/data/raw_markdown.md", "w") as f:
        f.write(markdown_content)
    
    # Initialize career map structure
    career_map = {
        "header": "Analytics & Artificial Intelligence Career Map",
        "vertical_tracks": [],
        "horizontal_job_grades": [],
        "roles": []
    }
    
    # Extract vertical tracks (domains)
    tracks_pattern = r'Career Tracks:?\s+(.*?)(?=\n\n|\Z)'
    tracks_match = re.search(tracks_pattern, markdown_content, re.DOTALL)
    if tracks_match:
        tracks = [track.strip() for track in re.split(r'[,•]', tracks_match.group(1)) if track.strip()]
        career_map["vertical_tracks"] = tracks
    
    # Extract job grades
    grades_pattern = r'Job Grades:?\s+(.*?)(?=\n\n|\Z)'
    grades_match = re.search(grades_pattern, markdown_content, re.DOTALL)
    if grades_match:
        grades = [grade.strip() for grade in re.split(r'[,•]', grades_match.group(1)) if grade.strip()]
        career_map["horizontal_job_grades"] = grades
    
    # Role extraction patterns
    job_role_pattern = r'(?:#+\s*(.*?)|\n\n(.*?))\n\n(.*?(?:This role|The \w+ \w+).*?)\n'
    critical_work_pattern = r'(?:Critical Work Functions|Critical Functions).*?\n(.*?)(?=\n\n\S|\Z)'
    skills_pattern = r'(?:Skills|Skills and Competencies).*?\n(.*?)(?=\n\n\S|\Z)'
    functional_pattern = r'(?:Functional|Technical) Skills.*?\n(.*?)(?=\n\nEnabling|\Z)'
    enabling_pattern = r'Enabling Skills.*?\n(.*?)(?=\n\n\S|\Z)'
    performance_pattern = r'Performance Expectations.*?\n(.*?)(?=\n\n\S|\Z)'
    
    # Process page by page to find roles
    pages = re.split(r'===== Page \d+ =====', markdown_content)
    
    # Search for common job titles to help identify role sections
    common_titles = [
        "Data Analyst", "Data Scientist", "Data Engineer", 
        "AI Engineer", "Associate", "Director", "Manager",
        "Chief Data", "Senior"
    ]
    
    for page in pages:
        # Look for sections that might contain role information
        for title in common_titles:
            if title in page:
                # Try to extract role info
                title_match = re.search(fr'(#+\s*.*{title}.*|{title}.*?(?=\n))', page)
                if title_match:
                    role_title = title_match.group(1).strip()
                    if role_title.startswith('#'):
                        role_title = re.sub(r'^#+\s*', '', role_title)
                    
                    # Try to find a description
                    desc_pattern = r'(This role|The \w+ \w+).*?(?=\n\n)'
                    desc_match = re.search(desc_pattern, page)
                    description = desc_match.group(0) if desc_match else "No description available"
                    
                    # Extract critical work functions
                    critical_work = ""
                    cw_match = re.search(critical_work_pattern, page, re.DOTALL)
                    if cw_match:
                        critical_work = cw_match.group(1).strip()
                    
                    # Extract skills and competencies
                    skills_competencies = {
                        "functional": [],
                        "enabling": []
                    }
                    
                    # Check for functional skills
                    func_match = re.search(functional_pattern, page, re.DOTALL)
                    if func_match:
                        func_text = func_match.group(1).strip()
                        skills_competencies["functional"] = [skill.strip() for skill in re.split(r'[\n•]', func_text) if skill.strip()]
                    
                    # Check for enabling skills
                    enabling_match = re.search(enabling_pattern, page, re.DOTALL)
                    if enabling_match:
                        enabling_text = enabling_match.group(1).strip()
                        skills_competencies["enabling"] = [skill.strip() for skill in re.split(r'[\n•]', enabling_text) if skill.strip()]
                    
                    # Extract performance expectations
                    performance = ""
                    perf_match = re.search(performance_pattern, page, re.DOTALL)
                    if perf_match:
                        performance = perf_match.group(1).strip()
                    
                    # Create role object
                    role = {
                        "title": role_title,
                        "description": description,
                        "critical_work_functions": critical_work,
                        "skills_and_competencies": skills_competencies,
                        "performance_expectations": performance
                    }
                    
                    # Only add if we have meaningful data
                    if critical_work or skills_competencies["functional"] or skills_competencies["enabling"]:
                        career_map["roles"].append(role)
    
    # Wrap the career map in the top-level structure
    output_data = {
        "career_map": career_map
    }
    
    # Save to JSON
    output_path = "backend/api/data/extracted_pathways.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Extracted career map with {len(career_map['roles'])} roles")
    return output_data

if __name__ == "__main__":
    extract_pathways_from_pdf()