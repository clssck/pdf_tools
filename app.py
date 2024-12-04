from flask import Flask, render_template, request, jsonify, send_from_directory, Blueprint, redirect, url_for
import os
from werkzeug.utils import secure_filename
try:
    import fitz  # type: ignore  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Please run: pip install PyMuPDF")
    raise

# Create Blueprint instead of app
pdf_merger = Blueprint('pdf_merger', __name__, template_folder='templates')

# Move configuration to main app
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def check_pdf_pages(file_path):
    doc = fitz.open(file_path)
    pages = len(doc)
    doc.close()
    return pages > 1

@pdf_merger.route('/merge-to-single')
def index():
    return render_template('pdf_merger.html')  # Renamed template

@pdf_merger.route('/merge-to-single/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        if file.filename is None:
            return jsonify({'error': 'Invalid filename'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        if not check_pdf_pages(filepath):
            os.remove(filepath)
            return jsonify({'error': 'PDF must have multiple pages'}), 400

        output_filename = f"merged_{filename}"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)

        try:
            input_doc = fitz.open(filepath)
            output_doc = fitz.open()

            total_height = sum(page.rect.height for page in input_doc)
            max_width = max(page.rect.width for page in input_doc)

            new_page = output_doc.new_page(width=max_width, height=total_height)

            current_height = 0
            for page in input_doc:
                rect = page.rect
                new_page.show_pdf_page(
                    fitz.Rect(0, current_height, rect.width, current_height + rect.height),
                    input_doc,
                    page.number
                )
                current_height += rect.height

            output_doc.save(output_path)
            input_doc.close()
            output_doc.close()

            os.remove(filepath)

            return jsonify({
                'success': True,
                'filename': output_filename
            })
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            if os.path.exists(output_path):
                os.remove(output_path)
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid file type'}), 400

@pdf_merger.route('/merge-to-single/download/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

def create_app():
    app = Flask(__name__)

    # Configure the app
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # Register blueprint
    app.register_blueprint(pdf_merger, url_prefix='/tools')

    # Add root route that redirects to the tool
    @app.route('/')
    def index():
        return redirect(url_for('pdf_merger.index'))

    return app

# For development/testing
if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
