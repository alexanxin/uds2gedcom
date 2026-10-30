import io
import re

import pytest

from uds2gedcom import gedcom, translit


def parse(text):
    """GEDCOM lines as (level, xref, tag, value), checked for basic validity."""
    out, last = [], -1
    for line in text.lstrip("﻿").split("\r\n")[:-1]:
        assert len(line) <= 255, line
        m = re.fullmatch(r"(\d+) (?:(@[^@]+@) )?(\w+)(?: (.*))?", line)
        assert m, line
        level = int(m.group(1))
        assert level <= last + 1, line
        last = level
        out.append((level, m.group(2), m.group(3), m.group(4)))
    return out


def records(lines):
    """{xref: [(level, tag, value), ...]} for every level-0 record."""
    recs, cur = {}, None
    for level, xref, tag, value in lines:
        if level == 0:
            cur = recs.setdefault(xref or tag, [])
        cur.append((level, tag, value))
    return recs


def name(text, latin=None):
    return {"text": text, "latin": latin or text}


TREE = {
    "people": [
        {"id": "I1", "given": name("Walter"), "surname": name("HAYES"), "sex": "M",
         "events": {"birth": {"date": "1921-04-02", "place": name("Leeds")}, "death": {"date": "1990", "place": None}},
         "facts": [{"type": "occupation", "text": name("Carpenter")}, {"type": "alias", "text": name("Wally")},
                   {"type": "Military service", "text": name("RAF 1940-45")}],
         "sources": [{"file": "hayes.uds", "record": 1}, {"file": "old.uds", "record": 4}],
         "conflicts": [{"field": "birth date", "chosen": "1921-04-02",
                        "values": [{"value": "1921-04-02", "file": "hayes.uds", "record": 1},
                                   {"value": "1922", "file": "old.uds", "record": 4}]}]},
        {"id": "I2", "given": name("Edith"), "surname": None, "sex": "F", "events": {}, "facts": [],
         "sources": [{"file": "hayes.uds", "record": 2}], "conflicts": []},
        {"id": "I3", "given": name("Joan"), "surname": name("HAYES"), "sex": None,
         "events": {"birth": {"date": "about 1950", "place": None}}, "facts": [],
         "sources": [{"file": "hayes.uds", "record": 3}], "conflicts": []},
    ],
    "families": [{"id": "F1", "husb": "I1", "wife": "I2", "children": ["I3"],
                  "events": {"marriage": {"date": "1948-06-12", "place": name("York")}},
                  "files": [{"file": "hayes.uds", "record": 10}]}],
    "stats": {},
}


def written(tree=TREE, **kw):
    fh = io.StringIO(newline="")
    gedcom.write(tree, fh, **kw)
    return fh.getvalue()


@pytest.mark.parametrize("given,expected", [
    ("1974-03-06", "6 MAR 1974"),
    ("1974-03", "MAR 1974"),
    ("1974", "1974"),
    ("1803 (about 1803)", "INT 1803 (about 1803)"),
    ("before the war", "(before the war)"),
    (None, None),
])
def test_dates(given, expected):
    assert gedcom.date(given) == expected


def test_long_and_multiline_values_are_split():
    lines = gedcom.lines(1, "NOTE", "x" * 450 + "\nsecond line")
    assert [line.split(" ", 2)[:2] for line in lines] == [["1", "NOTE"], ["2", "CONC"], ["2", "CONC"], ["2", "CONT"]]
    assert all(len(line) <= 255 for line in lines)
    assert "".join(line.split(" ", 2)[2] for line in lines[:3]) == "x" * 450
    assert lines[3] == "2 CONT second line"


def test_long_values_are_not_split_at_a_space():
    lines = gedcom.lines(1, "NOTE", ("word " * 100).strip())
    assert not any(line.endswith(" ") or line.split(" ", 2)[2].startswith(" ") for line in lines)
    assert "".join(line.split(" ", 2)[2] for line in lines) == ("word " * 100).strip()


def test_at_signs_are_doubled():
    assert gedcom.lines(1, "NOTE", "mail a@b") == ["1 NOTE mail a@@b"]


def test_a_whole_tree():
    text = written()
    recs = records(parse(text))
    assert text.startswith("﻿0 HEAD\r\n") and text.endswith("0 TRLR\r\n")
    assert (1, "CHAR", "UTF-8") in recs["HEAD"]
    walter = recs["@I1@"]
    assert (1, "NAME", "Walter /HAYES/") in walter
    assert (2, "GIVN", "Walter") in walter and (2, "SURN", "HAYES") in walter
    assert (1, "SEX", "M") in walter
    birt = walter.index((1, "BIRT", None))
    assert walter[birt + 1:birt + 3] == [(2, "DATE", "2 APR 1921"), (2, "PLAC", "Leeds")]
    assert (1, "DEAT", None) in walter and (2, "DATE", "1990") in walter
    assert (1, "OCCU", "Carpenter") in walter
    assert (1, "NAME", "Wally") in walter and (2, "TYPE", "aka") in walter
    assert (1, "FAMS", "@F1@") in walter
    notes = " ".join(v for _, t, v in walter if t in ("NOTE", "CONT", "CONC"))
    assert "Military service: RAF 1940-45" in notes
    assert "hayes.uds #1" in notes and "old.uds #4" in notes and "1922" in notes
    assert (1, "NAME", "Edith //") in recs["@I2@"]
    joan = recs["@I3@"]
    assert (1, "SEX", "U") in joan and (2, "DATE", "(about 1950)") in joan and (1, "FAMC", "@F1@") in joan
    fam = recs["@F1@"]
    assert fam[:4] == [(0, "FAM", None), (1, "HUSB", "@I1@"), (1, "WIFE", "@I2@"), (1, "CHIL", "@I3@")]
    assert (1, "MARR", None) in fam and (2, "DATE", "12 JUN 1948") in fam and (2, "PLAC", "York") in fam


def test_every_pointer_leads_somewhere():
    lines = parse(written())
    defined = {x for _, x, _, _ in lines if x}
    used = {v for _, _, _, v in lines if v and re.fullmatch(r"@[^@]+@", v)}
    assert used <= defined


def test_romanised_names_go_alongside_cyrillic():
    tree = {"people": [{"id": "I1", "given": name("Трајан", "Trajan"), "surname": name("МАРКОВ", "MARKOV"),
                        "sex": "M", "events": {"birth": {"date": "1925", "place": name("Прилеп", "Prilep")}},
                        "facts": [], "sources": [], "conflicts": []}], "families": [], "stats": {}}
    person = records(parse(written(tree)))["@I1@"]
    assert (1, "NAME", "Трајан /МАРКОВ/") in person
    assert (2, "ROMN", "Trajan /MARKOV/") in person and (3, "TYPE", "romanized") in person
    assert (2, "PLAC", "Прилеп") in person
    person = records(parse(written(tree, latin=True)))["@I1@"]
    assert (1, "NAME", "Trajan /MARKOV/") in person and (2, "PLAC", "Prilep") in person
    assert not any(t == "ROMN" for _, t, _ in person)


def test_date_phrases_follow_the_alphabet():
    translit.use("mk")
    try:
        assert gedcom.date("1803 (okolu 1803)") == "INT 1803 (околу 1803)"
        assert gedcom.date("1803 (okolu 1803)", latin=True) == "INT 1803 (okolu 1803)"
    finally:
        translit.use("plain")
