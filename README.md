# AI Resume Parser

This project allows you to extract personal details, education, work experience, and skills from a PDF resume using AI and NLP techniques. The application is built with Python and Flask and leverages several libraries including [pdfplumber](parser.py) and [spaCy](parser.py).

## Project Structure

- **app.py**: The Flask application that serves the website and handles resume uploads. ([app.py](app.py))
- **parser.py**: Contains functions to extract and process resume data. ([parser.py](parser.py))
- **templates/index.html**: The HTML template for the UI. ([templates/index.html](templates/index.html))
- **static/style.css** and **static/script.js**: The CSS and JavaScript files used by the web interface. ([static/style.css](static/style.css)) ([static/script.js](static/script.js))
- **requirements.txt**: Lists the required Python dependencies. ([requirements.txt](requirements.txt))
- **uploads/**: Directory where uploaded files are temporarily stored.

## Installation

### Prerequisites

- Python 3.11
- pip (Python package installer)

### Steps

1. **Clone the repository:**
    ```sh
   git clone https://github.com/jamesfabian316/AI-Based-Resume-Parser
   cd <repository_directory>
2. **Create a virtual Environment (optional but recommended)**
    ```sh
    python -m venv venv
    source venv/bin/activate   # On Windows use: venv\Scripts\activate
3. **Install the dependencies**
    ```sh
    pip install -r requirements.txt
4. **Download spaCy's English Model**
    ```sh
    python -m spacy download en_core_web_sm  
5. **Run the project
    ```sh
    python app.py
   
