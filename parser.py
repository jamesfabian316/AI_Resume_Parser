import logging
import pdfplumber
import spacy
import re
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)

nlp = spacy.load("en_core_web_sm")
HF_API_TOKEN = (
    "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"  # Replace with your Hugging Face token
)

# Precompiled regex patterns for performance
email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
phone_regex = re.compile(r"(\+\d{1,3}-?)?\d{3}-?\d{3}-?\d{4}")
education_regex = re.compile(
    r"(college|university|institute|iit|b\.\w+\.|m\.\w+\.|phd|pursuing|\d{4}.*\d{4}|\d{4}-present)",
    re.IGNORECASE,
)
work_title_regex = re.compile(
    r"[\|\$\.\•]+.*(react|javascript|python|css|html|typescript|mysql)",
    re.IGNORECASE,
)
work_date_regex = re.compile(r"\d{4}.*(present|\d{4})", re.IGNORECASE)
skills_regex = re.compile(r"^(www\.|\d+|-+|\s+|james|fabian|linkedin|github|es6\+)")
skills_noise_regex = re.compile(
    r"^(to|and|for|a|of|the|in|by|with|from|on|at)$", re.IGNORECASE
)


def extract_text_from_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        text = "".join(page.extract_text() or "" for page in pdf.pages)
        logging.info("Extracted Text: %s...", text[:200])
    return text


def extract_basic_info(text):
    doc = nlp(text)
    info = {"name": "", "email": "", "phone": ""}
    for ent in doc.ents:
        if ent.label_ == "PERSON" and not info["name"]:
            name = " ".join(ent.text.split()).strip()
            # Remove trailing phone-like digits (7+ consecutive digits)
            info["name"] = re.sub(r"\s*\d{7,}", "", name).strip()
            break
    if not info["name"]:
        first_line = text.split("\n")[0].strip()
        info["name"] = re.sub(r"[\d\-\+\s]{7,}", "", first_line).strip()
    email_match = email_regex.search(text)
    info["email"] = email_match.group() if email_match else ""
    phone_match = phone_regex.search(text)
    info["phone"] = phone_match.group() if phone_match else ""
    return info


def extract_sections(text):
    lines = text.split("\n")
    sections = {
        "education": [],
        "work_experience": [],
        "skills": [],
        "hobbies": [],
        "awards": [],
        "volunteering": [],
        "projects": [],
    }
    current_section = None
    work_entries = []  # Accumulate raw work lines

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower_line = stripped.lower()
        # Detect section headers
        if "technical skills" in lower_line:
            current_section = "skills"
            continue
        elif "professional experience" in lower_line:
            current_section = "work_experience"
            continue
        elif "education" in lower_line:
            current_section = "education"
            continue
        elif "interests & hobbies" in lower_line:
            current_section = "hobbies"
            continue
        elif "awards" in lower_line or "achievements" in lower_line:
            current_section = "awards"
            continue
        elif "volunteer" in lower_line or "volunteering" in lower_line:
            current_section = "volunteering"
            continue
        elif "project" in lower_line:
            current_section = "projects"
            continue

        # Process lines within detected sections
        if current_section == "education":
            if education_regex.search(lower_line):
                sections["education"].append({"degree": stripped})
        elif current_section == "work_experience":
            work_entries.append(stripped)
        elif current_section == "skills":
            if ":" in stripped:
                parts = stripped.split(":", 1)[1]
                for candidate in parts.split(","):
                    skill = candidate.strip()
                    if (
                        skill
                        and len(skill) >= 3
                        and len(skill.split()) <= 3
                        and not skills_regex.search(skill.lower())
                    ):
                        sections["skills"].append(skill)
        elif current_section == "hobbies":
            sections["hobbies"].append(stripped)
        elif current_section == "awards":
            sections["awards"].append(stripped)
        elif current_section == "volunteering":
            sections["volunteering"].append(stripped)
        elif current_section == "projects":
            sections["projects"].append(stripped)

    sections["work_experience"] = combine_work_experience_entries(work_entries)
    sections["skills"] = list(
        set(
            clean_skill(s)
            for s in sections["skills"]
            if s and not skills_noise_regex.search(s)
        )
    )
    return sections


def combine_work_experience_entries(entries):
    combined = []
    buffer = ""
    for entry in entries:
        clean_entry = entry.strip()
        # Start a new entry if bullet is detected or a header marker exists.
        if clean_entry.startswith("•"):
            if buffer:
                combined.append({"description": buffer.strip()})
            buffer = clean_entry.lstrip("• ").strip()
        elif buffer and " | " in clean_entry:
            combined.append({"description": buffer.strip()})
            buffer = clean_entry
        elif buffer and re.search(
            r"\b(Associate|Front End|Lead|Engineer)\b", clean_entry
        ):
            combined.append({"description": buffer.strip()})
            buffer = clean_entry
        else:
            buffer = f"{buffer} {clean_entry}".strip() if buffer else clean_entry
        # Commit the buffer if it ends with punctuation or is long enough.
        if (buffer.endswith((".", "!", "?"))) or (len(buffer) > 100):
            combined.append({"description": buffer.strip()})
            buffer = ""
    if buffer:
        combined.append({"description": buffer.strip()})
    return combined


def clean_skill(skill):
    mapping = {
        "TanStack Querry": "TanStack Query",
        "JavaScript (ES6+)": "JavaScript",
        # Add additional mappings as needed.
    }
    return mapping.get(skill, skill)


def generate_dynamic_summary(sections, ai_skills):
    """
    Generates a dynamic resume summary based on the extracted sections and AI-detected skills.
    """
    summary_parts = []
    # Use resume-extracted skills (and list up to three) if available
    if sections["skills"]:
        summary_parts.append(
            "Your resume highlights technical skills such as "
            + ", ".join(sections["skills"][:3])
            + "."
        )
    # Use skills detected by AI to add value
    if ai_skills:
        summary_parts.append(
            "Additional skills detected include " + ", ".join(ai_skills[:3]) + "."
        )
    # Include awards if found
    if sections["awards"]:
        summary_parts.append(
            "Notable achievements include: " + ", ".join(sections["awards"]) + "."
        )
    # Feedback on volunteering
    if sections["volunteering"]:
        summary_parts.append(
            "Your volunteering experience underscores important community involvement."
        )
    # Feedback on projects
    if sections["projects"]:
        summary_parts.append(
            "Projects such as "
            + ", ".join(sections["projects"][:3])
            + " demonstrate your practical expertise."
        )
    # Feedback on hobbies or a general fallback if nothing was detected
    if sections["hobbies"]:
        summary_parts.append(
            "Hobbies like "
            + ", ".join(sections["hobbies"][:3])
            + " suggest well-rounded interests."
        )
    if not summary_parts:
        summary_parts.append(
            "Consider including more details and examples that showcase your skills and achievements."
        )
    return " ".join(summary_parts)


def enhance_with_ai(text):
    api_url = "https://api-inference.huggingface.co/models/dslim/bert-base-NER"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": text[:500], "options": {"wait_for_model": True}}
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            skills = []
            for entity in result:
                if "entity_group" in entity and entity["entity_group"] in [
                    "ORG",
                    "MISC",
                ]:
                    word = entity["word"]
                    if (
                        len(word) > 2
                        and not word.startswith("##")
                        and re.match(r"^[A-Za-z][A-Za-z0-9\+\#\.\-]*$", word)
                    ):
                        skills.append(word)
            skills = list(set(skills))
            logging.info("AI found skills: %s", skills)
            return {"skills": skills}
        else:
            logging.error("API Error: %s - %s", response.status_code, response.text)
            return {"skills": []}
    except Exception as e:
        logging.exception("HF Error:")
        return {"skills": []}


def parse_resume(file_path):
    text = extract_text_from_pdf(file_path)
    resume_data = extract_basic_info(text)
    sections = extract_sections(text)
    ai_enhancement = enhance_with_ai(text)
    # Combine the parser's skills with the AI-detected ones
    combined_skills = list(set(sections["skills"] + ai_enhancement["skills"]))
    resume_data.update(sections)
    resume_data["skills"] = combined_skills
    # Generate a dynamic summary based on all sections and AI detected skills
    resume_data["ai_summary"] = generate_dynamic_summary(
        sections, ai_enhancement["skills"]
    )
    return resume_data
