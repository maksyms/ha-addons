import pytest
from pathlib import Path
from adapters.evernote import parse_enex, format_note_atom


SAMPLE_ENEX = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export>
  <note>
    <title>My First Note</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div>Hello world</div>
<div><br/></div>
<div>This is a <b>test</b> note.</div>
</en-note>]]></content>
    <created>20260411T120000Z</created>
    <updated>20260411T130000Z</updated>
    <note-attributes>
      <source-url>https://example.com/article</source-url>
    </note-attributes>
  </note>
  <note>
    <title>Second Note</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note>
<div>Short note</div>
</en-note>]]></content>
    <created>20260410T080000Z</created>
    <updated>20260410T090000Z</updated>
    <note-attributes/>
  </note>
</en-export>"""


class TestParseEnex:
    def test_parses_two_notes(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert len(notes) == 2

    def test_extracts_title(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert notes[0]["title"] == "My First Note"
        assert notes[1]["title"] == "Second Note"

    def test_extracts_content_as_html(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert "Hello world" in notes[0]["content_html"]

    def test_extracts_created_date(self, tmp_path):
        enex_file = tmp_path / "test.enex"
        enex_file.write_text(SAMPLE_ENEX)
        notes = list(parse_enex(enex_file))
        assert notes[0]["created"] == "2026-04-11T12:00:00Z"


class TestFormatNoteAtom:
    def test_formats_note_as_markdown(self):
        note = {
            "title": "My Note",
            "content_html": "<div>Hello <b>world</b></div>",
            "created": "2026-04-11T12:00:00Z",
        }
        content = format_note_atom(note)
        assert content.startswith("# My Note\n\n")
        assert "Hello" in content
        assert "**world**" in content

    def test_handles_empty_content(self):
        note = {"title": "Empty", "content_html": "", "created": "2026-04-11T12:00:00Z"}
        content = format_note_atom(note)
        assert content == "# Empty"
