import json
import os
import re
import requests 
from collections import defaultdict
from docling.document_converter import DocumentConverter

# --- ollama_generate function (no changes) ---
def ollama_generate(prompt: str, model: str = "llama3.1:8b-instruct-q2_K") -> str:
    """
    Sends a prompt to Ollama and returns the response text.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json" # Request JSON format
    }
    
    try:
        print(f"Sending prompt to Ollama (first 100 chars): {prompt[:100]}...") # Debugging
        response = requests.post(url, json=payload, timeout=600) # Increased timeout
        response.raise_for_status()
        result = response.json()
        print("Received response from Ollama.") # Debugging
        return result.get("response", "") 
    except requests.exceptions.Timeout:
        print(f"Error: Ollama request timed out after 600 seconds.")
        raise TimeoutError("Ollama request timed out.")
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        if "Connection refused" in str(e):
             raise ConnectionRefusedError("Connection to Ollama refused. Ensure Ollama is running.") from e
        raise Exception(f"Failed to connect to Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"Ollama API response was not valid JSON: {e}")
        print(f"Raw response text: {response.text}")
        raise ValueError("Ollama API did not return a valid JSON response.") from e

# --- extract_json_from_text function (no changes) ---
def extract_json_from_text(text: str) -> dict | list:
    """
    Extracts a JSON object or list from a string.
    Handles cases where the JSON is embedded within other text or markdown code blocks.
    Also handles cases where Ollama returns a JSON string directly (with format="json").
    """
    if not text or not text.strip():
        raise ValueError("Received empty or whitespace-only text, cannot extract JSON.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("Direct JSON parsing failed, attempting extraction...") 

        json_match = re.search(r'```(?:json)?\s*([\{\[][\s\S]*?[\]\}])\s*```', text, re.DOTALL)
        if json_match:
            potential_json = json_match.group(1).strip()
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON extracted from triple backticks: {e}")

        start_brace = text.find('{')
        end_brace = text.rfind('}')
        start_bracket = text.find('[')
        end_bracket = text.rfind(']')

        potential_json = None
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
             if end_brace != -1 and end_brace > start_brace:
                 potential_json = text[start_brace : end_brace + 1].strip()
        elif start_bracket != -1:
             if end_bracket != -1 and end_bracket > start_bracket:
                 potential_json = text[start_bracket : end_bracket + 1].strip()

        if potential_json:
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON extracted between first/last brackets/braces: {e}")
        
        print("Failed to parse JSON using all extraction methods. Received text:")
        print(text[:1000]) 
        raise ValueError("Could not extract valid JSON from the response text.")

# --- preprocess_markdown function (REFACTORED) ---
def preprocess_markdown(markdown: str) -> str:
    """
    Preprocesses markdown: cleans text, normalizes tables, merges duplicate columns.
    """
    lines = markdown.splitlines()
    processed_lines = []
    
    in_table = False
    header_cells = []
    merged_header = []
    column_map = {} # Maps original column index to merged column index/content list
    indices_to_skip = set()

    # Keywords indicating a likely header row (adjust as needed)
    header_keywords = {'Functions', 'Tasks', 'Skills', 'Competencies', 'Expectations', 'Level'}

    # Keywords indicating text that might be erroneously mixed into first data cell
    redundant_first_cell_text = {
        "Critical Work Functions, Key Tasks and Performance Expectations",
        "Skills and Competencies"
    }

    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1 # Increment here, adjust later if skipping lines

        # 1. Basic Line Cleaning (applied early)
        cleaned_line = re.sub(r'<!--\s*image\s*-->', '', line, flags=re.IGNORECASE)
        if re.search(r'^\s*Continue to next page\s*$', cleaned_line, flags=re.IGNORECASE):
            continue # Skip this line entirely
        cleaned_line = cleaned_line.strip()
        cleaned_line = re.sub(r'\s{2,}', ' ', cleaned_line) # Reduce multiple spaces

        # Skip empty lines for now, handle spacing later
        if not cleaned_line:
            processed_lines.append('')
            continue

        # Check for standalone header-like text outside tables
        if not (cleaned_line.startswith('|') and cleaned_line.endswith('|')):
            if cleaned_line in redundant_first_cell_text:
                 print(f"Removing standalone header text: {cleaned_line}")
                 continue # Skip this line

        # 2. Table Processing Logic
        is_table_row = cleaned_line.startswith('|') and cleaned_line.endswith('|')
        is_separator = is_table_row and re.match(r'^\|[ -]+\|$', cleaned_line)

        if is_table_row and not is_separator:
            cells = [cell.strip() for cell in cleaned_line.strip('|').split('|')]
            
            # Remove leading/trailing empty cells common in some conversions
            while cells and not cells[0]: del cells[0]
            while cells and not cells[-1]: del cells[-1]
            if not cells: continue # Skip rows that become empty

            # Check if this looks like a header row
            next_line_is_separator = (i < len(lines) and 
                                      lines[i].strip().startswith('|') and 
                                      re.match(r'^\|[ -]+\|$', lines[i].strip()))
            
            is_likely_header = next_line_is_separator and any(kw in cell for cell in cells for kw in header_keywords)

            if is_likely_header:
                print(f"Detected Header: {cells}")
                in_table = True
                header_cells = cells
                merged_header = []
                column_map = {}
                indices_to_skip = set()
                temp_indices = defaultdict(list)

                # Map header names to their indices
                for idx, name in enumerate(header_cells):
                    temp_indices[name].append(idx)

                # Build the merged header and column map
                current_merged_idx = 0
                processed_original_indices = set()
                for original_idx, name in enumerate(header_cells):
                    if original_idx in processed_original_indices:
                        continue
                    
                    indices = temp_indices[name]
                    merged_header.append(name)
                    column_map[current_merged_idx] = indices # Map merged index to list of original indices
                    processed_original_indices.update(indices) # Mark all original indices for this name as processed
                    
                    if len(indices) > 1:
                        print(f"  Merging header '{name}' from original indices: {indices}")
                        # Mark duplicates (all except the first) for skipping in data rows
                        indices_to_skip.update(indices[1:]) 
                    
                    current_merged_idx += 1
                
                # Add the processed header row
                processed_lines.append("| " + " | ".join(merged_header) + " |")
                
                # Process the separator line immediately
                if next_line_is_separator:
                    separator_line = lines[i].strip()
                    num_merged_columns = len(merged_header)
                    if num_merged_columns > 0:
                        # Ensure separator has dashes, not just spaces
                        dashes = " --- " 
                        processed_lines.append('|' + dashes * num_merged_columns + '|')
                    i += 1 # Skip the original separator line

            elif in_table: # Process data row
                merged_cells = [""] * len(merged_header)
                
                # Merge data cells based on column_map
                for merged_idx, original_indices in column_map.items():
                    content_parts = []
                    for original_idx in original_indices:
                        if original_idx < len(cells) and cells[original_idx]:
                            content_parts.append(cells[original_idx])
                    # Join content from merged columns (use newline, could be space)
                    merged_cells[merged_idx] = "\n".join(content_parts) 

                # Clean redundant text from the first cell if necessary
                if merged_cells and merged_cells[0] in redundant_first_cell_text:
                     print(f"Removing redundant text from first cell: {merged_cells[0]}")
                     merged_cells[0] = "" # Or try to extract actual content if possible

                # Skip rows that only contain repeated header text after potential cleaning
                is_just_repeated_header = True
                for cell_content in merged_cells:
                    if cell_content not in header_cells and cell_content:
                        is_just_repeated_header = False
                        break
                if is_just_repeated_header and len(merged_cells) > 0:
                     print(f"Skipping row containing only repeated header text: {merged_cells}")
                     continue

                # Reconstruct the data row
                processed_lines.append("| " + " | ".join(merged_cells) + " |")
            
            else: # Not a header, not in a table - treat as normal text
                in_table = False
                processed_lines.append(cleaned_line)

        elif is_separator:
            # Separators are handled when the header is detected. If we are not in a table
            # context when encountering one, it's likely noise or malformed.
            if not in_table:
                 print(f"Skipping unexpected separator line: {cleaned_line}")
                 continue
            # If in_table is true, it should have been handled by header logic, ignore here.

        else: # Normal text line
            in_table = False
            processed_lines.append(cleaned_line)

    # Final cleanup: Remove excessive blank lines and trim whitespace
    final_text = "\n".join(processed_lines)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text) # Reduce multiple blank lines
    return final_text.strip()


# --- Helper function to extract role title (no changes) ---
def get_role_title(section_text: str) -> str | None:
    """Extracts the role title (text after ##) from the first line."""
    if not section_text:
        return None
    first_line = section_text.split('\n', 1)[0].strip()
    if first_line.startswith('## '):
        return first_line[3:].strip()
    return None

# --- convert_pdf_to_structured_json function (MODIFIED TO USE EXISTING CLEANED MARKDOWN) ---
def convert_pdf_to_structured_json(pdf_path: str, force_reprocess_markdown: bool = False) -> list[dict]:
    """
    Converts a PDF containing multiple role descriptions into a list of structured 
    JSON objects by processing the document chunk by chunk, merging continued roles.
    
    Args:
        pdf_path: Path to the PDF file
        force_reprocess_markdown: If True, always reprocess the PDF even if cleaned markdown exists
    
    Returns:
        A list of structured JSON objects representing the roles
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Error: PDF file not found at {pdf_path}")
    
    # Ensure the data directory exists
    os.makedirs("backend/api/data", exist_ok=True)
    
    # Path to where cleaned markdown should be stored
    markdown_output_path = "backend/api/data/cleaned_markdown.md"
    
    # Step 1 & 2: Check if cleaned markdown already exists
    if os.path.exists(markdown_output_path) and not force_reprocess_markdown:
        print(f"Using existing cleaned markdown from {markdown_output_path}")
        with open(markdown_output_path, "r", encoding="utf-8") as f:
            cleaned_markdown = f.read()
    else:
        # Generate cleaned markdown from PDF
        print("Converting PDF to Markdown...")
        converter = DocumentConverter()
        raw_markdown = converter.convert(pdf_path).document.export_to_markdown()
        
        print("Preprocessing Markdown...")
        cleaned_markdown = preprocess_markdown(raw_markdown) # Use the refactored function
        
        # Save the cleaned markdown for future use
        print(f"Saving cleaned markdown to {markdown_output_path}")
        with open(markdown_output_path, "w", encoding="utf-8") as f:
            f.write(cleaned_markdown)
    
    # Step 3: Split markdown into initial sections based on Role headers (##)
    print("Splitting markdown into initial sections...")
    # Use positive lookbehind to keep the delimiter (## Role) with the section
    initial_sections = re.split(r'(?=\n##\s+[^\n]+)', cleaned_markdown) 
    
    # Step 3.5: Merge continued sections
    print("Merging continued role sections...")
    merged_sections_dict = {} # Use dict to group by role title
    
    current_title = None
    accumulated_content = ""

    for section in initial_sections:
        section = section.strip()
        if not section: 
            continue 

        title_match = re.match(r'^##\s+(.+)', section)
        
        if title_match:
            role_title = title_match.group(1).strip()
            # Extract content after the title line
            content_parts = section.split('\n', 1)
            content = content_parts[1].strip() if len(content_parts) > 1 else ""
            
            if role_title in merged_sections_dict:
                # Append content from the continued section
                print(f"Found continuation for role: {role_title}. Merging content.")
                merged_sections_dict[role_title] += "\n\n" + content # Add separator and new content
            else:
                # Add the first occurrence (including title)
                merged_sections_dict[role_title] = section # Store the full section initially
        elif section.startswith("##"):
             # Handle cases where title might be empty or malformed, though unlikely with regex
             print(f"Warning: Malformed title section skipped: {section[:50]}...")
        else:
             # Content before the first ## header - ignore for now, or handle if needed
             print(f"Skipping content before first valid role header: {section[:50]}...")


    final_sections_to_process = list(merged_sections_dict.values())
    print(f"Total unique roles found after merging: {len(final_sections_to_process)}")
    all_roles_data = []
    error_responses = [] 

    # Step 4: Process each MERGED chunk with Ollama
    for i, section in enumerate(final_sections_to_process):
        role_title_for_log = get_role_title(section) or f"Chunk {i+1}" 

        print(f"\n--- Processing Merged Chunk {i+1} ({role_title_for_log}) ---")

        # Prompt remains the same (with few-shot example)
        single_role_prompt = f"""
        Analyze the markdown content below describing ONE professional role. Convert it into a structured JSON object.
        Output ONLY the valid JSON object, starting with `{{` and ending with `}}`. No extra text, comments, or markdown.

        Required JSON structure:
        {{
          "Role": "string", 
          "Description": "string", 
          "CriticalWorkFunctions": [ {{ "Function": "string", "KeyTasks": ["string"], "PerformanceExpectations": ["string"] }} ],
          "FunctionalSkills": {{ "<skill_name>": "<level>" }}, 
          "EnablingSkills": {{ "<skill_name>": "<competency>" }} 
        }}

        **Instructions for Table Extraction (CRITICAL):**
        1.  **Critical Work Functions:** Combine rows from ALL CWF tables into a SINGLE list under "CriticalWorkFunctions".
        2.  **Skills/Competencies Table:** Locate the table with skills.
        3.  **Functional Skills:** Extract skill-level pairs (e.g., "Data Analytics": "Level 2") into the "FunctionalSkills" dictionary.
        4.  **Enabling Skills:** Extract skill-competency pairs (e.g., "Collaboration": "Basic") into the "EnablingSkills" dictionary. Ensure Skill Name is the key.
        5.  If tables are missing, use `[]` or `{{}}`.

        **Example of Skills Extraction:**
        If the markdown has a table like this:
        | Skills and Competencies | Functional Skills and Competencies | Enabling Skills and Competencies |
        |---|---|---|
        | Data Analytics | Level 2 | Collaboration | Basic |
        | Data Engineering | Level 3 | Communication | Intermediate |

        The JSON output MUST contain:
        "FunctionalSkills": {{
          "Data Analytics": "Level 2",
          "Data Engineering": "Level 3"
        }},
        "EnablingSkills": {{
          "Collaboration": "Basic",
          "Communication": "Intermediate"
        }}
        **DO NOT** output a list like `[ {{"SkillOrCompetency": "Data Analytics", "Level": 2}}, ... ]`.

        Markdown Content for this Role:
        ```markdown
        {section}
        ```

        Final Rules:
        - Output ONLY the JSON object. No introductory text, schema definitions, or markdown formatting.
        """

        try:
            ai_response_text = ollama_generate(single_role_prompt, model="llama3.1:8b-instruct-q2_K")
            
            if not ai_response_text or not ai_response_text.strip():
                 print(f"Warning: Received empty response for chunk {i+1} ({role_title_for_log}).")
                 error_responses.append({"chunk": i+1, "role": role_title_for_log, "error": "Empty response", "response": ""})
                 continue

            role_data = extract_json_from_text(ai_response_text) 

            # Validation logic remains the same
            if isinstance(role_data, dict) and "Role" in role_data:
                 extracted_title = role_data.get('Role', 'Unknown')
                 if extracted_title != role_title_for_log and role_title_for_log != f"Chunk {i+1}":
                      print(f"Warning: Extracted role title '{extracted_title}' differs from section header '{role_title_for_log}'")
                 print(f"Successfully extracted JSON for Role: {extracted_title}")
                 all_roles_data.append(role_data)
            elif isinstance(role_data, dict) and "$schema" in role_data:
                 print(f"Warning: Received schema instead of data for chunk {i+1} ({role_title_for_log}).")
                 error_responses.append({"chunk": i+1, "role": role_title_for_log, "error": "Received schema", "response": ai_response_text})
            elif isinstance(role_data, list):
                 print(f"Warning: Received a list instead of a single object for chunk {i+1} ({role_title_for_log}). Attempting to use the first element.")
                 if role_data and isinstance(role_data[0], dict) and "Role" in role_data[0]:
                     all_roles_data.append(role_data[0])
                 else:
                     error_responses.append({"chunk": i+1, "role": role_title_for_log, "error": "Received list, but invalid content", "response": ai_response_text})
            else:
                 # This is where the "Invalid object type: <class 'dict'>" error comes from
                 print(f"Warning: Could not extract a valid role object (dict missing 'Role' key?) for chunk {i+1} ({role_title_for_log}). Type received: {type(role_data)}")
                 error_responses.append({"chunk": i+1, "role": role_title_for_log, "error": f"Invalid object type or missing 'Role' key: {type(role_data)}", "response": ai_response_text})


        except (ValueError, json.JSONDecodeError, TimeoutError, ConnectionRefusedError, Exception) as e:
             # Error handling remains the same
             print(f"Error processing chunk {i+1} ({role_title_for_log}): {e}")
             error_responses.append({"chunk": i+1, "role": role_title_for_log, "error": str(e), "response": ai_response_text if 'ai_response_text' in locals() else "N/A"})
             error_output_path = f"backend/api/data/ollama_error_chunk_{i+1}_{re.sub('[^A-Za-z0-9]+', '', role_title_for_log)}.txt" # Sanitize filename
             try:
                 with open(error_output_path, "w", encoding="utf-8") as f:
                     f.write(f"--- ROLE: {role_title_for_log} ---\n--- PROMPT ---\n{single_role_prompt}\n\n--- RESPONSE ---\n{ai_response_text if 'ai_response_text' in locals() else 'N/A'}")
                 print(f"Saved problematic response/prompt for chunk {i+1} to {error_output_path}")
             except Exception as write_e:
                 print(f"Failed to write error file for chunk {i+1}: {write_e}")


    # Step 5: Final checks and return (no changes)
    print(f"\n--- Processing Complete ---")
    print(f"Successfully extracted data for {len(all_roles_data)} roles.")
    
    if error_responses:
        print(f"Encountered errors in {len(error_responses)} chunks. Check logs and 'ollama_error_chunk_*.txt' files.")
        error_summary_path = "backend/api/data/ollama_error_summary.json"
        try:
            with open(error_summary_path, "w", encoding="utf-8") as f:
                json.dump(error_responses, f, indent=2)
            print(f"Saved error summary to {error_summary_path}")
        except Exception as write_e:
            print(f"Failed to write error summary file: {write_e}")

    if not all_roles_data:
         # Changed to warning instead of raising error if some chunks failed but others succeeded
         print("Warning: Failed to extract valid role data for one or more chunks.")
         # raise ValueError("Failed to extract any valid role data from the document after processing all chunks.")

    json_output_path = "backend/api/data/extracted_pathways.json"
    print(f"Saving combined structured JSON ({len(all_roles_data)} roles) to {json_output_path}")
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(all_roles_data, f, indent=2)
    
    return all_roles_data

# --- Main execution block (added option to force reprocess) ---
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert PDF role descriptions to structured JSON")
    # Changed default PDF name to match user's likely file
    parser.add_argument("--pdf", default="backend/sample-roles.pdf", help="Path to the PDF file") 
    parser.add_argument("--force-reprocess", action="store_true", 
                        help="Force reprocessing of the PDF to regenerate cleaned_markdown.md")
    
    args = parser.parse_args()
    
    try:
        # Pass the force_reprocess flag to the function
        structured_json_list = convert_pdf_to_structured_json(args.pdf, args.force_reprocess) 
        print("\n--- Final Extracted JSON ---")
        if structured_json_list:
             # Print first valid role found, if any
             print(json.dumps(structured_json_list[0], indent=2)) 
             if len(structured_json_list) > 1:
                 print(f"\n... and {len(structured_json_list) - 1} more valid role(s). Full output saved to backend/api/data/extracted_pathways.json")
        else:
             print("No roles were successfully extracted and validated.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ConnectionRefusedError as e:
         print(f"Error: {e}. Please ensure the Ollama service is running.")
    except TimeoutError as e:
         print(f"Error: {e}. Ollama took too long to respond.")
    except Exception as e:
        print(f"An unexpected error occurred during the process: {str(e)}")
        import traceback
        traceback.print_exc() # Print full traceback for unexpected errors