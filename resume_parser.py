import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Union

import pdfplumber
import requests
import spacy
from spacy.language import Language

from config import (
    EMAIL_PATTERN,
    EDUCATION_PATTERN,
    HF_API_TOKEN,
    HF_API_TIMEOUT,
    PHONE_PATTERN,
    SKILLS_NOISE_PATTERN,
    SKILLS_PATTERN,
    SPACY_MODEL,
    WORK_DATE_PATTERN,
    WORK_TITLE_PATTERN,
    SKILL_MAPPING,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize spaCy model (cached)
try:
    nlp: Language = spacy.load(SPACY_MODEL)
    logger.info(f"Loaded spaCy model: {SPACY_MODEL}")
except Exception as e:
    logger.error(f"Failed to load spaCy model: {e}")
    raise

# Precompiled regex patterns for performance
email_regex = re.compile(EMAIL_PATTERN)
phone_regex = re.compile(PHONE_PATTERN)
education_regex = re.compile(EDUCATION_PATTERN, re.IGNORECASE)
work_title_regex = re.compile(WORK_TITLE_PATTERN, re.IGNORECASE)
work_date_regex = re.compile(WORK_DATE_PATTERN, re.IGNORECASE)
skills_regex = re.compile(SKILLS_PATTERN)
skills_noise_regex = re.compile(SKILLS_NOISE_PATTERN, re.IGNORECASE)

# ATS-optimized skill patterns
SKILL_PATTERNS = [
    # Programming Languages with versions
    r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|Ruby|PHP|Swift|Kotlin|Go|Rust|Scala|R|MATLAB)(?:\s+\d+(?:\.\d+)*)?',
    
    # Frameworks and Libraries
    r'\b(?:React(?:\.js)?|Angular(?:JS)?|Vue(?:\.js)?|Node(?:\.js)?|Express(?:\.js)?|Django|Flask|Spring|Laravel|TensorFlow|PyTorch|Pandas|NumPy|Scikit[-\s]learn)',
    
    # Database Technologies
    r'\b(?:SQL|MySQL|PostgreSQL|MongoDB|Oracle|Redis|Cassandra|SQLite|MariaDB|Neo4j|GraphQL)\b',
    
    # Cloud & DevOps
    r'\b(?:AWS|Amazon\s+Web\s+Services|Azure|Google\s+Cloud|GCP|Docker|Kubernetes|Jenkins|Git|CI/CD|DevOps)',
    
    # Common Technical Skills
    r'\b(?:REST|API|JSON|XML|HTML5?|CSS3?|SASS|LESS|Bootstrap|Material[-\s]UI|Webpack|Babel|ESLint)',
    
    # Data Science & AI
    r'\b(?:Machine\s+Learning|Deep\s+Learning|Neural\s+Networks|NLP|Computer\s+Vision|Data\s+Mining|Statistics|Big\s+Data|Data\s+Analysis|Data\s+Visualization|BI|Business\s+Intelligence)',
    
    # Testing & Quality
    r'\b(?:Unit\s+Testing|Integration\s+Testing|Jest|Mocha|Selenium|TestNG|JUnit|PyTest|QA|Quality\s+Assurance)',
    
    # Project Management & Methodologies
    r'\b(?:Agile|Scrum|Kanban|JIRA|Confluence|Project\s+Management|PMP|Prince2)',
    
    # Design & UI/UX
    r'\b(?:UI/UX|User\s+Interface|User\s+Experience|Figma|Sketch|Adobe\s+(?:XD|Photoshop|Illustrator)|InVision)',
    
    # Common Tools & Platforms
    r'\b(?:Linux|Unix|Windows|MacOS|Shell\s+Scripting|Bash|PowerShell)',
    
    # Certifications
    r'\b(?:AWS\s+Certified|Microsoft\s+Certified|Google\s+Certified|CISSP|CompTIA|PMP|ITIL)',
    
    # Soft Skills (carefully selected based on ATS frequency)
    r'\b(?:Leadership|Communication|Problem[-\s]Solving|Team\s+Management|Strategic\s+Planning|Analysis|Innovation)',
    
    # Version Control
    r'\b(?:Git(?:Hub)?|Bitbucket|GitLab|SVN|Mercurial)\b',
    
    # Mobile Development
    r'\b(?:iOS|Android|React\s+Native|Flutter|Xamarin|Mobile\s+Development|App\s+Development)',
    
    # Security
    r'\b(?:Cyber\s*security|Information\s+Security|Network\s+Security|Penetration\s+Testing|Security\s+Audit)',
]

class ResumeParserError(Exception):
    """Base exception for resume parser errors."""
    pass

def extract_text_from_pdf(file_path: Union[str, Path]) -> str:
    """Extract text content from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        ResumeParserError: If PDF extraction fails
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
            logger.info("Successfully extracted text from PDF")
            return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise ResumeParserError(f"Failed to extract text from PDF: {e}")

def extract_basic_info(text: str) -> Dict[str, str]:
    """Extract basic information (name, email, phone) from text.
    
    Args:
        text: Input text to process
        
    Returns:
        Dictionary containing name, email and phone
    """
    doc = nlp(text)
    info = {"name": "", "email": "", "phone": ""}
    
    # Extract name
    for ent in doc.ents:
        if ent.label_ == "PERSON" and not info["name"]:
            name = " ".join(ent.text.split()).strip()
            info["name"] = re.sub(r"\s*\d{7,}", "", name).strip()
            break
    if not info["name"]:
        first_line = text.split("\n")[0].strip()
        info["name"] = re.sub(r"[\d\-\+\s]{7,}", "", first_line).strip()
    
    # Extract email and phone
    email_match = email_regex.search(text)
    info["email"] = email_match.group() if email_match else ""
    
    phone_match = phone_regex.search(text)
    info["phone"] = phone_match.group() if phone_match else ""
    
    return info

def extract_sections(text: str) -> Dict[str, List[Union[Dict[str, str], str]]]:
    """Extract different sections from the resume text."""
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
    work_entries = []
    in_skills_section = False
    
    # Debug: Print the entire text
    logger.debug("Processing text:\n%s", text)
    
    # First pass: Extract skills using ATS patterns
    all_skills = set()
    for pattern in SKILL_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            skill = match.group().strip()
            if len(skill) >= 2 and not skills_noise_regex.search(skill.lower()):
                all_skills.add(clean_skill(skill))
                logger.debug(f"Found skill using pattern {pattern}: {skill}")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower_line = stripped.lower()
        
        # Debug: Print each line being processed
        logger.debug("Processing line: %s", stripped)
        
        # Detect section headers
        if any(skill_header in lower_line for skill_header in [
            "technical skills",
            "skills",
            "technologies",
            "programming languages",
            "competencies",
            "expertise",
            "proficiencies",
            "technical proficiencies",
            "tools",
            "software",
            "qualifications",
            "technical expertise",
            "core competencies",
            "professional skills",
            "key skills",
            "technical skills & tools",
            "languages & technologies",
            "professional expertise"
        ]):
            current_section = "skills"
            in_skills_section = True
            logger.debug("Entered skills section")
            continue
        elif any(header in lower_line for header in [
            "experience",
            "employment",
            "work history",
            "professional background"
        ]):
            current_section = "work_experience"
            in_skills_section = False
            continue
        elif "education" in lower_line:
            current_section = "education"
            in_skills_section = False
            continue
        elif any(new_section in lower_line for new_section in [
            "interests",
            "hobbies",
            "awards",
            "achievements",
            "volunteer",
            "project",
            "certifications",
            "languages"
        ]):
            in_skills_section = False
            if "interests" in lower_line or "hobbies" in lower_line:
                current_section = "hobbies"
            elif "awards" in lower_line or "achievements" in lower_line:
                current_section = "awards"
            elif "volunteer" in lower_line:
                current_section = "volunteering"
            elif "project" in lower_line:
                current_section = "projects"
            continue

        # Process sections
        if current_section == "education" and education_regex.search(lower_line):
            sections["education"].append({"degree": stripped})
        elif current_section == "work_experience":
            work_entries.append(stripped)
        elif current_section == "skills" or in_skills_section:
            # Debug: Log skill line processing
            logger.debug("Processing potential skill line: %s", stripped)
            
            # Extract skills from the line
            skills = []
            if ":" in stripped:
                # Handle "Category: skill1, skill2" format
                parts = stripped.split(":", 1)
                skills.extend(s.strip() for s in parts[1].split(","))
            else:
                # Handle various formats
                # Split by common separators
                for part in re.split(r'[,•⚫·⦁▪▫●○⚪-]|\band\b', stripped):
                    skill = part.strip()
                    if skill:
                        skills.append(skill)

            # Filter and clean skills
            for skill in skills:
                skill = skill.strip('() []{}')  # Remove common brackets
                if (skill and 
                    len(skill) >= 2 and  # Allow shorter skill names
                    len(skill.split()) <= 4 and  # Allow slightly longer skill phrases
                    not skills_noise_regex.search(skill.lower())):
                    cleaned_skill = clean_skill(skill)
                    sections["skills"].append(cleaned_skill)
                    logger.debug("Added skill: %s (cleaned from: %s)", cleaned_skill, skill)
        
        elif current_section in ["hobbies", "awards", "volunteering", "projects"]:
            sections[current_section].append(stripped)

    sections["work_experience"] = combine_work_experience_entries(work_entries)
    
    # Clean and normalize skills
    sections["skills"] = list(set(
        clean_skill(s) for s in sections["skills"]
        if s and not skills_noise_regex.search(s.lower())
    ))
    
    # Log extracted skills for debugging
    logger.info("Final extracted skills: %s", sections["skills"])
    
    return sections

def combine_work_experience_entries(entries: List[str]) -> List[Dict[str, str]]:
    """Combine work experience entries into coherent descriptions.
    
    Args:
        entries: List of work experience text entries
        
    Returns:
        List of work experience entries with descriptions
    """
    combined = []
    buffer = ""
    
    for entry in entries:
        clean_entry = entry.strip()
        if clean_entry.startswith("•"):
            if buffer:
                combined.append({"description": buffer.strip()})
            buffer = clean_entry.lstrip("• ").strip()
        elif buffer and " | " in clean_entry:
            combined.append({"description": buffer.strip()})
            buffer = clean_entry
        elif buffer and re.search(r"\b(Associate|Front End|Lead|Engineer)\b", clean_entry):
            combined.append({"description": buffer.strip()})
            buffer = clean_entry
        else:
            buffer = f"{buffer} {clean_entry}".strip() if buffer else clean_entry
        
        if (buffer.endswith((".", "!", "?"))) or (len(buffer) > 100):
            combined.append({"description": buffer.strip()})
            buffer = ""
            
    if buffer:
        combined.append({"description": buffer.strip()})
    return combined

def clean_skill(skill: str) -> str:
    """Clean and normalize skill names.
    
    Args:
        skill: Input skill name
        
    Returns:
        Cleaned skill name
    """
    # Normalize the skill
    cleaned = skill.strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize whitespace
    cleaned = re.sub(r'[-_]', ' ', cleaned)  # Replace hyphens and underscores with spaces
    cleaned = cleaned.lower()  # Convert to lowercase
    
    # Remove common noise words
    noise_words = {'and', 'or', 'in', 'with', 'using', 'the', 'a', 'an'}
    cleaned_parts = [word for word in cleaned.split() if word not in noise_words]
    cleaned = ' '.join(cleaned_parts)
    
    # Check skill mapping for standardization
    return SKILL_MAPPING.get(cleaned, cleaned)

def generate_dynamic_summary(
    sections: Dict[str, List], ai_skills: List[str]
) -> str:
    """Generate a dynamic summary of the resume.
    
    Args:
        sections: Extracted resume sections
        ai_skills: Skills detected by AI
        
    Returns:
        Generated summary text
    """
    summary_parts = []
    
    if sections["skills"]:
        summary_parts.append(
            "Your resume highlights technical skills such as "
            + ", ".join(sections["skills"][:3])
            + "."
        )
    if ai_skills:
        summary_parts.append(
            "Additional skills detected include " + ", ".join(ai_skills[:3]) + "."
        )
    if sections["awards"]:
        summary_parts.append(
            "Notable achievements include: " + ", ".join(sections["awards"]) + "."
        )
    if sections["volunteering"]:
        summary_parts.append(
            "Your volunteering experience underscores important community involvement."
        )
    if sections["projects"]:
        summary_parts.append(
            "Projects such as "
            + ", ".join(sections["projects"][:3])
            + " demonstrate your practical expertise."
        )
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

def enhance_with_ai(text: str) -> Dict[str, List[str]]:
    """Enhance resume parsing with AI-based skill detection.
    
    Args:
        text: Input text to process
        
    Returns:
        Dictionary containing detected skills
    """
    if not HF_API_TOKEN:
        logger.warning("No Hugging Face API token provided")
        return {"skills": []}
        
    api_url = "https://api-inference.huggingface.co/models/dslim/bert-base-NER"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {"inputs": text[:500], "options": {"wait_for_model": True}}
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=HF_API_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        skills = []
        for entity in result:
            if "entity_group" in entity and entity["entity_group"] in ["ORG", "MISC"]:
                word = entity["word"]
                if (
                    len(word) > 2
                    and not word.startswith("##")
                    and re.match(r"^[A-Za-z][A-Za-z0-9\+\#\.\-]*$", word)
                ):
                    skills.append(word)
                    
        skills = list(set(skills))
        logger.info("AI found skills: %s", skills)
        return {"skills": skills}
        
    except requests.Timeout:
        logger.error("Hugging Face API request timed out")
        return {"skills": []}
    except requests.RequestException as e:
        logger.error("Hugging Face API error: %s", e)
        return {"skills": []}
    except Exception as e:
        logger.exception("Unexpected error in AI enhancement:")
        return {"skills": []}

def parse_resume(file_path: Union[str, Path]) -> Dict:
    """Parse a resume PDF file and extract structured information.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Dictionary containing parsed resume data
        
    Raises:
        ResumeParserError: If parsing fails
    """
    try:
        text = extract_text_from_pdf(file_path)
        resume_data = extract_basic_info(text)
        sections = extract_sections(text)
        ai_enhancement = enhance_with_ai(text)
        
        # Combine skills and generate summary
        combined_skills = list(set(sections["skills"] + ai_enhancement["skills"]))
        resume_data.update(sections)
        resume_data["skills"] = combined_skills
        resume_data["ai_summary"] = generate_dynamic_summary(
            sections, ai_enhancement["skills"]
        )
        
        return resume_data
        
    except Exception as e:
        logger.exception("Failed to parse resume:")
        raise ResumeParserError(f"Failed to parse resume: {str(e)}")
