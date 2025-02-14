import os
import time
import google.generativeai as genai
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
import re

app = Flask(__name__)
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
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(image_file.read())
            temp_file_path = temp_file.name

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