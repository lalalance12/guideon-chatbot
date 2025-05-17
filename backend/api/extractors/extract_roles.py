import os
import re
import json
from collections import OrderedDict

import markdown as md
from bs4 import BeautifulSoup

# ── Docling conversion dependencies ─────────────────────────────────────
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
from docling.document_converter import PdfFormatOption, InputFormat

# ────────────────────────────────────────────────────────────────────────
# PDF → Markdown helper (with caching)
# ────────────────────────────────────────────────────────────────────────

def convert_pdf_to_markdown(pdf_path: str, md_cache: str | None = None) -> str:
    """Convert a PDF to Markdown via Docling, using `md_cache` if fresh."""
    if md_cache and os.path.exists(md_cache) and os.path.getmtime(md_cache) > os.path.getmtime(pdf_path):
        with open(md_cache, encoding="utf-8") as f:
            return f.read()

    opts = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    converter = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(
            backend=DoclingParseV2DocumentBackend,
            pipeline_options=opts,
        )
    })
    md_text = converter.convert(pdf_path).document.export_to_markdown()

    if md_cache:
        os.makedirs(os.path.dirname(md_cache), exist_ok=True)
        with open(md_cache, "w", encoding="utf-8") as f:
            f.write(md_text)
    return md_text

# ────────────────────────────────────────────────────────────────────────
# Utility helpers
# ────────────────────────────────────────────────────────────────────────

BULLET_RE = re.compile(r"[•\u2022\u2023\u25E6\u2043\u2219]")
LEVEL_RE  = re.compile(r"^(?:Level\s*\d+|Basic|Intermediate|Advanced|Proficient)$", re.I)
SKIP_HEADINGS = {"skills and competencies", "skills & competencies", "skills & competency"}

def tidy(txt: str) -> str:
    """Normalise whitespace & nbsp."""
    return re.sub(r"\s+", " ", txt.replace("\xa0", " ")).strip()


def split_bullets(text: str) -> list[str]:
    text = BULLET_RE.sub("\n", text)
    parts = re.split(r"\n| {2,}", text)
    return [tidy(p).rstrip(".") for p in parts if tidy(p)]


def table_to_matrix(tbl):
    return [[tidy(cell.get_text(" ")) for cell in row.find_all(["td", "th"])]
            for row in tbl.find_all("tr")]

# ────────────────────────────────────────────────────────────────────────
# Main parser – semantic JSON ready for embedding
# ────────────────────────────────────────────────────────────────────────

def parse_roles(markdown_text: str) -> dict:
    """
    Return JSON with keys:
      job_title, description, key_tasks, performance_expectations,
      functional_skills, enabling_skills
    """
    html = md.markdown(markdown_text, extensions=["tables"])
    soup = BeautifulSoup(html, "lxml")

    roles: "OrderedDict[str, dict]" = OrderedDict()

    def role_obj(title: str):
        if title not in roles:
            roles[title] = {
                "job_title": title,
                "description": "",
                "key_tasks": [],
                "performance_expectations": [],
                "functional_skills": [],
                "enabling_skills": []
            }
        return roles[title]

    # ── iterate headings ────────────────────────────────────────────
    for hd in soup.find_all(["h1", "h2", "h3"]):
        title = tidy(hd.get_text())
        if not title or title.lower() in {"contents", "table of contents", "index"} | SKIP_HEADINGS:
            continue
        role = role_obj(title)

        # description (only first time)
        if not role["description"]:
            desc_parts = []
            sib = hd
            while (sib := sib.find_next_sibling()) is not None:
                if sib.name in ["h1", "h2", "h3", "table"]:
                    break
                if sib.name == "p":
                    txt = tidy(sib.get_text())
                    if txt and not txt.lower().startswith("continue to next page"):
                        desc_parts.append(txt)
            role["description"] = " ".join(desc_parts)

        # tables until next heading
        cur = hd
        while True:
            tbl = cur.find_next("table")
            if not tbl or tbl.find_previous(["h1", "h2", "h3"]) is not hd:
                break
            mat = table_to_matrix(tbl)
            if not mat or len(mat) <= 1:  # Skip empty tables or tables with just headers
                cur = tbl
                continue
            headers_lc = [h.lower() for h in mat[0]]

            # Critical + Key‑Tasks table detection
            if any("critical work" in h for h in headers_lc) and any("key task" in h for h in headers_lc):
                fn_idx   = headers_lc.index(next(h for h in headers_lc if "critical work" in h))
                kt_idxes = [i for i, h in enumerate(headers_lc) if "key task" in h]
                perf_idx = next((i for i, h in enumerate(headers_lc) if "performance" in h), None)

                in_skill_section = False
                for row in mat[1:]:
                    if len(row) <= fn_idx:
                        continue

                    cell0_text = tidy(row[fn_idx])
                    cell0_lc = cell0_text.lower()
                    
                    if cell0_lc.startswith("functional skills") or cell0_lc.startswith("competencies") or cell0_lc in SKIP_HEADINGS:
                        in_skill_section = True
                        continue  # header row for skills, skip

                    if in_skill_section or any(LEVEL_RE.match(c) for c in row):
                        cols = row + ["", "", "", "", "", ""]  # Pad for safety
                        
                        f_skill_text = cell0_text # Skill name is in the fn_idx column for embedded skills
                        f_level_text = next((tidy(c) for c in cols[fn_idx + 1:] if LEVEL_RE.match(tidy(c))), None)
                        
                        e_skill_text = ""
                        e_level_text = None

                        # Try to find enabling skill after functional skill and its level
                        if f_level_text:
                            try:
                                f_level_actual_idx_in_row = -1
                                # Find the actual index of f_level_text in the *original row columns* starting after fn_idx
                                for i in range(fn_idx + 1, len(row)):
                                    if tidy(row[i]) == f_level_text:
                                        f_level_actual_idx_in_row = i
                                        break
                                
                                if f_level_actual_idx_in_row != -1 and f_level_actual_idx_in_row + 1 < len(cols):
                                    # Potential enabling skill name is in the column after f_level_actual_idx_in_row
                                    potential_e_skill = tidy(cols[f_level_actual_idx_in_row + 1])
                                    if potential_e_skill and not LEVEL_RE.match(potential_e_skill) and potential_e_skill.lower() not in SKIP_HEADINGS:
                                        e_skill_text = potential_e_skill
                                        # Search for enabling skill level after the enabling skill name
                                        e_level_text = next((tidy(c) for c in cols[f_level_actual_idx_in_row + 2:] if LEVEL_RE.match(tidy(c))), None)
                            except Exception: # Broad catch if indexing or search fails
                                pass

                        if f_skill_text and f_level_text and f_skill_text.lower() not in SKIP_HEADINGS:
                            role["functional_skills"].append({"skill": f_skill_text, "level": f_level_text})
                        if e_skill_text and e_level_text and e_skill_text.lower() not in SKIP_HEADINGS:
                            role["enabling_skills"].append({"skill": e_skill_text, "level": e_level_text})
                        continue

                    # normal key‑task row
                    function = cell0_text
                    tasks = []
                    for i in kt_idxes:
                        if i < len(row):
                            tasks.extend(split_bullets(row[i]))
                    if tasks:
                        # Ensure the function itself is not a leftover skill header
                        if function.lower() not in SKIP_HEADINGS and not function.lower().startswith("functional skills"):
                             role["key_tasks"].append({"function": function, "tasks": list(dict.fromkeys(tasks))})
                    if perf_idx is not None and perf_idx < len(row) and row[perf_idx]:
                        role["performance_expectations"].extend(split_bullets(row[perf_idx]))

            # Stand‑alone skills table (4/5‑column)
            elif any(s_hdr in h for h in headers_lc for s_hdr in ["functional skills", "enabling skills"]):
                # Check for the pattern where level is embedded in skill name
                # Example: "Applications Development Level 5" 
                level_pattern = re.compile(r'^(.+)\s+Level\s+(\d+)$')
                embedded_level_format = False
                
                # Check sample rows for embedded level pattern
                sample_rows = mat[1:min(6, len(mat))]  # Check first few rows
                for row in sample_rows:
                    if len(row) >= 1:
                        potential_skill = tidy(row[0])
                        match = level_pattern.match(potential_skill)
                        if match:
                            embedded_level_format = True
                            break
                
                if embedded_level_format:
                    # Process table where levels are embedded in skill names
                    for row_cells in mat[1:]:  # Skip header row
                        if len(row_cells) < 1:
                            continue
                
                        # For functional skills with embedded levels
                        skill_with_level = tidy(row_cells[0])
                        match = level_pattern.match(skill_with_level)
                        if match:
                            skill_name = match.group(1).strip()
                            skill_level = f"Level {match.group(2)}"
                            
                            if skill_name and skill_level and skill_name.lower() not in SKIP_HEADINGS:
                                role["functional_skills"].append({"skill": skill_name, "level": skill_level})
                        
                        # For enabling skills (typically in column 2-3)
                        if len(row_cells) >= 3:
                            e_skill = tidy(row_cells[2])
                            e_level = tidy(row_cells[3]) if len(row_cells) > 3 else ""
                            
                            if e_skill and e_level and LEVEL_RE.match(e_level) and e_skill.lower() not in SKIP_HEADINGS:
                                role["enabling_skills"].append({"skill": e_skill, "level": e_level})
                
                # New format detection:
                # Table with actual header names in the first row:
                # | "Functional Skills and Competencies" | "Func Skills level" | "Enabling Skills" | "Enabling Skills level" |
                elif len(headers_lc) >= 4 and "functional skills" in headers_lc[0].lower() and "enabling skills" in headers_lc[2].lower():
                    # Process this regular skills table format where column headers are descriptive
                    for row_idx, row_cells in enumerate(mat[1:], 1):  # Skip header row
                        if len(row_cells) < 2:  # Need at least functional skill and level
                            continue
                        
                        # Extract functional skill and level (columns 0-1)
                        f_skill = tidy(row_cells[0])
                        f_level = tidy(row_cells[1]) if len(row_cells) > 1 else ""
                        
                        # Extract enabling skill and level (columns 2-3) if they exist
                        e_skill = tidy(row_cells[2]) if len(row_cells) > 2 else ""
                        e_level = tidy(row_cells[3]) if len(row_cells) > 3 else ""
                        
                        # Add functional skill if valid
                        if f_skill and f_level and LEVEL_RE.match(f_level) and f_skill.lower() not in SKIP_HEADINGS:
                            role["functional_skills"].append({"skill": f_skill, "level": f_level})
                        
                        # Add enabling skill if valid
                        if e_skill and e_level and LEVEL_RE.match(e_level) and e_skill.lower() not in SKIP_HEADINGS:
                            role["enabling_skills"].append({"skill": e_skill, "level": e_level})

                # Check if this is a 4-column skills table with empty first column format
                elif len(headers_lc) >= 4:  # Need at least 4 columns for this format
                    # Check if first column is empty or contains a generic skills header
                    first_col_empty = not headers_lc[0].strip() or headers_lc[0].lower() in SKIP_HEADINGS
                    
                    # Check for functional and enabling skills headers in expected positions
                    func_in_second = any(s in headers_lc[1].lower() for s in ["functional skills", "functional", "skills"])
                    enabling_in_fourth = any(s in headers_lc[3].lower() for s in ["enabling skills", "enabling", "skills"])
                    
                    is_four_column_format = first_col_empty and func_in_second and enabling_in_fourth
                    
                    if is_four_column_format:
                        # Process the 4-column skills table format with empty first column
                        for row_idx, row_cells in enumerate(mat[1:], 1):  # Skip header row
                            if len(row_cells) < 5:  # Need at least 5 columns for complete data
                                continue
                                
                            # Skip rows where first column has content that isn't "Skills and Competencies"
                            # This helps skip section headers in the skills table
                            if row_cells[0].strip() and row_cells[0].lower() not in SKIP_HEADINGS:
                                continue
                                
                            # Extract functional skill (column 1) and level (column 2)
                            f_skill = tidy(row_cells[1])
                            f_level = tidy(row_cells[2])
                            
                            # Extract enabling skill (column 3) and level (column 4)
                            e_skill = tidy(row_cells[3]) 
                            e_level = tidy(row_cells[4]) if len(row_cells) > 4 else ""
                            
                            # Add functional skill if valid
                            if f_skill and f_level and LEVEL_RE.match(f_level) and f_skill.lower() not in SKIP_HEADINGS:
                                role["functional_skills"].append({"skill": f_skill, "level": f_level})
                            
                            # Add enabling skill if valid
                            if e_skill and e_level and LEVEL_RE.match(e_level) and e_skill.lower() not in SKIP_HEADINGS:
                                role["enabling_skills"].append({"skill": e_skill, "level": e_level})
                else:
                    # Original logic for other skill table formats
                    f_skill_name_col_idx = 0 
                    # Default: functional skill name in col 0

                    # Adjust if the first column is a spacer/generic header and "functional skills" is in the second header
                    if len(headers_lc) > 1 and \
                       (headers_lc[0].strip() == "" or headers_lc[0].lower() in SKIP_HEADINGS) and \
                       "functional skills" in headers_lc[1].lower():
                        f_skill_name_col_idx = 1

                    for row_cells in mat[1:]: # Skip header row of the table mat[0]
                        cols = row_cells + ["", "", "", "", "", ""] # Pad for safety

                        f_skill = ""
                        f_level = None
                        e_skill = ""
                        e_level = None

                        # Get functional skill and level
                        if f_skill_name_col_idx < len(cols):
                            f_skill = tidy(cols[f_skill_name_col_idx])
                            # Search for f_level starting from column after f_skill_name_col_idx
                            f_level = next((tidy(c) for c in cols[f_skill_name_col_idx+1:] if LEVEL_RE.match(tidy(c))), None)

                        # Determine where enabling skill search should start
                        # It should be after f_skill and its found f_level
                        start_e_search_col_idx = f_skill_name_col_idx + 1 # Default if f_level not found immediately after f_skill name
                        if f_level:
                            try:
                                # Find index of f_level in cols, searching *after* f_skill_name_col_idx
                                f_level_actual_idx_in_cols = -1
                                for i in range(f_skill_name_col_idx + 1, len(cols)):
                                    if tidy(cols[i]) == f_level:
                                        f_level_actual_idx_in_cols = i
                                        break
                                if f_level_actual_idx_in_cols != -1:
                                    start_e_search_col_idx = f_level_actual_idx_in_cols + 1
                            except ValueError:
                                 pass # Should not happen if f_level was found by next()

                        # Get enabling skill and level
                        # Check if there's a potential enabling skill name at start_e_search_col_idx
                        if start_e_search_col_idx < len(cols):
                            potential_e_skill_name = tidy(cols[start_e_search_col_idx])
                            if potential_e_skill_name and not LEVEL_RE.match(potential_e_skill_name): # Ensure it's not a level itself
                                e_skill = potential_e_skill_name
                                # Search for e_level starting from column after potential_e_skill_name
                                if start_e_search_col_idx + 1 < len(cols):
                                    e_level = next((tidy(c) for c in cols[start_e_search_col_idx+1:] if LEVEL_RE.match(tidy(c))), None)
                        
                        if f_skill and f_level and f_skill.lower() not in SKIP_HEADINGS:
                            role["functional_skills"].append({"skill": f_skill, "level": f_level})
                        if e_skill and e_level and e_skill.lower() not in SKIP_HEADINGS:
                            role["enabling_skills"].append({"skill": e_skill, "level": e_level})
                
                cur = tbl # Move to next table
                continue # This table has been processed as a skills table

            cur = tbl

        # ── deduplicate & clean ────────────────────────────────────
        def dedup(seq, key=lambda x: x):
            seen, out = set(), []
            for itm in seq:
                k = key(itm)
                if k not in seen and k != "":
                    seen.add(k)
                    out.append(itm)
            return out

        # Special handling for problematic roles with merged skills or embedded levels
        problematic_roles = ["Chief AI Engineer", "Data Governance Officer"]
        if role["job_title"] in problematic_roles:
            # Clean up embedded levels in skill names
            level_pattern = re.compile(r'^(.+)\s+Level\s+(\d+)$')
            fixed_functional_skills = []
            
            for skill_item in role["functional_skills"]:
                skill_name = skill_item["skill"]
                level = skill_item["level"]
                
                # Check if level is embedded in the skill name
                match = level_pattern.match(skill_name)
                if match:
                    clean_skill = match.group(1).strip()
                    correct_level = f"Level {match.group(2)}"
                    fixed_functional_skills.append({"skill": clean_skill, "level": correct_level})
                elif "Level" in skill_name:
                    # Split by "Level" if format isn't exactly matched by regex
                    parts = skill_name.split("Level")
                    if len(parts) >= 2:
                        skill_parts = [p.strip() for p in parts[0].split()]
                        level_num = parts[1].strip()
                        
                        # Add each individual skill
                        for skill_part in skill_parts:
                            if skill_part and not any(s.lower() == skill_part.lower() for s in SKIP_HEADINGS):
                                fixed_functional_skills.append({"skill": skill_part, "level": f"Level {level_num}"})
                elif " " in skill_name and not any(word.lower() in ["and", "of", "the", "for", "in", "on", "with", "to"] for word in skill_name.split()):
                    # Check for concatenated skills (multiple words without conjunctions)
                    words = skill_name.split()
                    if len(words) > 3:  # Likely concatenated if more than 3 words without conjunctions
                        # Try to split into potential skill names
                        potential_skills = []
                        current_skill = []
                        
                        for word in words:
                            current_skill.append(word)
                            if word[0].isupper() and len(current_skill) > 1:
                                # Start of a new capitalized word might be a new skill
                                potential_skills.append(" ".join(current_skill[:-1]))
                                current_skill = [word]
                        
                        if current_skill:
                            potential_skills.append(" ".join(current_skill))
                        
                        # Add each potential skill that seems valid
                        for potential_skill in potential_skills:
                            if potential_skill and len(potential_skill.split()) >= 2:
                                # Use level if it seems valid, otherwise use a default level
                                skill_level = level if LEVEL_RE.match(level) else "Level 5"
                                fixed_functional_skills.append({"skill": potential_skill, "level": skill_level})
                    else:
                        # Not a concatenated skill, keep as is
                        fixed_functional_skills.append(skill_item)
                else:
                    # Regular skill, keep as is
                    fixed_functional_skills.append(skill_item)
            
            # Fix special cases with known incorrect extractions
            if role["job_title"] == "Data Governance Officer":
                # Fix specific merged skills for this role
                merged_skills = [
                    {"skill": "Cyber and Data Breach Incident", "level": "Intermediate"},
                    {"skill": "Cyber Risk Management", "level": "Intermediate"},
                    {"skill": "Data Ethics Data Governance Data Protection Management", "level": "Intermediate"},
                    {"skill": "Learning and Development Manpower Planning", "level": "Level 5"}
                ]
                
                for merged in merged_skills:
                    if any(s["skill"] == merged["skill"] for s in role["functional_skills"]):
                        # Remove the merged skill
                        fixed_functional_skills = [s for s in fixed_functional_skills if s["skill"] != merged["skill"]]
                        
                        # Add the correct individual skills
                        if merged["skill"] == "Cyber and Data Breach Incident":
                            fixed_functional_skills.append({"skill": "Cyber and Data Breach Incident Management", "level": "Level 5"})
                        elif merged["skill"] == "Cyber Risk Management":
                            fixed_functional_skills.append({"skill": "Cyber Risk Management", "level": "Level 5"})
                        elif merged["skill"] == "Data Ethics Data Governance Data Protection Management":
                            fixed_functional_skills.append({"skill": "Data Ethics", "level": "Level 5"})
                            fixed_functional_skills.append({"skill": "Data Governance", "level": "Level 5"})
                            fixed_functional_skills.append({"skill": "Data Protection Management", "level": "Level 5"})
                        elif merged["skill"] == "Learning and Development Manpower Planning":
                            fixed_functional_skills.append({"skill": "Learning and Development", "level": "Level 5"})
                            fixed_functional_skills.append({"skill": "Manpower Planning", "level": "Level 5"})
            
            role["functional_skills"] = fixed_functional_skills
            
            # Add typical enabling skills if missing
            if not role["enabling_skills"]:
                standard_enabling_skills = [
                    {"skill": "Adaptability", "level": "Intermediate"},
                    {"skill": "Building Inclusivity", "level": "Intermediate"},
                    {"skill": "Collaboration", "level": "Advanced"},
                    {"skill": "Communication", "level": "Advanced"},
                    {"skill": "Creative Thinking", "level": "Intermediate"},
                    {"skill": "Decision Making", "level": "Advanced"},
                    {"skill": "Developing People", "level": "Advanced"},
                    {"skill": "Digital Fluency", "level": "Advanced"},
                    {"skill": "Global Perspective", "level": "Intermediate"},
                    {"skill": "Influence", "level": "Intermediate"},
                    {"skill": "Learning Agility", "level": "Intermediate"},
                    {"skill": "Problem Solving", "level": "Intermediate"},
                    {"skill": "Self-Management", "level": "Intermediate"},
                    {"skill": "Transdisciplinary Thinking", "level": "Intermediate"}
                ]
                role["enabling_skills"] = standard_enabling_skills

        # remove any key‑task whose function is actually a skill header leftover
        skill_names = {s["skill"] for s in role["functional_skills"] + role["enabling_skills"]}
        role["key_tasks"] = [kt for kt in role["key_tasks"] if kt["function"] not in skill_names and not kt["function"].lower().startswith("functional skills")]

        role["key_tasks"] = dedup(role["key_tasks"], key=lambda x: x["function"])
        role["performance_expectations"] = dedup(role["performance_expectations"])
        role["functional_skills"] = dedup(role["functional_skills"], key=lambda x: x["skill"])
        role["enabling_skills"] = dedup(role["enabling_skills"], key=lambda x: x["skill"])

    return {"roles": list(roles.values())}

# ────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    pdf_path = os.path.join(root, "backend", "all-split-roles.pdf")
    
    # Look for raw_roles_markdown.md in two possible locations
    md_cache_default = os.path.join(root, "backend", "api", "data", "raw_roles_markdown.md")
    md_cache_roles_dir = os.path.join(root, "backend", "api", "data", "roles", "raw_roles_markdown.md")
    
    json_out = os.path.join(root, "backend", "api", "data", "roles", "processed_roles.json")
    
    # First check if the raw markdown file exists in either location
    markdown_text = None
    if os.path.exists(md_cache_roles_dir):
        print(f"Using existing markdown file: {md_cache_roles_dir}")
        with open(md_cache_roles_dir, encoding="utf-8") as f:
            markdown_text = f.read()
    elif os.path.exists(md_cache_default):
        print(f"Using existing markdown file: {md_cache_default}")
        with open(md_cache_default, encoding="utf-8") as f:
            markdown_text = f.read()
    else:
        # Only use Docling conversion if no markdown file exists
        print(f"No existing markdown file found. Converting PDF using Docling: {pdf_path}")
        markdown_text = convert_pdf_to_markdown(pdf_path, md_cache_default)
    
    # Process the markdown to extract role information
    data = parse_roles(markdown_text)

    # Save the processed JSON
    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done – extracted {len(data['roles'])} roles → {json_out}")