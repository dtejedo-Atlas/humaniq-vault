"""Visible CV storage failure metadata; no local file creation or fake file references."""
from datetime import datetime, timezone


def storage_issue(file_name, error, has_previous_cv=False):
    message = 'No se pudo confirmar el guardado remoto del CV original. La ficha se conserva; vuelve a subir el archivo.'
    if has_previous_cv:
        message = 'No se pudo confirmar el guardado remoto del nuevo CV. El CV anterior se conserva; vuelve a subir el nuevo archivo.'
    return {'status': 'failed', 'file_name': file_name, 'message': message,
            'attempts': getattr(error, 'attempts', 1), 'failed_at': datetime.now(timezone.utc).isoformat()}