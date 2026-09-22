"""Per-page native extraction plus targeted OCR; no AI, scoring or matching."""
import io
import logging
import re
import threading
from difflib import SequenceMatcher
import pdfplumber
import pypdfium2 as pdfium
from text_utils import clean_text_encoding

logger = logging.getLogger(__name__)
PDFIUM_LOCK = threading.Lock()
EXTRACTION_VERSION = 'cv-text-v3-tables-page-ocr'


def _has_image_text(page):
    # Wide text blocks trigger OCR even when the rest of the page has native text.
    return any(
        abs(image['x1'] - image['x0']) > page.width * .35
        and abs(image['bottom'] - image['top']) > page.height * .025
        for image in page.images
    )


def _ocr_page(data, index, fallback_document):
    import pytesseract
    from pdf2image import convert_from_bytes
    images = []
    try:
        images = convert_from_bytes(data, dpi=250, first_page=index + 1, last_page=index + 1, thread_count=1, timeout=60)
        if not images:
            raise ValueError('Página no renderizada por Poppler')
        image = images[0]
    except Exception:
        image = fallback_document[index].render(scale=250 / 72).to_pil().convert('RGB')
        images = [image]
    try:
        return pytesseract.image_to_string(image, lang='spa+eng', config='--psm 3', timeout=60).strip()
    finally:
        for image in images:
            image.close()


def _merge_text(native, ocr):
    if not native.strip():
        return ocr
    if len(ocr.strip()) > len(native.strip()) * 1.15:
        return ocr
    normalize = lambda line: re.sub(r'\W+', '', line).casefold()
    known = [normalize(line) for line in native.splitlines() if line.strip()]
    additions = [line for line in ocr.splitlines() if len(normalize(line)) > 8
                 and not any(SequenceMatcher(None, normalize(line), other).ratio() > .82 for other in known)]
    return native + ('\n' + '\n'.join(additions) if additions else '')


def extract_pdf(data, native_extractor):
    texts, pages, warnings = [], [], []
    with PDFIUM_LOCK:
        fallback = pdfium.PdfDocument(data)
        try:
            count = len(fallback)
            if not count:
                raise ValueError('El PDF no contiene páginas legibles.')
            if count > 60:
                raise ValueError('El PDF supera 60 páginas; requiere revisión de archivo.')
            try:
                native_pdf = pdfplumber.open(io.BytesIO(data))
            except Exception:
                native_pdf = None
            try:
                for index in range(count):
                    native, image_text = '', False
                    if native_pdf is not None and index < len(native_pdf.pages):
                        page = native_pdf.pages[index]
                        try:
                            native = native_extractor(page) or ''
                            image_text = _has_image_text(page)
                        except Exception as error:
                            warnings.append(f'Página {index + 1}: lector principal falló ({type(error).__name__}).')
                    alternate = fallback[index].get_textpage().get_text_range()
                    method = 'native'
                    if len(alternate.strip()) > max(20, len(native.strip()) * 1.3):
                        native, method = alternate, 'alternate_reader'
                    needs_ocr = len(native.strip()) < 80 or image_text
                    result, ocr_chars, failed = native, 0, False
                    if needs_ocr:
                        try:
                            ocr = _ocr_page(data, index, fallback)
                            ocr_chars = len(ocr)
                            result = _merge_text(native, ocr)
                            method = 'mixed_ocr' if native.strip() else 'ocr'
                        except Exception as error:
                            failed = True
                            warnings.append(f'Página {index + 1}: OCR no disponible o fallido ({type(error).__name__}).')
                    pages.append({'page': index + 1, 'method': method, 'native_chars': len(native), 'ocr_chars': ocr_chars,
                                  'text_chars': len(result.strip()), 'ocr_attempted': needs_ocr, 'ocr_failed': failed})
                    if result.strip():
                        texts.append(result.strip())
            finally:
                if native_pdf is not None:
                    native_pdf.close()
        finally:
            fallback.close()
    return {'text': clean_text_encoding('\n\n'.join(texts)).strip(), 'pages': pages, 'warnings': warnings,
            'version': EXTRACTION_VERSION}