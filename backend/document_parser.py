"""
Document Parser
===============
Extractor de texto de documentos PDF y DOCX.

Incluye fallback automático de OCR para PDFs escaneados (imágenes).

REQUISITOS DEL SISTEMA:
-----------------------
Para el OCR de PDFs escaneados, el servidor necesita tener instalados:
- tesseract-ocr: Motor de OCR
- tesseract-ocr-spa: Datos de idioma español
- poppler-utils: Herramientas para convertir PDF a imagen (pdftoppm)

Instalación en Debian/Ubuntu:
    apt-get install tesseract-ocr tesseract-ocr-spa poppler-utils

Instalación en macOS:
    brew install tesseract poppler
"""

import pdfplumber
from docx import Document
from pathlib import Path
import io
import logging
from text_utils import clean_text_encoding

# Configurar logger
logger = logging.getLogger(__name__)

# Umbral mínimo de caracteres para considerar que un PDF tiene texto extraíble
MIN_TEXT_THRESHOLD = 20


def _extract_text_with_ocr(file_bytes: bytes) -> str:
    """
    Extrae texto de un PDF usando OCR (pytesseract + pdf2image).
    
    Este método se usa como fallback cuando pdfplumber no puede extraer texto,
    típicamente en PDFs escaneados donde el contenido son imágenes.
    
    Args:
        file_bytes: Bytes del archivo PDF
        
    Returns:
        Texto extraído via OCR
        
    Raises:
        Exception: Si el OCR falla o no está disponible
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        from PIL import Image
    except ImportError as e:
        raise Exception(
            f"OCR no disponible: {str(e)}. "
            "Instalar: pip install pytesseract pdf2image Pillow"
        )
    
    try:
        # Convertir PDF a imágenes
        logger.info("[OCR] Convirtiendo PDF a imágenes...")
        images = convert_from_bytes(file_bytes, dpi=300)
        
        if not images:
            raise Exception("No se pudieron extraer imágenes del PDF")
        
        logger.info(f"[OCR] PDF tiene {len(images)} página(s)")
        
        # Extraer texto de cada página con OCR
        all_text = []
        for i, image in enumerate(images):
            logger.info(f"[OCR] Procesando página {i+1}/{len(images)}...")
            
            # Usar español + inglés para mejor cobertura
            page_text = pytesseract.image_to_string(
                image, 
                lang='spa+eng',
                config='--psm 1'  # Automatic page segmentation with OSD
            )
            
            if page_text.strip():
                all_text.append(page_text.strip())
        
        combined_text = "\n\n".join(all_text)
        
        # Limpiar encoding
        combined_text = clean_text_encoding(combined_text)
        
        logger.info(f"[OCR] Texto extraído: {len(combined_text)} caracteres")
        
        return combined_text.strip()
        
    except Exception as e:
        error_msg = str(e)
        if "tesseract" in error_msg.lower():
            raise Exception(
                "OCR falló: Tesseract no está instalado o no se encuentra. "
                "Instalar: apt-get install tesseract-ocr tesseract-ocr-spa"
            )
        elif "poppler" in error_msg.lower() or "pdftoppm" in error_msg.lower():
            raise Exception(
                "OCR falló: Poppler no está instalado. "
                "Instalar: apt-get install poppler-utils"
            )
        else:
            raise Exception(f"OCR falló: {error_msg}")

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
        """
        Extract text from bytes based on file type.
        
        Para PDFs escaneados (sin texto extraíble), automáticamente intenta
        OCR como fallback antes de rechazar el archivo.
        """
        file_type_lower = file_type.lower()
        
        # PDF
        if file_type_lower in ['pdf', 'application/pdf']:
            text = DocumentParser.extract_text_from_pdf_bytes(file_bytes)
            
            # Verificar si el PDF tiene texto extraíble
            if not text or len(text.strip()) < MIN_TEXT_THRESHOLD:
                logger.warning(
                    f"[DocumentParser] PDF sin texto extraíble (solo {len(text.strip()) if text else 0} chars). "
                    "Intentando OCR como fallback..."
                )
                
                try:
                    # Intentar OCR como fallback
                    ocr_text = _extract_text_with_ocr(file_bytes)
                    
                    if ocr_text and len(ocr_text.strip()) >= MIN_TEXT_THRESHOLD:
                        logger.info(
                            f"[DocumentParser] OCR exitoso: {len(ocr_text)} caracteres extraídos. "
                            "CV procesado como PDF escaneado."
                        )
                        return ocr_text
                    else:
                        raise Exception(
                            "PDF escaneado: OCR no pudo extraer texto suficiente. "
                            "El archivo puede estar dañado o ser de muy baja calidad."
                        )
                        
                except Exception as ocr_error:
                    logger.error(f"[DocumentParser] OCR falló: {str(ocr_error)}")
                    raise Exception(
                        f"PDF sin texto extraíble y OCR falló: {str(ocr_error)}. "
                        "Intente convertir el documento a DOCX o a un PDF con texto seleccionable."
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