import json, sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.append(str(BASE_DIR))
print(BASE_DIR)

def build_job_domain_mapping(career_map_path):
    """
    Build a mapping of job titles to their domains from the career map JSON
    """
    try:
        with open(career_map_path, 'r') as file:
            career_map = json.load(file)
        
        job_domain_map = {}
        
        # First extract from jobGrades section which contains explicit domain assignments
        for grade in career_map.get("jobGrades", []):
            for position in grade.get("positions", []):
                job_title = position.get("name", "").strip()
                domain = position.get("domain", "")
                if job_title:
                    if domain == "All Domains":
                        # For "All Domains", get list of all domain names
                        domains = [d.get("name") for d in career_map.get("domains", [])]
                        job_domain_map[job_title.lower()] = domains
                    elif "," in domain:
                        # Handle comma-separated domain lists
                        domains = [d.strip() for d in domain.split(",")]
                        job_domain_map[job_title.lower()] = domains
                    else:
                        job_domain_map[job_title.lower()] = [domain]
        
        # Extract domains from the domains section as a fallback 
        # or to supplement existing entries
        for domain in career_map.get("domains", []):
            domain_name = domain.get("name", "")
            for role_info in domain.get("roles", []):
                job_title = role_info.get("role", "").strip()
                if job_title:
                    if job_title.lower() in job_domain_map:
                        if domain_name not in job_domain_map[job_title.lower()]:
                            job_domain_map[job_title.lower()].append(domain_name)
                    else:
                        job_domain_map[job_title.lower()] = [domain_name]
        
        return job_domain_map
    
    except Exception as e:
        print(f"Error building job domain mapping: {e}")
        return {}

def extract_job_info(json_file_path, career_map_path):
    """
    Extract job title, description, functional skills, and domain from a JSON file
    """
    # Build the job title to domain mapping
    job_domain_map = build_job_domain_mapping(career_map_path)
    
    # Read the JSON file
    with open(json_file_path, 'r') as file:
        data = json.load(file)
    
    # Handle different JSON structures
    if isinstance(data, dict) and "roles" in data:
        # If data is in format {"roles": [job1, job2, ...]}
        jobs = data["roles"]
    elif isinstance(data, list):
        # If data is already a list of jobs
        jobs = data
    else:
        raise ValueError(f"Unexpected JSON structure in {json_file_path}")
    
    result = []
    
    # Process each job in the JSON data
    for job in jobs:
        job_title = job.get("job_title", "Unknown Title")
        description = job.get("description", "No description available")
        
        # Get domain information from the mapping
        domain = job_domain_map.get(job_title.lower(), [])
        if not domain:
            # Try a more flexible match for titles that might have variations
            for title in job_domain_map:
                if title in job_title.lower() or job_title.lower() in title:
                    domain = job_domain_map[title]
                    break
        
        # Extract only the skill names from functional skills, not the levels
        functional_skills = []
        for skill_item in job.get("functional_skills", []):
            skill_name = skill_item.get("skill")
            if skill_name and skill_name.lower() != "skills and competencies":
                functional_skills.append(skill_name)
        
        # Add the job info to our results
        result.append({
            "job_title": job_title,
            "description": description,
            "functional_skills": functional_skills,
            "domains": domain if domain else ["Unknown"]
        })
    
    return result

def main():
    # Paths to your JSON files
    file_path = f"{BASE_DIR}/data/processed_roles.json" 
    career_map_path = f"{BASE_DIR}/data-sample/career_map.json"
    
    # Check if the career map file exists
    if not Path(career_map_path).exists():
        # Try alternate locations
        alt_career_paths = [
            f"{BASE_DIR}/api/data-sample/career_map.json",
            f"{BASE_DIR}/../data-sample/career_map.json",
            f"{Path.cwd()}/career_map.json"
        ]
        
        for alt_path in alt_career_paths:
            if Path(alt_path).exists():
                career_map_path = alt_path
                print(f"Found career map at: {career_map_path}")
                break
        else:
            print("Warning: Could not find career_map.json")
            career_map_path = None

    try:
        # Extract job information with domain mapping if available
        if career_map_path and Path(career_map_path).exists():
            extracted_info = extract_job_info(file_path, career_map_path)
        else:
            # Fallback to regular extraction without domains
            extracted_info = extract_job_info(file_path, None)
        
        # Print the results in a readable format
        for job in extracted_info:
            print(f"Job Title: {job['job_title']}")
            print(f"Domains: {', '.join(job['domains'])}")
            print(f"Description: {job['description'][:100]}...")  # Print just the beginning for readability
            print("Functional Skills:")
            for skill in job['functional_skills']:
                print(f"  - {skill}")
            print("\n" + "-"*80 + "\n")
        
        # Save the extracted data to a new file
        output_path = f"{BASE_DIR}/data/roles/extracted_job_info.json"
        with open(output_path, "w") as file:
            json.dump(extracted_info, file, indent=2)
        print(f"Extracted data saved to {output_path}")
        
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        print(f"Looking for alternative paths...")
        
        # Try alternative locations for the roles file
        alt_paths = [
            f"{BASE_DIR}/data/roles/processed_roles.json",
            f"{BASE_DIR}/api/data/processed_roles.json",
            f"{BASE_DIR}/../data/processed_roles.json"
        ]
        
        for alt_path in alt_paths:
            try:
                print(f"Trying {alt_path}...")
                if career_map_path and Path(career_map_path).exists():
                    extracted_info = extract_job_info(alt_path, career_map_path)
                else:
                    extracted_info = extract_job_info(alt_path, None)
                    
                print(f"Success! Found {len(extracted_info)} roles.")
                
                # Save the extracted data
                output_path = f"{BASE_DIR}/data/roles/extracted_job_info.json"
                with open(output_path, "w") as file:
                    json.dump(extracted_info, file, indent=2)
                print(f"Extracted data saved to {output_path}")
                break
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Error with {alt_path}: {e}")
            
    except Exception as e:
        print(f"Error processing the file: {e}")

if __name__ == "__main__":
    main()