from PyPDF2 import PdfReader
from docx import Document
import os
from werkzeug.utils import secure_filename
from typing import Tuple

class DocumentProcessor:
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in DocumentProcessor.ALLOWED_EXTENSIONS
    
    @staticmethod
    def process_document(file) -> Tuple[str, str]:
        """Process uploaded document and return content and document type"""
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        if file_ext == 'pdf':
            return DocumentProcessor._process_pdf(file), file_ext
        elif file_ext == 'docx':
            return DocumentProcessor._process_docx(file), file_ext
        elif file_ext == 'txt':
            return file.read().decode('utf-8'), file_ext
        
        raise ValueError(f"Unsupported file type: {file_ext}")
    
    @staticmethod
    def _process_pdf(file) -> str:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    @staticmethod
    def _process_docx(file) -> str:
        doc = Document(file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text 