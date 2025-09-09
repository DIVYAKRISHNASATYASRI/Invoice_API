import os
import time
import mimetypes
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import io
import csv
from reportlab.pdfgen import canvas
import stripe

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_yourkey")
stripe.api_key = STRIPE_SECRET_KEY

# Flask setup
app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']

# Gemini Model
generation_config = {
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 7000,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-lite-preview-02-05",
    generation_config=generation_config,
)

# =====================
# MODELS
# =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    stripe_subscription_id = db.Column(db.String(128), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    prompt = db.Column(db.String(500), nullable=True)


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")


# =====================
# DATABASE INIT
# =====================
with app.app_context():
    db.create_all()


# =====================
# USER AUTH ROUTES
# =====================
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data or not all([data.get('name'), data.get('email'), data.get('password')]):
        return jsonify({"error": "Name, email and password required"}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already exists"}), 400
    user = User(name=data['name'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Registered successfully!", "user": {"id": user.id, "name": user.name, "email": user.email}}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    if not user or not user.check_password(data.get('password')):
        return jsonify({"error": "Invalid email or password"}), 401
    return jsonify({"message": "Login successful!", "user": {"id": user.id, "name": user.name, "email": user.email}}), 200


# =====================
# VENDOR ROUTES
# =====================
@app.route('/vendors', methods=['GET'])
def get_vendors():
    vendors = Vendor.query.all()
    return jsonify([{"id": v.id, "name": v.name, "prompt": v.prompt} for v in vendors])


@app.route('/add_vendor', methods=['POST'])
def add_vendor():
    name = request.json.get('name')
    if not name:
        return jsonify({"error": "Vendor name required"}), 400
    vendor = Vendor(name=name)
    db.session.add(vendor)
    db.session.commit()
    return jsonify({"message": "Vendor added successfully!", "vendor_id": vendor.id}), 201


@app.route('/add_prompt', methods=['POST'])
def add_prompt():
    vendor_id = request.json.get('vendor_id')
    prompt = request.json.get('prompt')
    if not vendor_id or prompt is None:
        return jsonify({"error": "Vendor ID and prompt required"}), 400
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404
    vendor.prompt = prompt
    db.session.commit()
    return jsonify({"message": "Prompt saved successfully!"}), 201


@app.route('/delete_vendor/<int:vendor_id>', methods=['DELETE'])
def delete_vendor(vendor_id):
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404
    db.session.delete(vendor)
    db.session.commit()
    return jsonify({"message": f"Vendor '{vendor.name}' deleted successfully!"}), 200


# =====================
# INVOICE ROUTES
# =====================
@app.route("/invoices", methods=["GET"])
def get_invoices():
    invoices = Invoice.query.all()
    return jsonify([{"id": i.id, "vendor": i.vendor, "amount": i.amount, "date": i.date.isoformat(), "status": i.status} for i in invoices])


@app.route("/add_invoice", methods=["POST"])
def add_invoice():
    data = request.json
    if not data.get("vendor") or not data.get("amount"):
        return jsonify({"error": "Vendor and amount required"}), 400
    invoice = Invoice(
        vendor=data["vendor"],
        amount=float(data["amount"]),
        date=datetime.strptime(data.get("date"), "%Y-%m-%d") if data.get("date") else datetime.utcnow(),
        status=data.get("status", "pending")
    )
    db.session.add(invoice)
    db.session.commit()
    return jsonify({"message": "Invoice added successfully!", "id": invoice.id}), 201


@app.route("/save_invoice", methods=["POST"])
def save_invoice():
    data = request.json
    vendor = data.get("vendor") or data.get("vendor_id")
    amount = data.get("amount")
    date_str = data.get("date")
    status = data.get("status", "pending")
    if not vendor or amount is None:
        return jsonify({"error": "Vendor and amount required"}), 400
    date_obj = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.utcnow()
    invoice = Invoice(vendor=vendor, amount=float(amount), date=date_obj, status=status)
    db.session.add(invoice)
    db.session.commit()
    return jsonify({"message": "Invoice saved successfully!", "id": invoice.id}), 201


# =====================
# ANALYTICS
# =====================
@app.route('/analytics', methods=['GET'])
def analytics():
    try:
        invoices = Invoice.query.all()
        if not invoices: return jsonify([])
        data = {}
        for i in invoices:
            month = i.date.strftime("%b %Y")
            if month not in data: data[month] = {"total": 0, "count": 0}
            data[month]["total"] += i.amount
            data[month]["count"] += 1
        sorted_data = [{"month": k, "total": v["total"], "count": v["count"]} for k, v in sorted(data.items(), key=lambda x: datetime.strptime(x[0], "%b %Y"))]
        return jsonify(sorted_data)
    except Exception as e:
        logging.exception("Analytics error")
        return jsonify({"error": str(e)}), 500


# =====================
# EXPORT INVOICES
# =====================
@app.route("/export/<string:file_type>", methods=["GET"])
def export_invoices(file_type):
    invoices = Invoice.query.all()
    if file_type == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Vendor", "Amount", "Date", "Status"])
        for i in invoices: writer.writerow([i.id, i.vendor, i.amount, i.date, i.status])
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="invoices.csv")
    elif file_type == "pdf":
        output = io.BytesIO()
        p = canvas.Canvas(output)
        p.setFont("Helvetica", 12)
        y = 800
        p.drawString(100, y, "Invoices Report")
        y -= 40
        for i in invoices:
            p.drawString(100, y, f"{i.vendor} | ₹{i.amount} | {i.date.strftime('%Y-%m-%d')} | {i.status}")
            y -= 20
        p.save()
        output.seek(0)
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name="invoices.pdf")
    return jsonify({"error": "Invalid export type"}), 400


# =====================
# GEMINI INVOICE VALIDATION
# =====================
@app.route('/validate', methods=['POST'])
def validate():
    vendor = request.form.get('vendor')
    image_file = request.files.get('image')
    user_prompt = request.form.get('prompt')
    if not image_file:
        return jsonify({'error': 'No image/PDF uploaded'}), 400
    mime_type = mimetypes.guess_type(image_file.filename)[0]
    if mime_type not in ALLOWED_MIME_TYPES:
        return jsonify({'error': f'Invalid file type. Allowed: {ALLOWED_MIME_TYPES}'}), 400
    try:
        gemini_file = genai.upload_file(image_file.stream, mime_type=image_file.content_type)
        wait_for_files_active([gemini_file])
        chat_session = model.start_chat(history=[{"role": "user", "parts": [gemini_file]}])
        extracted_data = {}
        if user_prompt:
            response = chat_session.send_message(f"Extract info from PDF: '{user_prompt}'")
            extracted_data["Data"] = response.text.strip()
        else:
            extracted_data["Data"] = "No prompt provided"
        # Auto-save invoice
        amount = extracted_data.get("amount")
        try: amount = float(amount)
        except: amount = 0.0
        invoice = Invoice(vendor=vendor or "Unknown", amount=amount, date=datetime.utcnow(), status="pending")
        db.session.add(invoice)
        db.session.commit()
        extracted_data["saved_invoice_id"] = invoice.id
        return jsonify(extracted_data)
    except Exception as e:
        logging.exception("Error processing file")
        return jsonify({'error': str(e)}), 500


def wait_for_files_active(files):
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(0.2)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed processing")


# =====================
# STRIPE SUBSCRIPTION
# =====================
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.json
    plan_id = data.get("planId")
    if not plan_id:
        return jsonify({"error": "Plan ID required"}), 400
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan_id, "quantity": 1}],
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/cancel"
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =====================
# RUN APP
# =====================
if __name__ == "__main__":
    app.run(debug=True, port=5000)
