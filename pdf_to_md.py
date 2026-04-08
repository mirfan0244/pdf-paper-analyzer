from PyPDF2 import PdfReader
import json
import os
import re


def extract_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def build_extraction_prompt(raw_text, user_schema):
    return (
        "Extract metadata from this paper.\n\n"
        "Rules:\n"
        "1. Return EXACTLY one valid JSON object inside a ```json fenced block.\n"
        "2. After the JSON block, write ---BODY--- and then a short markdown summary.\n"
        "3. Do not write any explanation before or after.\n"
        "4. Ensure the JSON is valid and complete.\n\n"
        f"Schema:\n{user_schema}\n\n"
        "Required output format:\n"
        "```json\n"
        "{\n"
        '  "title": "",\n'
        '  "authors": [],\n'
        '  "year": "",\n'
        '  "research_field": "",\n'
        '  "methodology": "",\n'
        '  "keywords": [],\n'
        '  "summary": ""\n'
        "}\n"
        "```\n"
        "---BODY---\n"
        "Markdown summary here\n\n"
        f"Paper text:\n{raw_text[:30000]}"
    )


def parse_llm_response(response_text):
    metadata = {}
    body = ""

    if "---BODY---" in response_text:
        body = response_text.split("---BODY---", 1)[1].strip()

    match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try:
            metadata = json.loads(json_str)
            return metadata, body
        except json.JSONDecodeError:
            pass

    match = re.search(r"(\{.*\})", response_text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError as e:
            metadata = {
                "_parse_error": str(e),
                "_raw_response_preview": response_text[:2000]
            }

    return metadata, body


def save_markdown(output_dir, filename, metadata, body):
    os.makedirs(output_dir, exist_ok=True)

    lines = ["---"]
    for k, v in metadata.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                safe_item = str(item).replace('"', '\\"')
                lines.append(f'  - "{safe_item}"')
        else:
            safe_value = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{safe_value}"')

    lines.extend(["---", "", body])

    md_path = os.path.join(output_dir, filename.replace(".pdf", ".md"))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return md_path


def load_all_metadata(md_dir):
    all_meta = []

    if not os.path.exists(md_dir):
        return all_meta

    for fname in sorted(os.listdir(md_dir)):
        if not fname.endswith(".md"):
            continue

        file_path = os.path.join(md_dir, fname)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.startswith("---"):
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1].strip().split("\n")
        meta = {"_filename": fname}
        current_key = None
        current_list = []

        for line in frontmatter:
            if line.startswith("  - "):
                current_list.append(line.strip()[2:].strip('"'))
            else:
                if current_key and current_list:
                    meta[current_key] = json.dumps(current_list)
                    current_list = []

                if ": " in line:
                    k, v = line.split(": ", 1)
                    v = v.strip().strip('"')
                    if v in ("", "|"):
                        current_key = k
                    else:
                        meta[k] = v
                        current_key = None
                elif line.endswith(":"):
                    current_key = line[:-1].strip()
                else:
                    current_key = None

        if current_key and current_list:
            meta[current_key] = json.dumps(current_list)

        all_meta.append(meta)

    return all_meta