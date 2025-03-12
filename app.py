import logging
import os
from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from flask import Flask, Response, jsonify, request, render_template, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from config import ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, UPLOAD_FOLDER, HF_API_TOKEN
from resume_parser import ResumeParserError, parse_resume

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Verify Hugging Face API token
if not HF_API_TOKEN:
    logger.warning("No Hugging Face API token found. AI-enhanced skill detection will be disabled.")
else:
    logger.info("Hugging Face API token loaded successfully.")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH * 50
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_WORKERS'] = 4  # Limit concurrent file processing

# Setup rate limiting with custom error handler
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per day", "10 per minute"]
)

@lru_cache(maxsize=128)
def allowed_file(filename: str) -> bool:
    """Cache frequently checked file extensions."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_files(files: List[FileStorage]) -> Tuple[Optional[str], Optional[int]]:
    """Validate uploaded files with improved error messages."""
    if not files:
        return "No files were uploaded. Please select at least one resume file.", 400
        
    if len(files) > 50:
        return f"Maximum 50 files allowed. You uploaded {len(files)} files.", 400
        
    invalid_files = []
    for file in files:
        if not file.filename:
            return "One or more files have no name. Please ensure all files are properly selected.", 400
            
        if not allowed_file(file.filename):
            invalid_files.append(file.filename)
            
    if invalid_files:
        return f"Invalid file type(s): {', '.join(invalid_files)}. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}", 400
            
    return None, None

def process_resume(file: FileStorage) -> Dict:
    """Process a single resume file with improved cleanup."""
    filename = secure_filename(file.filename)
    file_path = UPLOAD_FOLDER / filename
    
    try:
        file.save(file_path)
        result = parse_resume(file_path)
        result['filename'] = filename  # Add filename to result
        return result
    except Exception as e:
        logger.error("Error processing %s: %s", filename, str(e))
        raise
    finally:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.error("Failed to delete uploaded file %s: %s", filename, str(e))

def process_files_batch(files: List[FileStorage]) -> List[Dict]:
    """Process multiple files concurrently."""
    with ThreadPoolExecutor(max_workers=current_app.config['MAX_WORKERS']) as executor:
        future_to_file = {executor.submit(process_resume, file): file for file in files}
        results = []
        errors = []
        
        for future in future_to_file:
            file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append(f"{file.filename}: {str(e)}")
                logger.error("Failed to process %s: %s", file.filename, str(e))
                
        if errors and not results:
            raise ResumeParserError(f"All files failed to process. Errors: {'; '.join(errors)}")
            
        return results

@app.route("/")
def index() -> str:
    """Render the main page."""
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file() -> Union[Response, Tuple[Response, int]]:
    """Handle resume file upload and parsing with improved error handling."""
    try:
        files = request.files.getlist("resume")
        error, status_code = validate_files(files)
        if error:
            return jsonify({"error": error}), status_code
            
        # Ensure upload directory exists
        UPLOAD_FOLDER.mkdir(exist_ok=True, parents=True)
        
        try:
            results = process_files_batch(files)
            
            if not results:
                return jsonify({
                    "error": "No resumes could be processed. Please check file formats and try again."
                }), 400
                
            return jsonify({"results": results})
            
        except ResumeParserError as e:
            logger.error("Resume parsing error: %s", str(e))
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("Unexpected error processing resumes:")
            return jsonify({
                "error": "An unexpected error occurred while processing the resumes. Please try again."
            }), 500
                
    except Exception as e:
        logger.exception("Unexpected error in upload handler:")
        return jsonify({
            "error": "Internal server error. Please try again later."
        }), 500

@app.errorhandler(413)
def request_entity_too_large(error: Exception) -> Tuple[Response, int]:
    """Handle file too large error with clearer message."""
    max_size_mb = MAX_CONTENT_LENGTH * 50 / (1024 * 1024)
    return jsonify({
        "error": f"Total file size too large. Maximum allowed size is {max_size_mb:.1f}MB"
    }), 413

@app.errorhandler(429)
def ratelimit_handler(error: Exception) -> Tuple[Response, int]:
    """Handle rate limit exceeded error."""
    return jsonify({
        "error": "Too many requests. Please wait before trying again."
    }), 429

if __name__ == "__main__":
    app.run(debug=True)
