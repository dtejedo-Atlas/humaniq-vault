"""Detección de nombres mal parseados (placeholder, nombre de archivo, basura)."""
import re
import unicodedata

PLACEHOLDERS = {"no especificado", "sin nombre", "n/a", "na", "desconocido", "nombre", "candidato", "sin datos"}
FILE_HINTS = re.compile(r"\.(pdf|docx?|rtf|odt)\b|^(cv|curriculum|curriculum vitae|resume|candidato)\b", re.IGNORECASE)
SUSPICIOUS_CHARS = re.compile(r"[0-9_@|/\\]|\(\d+\)")

SUSPICIOUS_NAME_MESSAGE = "Nombre dudoso: no se pudo leer bien el nombre del CV. Revisa y captúralo manualmente."


def suspicious_name_issues(name):
    """Lista de problemas detectados en el nombre. Vacía si el nombre parece correcto."""
    issues = []
    clean = (name or "").strip()
    if not clean:
        return ["vacio"]
    if clean.lower() in PLACEHOLDERS:
        issues.append("placeholder")
    if FILE_HINTS.search(clean):
        issues.append("nombre_de_archivo")
    if SUSPICIOUS_CHARS.search(clean):
        issues.append("caracteres_invalidos")
    words = clean.split()
    if len(words) == 1:
        issues.append("una_sola_palabra")
    if len(words) > 6:
        issues.append("demasiadas_palabras")
    letters = [c for c in clean if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 3:
        issues.append("todo_mayusculas")
    if letters and all(c.islower() for c in letters):
        issues.append("todo_minusculas")
    if any(unicodedata.category(c) == "Cc" for c in clean) or "  " in clean:
        issues.append("espacios_o_control")
    return issues


def title_case_name(name):
    """Normaliza la capitalización de un nombre propio en español."""
    small = {"de", "del", "la", "las", "los", "y", "da", "das", "do", "dos", "van", "von"}
    parts = []
    for index, word in enumerate(re.split(r"(\s+|-)", (name or "").strip().lower())):
        if not word.strip() or word == "-":
            parts.append(word)
            continue
        parts.append(word if (word in small and index > 0) else word[0].upper() + word[1:])
    return "".join(parts)
