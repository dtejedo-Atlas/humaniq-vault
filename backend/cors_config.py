"""Fail closed: credentialed CORS must use explicit origins from configuration."""
import logging
import os
from urllib.parse import urlsplit
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Respaldo explícito cuando la clave gestionada CORS_ORIGINS llega como comodín ("*"),
# que nunca es utilizable con credenciales. Se puede sustituir con HUMANIQ_CORS_ORIGINS.
FALLBACK_ORIGINS = (
    'https://atlas-recruiting-ai.emergent.host',
    'https://atlas-recruiting-ai.preview.emergentagent.com',
)


def get_cors_origins():
    raw = os.environ.get('HUMANIQ_CORS_ORIGINS')
    if not (raw and raw.strip()):
        raw = os.environ['CORS_ORIGINS']
        if raw.strip().strip('/') == '*':
            logger.warning(
                'CORS_ORIGINS llegó como comodín; se usan los orígenes explícitos de respaldo. '
                'Defina HUMANIQ_CORS_ORIGINS para controlarlos.'
            )
            return list(FALLBACK_ORIGINS)
    values = [origin.strip().rstrip('/') for origin in raw.split(',') if origin.strip()]
    if not values:
        raise RuntimeError('CORS_ORIGINS debe contener los orígenes autorizados explícitos')
    for origin in values:
        parsed = urlsplit(origin)
        if ('*' in origin or parsed.scheme not in ('https', 'http') or not parsed.netloc
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise RuntimeError('CORS_ORIGINS contiene un origen no válido; no se permiten comodines con credenciales')
    return list(dict.fromkeys(values))


class PreviewAwareCORSMiddleware(CORSMiddleware):
    """Normalize one explicitly configured preview proxy alias; never allow arbitrary origins."""
    def __init__(self, app, **kwargs):
        self.proxy_origin = os.environ.get('CORS_PREVIEW_PROXY_ORIGIN')
        self.public_origin = os.environ.get('CORS_PREVIEW_PUBLIC_ORIGIN')
        if bool(self.proxy_origin) != bool(self.public_origin):
            raise RuntimeError('La configuración de origen del proxy está incompleta')
        if self.proxy_origin:
            parsed = urlsplit(self.proxy_origin)
            if (parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment
                    or parsed.username or '*' in self.proxy_origin or self.public_origin not in kwargs.get('allow_origins', [])):
                raise RuntimeError('El alias del proxy debe corresponder a un origen público autorizado')
        super().__init__(app, **kwargs)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and self.proxy_origin:
            original = self.proxy_origin.encode()
            if any(key.lower() == b'origin' and value == original for key, value in scope['headers']):
                scope = {**scope, 'headers': [(key, self.public_origin.encode() if key.lower() == b'origin' else value)
                                             for key, value in scope['headers']]}
        await super().__call__(scope, receive, send)