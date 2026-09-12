"""Export the exact clean chapter frames as PDF/ODP with native speaker notes."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from odf.draw import Frame, Image, Page, TextBox
from odf.opendocument import OpenDocumentPresentation
from odf.presentation import Notes
from odf.style import MasterPage, PageLayout, PageLayoutProperties
from odf.text import P
from PIL import Image as PILImage
from pypdf import PdfReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
STORY = json.loads((ROOT/'src/story.json').read_text())
TIMING = json.loads((ROOT/'src/generated/timing.json').read_text())
OUT = ROOT/'public/slides'
OUT.mkdir(parents=True, exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {'sourceStorySha256':sha(ROOT/'src/story.json'), 'timingSha256':sha(ROOT/'src/generated/timing.json'),
            'spec':[1920,1080], 'format':'Lossless raster keyframes; editable native ODP notes', 'editions':{}}
for lang in ['zh','en']:
    deck = OpenDocumentPresentation()
    deck_layout = PageLayout(name='Film16x9')
    deck_layout.addElement(PageLayoutProperties(pagewidth='33.8667cm', pageheight='19.05cm',
                                               printorientation='landscape', margin='0cm'))
    deck.automaticstyles.addElement(deck_layout)
    deck.masterstyles.addElement(MasterPage(name='Default', pagelayoutname=deck_layout))
    pdf_path = OUT/f'hermes-weekend-{lang}.pdf'
    pdf = canvas.Canvas(str(pdf_path), pagesize=(960,540), pageCompression=1)
    pdf.setTitle(f"hermes on herdr — {STORY['title'][lang]}")
    pdf.setAuthor('Hexly AI / Zheng Li')
    notes_text = [f"# {STORY['title'][lang]} — speaker notes",'']
    pages = []
    for index, (scene, timing) in enumerate(zip(STORY['scenes'],TIMING['scenes'],strict=True)):
        source = ROOT/f"public/review/stills/{lang}/{index:02}-{scene['id']}.png"
        with PILImage.open(source) as image:
            assert image.size == (1920,1080)
        note = ' '.join(scene['narration'][lang]) or ('片头音乐，无旁白。' if lang=='zh' else 'Opening music; no narration.')
        page = Page(name=f"{index:02}-{scene['id']}",masterpagename='Default')
        frame = Frame(x='0cm',y='0cm',width='33.8667cm',height='19.05cm')
        frame.addElement(Image(href=deck.addPicture(str(source)),type='simple',show='embed',actuate='onLoad'))
        page.addElement(frame)
        notes = Notes()
        note_frame = Frame(**{'class':'notes'},x='1cm',y='1cm',width='28cm',height='15cm')
        box = TextBox()
        box.addElement(P(text=note))
        note_frame.addElement(box)
        notes.addElement(note_frame)
        page.addElement(notes)
        deck.presentation.addElement(page)
        pdf.bookmarkPage(scene['id'])
        pdf.addOutlineEntry(scene['copy'][lang]['title'].replace('\n',' '),scene['id'])
        pdf.drawImage(str(source),0,0,width=960,height=540)
        pdf.showPage()
        pages.append(dict(scene=scene['id'],frame=timing['keyframe'],file=str(source.relative_to(ROOT/'public')),
                          imageSha256=sha(source),notes=note))
        notes_text += [f"## {index:02} · {scene['copy'][lang]['title'].replace(chr(10),' ')}",'',note,'']
    pdf.save()
    odp_path = OUT/f'hermes-weekend-{lang}.odp'
    deck.save(str(odp_path))
    (OUT/f'speaker-notes-{lang}.md').write_text('\n'.join(notes_text))
    # Verify the actual exported package and each embedded picture/notes entry.
    with zipfile.ZipFile(odp_path) as archive:
        assert archive.testzip() is None
        assert archive.infolist()[0].filename=='mimetype'
        assert archive.infolist()[0].compress_type==zipfile.ZIP_STORED
        assert archive.read('mimetype')==b'application/vnd.oasis.opendocument.presentation'
        xml = ET.fromstring(archive.read('content.xml'))
        ns = {'draw':'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
              'presentation':'urn:oasis:names:tc:opendocument:xmlns:presentation:1.0',
              'text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
              'xlink':'http://www.w3.org/1999/xlink'}
        actual = xml.findall('.//draw:page',ns)
        assert len(actual)==len(pages)
        for page,expected in zip(actual,pages,strict=True):
            paragraphs=page.findall('./presentation:notes//text:p',ns)
            assert '\n'.join(''.join(p.itertext()) for p in paragraphs)==expected['notes']
            href=page.find('./draw:frame/draw:image',ns).get('{http://www.w3.org/1999/xlink}href')
            assert hashlib.sha256(archive.read(href)).hexdigest()==expected['imageSha256']
    reader=PdfReader(pdf_path)
    assert len(reader.pages)==len(pages)
    for page,expected in zip(reader.pages,pages,strict=True):
        assert list(page.mediabox)==[0,0,960,540]
        pictures=list(page.images)
        assert len(pictures)==1
        with PILImage.open(ROOT/'public'/expected['file']) as original:
            assert pictures[0].image.convert('RGB').tobytes()==original.convert('RGB').tobytes()
    manifest['editions'][lang]=dict(pages=pages,pdf={'file':pdf_path.name,'sha256':sha(pdf_path)},
                                   odp={'file':odp_path.name,'sha256':sha(odp_path)},verified=True)
    print(f'{lang}: {len(pages)} PDF/ODP pages; exact image pixels and native notes verified',flush=True)
(OUT/'slides.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(ROOT/'verification/slides.json').write_text(json.dumps({'status':'passed','editions':list(manifest['editions']),
    'pagesPerEdition':len(STORY['scenes']),'pdfPixels':'exact match','odpNotes':'exact match',
    'officeApplicationReview':'Not used; exported packages and raster PDF images independently parsed.'},indent=2)+'\n')
