from flask import Flask, request, jsonify, render_template
from parser import parse_resume
import os

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["resume"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    file_path = os.path.join("uploads", file.filename)
    os.makedirs("uploads", exist_ok=True)
    file.save(file_path)

    try:
        result = parse_resume(file_path)
        os.remove(file_path)
        return jsonify(result)
    except Exception as e:
        print(f"Error: {str(e)}")  # Debugging
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
