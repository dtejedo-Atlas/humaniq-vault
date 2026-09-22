"""Extract OOXML stories, including tables/textboxes, once and in document order."""
import io
import zipfile
from lxml import etree
from text_utils import clean_text_encoding

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'


def _story_text(xml):
    root = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    chunks = []

    def visit(node):
        if node.tag in {W + 'del', W + 'instrText'}:
            return
        if node.tag == MC + 'AlternateContent':
            alternatives = list(node)
            selected = next((child for child in alternatives if next(child.iter(W + 't'), None) is not None), None)
            if selected is not None:
                visit(selected)
            return
        if node.tag == W + 't':
            chunks.append(node.text or '')
            return
        if node.tag in {W + 'tab', W + 'br', W + 'cr'}:
            chunks.append('\t' if node.tag == W + 'tab' else '\n')
        for child in node:
            visit(child)
        if node.tag == W + 'p':
            chunks.append('\n')

    visit(root)
    return '\n'.join(line.strip() for line in ''.join(chunks).splitlines() if line.strip())


def extract_docx(file_bytes):
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
            raise ValueError('El contenido descomprimido del DOCX excede el límite seguro.')
        names = archive.namelist()
        headers = sorted(name for name in names if name.startswith('word/header') and name.endswith('.xml'))
        footers = sorted(name for name in names if name.startswith('word/footer') and name.endswith('.xml'))
        stories, seen_auxiliary = [], set()
        for name in headers + ['word/document.xml'] + footers:
            text = _story_text(archive.read(name))
            if name != 'word/document.xml':
                if text in seen_auxiliary:
                    continue
                seen_auxiliary.add(text)
            if text:
                stories.append(text)
        return clean_text_encoding('\n\n'.join(stories)).strip()