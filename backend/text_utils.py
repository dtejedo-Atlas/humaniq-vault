import unicodedata
import re

def normalize_for_search(text: str) -> str:
    """
    Normalizar texto para búsqueda SIN modificar el original.
    
    Convierte: "José Muñoz García" → "jose munoz garcia"
    
    Uso: Solo para búsqueda. El texto original se conserva intacto.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Normalizar Unicode a forma NFD (descomponer acentos)
    nfd = unicodedata.normalize('NFD', text)
    
    # 2. Remover marcas diacríticas (acentos, tildes)
    without_accents = ''.join(
        char for char in nfd 
        if unicodedata.category(char) != 'Mn'  # Mn = Nonspacing_Mark (acentos)
    )
    
    # 3. Lowercase
    normalized = without_accents.lower()
    
    # 4. Limpiar espacios extra
    normalized = ' '.join(normalized.split())
    
    return normalized.strip()


def clean_text_encoding(text: str) -> str:
    """
    Limpiar texto con encoding corrupto SOLO si hay evidencia de problema.
    
    NO modifica texto que ya viene bien.
    Conservador: solo corrige casos obvios de corrupción.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Detectar caracteres de reemplazo de Unicode (evidencia de corrupción)
    # � (U+FFFD) es el carácter de reemplazo
    has_replacement_char = '\ufffd' in text
    
    # Detectar patrones comunes de Latin-1 mal interpretado como UTF-8
    # Ejemplos: "JosÃ©" (debería ser "José"), "MuÃ±oz" (debería ser "Muñoz")
    latin1_corrupted_pattern = re.search(r'[ÃÂ][©ª±¡º»¿]', text)
    
    # Solo intentar corrección si hay evidencia clara de corrupción
    if has_replacement_char or latin1_corrupted_pattern:
        try:
            # Intentar re-encodear desde Latin-1
            corrected = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
            
            # Solo usar la corrección si parece mejor (menos caracteres raros)
            if corrected.count('�') < text.count('�'):
                text = corrected
        except (UnicodeDecodeError, UnicodeEncodeError):
            # Si falla, mantener el original
            pass
    
    # Normalizar a forma NFC (forma compuesta estándar)
    text = unicodedata.normalize('NFC', text)
    
    # Remover caracteres de control (excepto saltos de línea y tabs útiles)
    text = ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in '\n\r\t '
    )
    
    return text.strip()


# Tests rápidos (para verificar)
if __name__ == "__main__":
    # Test normalización
    assert normalize_for_search("José Muñoz García") == "jose munoz garcia"
    assert normalize_for_search("María López") == "maria lopez"
    assert normalize_for_search("Peña Nieto") == "pena nieto"
    assert normalize_for_search("Ñoño Sánchez") == "nono sanchez"
    
    print("✓ Normalización funcionando correctamente")
    
    # Test limpieza conservadora
    assert clean_text_encoding("José Muñoz") == "José Muñoz"  # No debe cambiar
    assert clean_text_encoding("María López") == "María López"  # No debe cambiar
    
    print("✓ Limpieza conservadora funcionando correctamente")
