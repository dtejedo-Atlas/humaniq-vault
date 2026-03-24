import pdfplumber
from docx import Document
from pathlib import Path
import io
from text_utils import clean_text_encoding

class DocumentParser:
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                
                # Limpiar encoding solo si hay corrupción evidente
                text = clean_text_encoding(text)
                return text.strip()
        except Exception as e:
            raise Exception(f"Error extrayendo texto de PDF: {str(e)}")
    
    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            # Limpiar encoding solo si hay corrupción evidente
            text = clean_text_encoding(text)
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extrayendo texto de DOCX: {str(e)}")
    
    @staticmethod
    def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
        """Extract text from PDF bytes"""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                
                # Limpiar encoding solo si hay corrupción evidente
                text = clean_text_encoding(text)
                return text.strip()
        except Exception as e:
            raise Exception(f"Error extrayendo texto de PDF: {str(e)}")
    
    @staticmethod
    def extract_text_from_docx_bytes(file_bytes: bytes) -> str:
        """Extract text from DOCX bytes"""
        try:
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            # Limpiar encoding solo si hay corrupción evidente
            text = clean_text_encoding(text)
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extrayendo texto de DOCX: {str(e)}")
    
    @staticmethod
    def extract_text(file_path: str) -> str:
        """Auto-detect file type and extract text"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return DocumentParser.extract_text_from_pdf(file_path)
        elif file_ext in ['.docx', '.doc']:
            return DocumentParser.extract_text_from_docx(file_path)
        else:
            raise Exception(f"Formato de archivo no soportado: {file_ext}")
    
    @staticmethod
    def extract_text_from_bytes(file_bytes: bytes, file_type: str) -> str:
        """Extract text from bytes based on file type"""
        file_type_lower = file_type.lower()
        
        # PDF
        if file_type_lower in ['pdf', 'application/pdf']:
            text = DocumentParser.extract_text_from_pdf_bytes(file_bytes)
            
            # Verificar si el PDF tiene texto extraíble
            if not text or len(text.strip()) < 20:
                raise Exception(
                    "PDF sin texto extraíble. Posiblemente es un PDF escaneado (imagen). "
                    "Para procesarlo, primero debe convertirse a texto usando OCR."
                )
            return text
        
        # DOCX (Word moderno)
        elif file_type_lower in ['docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return DocumentParser.extract_text_from_docx_bytes(file_bytes)
        
        # DOC (Word antiguo 97-2003) - RECHAZAR con mensaje claro
        elif file_type_lower in ['doc', 'application/msword']:
            raise Exception(
                "Formato DOC (Word 97-2003) no soportado. "
                "Por favor convierte el archivo a PDF o DOCX antes de subirlo."
            )
        
        else:
            raise Exception(f"Formato de archivo no soportado: {file_type}. Solo se permiten PDF y DOCX.")