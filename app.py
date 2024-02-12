import os
from flask import Flask, request, send_file, render_template, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from image_analysis_module import analyze_image
import cv2 as cv

app = Flask(__name__, static_folder='assets')
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

UPLOAD_FOLDER = os.path.join(app.root_path, 'assets', 'uploads')
ALLOWED_MIME_TYPES = [
    'image/bmp', 'image/x-canon-cr2', 'image/jpeg', 'image/png',
    'image/x-canon-crw', 'image/x-eps', 'image/x-nikon-nef',
    'application/postscript', 'image/gif', 'image/x-minolta-mrw',
    'image/x-olympus-orf', 'image/x-photoshop', 'image/x-fuji-raf',
    'image/x-panasonic-raw2', 'image/x-tga', 'image/tiff', 'image/pjpeg',
    'image/x-x3f', 'image/x-portable-pixmap'
]
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(file):
    return file.content_type in ALLOWED_MIME_TYPES

@app.route('/')
def index():
    return render_template('index-server.html')
@app.route('/analyze', methods=['post'])
def analyze():
    if 'photoUpload' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['photoUpload']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        result = analyze_image(filepath)

        response_data = {
            "success": True,
            "result": result 
        }

        session['result'] = result
        return jsonify(response_data)
    else:
        flash('Invalid file type.')
        return redirect(request.url)

@app.route('/report_result', methods=['GET', 'POST'])
def report_result():
    report_data = session.get('result', {})

    if not report_data:
        flash('No Image Uploaded', 'error')
        return redirect(url_for('index'))
    
    return render_template('full_report.html', report=report_data)

@app.route('/handle_contact', methods=['POST'])
def handle_contact():
    name = request.form['name']
    email = request.form['email']
    subject = request.form['subject']
    message = request.form['message']

    flash('Thank you for your message. We will contact you shortly!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
