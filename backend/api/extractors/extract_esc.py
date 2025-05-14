# backend/api/utils/r.py

import os
import re
import json
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
            backend=DoclingParseV2DocumentBackend,
            pipeline_options=opts
        )
    })
    markdown = conv.convert(pdf_path).document.export_to_markdown()

    if md_cache:
        os.makedirs(os.path.dirname(md_cache), exist_ok=True)
        with open(md_cache, "w", encoding="utf-8") as f:
            f.write(markdown)
    return markdown
# --------------------------------------------------------------------

# match e.g. ESC-SRE-B001-1, ESC-IWO-A002-1, etc.
CODE = re.compile(r'ESC-[A-Z]{3}-[BIA]\d{3}-1')

def bullets(raw: str) -> list[str]:
    """
    Extract list items from a cell, preserving long lines.
    """
    soup = BeautifulSoup(raw, "lxml")
    items = [li.get_text(" ", strip=True) for li in soup.find_all("li")]
    if items:
        return items

    txt = soup.get_text(" ", strip=True)
    if "•" in txt:
        parts = txt.split("•")
    else:
        # split only on actual newlines
        parts = re.split(r"\n+", txt)
    return [p.strip(" •").rstrip(".") for p in parts if p.strip(" •")]

def first_table_after(elem):
    sib = elem
    while sib := sib.find_next_sibling():
        if sib.name == "table":
            return sib
        if sib.name and sib.name.startswith("h"):
            return None
    return None

def table_has_esc_codes(table) -> bool:
    return bool(CODE.search(table.get_text(" ", strip=True)))

def parse_escs(markdown_text: str) -> list[dict]:
    html = md.markdown(markdown_text, extensions=["tables"])
    soup = BeautifulSoup(html, "lxml")
    sections = []

    LEVEL_MAP   = {"BASIC":"Basic","INTERMEDIATE":"Intermediate","ADVANCED":"Advanced"}
    LEVEL_ORDER = ["Basic","Intermediate","Advanced"]

    for h2 in soup.find_all("h2"):
        prof_tbl = first_table_after(h2)
        if not prof_tbl or not table_has_esc_codes(prof_tbl):
            continue

        esc = {
            "title":               h2.get_text(strip=True),
            "description":         "",
            "codePrefix":          "",
            "proficiencyLevels":   [],
            "rangeOfApplication":  {"title":"Range of Application","items":[]}
        }

        # 1-line description
        desc = []
        for sib in h2.find_next_siblings():
            if sib == prof_tbl or (sib.name and sib.name.startswith("h2")):
                break
            if sib.name == "p":
                desc.append(sib.get_text(" ", strip=True))
        esc["description"] = " ".join(desc).strip()

        # codePrefix
        codes = CODE.findall(prof_tbl.get_text(" ", strip=True))
        if codes:
            esc["codePrefix"] = codes[0].rsplit("-",2)[0]

        prof_map   = {}
        headers    = [c.get_text(" ",strip=True).upper() 
                      for c in prof_tbl.find("tr").find_all(["td","th"])]

        for tr in prof_tbl.find_all("tr")[1:]:
            cells   = tr.find_all(["td","th"])
            raw_key = cells[0].get_text(" ", strip=True).strip()
            row_key = raw_key.upper()

            # skip entirely empty rows
            if not any(c.get_text(strip=True) for c in cells[1:]):
                continue

            # 1) Code row
            if not raw_key and any(CODE.fullmatch(c.get_text(strip=True)) for c in cells[1:]):
                for idx,cell in enumerate(cells[1:],start=1):
                    hdr = headers[idx]
                    if hdr in LEVEL_MAP:
                        lvl = LEVEL_MAP[hdr]
                        ent = prof_map.setdefault(lvl, {"level":lvl})
                        txt = cell.get_text(strip=True)
                        if CODE.fullmatch(txt):
                            ent["escCode"] = txt

            # 2) Proficiency description row
            elif "PROFICIENCY" in row_key:
                for idx,cell in enumerate(cells[1:],start=1):
                    hdr = headers[idx]
                    if hdr in LEVEL_MAP:
                        lvl = LEVEL_MAP[hdr]
                        ent = prof_map.setdefault(lvl, {"level":lvl})
                        text = cell.get_text(" ", strip=True)
                        m    = CODE.search(text)
                        if m:
                            ent["escCode"]      = m.group(0)
                            ent["description"]  = text[m.end():].strip()
                        else:
                            ent["description"]  = text

            # 3) UNDERPINNING row (now before Skills!)
            elif (
                "UNDERPINNING" in row_key
                or (
                    not raw_key
                    and not any(CODE.fullmatch(c.get_text(strip=True)) for c in cells[1:])
                    and not ("SKILLS" in row_key and "APPLICATION" in row_key)
                    and any(c.get_text(strip=True).startswith("•") for c in cells[1:])
                )
            ):
                for idx,cell in enumerate(cells[1:],start=1):
                    hdr = headers[idx]
                    if hdr in LEVEL_MAP:
                        lvl = LEVEL_MAP[hdr]
                        ent = prof_map.setdefault(lvl, {"level":lvl})
                        txt = cell.get_text(" ", strip=True)
                        txt = re.sub(r'^[Uu]nderpinning\s+Knowledge\s*•?\s*', '', txt)
                        ent["underpinningKnowledge"] = bullets(txt)

            # 4) Skills Application
            elif "SKILLS" in row_key and "APPLICATION" in row_key:
                for idx,cell in enumerate(cells[1:],start=1):
                    hdr = headers[idx]
                    if hdr in LEVEL_MAP:
                        lvl = LEVEL_MAP[hdr]
                        ent = prof_map.setdefault(lvl, {"level":lvl})
                        ent["skillsApplication"] = bullets(cell.get_text(" ", strip=True))

            # 5) Range of Application
            elif "RANGE" in row_key:
                items = []
                for cell in cells[1:]:
                    items += bullets(cell.get_text(" ", strip=True))
                esc["rangeOfApplication"]["items"] = items

        # defaults + ordering
        for lvl in LEVEL_ORDER:
            if lvl in prof_map:
                ent = prof_map[lvl]
                ent.setdefault("escCode", "")
                ent.setdefault("description", "")
                ent.setdefault("underpinningKnowledge", [])
                ent.setdefault("skillsApplication", [])

        esc["proficiencyLevels"] = [prof_map[l] for l in LEVEL_ORDER if l in prof_map]
        sections.append({"enablingSkill":esc})

    return sections


# ----------------------------- CLI ----------------------------------
if __name__ == "__main__":
    root     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    pdf_path = os.path.join(root, "backend", "all-split-esc.pdf")
    cache_md = os.path.join(root, "backend", "api", "data", "raw_esc.md")
    json_out = os.path.join(root, "backend", "api", "data", "esc_data.json")

    md_text  = convert_pdf_to_markdown(pdf_path, cache_md)
    data     = parse_escs(md_text)

    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done – extracted {len(data)} ESC sections → {json_out}")
