import os
import time
import google.generativeai as genai
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
import re

app = Flask(__name__)
<<<<<<< HEAD
CORS(app)

GEMINI_API_KEY = "AIzaSyDDrf9x6heE-nXVYljXenZI2kAMV75Fofk"  
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 4096,
    "response_mime_type": "text/plain",
}
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
)
=======
CORS(app)  

GEMINI_API_KEY = "GEMINI KEY" 
client = genai.Client(api_key=GEMINI_API_KEY)
>>>>>>> c1bc7b80a6ba6d9c0c9be3326ece3091e0c58d84

@app.route('/vendors', methods=['GET'])
def get_vendors():
    vendors = [
        {"id": "1", "name": "Vendor A"},
        {"id": "2", "name": "Vendor B"},
        {"id": "3", "name": "Vendor C"}
    ]
    return jsonify(vendors)

@app.route('/validate', methods=['POST'])
def validate():
    vendor = request.form.get('vendor')
    image_file = request.files.get('image')
    prompt = request.form.get('prompt')

    if not image_file:
        return jsonify({'error': 'No image or PDF uploaded'}), 400

    try:
<<<<<<< HEAD
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(image_file.read())
            temp_file_path = temp_file.name
=======
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
>>>>>>> c1bc7b80a6ba6d9c0c9be3326ece3091e0c58d84

        mime_type = image_file.content_type
        file = genai.upload_file(temp_file_path, mime_type=mime_type)

        if file:
            wait_for_files_active([file])
        else:
            print("Error: Unable to upload the image to Gemini")
            os.remove(temp_file_path)
            return jsonify({'error': 'Failed to upload to Gemini'}), 500

        chat_session = model.start_chat(
            history=[{"role": "user", "parts": [file]}]
        )
        if prompt: #If prompt is given in front end show output based on that

            response = chat_session.send_message("Extract text from the image") 
            extracted_text = response.text

            # Constructing JSON object
            invoice_number_match = re.search(r"Invoice #: (\d+)", extracted_text)
            invoice_date_match = re.search(r"Invoice Date: (\d{2}/\d{2}/\d{4})", extracted_text)
            due_date_match = re.search(r"Due Date: (\d{2}/\d{2}/\d{4})", extracted_text)
            total_amount_match = re.search(r"Invoice #:(\d+).*Pay this amount:[\s\$]*(\d+\.?\d*)", extracted_text, re.DOTALL)

            line_items = []
            #Regex for the items and attributes in the item table
            item_table = re.findall(r"(\d+)\s+(\S+)\s+(\S+)\s+(.+?)\s*(\d+\.?\d*)\s*(\d+\.?\d*)", extracted_text, re.MULTILINE)

            for item in item_table:
              quantity, item_num, size, description, net_amount, ext_amount = item

              line_items.append({
                  "item_number": item_num,
                  "description": description.strip(),
                  "quantity": int(quantity), 
                  "price": float(net_amount), 
                  "net_amount": float(net_amount),
                  "ext_amount": float(ext_amount)
              })

            json_data = {
                "invoice_number": invoice_number_match.group(1) if invoice_number_match else None,
                "invoice_date": invoice_date_match.group(1).replace('/','-') if invoice_date_match else None, 
                "due_date": due_date_match.group(1).replace('/','-') if due_date_match else None, 
                "vendor_name": "Breakthru Beverage Missouri", 
                "customer_number": None, 
                "total_amount": float(total_amount_match.group(2)) if total_amount_match else None, 
                "line_items": line_items
            }

            return jsonify(json_data)

          #If Gemini does not generate information from this prompt, the default structure with no values in the JSON will be displayed
        else:
          #If there is no prompt, or its just whitespace there is nothing to display
          json_data = {}
          return jsonify(json_data)

    except Exception as e:
        return jsonify({'error': f'Error processing image or extracting text: {str(e)}'}), 500
    finally:
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

<<<<<<< HEAD
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
=======
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
>>>>>>> c1bc7b80a6ba6d9c0c9be3326ece3091e0c58d84

if __name__ == '__main__':
    app.run(debug=True)
