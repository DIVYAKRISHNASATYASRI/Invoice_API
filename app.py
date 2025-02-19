import os
import time
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import mimetypes
import logging

app = Flask(__name__)
CORS(app)

# **WARNING: Hardcoding API keys is a SECURITY RISK! Only for testing.**
GEMINI_API_KEY = "AIzaSyDDrf9x6heE-nXVYljXenZI2kAMV75Fofk"  # Replace with your actual API key

genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.0,  # Reduced temperature for more deterministic output
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 7000,  # Keep the token limit high
    "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-lite-preview-02-05",  # Verify model support of PDFs. gemini-pro-vision might be better
    generation_config=generation_config,
)

ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vendors.db'  # You can change to your preferred database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Create a Vendor model
class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Vendor {self.name}>'

# Create the database (tables)
with app.app_context():
    db.create_all()

# Route to fetch all vendors
@app.route('/vendors', methods=['GET'])
def get_vendors():
    vendors = Vendor.query.all()
    return jsonify([{"id": vendor.id, "name": vendor.name} for vendor in vendors])

# Route to add a new vendor
@app.route('/add_vendor', methods=['POST'])
def add_vendor():
    vendor_name = request.json.get('name')

    if not vendor_name:
        return jsonify({"error": "Vendor name is required"}), 400

    # Create a new vendor instance
    new_vendor = Vendor(name=vendor_name)

    try:
        # Add the vendor to the database
        db.session.add(new_vendor)
        db.session.commit()
        return jsonify({"message": "Vendor added successfully!"}), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding vendor: {e}")
        return jsonify({"error": "An error occurred while adding the vendor"}), 500

@app.route('/validate', methods=['POST'])
def validate():
    vendor = request.form.get('vendor')
    image_file = request.files.get('image')
    user_prompt = request.form.get('prompt')  # Renamed 'prompt' to 'user_prompt'

    if not image_file:
        return jsonify({'error': 'No image or PDF uploaded'}), 400

    mime_type = mimetypes.guess_type(image_file.filename)[0]
    if mime_type not in ALLOWED_MIME_TYPES:
        logging.warning(f"Received file with invalid MIME type: {mime_type}")
        return jsonify({'error': 'Invalid file type. Allowed types: ' + ', '.join(ALLOWED_MIME_TYPES)}), 400

    try:
        # Upload the file directly to Gemini without saving it temporarily
        genai_mime_type = image_file.content_type
        gemini_file = genai.upload_file(image_file.stream, mime_type=genai_mime_type)

        if gemini_file:
            wait_for_files_active([gemini_file])
        else:
            logging.error("Error: Unable to upload the image to Gemini")
            return jsonify({'error': 'Failed to upload to Gemini'}), 500

        # Start chat session and pass the file
        chat_session = model.start_chat(
            history=[{"role": "user", "parts": [gemini_file]}]
        )

        if user_prompt:
            user_prompt = user_prompt.strip()

            if user_prompt.lower() == "extract text in json":
                extract_prompt = "Extract all the text from this PDF document into a JSON object where the key 'pages' contains an array. Each object in the array represents a page, containing keys 'page_number' and 'raw_text' for the content. Do not include any explanations, code fences, or other formatting."
                response = chat_session.send_message(extract_prompt)
                generated_content = response.text
                generated_content = generated_content.replace('```json', '').replace('```', '').strip()
                return jsonify({"pages": generated_content})

            else:
                # Extract user code
                extract_prompt = f"Based on the following user request: '{user_prompt}', extract the relevant information from the PDF document. If that fails, return 'Information is not available on the PDF. Do not format JSON or make code format and just display the raw.'"
                response = chat_session.send_message(extract_prompt)
                generated_content = response.text
                generated_content = generated_content.replace('```json', '').replace('```', '').strip()
                return jsonify({"Data": generated_content})

        else:
            return jsonify({"error": "No prompt provided"}), 400

    except Exception as e:
        logging.exception("Error processing image or extracting text:")
        return jsonify({'error': f'Error processing image or extracting text: {str(e)}'}), 500

def wait_for_files_active(files):
    print("Waiting for file processing...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
    print("...all files ready")

if __name__ == '__main__':
    app.run(debug=True)
