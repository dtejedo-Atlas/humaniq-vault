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
            return DocumentParser.extract_text_from_pdf_bytes(file_bytes)
        
        # DOCX (Word moderno)
        elif file_type_lower in ['docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return DocumentParser.extract_text_from_docx_bytes(file_bytes)
        
        # DOC (Word antiguo 97-2003) - Intentar como DOCX primero, luego textract
        elif file_type_lower in ['doc', 'application/msword']:
            # Primero intentar como DOCX (algunos .doc modernos funcionan)
            try:
                return DocumentParser.extract_text_from_docx_bytes(file_bytes)
            except Exception:
                # Si falla, intentar con textract o antiword
                try:
                    import subprocess
                    import tempfile
                    import os
                    
                    # Guardar temporalmente y usar antiword si está disponible
                    with tempfile.NamedTemporaryFile(suffix='.doc', delete=False) as tmp:
                        tmp.write(file_bytes)
                        tmp_path = tmp.name
                    
                    try:
                        # Intentar con antiword
                        result = subprocess.run(
                            ['antiword', tmp_path],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            return clean_text_encoding(result.stdout.strip())
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        pass
                    finally:
                        os.unlink(tmp_path)
                    
                    # Si antiword no está disponible, dar mensaje claro
                    raise Exception(
                        "Formato DOC (Word 97-2003) detectado. "
                        "Por favor convierte el archivo a PDF o DOCX para procesarlo."
                    )
                except Exception as e:
                    if "convierte el archivo" in str(e):
                        raise
                    raise Exception(
                        f"No se pudo procesar archivo DOC: {str(e)}. "
                        "Por favor convierte a PDF o DOCX."
                    )
        
        else:
            raise Exception(f"Formato de archivo no soportado: {file_type}")