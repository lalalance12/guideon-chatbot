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
    SKIP_HEADINGS = {"skills and competencies", "skills & competencies", "skills & competency"}

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
            if not mat:
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

                    # Detect beginning of the skills sub‑section inside the same table
                    cell0 = row[fn_idx].lower()
                    if cell0.startswith("functional skills") or cell0.startswith("competencies"):
                        in_skill_section = True
                        continue  # header row, skip

                    # Rows *after* header or rows containing a Level cell → treat as skills
                    if in_skill_section or any(LEVEL_RE.match(c) for c in row):
                        # parse skill row → func + enabling
                        cols = row + ["", "", "", ""]  # pad
                        f_skill = row[fn_idx]
                        # first level after f_skill
                        f_level = next((c for c in cols[fn_idx + 1:] if LEVEL_RE.match(c)), None)
                        after_lvl_idx = cols.index(f_level) + 1 if f_level else fn_idx + 2
                        e_skill = cols[after_lvl_idx] if after_lvl_idx < len(cols) else ""
                        e_level = next((c for c in cols[after_lvl_idx + 1:] if LEVEL_RE.match(c)), None)
                        if f_skill and f_level:
                            role["functional_skills"].append({"skill": f_skill, "level": f_level})
                        if e_skill and e_level:
                            role["enabling_skills"].append({"skill": e_skill, "level": e_level})
                        continue  # do not treat as key‑task

                    # normal key‑task row
                    function = row[fn_idx]
                    tasks = []
                    for i in kt_idxes:
                        if i < len(row):
                            tasks.extend(split_bullets(row[i]))
                    if tasks:
                        role["key_tasks"].append({"function": function, "tasks": list(dict.fromkeys(tasks))})
                    if perf_idx is not None and perf_idx < len(row) and row[perf_idx]:
                        role["performance_expectations"].extend(split_bullets(row[perf_idx]))

            # Stand‑alone skills table (4/5‑column)
            elif any("functional skills" in h for h in headers_lc) or any("enabling skills" in h for h in headers_lc):
                for row in mat[1:]:
                    cols = row + ["", "", "", ""]
                    f_skill = cols[0]
                    f_level = next((c for c in cols[1:] if LEVEL_RE.match(c)), None)
                    after_lvl = cols.index(f_level) + 1 if f_level else 2
                    e_skill  = cols[after_lvl] if after_lvl < len(cols) else ""
                    e_level  = next((c for c in cols[after_lvl + 1:] if LEVEL_RE.match(c)), None)
                    if f_skill and f_level:
                        role["functional_skills"].append({"skill": f_skill, "level": f_level})
                    if e_skill and e_level:
                        role["enabling_skills"].append({"skill": e_skill, "level": e_level})

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
    md_cache = os.path.join(root, "backend", "api", "data", "raw_roles_markdown.md")
    json_out = os.path.join(root, "backend", "api", "data", "processed_roles.json")
 
    markdown_text = convert_pdf_to_markdown(pdf_path, md_cache)
    data = parse_roles(markdown_text)

    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done – extracted {len(data['roles'])} roles → {json_out}")
