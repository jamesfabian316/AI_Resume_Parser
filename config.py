import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
HF_API_TOKEN = os.getenv('HF_API_TOKEN', '')
HF_API_TIMEOUT = 30  # seconds

# File Upload Configuration
UPLOAD_FOLDER = Path('uploads')
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'pdf'}

# Model Configuration
SPACY_MODEL = 'en_core_web_sm'

# Regex Patterns
EMAIL_PATTERN = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
PHONE_PATTERN = r'(\+\d{1,3}-?)?\d{3}-?\d{3}-?\d{4}'
EDUCATION_PATTERN = r'(college|university|institute|iit|b\.\w+\.|m\.\w+\.|phd|pursuing|\d{4}.*\d{4}|\d{4}-present)'
WORK_TITLE_PATTERN = r'[\|\$\.\•]+.*(react|javascript|python|css|html|typescript|mysql)'
WORK_DATE_PATTERN = r'\d{4}.*(present|\d{4})'
SKILLS_PATTERN = r'^(www\.|\d+|-+|\s+|james|fabian|linkedin|github|es6\+)'
SKILLS_NOISE_PATTERN = r'^(to|and|for|a|of|the|in|by|with|from|on|at)$'

# Skill Mapping
SKILL_MAPPING = {
    'TanStack Querry': 'TanStack Query',
    'JavaScript (ES6+)': 'JavaScript',
} 