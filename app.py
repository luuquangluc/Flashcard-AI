"""
Flask web server for the Flashcard Generator.
Provides REST API endpoints matching the original FlashCard-Generator backend.
"""

import io
import logging
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

from src.config import GEMINI_API_KEY, TESSERACT_CMD, LOG_LEVEL
from src.tools import generate_flashcards, read_file

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='frontend', static_url_path='/frontend')
CORS(app)  # Allow frontend to access backend


@app.route('/')
def serve_index():
    """Serve the frontend index.html."""
    return send_file('index.html')


def extract_text_from_file(file):
    """Extract text from uploaded file (PDF, TXT, JPG, PNG)."""
    import fitz
    import json as json_mod

    filename = file.filename.lower()
    file_bytes = file.read()

    if filename.endswith('.pdf'):
        # Try PyMuPDF text extraction first
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()

        # If no text found (scanned PDF), fallback to OCR
        if not text.strip():
            logger.info("PDF has no text layer, using OCR...")
            try:
                import pytesseract
                from PIL import Image

                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

                doc = fitz.open(stream=file_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text += pytesseract.image_to_string(img, lang='eng+vie') + "\n"
                doc.close()
            except Exception as e:
                logger.error(f"OCR error: {e}")
                return ""
        return text

    elif filename.endswith('.txt'):
        return file_bytes.decode('utf-8')

    elif filename.endswith(('.jpg', '.jpeg', '.png')):
        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image, lang='eng+vie')
            return text
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return ""

    else:
        raise ValueError(
            "Unsupported file format. Please upload a PDF, TXT, JPG, or PNG file."
        )


@app.route('/api/generate', methods=['POST'])
def api_generate_flashcards():
    """Generate flashcards from text input."""
    data = request.get_json()
    input_text = data.get('text', '')
    num_cards = data.get('num_cards', 20)
    
    if not input_text.strip():
        return jsonify({"error": "Empty input"}), 400

    import json as json_mod
    result = generate_flashcards(input_text, num_cards=num_cards)
    parsed = json_mod.loads(result)

    if "error" in parsed:
        return jsonify({"error": parsed["error"]}), 500

    return jsonify({"flashcards": parsed.get("flashcards", [])})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a file and extract text from it."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        text = extract_text_from_file(file)
        if not text.strip():
            return jsonify({"error": "Could not extract text from file"}), 400

        return jsonify({"text": text})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


if __name__ == '__main__':
    print("=" * 50)
    print("  🧠 Flashcard Generator - Web Server")
    print("=" * 50)
    print("  Frontend:  http://localhost:5000")
    print("  API:       http://localhost:5000/api/...")
    print("=" * 50)
    app.run(debug=True, port=5000)
