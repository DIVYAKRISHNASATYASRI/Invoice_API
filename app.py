from flask import Flask, request, jsonify
from PIL import Image
from pdf2image import convert_from_path
from google import genai
from flask_cors import CORS
import re
import os

app = Flask(__name__)
CORS(app)  

GEMINI_API_KEY = "GEMINI KEY" 
client = genai.Client(api_key=GEMINI_API_KEY)

@app.route('/vendors', methods=['GET'])
def get_vendors():
    # Example vendor list
    vendors = [
        {"id": "1", "name": "Vendor A"},
        {"id": "2", "name": "Vendor B"},
        {"id": "3", "name": "Vendor C"}
    ]
    return jsonify(vendors)

@app.route('/validate', methods=['POST'])
def validate():
    # Get the data from the request
    vendor = request.form.get('vendor')
    image_file = request.files.get('image')
    prompt = request.form.get('prompt')

    # Check if image was provided
    if not image_file:
        return jsonify({'error': 'No image or PDF uploaded'}), 400

    try:
        # Check if the file is a PDF
        if image_file.filename.lower().endswith('.pdf'):
            pdf_path = os.path.join("temp.pdf")
            image_file.save(pdf_path)
            # Convert PDF to images
            images = convert_pdf_to_images(pdf_path)
            os.remove(pdf_path)
        else:
            # If it's not a PDF, treat it as an image directly
            images = [Image.open(image_file.stream)]

        extracted_text = ''
        for image in images:
            # Send image to Gemini for text extraction
            response = client.models.generate_content(
                model="gemini-2.0-flash",  # Use the correct Gemini model
                contents=[image, "Extract text from this receipt"]
            )
            extracted_text += response.text  # Concatenate the extracted text from each page

        # If prompt is provided, filter the extracted text based on the prompt
        if prompt:
            filtered_text = process_prompt(extracted_text, prompt)
            return jsonify(filtered_text)  # Return only the filtered text
        else:
            # If no prompt, return the entire extracted text in a clean JSON format
            return jsonify(format_extracted_text(extracted_text))  # Return the extracted text as JSON

    except Exception as e:
        return jsonify({'error': f'Error processing image or extracting text: {str(e)}'}), 500

def convert_pdf_to_images(pdf_path):
    """
    Converts the PDF file to a list of images (one image per page).
    """
    images = convert_from_path(pdf_path, 300)
    return images

def process_prompt(extracted_text, prompt):
    """
    Process the prompt by searching for specific information within the extracted text.
    This function looks for the prompt keyword inside the extracted text and returns the relevant info.
    """
    prompt_lower = prompt.lower()
    extracted_text_lower = extracted_text.lower()

    # Use regex to find the line containing the prompt keyword
    pattern = rf"{re.escape(prompt_lower)}.*?(\d+\.\d{2})"  
    match = re.search(pattern, extracted_text_lower)

    if match:
        # Return the matched line or value
        return f"{prompt.capitalize()}: {match.group(1)}"
    else:
        # If no match, search for the keyword in the text and return the entire line
        lines = extracted_text.split('\n')
        for line in lines:
            if prompt_lower in line.lower():
                return line.strip()
        # If no line contains the keyword, return a default message
        return f"Sorry, no information found for the prompt '{prompt}'."

import re

def format_extracted_text(extracted_text):
    extracted_text = re.sub(r"Here's the extracted text from the receipt.*", "", extracted_text, re.DOTALL | re.IGNORECASE).strip() 
    extracted_text = re.sub(r"\*{2}.*", "", extracted_text).strip()
    extracted_text = re.sub(r"\|---|\|", "", extracted_text).strip()  # Remove table separators
    extracted_text = re.sub(r"Page \d+ of \d+", "", extracted_text).strip()  # Remove page numbers
    extracted_text = re.sub(r"\(Empty\)", "", extracted_text).strip() # Remove empty entries
    lines = extracted_text.splitlines()
    data = {}
    items = []  
    current_item = {}

    for line in lines:
        line = line.strip()

        if not line:
            continue

        item_match = re.match(r"(.+?)\s+(\d+\.\d+)", line) 
        if item_match:
            item_name = item_match.group(1).strip()
            item_price = item_match.group(2)
            current_item[item_name] = item_price
            items.append(current_item)  # Add the item to the list
            current_item = {}  # Reset for the next item
            continue  # Move to the next line

        kv_match = re.match(r"(.+?):\s*(.+)", line)
        if kv_match:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()
            data[key] = value
            continue  # Move to the next line

        if line and not current_item: 
            data[line] = None


    if items:
        data["items"] = items

    return data

if __name__ == '__main__':
    app.run(debug=True)
