import os
import pdfplumber
import re
import json
import requests # Added import

# --- Helper: Preprocess Text ---
def preprocess_text(text: str) -> str:
    """
    Preprocesses raw extracted text with general cleaning:
    - Strips leading/trailing whitespace from each line.
    - Reduces multiple consecutive spaces within a line to a single space.
    - Removes excessive blank lines (more than one consecutive).
    - Removes leading/trailing whitespace from the entire text.
    """
    if not text:
        return ""
        
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # 1. Strip leading/trailing whitespace from the line
        cleaned_line = line.strip()
        
        # 2. Reduce multiple spaces within the line to single spaces
        cleaned_line = re.sub(r'\s{2,}', ' ', cleaned_line)

        # Add the cleaned line (even if empty, to preserve paragraph breaks)
        cleaned_lines.append(cleaned_line)

    # Reconstruct the text
    cleaned_text = "\n".join(cleaned_lines)

    # Remove duplicate blank lines (more than one consecutive blank line)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)

    # Remove leading/trailing whitespace from the final output
    return cleaned_text.strip()

# --- Helper: Extract Column Text (No changes needed here) ---
def extract_column_text(page, left=True):
    width = page.width
    height = page.height
    mid_x = width / 2
    
    # Define bounding box and extract text
    # Added a small vertical margin (10) to potentially avoid headers/footers if needed
    bbox = (0, 10, mid_x, height - 10) if left else (mid_x, 10, width, height - 10)
    cropped = page.crop(bbox)
    # Increased x_density slightly, might help with spacing
    text = cropped.extract_text(layout=True, x_density=3, y_density=12) or "" 
    # Ensure UTF-8 handling early
    return text.encode('utf-8', 'replace').decode('utf-8')

# --- Helper: Ollama Interaction (Copied from roles_docling.py) ---
def ollama_generate(prompt: str, model: str = "llama3.1") -> str:
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
        response = requests.post(url, json=payload, timeout=300) # Added timeout
        response.raise_for_status()
        result = response.json()
        print("Received response from Ollama.") # Debugging
        # The 'response' field should contain the JSON string when format="json"
        return result.get("response", "") 
    except requests.exceptions.Timeout:
        print(f"Error: Ollama request timed out after 300 seconds.")
        raise TimeoutError("Ollama request timed out.")
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        if "Connection refused" in str(e):
             raise ConnectionRefusedError("Connection to Ollama refused. Ensure Ollama is running.") from e
        raise Exception(f"Failed to connect to Ollama API: {str(e)}")
    except json.JSONDecodeError as e:
        # Check if response exists before accessing text
        raw_response_text = response.text if response else "N/A"
        print(f"Ollama API response was not valid JSON: {e}")
        print(f"Raw response text: {raw_response_text}")
        raise ValueError("Ollama API did not return a valid JSON response.") from e

# --- Helper: Extract JSON (Copied from roles_docling.py) ---
def extract_json_from_text(text: str) -> dict | list: # Can return dict or list now
    """
    Extracts a JSON object or list from a string.
    Handles cases where the JSON is embedded within other text or markdown code blocks.
    Also handles cases where Ollama returns a JSON string directly (with format="json").
    """
    if not text or not text.strip():
        raise ValueError("Received empty or whitespace-only text, cannot extract JSON.")

    try:
        # First, try parsing the entire text directly, in case format="json" worked perfectly
        return json.loads(text)
    except json.JSONDecodeError:
        # If direct parsing fails, try extracting from markdown or finding the outermost braces/brackets
        print("Direct JSON parsing failed, attempting extraction...") # Debugging

        # Look for JSON object/list within ```json ... ``` or ``` ... ```
        json_match = re.search(r'```(?:json)?\s*([\{\[][\s\S]*?[\]\}])\s*```', text, re.DOTALL)
        if json_match:
            potential_json = json_match.group(1).strip()
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON extracted from triple backticks: {e}")
                # Continue to next method if this fails

        # If no backticks or parsing failed, find the first '{' or '[' and the last '}' or ']'
        start_brace = text.find('{')
        end_brace = text.rfind('}')
        start_bracket = text.find('[')
        end_bracket = text.rfind(']')

        potential_json = None
        # Prioritize object if both seem present and object starts first or no brackets
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
             if end_brace != -1 and end_brace > start_brace:
                 potential_json = text[start_brace : end_brace + 1].strip()
        # Else, prioritize list if present
        elif start_bracket != -1:
             if end_bracket != -1 and end_bracket > start_bracket:
                 potential_json = text[start_bracket : end_bracket + 1].strip()

        if potential_json:
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON extracted between first/last brackets/braces: {e}")
                # Fall through to the final error if this also fails
        
        # If all methods fail
        print("Failed to parse JSON using all extraction methods. Received text:")
        print(text[:1000]) # Print more for debugging
        raise ValueError("Could not extract valid JSON from the response text.")

# --- Main Conversion Function ---
def extract_roles_to_json(pdf_path: str, save_output: bool = True) -> list[dict]:
    """
    Extracts role descriptions from a two-column PDF, cleans the text,
    and uses Ollama to convert each role (assumed one per page) into a 
    structured JSON object.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Error: PDF file not found at {pdf_path}")

    all_roles_data = []
    error_responses = []
    page_texts = [] # Store raw text per page first

    # Step 1: Extract raw text page by page
    print(f"Extracting text from {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"Processing page {i+1}/{len(pdf.pages)}...")
            left_text = extract_column_text(page, left=True)
            right_text = extract_column_text(page, left=False)
            # Combine columns simply, preprocessing will handle spacing
            page_content = f"{left_text}\n\n{right_text}" 
            page_texts.append(page_content)
    
    print(f"Extracted text from {len(page_texts)} pages.")

    # Step 2: Process each page's text with AI
    for i, page_text in enumerate(page_texts):
        print(f"\n--- Processing Page {i+1} with AI ---")
        
        # Step 2a: Clean the extracted text for this page
        cleaned_text = preprocess_text(page_text)
        
        if not cleaned_text:
            print(f"Skipping page {i+1} due to empty content after cleaning.")
            continue

        # Save cleaned text for debugging (optional)
        # debug_dir = os.path.join("backend", "api", "data", "debug_cleaned")
        # os.makedirs(debug_dir, exist_ok=True)
        # with open(os.path.join(debug_dir, f"page_{i+1}_cleaned.txt"), "w", encoding="utf-8") as f:
        #     f.write(cleaned_text)

        # Step 2b: Define the prompt for Ollama
        single_role_prompt = f"""
        Analyze the following text content which describes ONE professional role, extracted from a page of a PDF.
        Convert the role description into a structured JSON object based on the structure described below.
        Output ONLY a valid JSON object. 

        **CRITICAL INSTRUCTION:** Do NOT output a JSON schema definition. Output ONLY the JSON data instance itself, starting with `{{` and ending with `}}`. Do not include any introductory text, explanations, comments, or markdown formatting like ```json.

        Required structure for the role object:
        {{
          "Role": "string", // The main title of the role (e.g., "Associate Data Analyst")
          "Description": "string", // The paragraph(s) describing the role, usually below the title
          "CriticalWorkFunctions": [ // Extracted from the table-like structure detailing functions/tasks/expectations
            {{
              "Function": "string", // The main function category (e.g., "Identify business needs")
              "KeyTasks": ["string"], // List of bullet points or sentences describing tasks for that function
              "PerformanceExpectations": ["string"] // List of bullet points or sentences describing expectations (often starts with "In accordance with:")
            }}
          ],
          "FunctionalSkills": {{ "<skill>": "<level>" }}, // Map skill name to level (e.g., "Level 3") from the skills/competencies section
          "EnablingSkills": {{ "<skill>": "<competency>" }} // Map skill name to competency (e.g., "Basic") from the skills/competencies section
        }}

        Text Content for this Role (from Page {i+1}):
        ```text
        {cleaned_text}
        ```

        Important rules:
        - The final output MUST be a single JSON object `{{...}}`.
        - Do NOT output a JSON schema. Output only the data object.
        - Identify the main Role Title accurately.
        - Parse the tables or lists for CriticalWorkFunctions, FunctionalSkills, and EnablingSkills carefully.
        - If a section (like PerformanceExpectations or skills tables) seems missing for a role, use empty lists `[]` or empty objects `{{}}` respectively in the JSON.
        - Respond ONLY with the JSON object, starting with `{{` and ending with `}}`.
        """

        # Step 2c: Call Ollama and parse the response
        ai_response_text = "" # Initialize in case ollama_generate fails early
        try:
            ai_response_text = ollama_generate(single_role_prompt, model="llama3.1")
            
            if not ai_response_text or not ai_response_text.strip():
                 print(f"Warning: Received empty response for page {i+1}.")
                 error_responses.append({"page": i+1, "error": "Empty response", "response": ""})
                 continue

            role_data = extract_json_from_text(ai_response_text) 

            # Basic validation
            if isinstance(role_data, dict) and "Role" in role_data and "Description" in role_data:
                 print(f"Successfully extracted JSON for Role: {role_data.get('Role', 'Unknown')}")
                 all_roles_data.append(role_data)
            else:
                 print(f"Warning: Could not extract a valid role object for page {i+1}. Type received: {type(role_data)}")
                 error_responses.append({"page": i+1, "error": f"Invalid object structure or type: {type(role_data)}", "response": ai_response_text})

        except (ValueError, json.JSONDecodeError, TimeoutError, ConnectionRefusedError, Exception) as e:
             print(f"Error processing page {i+1}: {e}")
             error_responses.append({"page": i+1, "error": str(e), "response": ai_response_text})
             # Save problematic response/prompt for debugging
             error_dir = os.path.join("backend", "api", "data", "debug_errors")
             os.makedirs(error_dir, exist_ok=True)
             error_output_path = os.path.join(error_dir, f"ollama_error_page_{i+1}.txt")
             try:
                 with open(error_output_path, "w", encoding="utf-8") as f:
                     f.write(f"--- PROMPT ---\n{single_role_prompt}\n\n--- RESPONSE ---\n{ai_response_text}")
                 print(f"Saved problematic response/prompt for page {i+1} to {error_output_path}")
             except Exception as write_e:
                 print(f"Failed to write error file for page {i+1}: {write_e}")

    # Step 3: Final checks and save output
    print(f"\n--- AI Processing Complete ---")
    print(f"Successfully extracted data for {len(all_roles_data)} roles.")
    
    if error_responses:
        print(f"Encountered errors on {len(error_responses)} pages. Check logs and 'debug_errors' directory.")
        # Optionally save a summary of errors
        error_summary_path = os.path.join("backend", "api", "data", "ollama_error_summary.json")
        try:
            with open(error_summary_path, "w", encoding="utf-8") as f:
                json.dump(error_responses, f, indent=2)
            print(f"Saved error summary to {error_summary_path}")
        except Exception as write_e:
            print(f"Failed to write error summary file: {write_e}")

    if not all_roles_data:
         print("Warning: Failed to extract any valid role data from the document.")
         # Decide if this should be an error or just return empty list
         # raise ValueError("Failed to extract any valid role data from the document.")

    if save_output and all_roles_data:
        output_dir = os.path.join("backend", "api", "data")
        os.makedirs(output_dir, exist_ok=True)
        # Use a different name to avoid overwriting docling output
        json_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(pdf_path))[0]}_extracted_roles.json") 
        print(f"Saving combined structured JSON ({len(all_roles_data)} roles) to {json_path}")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(all_roles_data, f, indent=2, ensure_ascii=False) # ensure_ascii=False for UTF-8
            print(f"Successfully saved JSON output.")
        except Exception as e:
            print(f"Error saving JSON file to {json_path}: {e}")

    return all_roles_data


if __name__ == "__main__":
    # Use the double-role PDF for testing this script's capability
    pdf_path = "backend/sample-double-role.pdf" 
    # pdf_path = "backend/sample-roles.pdf" # Or use the multi-page one
    
    output_dir = os.path.join("backend", "api", "data")
    os.makedirs(output_dir, exist_ok=True) # Ensure data directory exists

    try:
        structured_json_list = extract_roles_to_json(pdf_path, save_output=True)
        
        print("\n--- Main Execution Summary ---")
        if structured_json_list:
             print(f"Successfully processed PDF and extracted {len(structured_json_list)} role(s).")
             print("First extracted role:")
             # Pretty print the first role
             print(json.dumps(structured_json_list[0], indent=2, ensure_ascii=False)) 
             print(f"\nFull output saved to {output_dir}/{os.path.splitext(os.path.basename(pdf_path))[0]}_extracted_roles.json")
        else:
             print("Processing finished, but no valid role data was extracted.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ConnectionRefusedError as e:
         print(f"Error: {e}. Please ensure the Ollama service is running at http://localhost:11434.")
    except TimeoutError as e:
         print(f"Error: {e}. Ollama took too long to respond.")
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred during the main execution: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
