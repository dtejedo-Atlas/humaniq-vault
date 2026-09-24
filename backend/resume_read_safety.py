"""Read the current original CV before classification; never classify an unreadable file."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from cv_recheck_service import current_resume
from document_parser import DocumentParser
from storage_service import storage_service

ROOT = Path(__file__).parent


class ResumeReadError(Exception):
    def __init__(self, reason, message):
        self.reason = reason
        super().__init__(message)


def read_original(reference):
    key = reference.get('key')
    if not isinstance(key, str) or not key:
        raise ResumeReadError('missing_reference', 'No se encontró la referencia al CV original.')
    if key.startswith('atlas-talent-vault/'):
        try:
            data, _ = storage_service.get_object(key)
            return data
        except Exception as error:
            code = getattr(getattr(error, 'response', None), 'status_code', None)
            message = ('El CV original no se encontró en el almacenamiento remoto.' if code == 404 else
                       'No se pudo recuperar el CV original del almacenamiento remoto. Vuelve a intentarlo o carga el archivo.')
            raise ResumeReadError('remote_read_failed', message) from error
    path = (ROOT / key).resolve()
    if not path.is_relative_to((ROOT / 'uploads').resolve()):
        raise ResumeReadError('invalid_reference', 'La referencia al CV original no es válida.')
    try:
        return path.read_bytes()
    except Exception as error:
        raise ResumeReadError('local_read_failed', 'El CV original local no está disponible o no se puede leer. Vuelve a subirlo.') from error


async def readable_resume(db, candidate):
    try:
        reference = await current_resume(db, candidate)
    except ValueError as error:
        raise ResumeReadError('missing_resume', 'Este candidato no tiene un CV original disponible para clasificar.') from error
    raw = await asyncio.to_thread(read_original, reference)
    try:
        extraction = await asyncio.to_thread(DocumentParser.extract_with_details, raw, reference['type'])
    except Exception as error:
        raise ResumeReadError('extraction_failed', 'No se pudo extraer texto legible del CV original. Verifica el archivo o completa la ficha manualmente.') from error
    text = extraction.get('text') or ''
    if not extraction.get('readable') or len(text.strip()) < 50:
        raise ResumeReadError('unreadable_resume', 'El CV original no contiene suficiente texto legible, incluso tras la extracción disponible.')
    return text, reference


def snapshot_filter(candidate):
    return {'id': candidate['id'], 'is_deleted': {'$ne': True},
            'updated_at': candidate.get('updated_at'), 'resume_files': candidate.get('resume_files')}


async def mark_manual_capture(db, candidate, error):
    message = f'Requiere captura manual. {error}'
    previous = candidate.get('ai_classification') or (candidate.get('classification_read_error') or {}).get('previous_classification')
    now = datetime.now(timezone.utc).isoformat()
    result = await db.candidates.update_one(snapshot_filter(candidate), {'$set': {
        'review_status': 'manual_capture', 'review_message': message, 'ai_classification': None,
        'classification_read_error': {'reason': error.reason, 'message': str(error), 'failed_at': now,
                                      'previous_classification': previous},
        'updated_at': now,
    }})
    if result.matched_count != 1:
        raise HTTPException(409, 'La ficha cambió durante la lectura del CV. No se sobrescribieron los cambios recientes.')
    return message