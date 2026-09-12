"""Export the same native keyframes and speaker notes as an OpenDocument deck."""

import json
from pathlib import Path

from odf.draw import Frame, Image, Page, TextBox
from odf.opendocument import OpenDocumentPresentation
from odf.presentation import Notes
from odf.style import MasterPage, PageLayout, PageLayoutProperties
from odf.text import P

ROOT = Path(__file__).resolve().parents[1]
pages = json.loads((ROOT / "public/slides/slides.json").read_text())["pages"]
deck = OpenDocumentPresentation()
layout = PageLayout(name="Film16x9")
layout.addElement(PageLayoutProperties(pagewidth="33.8667cm", pageheight="19.05cm",
                                      printorientation="landscape", margin="0cm"))
deck.automaticstyles.addElement(layout)
deck.masterstyles.addElement(MasterPage(name="Default", pagelayoutname=layout))
for item in pages:
    page = Page(name=item["scene"], masterpagename="Default")
    frame = Frame(x="0cm", y="0cm", width="33.8667cm", height="19.05cm")
    frame.addElement(Image(href=deck.addPicture(str(ROOT / "public" / item["file"])),
                           type="simple", show="embed", actuate="onLoad"))
    page.addElement(frame)
    notes = Notes()
    box_frame = Frame(**{"class": "notes"}, x="1cm", y="1cm", width="28cm", height="15cm")
    box = TextBox()
    box.addElement(P(text=item["notes"]))
    box_frame.addElement(box)
    notes.addElement(box_frame)
    page.addElement(notes)
    deck.presentation.addElement(page)
deck.save(str(ROOT / "public/slides/hermes-context-en.odp"))
print(f"ODP: {len(pages)} pages with full native notes")
