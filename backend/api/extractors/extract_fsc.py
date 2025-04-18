# backend/api/utils/r.py
import os, re, json, io
import markdown as md
from bs4 import BeautifulSoup

# ---------- fast Docling conversion ---------------------------------
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
from docling.document_converter import PdfFormatOption, InputFormat

def convert_pdf_to_markdown(pdf_path: str, md_cache: str | None = None) -> str:
    if md_cache and os.path.exists(md_cache) \
            and os.path.getmtime(md_cache) > os.path.getmtime(pdf_path):
        with open(md_cache, encoding="utf-8") as f:
            return f.read()

    opts = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    conv = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(
            backend=DoclingParseV2DocumentBackend, pipeline_options=opts)
    })
    markdown = conv.convert(pdf_path).document.export_to_markdown()

    if md_cache:
        os.makedirs(os.path.dirname(md_cache), exist_ok=True)
        with open(md_cache, "w", encoding="utf-8") as f:
            f.write(markdown)
    return markdown
# --------------------------------------------------------------------


# ---------- helpers -------------------------------------------------
CODE   = re.compile(r'[A-Z]{3}-[A-Z]{3}\d?-\d{4}-1\.\d')   # AAI‑DIM1‑3001‑1.1

def bullets(raw_html_or_text: str) -> list[str]:
    """
    Extract list items from a cell, whether they are proper <li>,
    '•' bullets, or newline‑separated phrases.
    """
    soup = BeautifulSoup(raw_html_or_text, "lxml")
    li_tags = [li.get_text(" ", strip=True) for li in soup.find_all("li")]
    if li_tags:                             # HTML list detected
        return li_tags

    txt = soup.get_text(" ", strip=True)    # plain text fallback
    if "•" in txt:
        parts = txt.split("•")
    else:
        parts = re.split(r"\s{2,}|\n+", txt)   # split on double‑space / newline
    return [p.strip(" •").rstrip(".") for p in parts if p.strip(" •")]

def first_table_after(elem):
    sib = elem
    while sib := sib.find_next_sibling():
        if sib.name == "table":
            return sib
        if sib.name and sib.name.startswith("h"):
            return None
    return None

def table_has_fsc_code(table) -> bool:
    for tr in table.find_all("tr"):
        first = tr.find(["td", "th"])
        if first and first.get_text(strip=True) == "FSC Code":
            return True
    return False
# --------------------------------------------------------------------


def parse_fscs(markdown_text: str) -> list[dict]:
    html  = md.markdown(markdown_text, extensions=["tables"])
    soup  = BeautifulSoup(html, "lxml")

    sections: list[dict] = []

    for h2 in soup.find_all("h2"):
        table = first_table_after(h2)
        if not table or not table_has_fsc_code(table):
            continue

        fs = {
            "title":               h2.get_text(strip=True),
            "description":         "",
            "codePrefix":          "",
            "proficiencyLevels":   [],
            "rangeOfApplication":  {"title": "", "items": []}
        }

        desc = []
        for sib in h2.find_next_siblings():
            if sib == table or (sib.name and sib.name.startswith("h2")):
                break
            if sib.name == "p":
                txt = sib.get_text(" ", strip=True)
                if txt.lower().startswith("continue to next page"):
                    continue
                desc.append(txt)
        fs["description"] = " ".join(desc)

              # -------- collect tables for this FSC --------------------
        tables = [table]
        sib = table
        while True:
            sib = sib.find_next_sibling()
            if sib is None:
                break

            # hit another h2
            if sib.name and sib.name.startswith("h2"):
                # look ahead: if the very next table *after* this h2
                # does NOT contain an "FSC Code" row, treat that table
                # as part of the *current* FSC (it’s the functional‑skills table)
                nxt_tbl = first_table_after(sib)
                if nxt_tbl and not table_has_fsc_code(nxt_tbl):
                    tables.append(nxt_tbl)
                    # advance cursor to the end of that table
                    sib = nxt_tbl
                    continue
                else:
                    break

            if sib.name == "table":
                tables.append(sib)

        codes = CODE.findall(" ".join(t.get_text(" ", strip=True) for t in tables))
        if codes:
            m = re.match(r'([A-Z]{3}-[A-Z]{3}\d?)', codes[0])
            if m:
                fs["codePrefix"] = m.group(1)

        prof: dict[int, dict] = {}
        for tbl in tables:
            hdr_cells = [c.get_text(strip=True) for c in tbl.find("tr").find_all(["td","th"])]
            if not any("LEVEL" in h for h in hdr_cells):
                continue

            for tr in tbl.find_all("tr")[1:]:
                cells = tr.find_all(["td","th"])
                if not cells:
                    continue
                row_key = cells[0].get_text(strip=True)

                for idx, cell in enumerate(cells[1:], 1):
                    if idx >= len(hdr_cells) or "LEVEL" not in hdr_cells[idx]:
                        continue
                    level = int(hdr_cells[idx].replace("LEVEL", "").strip())
                    entry = prof.setdefault(level, {"level": level})   # --- NEW line

                    text  = cell.get_text(" ", strip=True)

                    if row_key == "FSC Code" and CODE.fullmatch(text):
                        entry["fscCode"] = text
                    elif row_key.startswith("FSC Proficiency") and text:
                        entry["description"] = text
                    elif "Underpinning" in row_key and "Knowledge" in row_key and text:
                        entry["underpinningKnowledge"] = bullets(text)
                    elif "Skills" in row_key and "Application" in row_key and text:
                        entry["skillsApplication"] = bullets(text)
                    elif re.search(r'Range\s+of\s+Application', row_key, re.I) and text:
                        # normalise internal spaces in the heading itself
                        clean_heading = re.sub(r'\s+', ' ', row_key).strip()
                        fs["rangeOfApplication"]["title"] = (
                            clean_heading.split(":", 1)[-1].strip() or "Range of Application"
                        )
                        fs["rangeOfApplication"]["items"] = bullets(text)

        for ent in prof.values():                    # default empty lists
            ent.setdefault("underpinningKnowledge", [])
            ent.setdefault("skillsApplication",   [])
        fs["proficiencyLevels"] = [prof[k] for k in sorted(prof)]

        sections.append({"functionalSkill": fs})

    return sections


# ----------------------------- CLI ----------------------------------
if __name__ == "__main__":
    root     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    pdf_path = os.path.join(root, "backend", "all-split-fsc.pdf")
    cache_md = os.path.join(root, "backend", "api", "data", "raw_markdown.md")
    json_out = os.path.join(root, "backend", "api", "data", "processed_data.json")

    md_text  = convert_pdf_to_markdown(pdf_path, cache_md)
    data     = parse_fscs(md_text)

    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done – extracted {len(data)} FSC sections → {json_out}")
