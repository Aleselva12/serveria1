"""Owner Word notes editor: patch document.xml, preserve all other package parts."""
from copy import deepcopy
from difflib import SequenceMatcher
from io import BytesIO
import re
import zipfile

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from lxml import etree
from pydantic import BaseModel, Field

from core.file_editor import revision, save_bytes

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
MAX_FILE = 10 * 1024 * 1024
MAX_EXPANDED = 30 * 1024 * 1024

def tag(name):
    return '{' + W + '}' + name


def read_word(target):
    if target.suffix.lower() != '.docx':
        raise HTTPException(415, 'Usa un documento .docx. I vecchi .doc vanno prima salvati come .docx in Word o LibreOffice.')
    if not target.is_file():
        raise HTTPException(400, 'Seleziona un documento Word.')
    with target.open('rb') as stream:
        content = stream.read(MAX_FILE + 1)
    if len(content) > MAX_FILE:
        raise HTTPException(413, 'Documento oltre il limite di 10 MiB.')
    return content


def xml(content):
    if b'<!DOCTYPE' in content.upper():
        raise ValueError('DOCTYPE not supported')
    return etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))


def package(content):
    archive = None
    try:
        archive = zipfile.ZipFile(BytesIO(content))
        infos = archive.infolist()
        if len(infos) > 2000 or len({i.filename for i in infos}) != len(infos) or sum(i.file_size for i in infos) > MAX_EXPANDED:
            raise ValueError('Package limits')
        if any(i.flag_bits & 1 for i in infos):
            raise ValueError('Encrypted file')
        document = xml(archive.read('word/document.xml'))
        if document.tag != tag('document') or document.find('w:body', NS) is None:
            raise ValueError('Not a Word document')
        paragraphs = list(document.iter(tag('p')))
        if len(paragraphs) > 3000 or sum(len(p.text or '') for p in document.iter(tag('t'))) > 1_000_000:
            raise ValueError('Document too large')
        protected = any(i.filename.startswith('_xmlsignatures/') for i in infos)
        if 'word/settings.xml' in archive.namelist():
            settings = xml(archive.read('word/settings.xml'))
            protected |= any(p.get(tag('enforcement')) in {'1', 'true', 'on'} for p in settings.iter(tag('documentProtection')))
        return archive, document, paragraphs, protected
    except (ValueError, KeyError, zipfile.BadZipFile, RuntimeError, etree.XMLSyntaxError, NotImplementedError, OSError):
        if archive is not None:
            archive.close()
        raise HTTPException(422, 'Documento Word non leggibile, protetto da password o troppo complesso per questo editor.') from None


def run_text(run):
    return ''.join((child.text or '') if child.tag == tag('t') else '\t' if child.tag == tag('tab') else '\n' if child.tag in {tag('br'), tag('cr')} else '' for child in run)


def editable(paragraph):
    if any(parent.tag in {tag('sdt'), tag('ins'), tag('del')} for parent in paragraph.iterancestors()):
        return False
    allowed = {tag(n) for n in ['pPr', 'r', 'hyperlink', 'bookmarkStart', 'bookmarkEnd', 'proofErr']}
    if any(child.tag not in allowed for child in paragraph):
        return False
    if any(child.tag not in {tag(n) for n in ['rPr', 't', 'tab', 'br', 'cr']} for run in paragraph.iter(tag('r')) for child in run):
        return False
    if any(br.get(tag('type')) not in {None, 'textWrapping'} for br in paragraph.iter(tag('br'))):
        return False
    return True


def paragraph_view(paragraph, ident, protected):
    def toggle(props, name):
        value = props.find('w:' + name, NS) if props is not None else None
        return value is not None and value.get(tag('val'), 'true') not in {'0', 'false', 'off', 'none'}
    runs = []
    for run in paragraph.iter(tag('r')):
        props = run.find('w:rPr', NS)
        color = props.find('w:color', NS) if props is not None else None
        color = color.get(tag('val'), '') if color is not None else ''
        runs.append({'text': run_text(run), 'bold': toggle(props, 'b'), 'italic': toggle(props, 'i'),
                     'underline': toggle(props, 'u'), 'color': '#' + color if re.fullmatch(r'[0-9A-Fa-f]{6}', color) else None})
    style = paragraph.find('w:pPr/w:pStyle', NS)
    style = style.get(tag('val'), '') if style is not None else ''
    heading = re.search(r'(?:heading|titolo)([1-6])', style, re.I)
    return {'id': ident, 'text': ''.join(r['text'] for r in runs), 'runs': runs,
            'heading': int(heading[1]) if heading else 0,
            'list': paragraph.find('w:pPr/w:numPr', NS) is not None,
            'editable': not protected and editable(paragraph)}


def view(content, archive, document, paragraphs, protected):
    ids = {p: 'p' + str(i) for i, p in enumerate(paragraphs)}
    def blocks(parent):
        result = []
        for child in parent:
            if child.tag == tag('p'):
                result.append({'kind': 'paragraph', 'id': ids[child]})
            elif child.tag == tag('tbl'):
                rows = []
                for row in child.findall('w:tr', NS):
                    cells = []
                    for cell in row.findall('w:tc', NS):
                        span = cell.find('w:tcPr/w:gridSpan', NS)
                        value = span.get(tag('val'), '1') if span is not None else '1'
                        cells.append({'blocks': blocks(cell), 'colSpan': min(50, max(1, int(value))) if value.isdigit() else 1})
                    rows.append({'cells': cells})
                result.append({'kind': 'table', 'rows': rows})
            elif child.tag not in {tag(name) for name in ['sectPr', 'tcPr', 'tblPr', 'tblGrid', 'trPr']}:
                result.append({'kind': 'notice', 'text': 'Elemento avanzato: consultare il documento originale per il layout completo.'})
                for p in child.iter(tag('p')):
                    result.append({'kind': 'paragraph', 'id': ids[p]})
        return result
    return {'revision': revision(content), 'editable': not protected,
            'paragraphs': [paragraph_view(p, ids[p], protected) for p in paragraphs],
            'blocks': blocks(document.find('w:body', NS)),
            'note': 'Documento protetto o firmato: disponibile in lettura.' if protected else 'Vista degli appunti: il layout di pagina di Word può differire. Oggetti avanzati e immagini restano nel file originale.'}


def replace_paragraph(paragraph, text):
    """Assign new characters to the original runs; keep all run properties/wrappers."""
    runs = list(paragraph.iter(tag('r')))
    if not runs:
        runs = [etree.SubElement(paragraph, tag('r'))]
    parts = [run_text(run) for run in runs]
    old = ''.join(parts)
    positions = []
    for index, part in enumerate(parts):
        positions.extend([index] * len(part))
    output = [''] * len(runs)
    for mode, start, end, new_start, new_end in SequenceMatcher(None, old, text).get_opcodes():
        if mode == 'equal':
            for position in range(start, end):
                output[positions[position]] += old[position]
        elif mode in {'replace', 'insert'}:
            index = positions[start] if start < len(positions) else positions[-1] if positions else 0
            output[index] += text[new_start:new_end]
    for run, value in zip(runs, output):
        for child in list(run):
            if child.tag != tag('rPr'):
                run.remove(child)
        for chunk in re.split(r'([\t\n])', value):
            if chunk in {'\t', '\n'}:
                etree.SubElement(run, tag('tab') if chunk == '\t' else tag('br'))
            elif chunk:
                element = etree.SubElement(run, tag('t'))
                element.set(XML_SPACE, 'preserve')
                element.text = chunk


class Note(BaseModel):
    after: str = Field(pattern=r'^(?:p\d+|end)$')
    text: str = Field(min_length=1, max_length=30000)


class WordSave(BaseModel):
    root_id: str
    path: str
    revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    edits: dict[str, str] = Field(default_factory=dict, max_length=300)
    notes: list[Note] = Field(default_factory=list, max_length=100)


def patch_document(content, body):
    archive, document, paragraphs, protected = package(content)
    try:
        if protected:
            raise HTTPException(403, 'Documento protetto o firmato: aprilo in Word.')
        mapping = {'p' + str(i): p for i, p in enumerate(paragraphs)}
        if sum(len(text) for text in body.edits.values()) + sum(len(note.text) for note in body.notes) > 1_000_000:
            raise HTTPException(413, 'Troppe modifiche in un singolo salvataggio.')
        def select(ident):
            p = mapping.get(ident)
            if p is None or not editable(p):
                raise HTTPException(422, 'Paragrafo non modificabile. Riapri il documento o usa Word per gli elementi avanzati.')
            return p
        def valid_text(text):
            if len(text) > 30000 or any(ord(c) < 32 and c not in '\t\n\r' for c in text):
                raise HTTPException(422, 'Testo del paragrafo non valido o troppo lungo.')
            return text.replace('\r\n', '\n').replace('\r', '\n')
        for ident, text in body.edits.items():
            replace_paragraph(select(ident), valid_text(text))
        anchors = {}
        for note in body.notes:
            original = select(note.after) if note.after != 'end' else None
            body_element = document.find('w:body', NS)
            last = next((child for child in reversed(body_element) if child.tag != tag('sectPr')), None)
            anchor = anchors.get(note.after, original if original is not None else last)
            for line in valid_text(note.text).split('\n'):
                new = etree.Element(tag('p'))
                props = original.find('w:pPr', NS) if original is not None else None
                if props is not None:
                    props = deepcopy(props)
                    for child in list(props):
                        if child.tag in {tag('pStyle'), tag('numPr'), tag('sectPr')}:
                            props.remove(child)
                    new.append(props)
                replace_paragraph(new, line)
                if anchor is not None:
                    anchor.addnext(new)
                else:
                    body_element.insert(0, new)
                anchor = new
            anchors[note.after] = anchor
        result = BytesIO()
        with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            output.comment = archive.comment
            for info in archive.infolist():
                data = etree.tostring(document, encoding='UTF-8', xml_declaration=True, standalone=True) if info.filename == 'word/document.xml' else archive.read(info.filename)
                output.writestr(info, data)
        if len(result.getvalue()) > MAX_FILE:
            raise HTTPException(413, 'Documento risultante oltre 10 MiB.')
        return result.getvalue()
    except (ValueError, UnicodeError, zipfile.BadZipFile, etree.LxmlError, RuntimeError, NotImplementedError, OSError):
        raise HTTPException(422, 'Modifiche non valide per questo documento Word.') from None
    finally:
        archive.close()


def register_word_editor(router, root_provider):
    from core.server_files import operation, root_for, resolve, exists

    @router.get('/word')
    def open_word(root_id: str, path: str):
        with operation():
            root, base = root_for(root_id, root_provider=root_provider)
            target = resolve(base, path)
            exists(target)
            content = read_word(target)
            archive, document, paragraphs, protected = package(content)
            try:
                data = view(content, archive, document, paragraphs, protected)
                data['editable'] = root['writable'] and data['editable']
                return JSONResponse(data, headers={'Cache-Control': 'private, no-store'})
            finally:
                archive.close()

    @router.post('/word')
    def save_word(body: WordSave):
        with operation():
            _, base = root_for(body.root_id, write=True, root_provider=root_provider)
            target = resolve(base, body.path)
            exists(target)
            content = read_word(target)
            if revision(content) != body.revision:
                raise HTTPException(409, 'Il documento è cambiato dopo l’apertura. Conserva i tuoi appunti e riaprilo prima di salvare.')
            updated = patch_document(content, body)
            # Validate the candidate before publication; the saved file must open here again.
            archive, document, paragraphs, protected = package(updated)
            try:
                data = view(updated, archive, document, paragraphs, protected)
            finally:
                archive.close()
            result = save_bytes(base, body.path, content, updated, body.revision)
            return {**data, **result}
