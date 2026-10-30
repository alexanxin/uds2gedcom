"""A merged tree as GEDCOM 5.5.1 in UTF-8: the file every genealogy program
imports (Gramps, MyHeritage, Ancestry, FamilySearch, webtrees, ...)."""
import collections
import re

from . import __version__, translit

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
EVENT_TAGS = {"birth": "BIRT", "christening": "CHR", "baptism": "BAPM", "death": "DEAT", "burial": "BURI"}
FACT_TAGS = {"occupation": "OCCU", "education": "EDUC", "religion": "RELI"}
WIDTH = 200  # GEDCOM allows 255 characters a line; longer values continue with CONC

_DATE = re.compile(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(?: \((.*)\))?")


def _script(raw, latin):
    return translit.latin(raw) if latin else translit.native(raw)


def date(s, latin=False):
    """A merged-tree date ("1974-03-06", "1803 (okolu 1803)") as a GEDCOM date."""
    if not s:
        return None
    m = _DATE.fullmatch(s)
    if not m:
        return f"({_script(s, latin)})"
    year, month, day, phrase = m.groups()
    parts = [str(int(day)) if day else "", MONTHS[int(month) - 1] if month else "", year]
    exact = " ".join(p for p in parts if p)
    return f"INT {exact} ({_script(phrase, latin)})" if phrase else exact


def _chunks(s):
    out = []
    while len(s) > WIDTH:
        cut = WIDTH
        # readers may trim spaces at either end of a line, and @@ must stay whole
        while cut > 1 and (s[cut - 1] in " @" or s[cut] == " "):
            cut -= 1
        out.append(s[:cut])
        s = s[cut:]
    return out + [s]


def lines(level, tag, value=None, xref=None):
    """One GEDCOM field, split into CONT (new line) and CONC (same line) parts."""
    head = f"{level} {xref} {tag}" if xref else f"{level} {tag}"
    if value is None or value == "":
        return [head]
    out = []
    for n, part in enumerate(str(value).replace("@", "@@").split("\n")):
        first, *rest = _chunks(part)
        start = head if n == 0 else f"{level + 1} CONT"
        out.append(f"{start} {first}" if first else start)
        out += [f"{level + 1} CONC {c}" for c in rest]
    return out


def _pointer(level, tag, rid):
    return f"{level} {tag} @{rid}@"


def _event(tag, ev, side, latin):
    out = lines(1, tag)
    if ev.get("date"):
        out += lines(2, "DATE", date(ev["date"], latin))
    if ev.get("place"):
        out += lines(2, "PLAC", ev["place"][side])
    return out


def _name(p, side):
    given = p["given"][side] if p["given"] else ""
    surname = p["surname"][side] if p["surname"] else ""
    return given, surname, f"{given} /{surname}/".strip()


def _person(p, famc, fams, latin):
    side = "latin" if latin else "text"
    given, surname, full = _name(p, side)
    out = lines(0, "INDI", xref=f"@{p['id']}@") + lines(1, "NAME", full)
    if given:
        out += lines(2, "GIVN", given)
    if surname:
        out += lines(2, "SURN", surname)
    romanised = _name(p, "latin")[2]
    if not latin and romanised != full:
        out += lines(2, "ROMN", romanised) + lines(3, "TYPE", "romanized")
    notes = []
    for f in p["facts"]:
        text = f["text"][side]
        if f["type"] == "alias":
            out += lines(1, "NAME", text) + lines(2, "TYPE", "aka")
    out += lines(1, "SEX", p["sex"] or "U")
    for etype, tag in EVENT_TAGS.items():
        if p["events"].get(etype):
            out += _event(tag, p["events"][etype], side, latin)
    for f in p["facts"]:
        text = f["text"][side]
        if f["type"] in FACT_TAGS:
            out += lines(1, FACT_TAGS[f["type"]], text)
        elif f["type"] == "note":
            notes.append(text)
        elif f["type"] != "alias":
            notes.append(f"{_script(f['type'], latin)}: {text}")
    out += [_pointer(1, "FAMC", fid) for fid in famc]
    out += [_pointer(1, "FAMS", fid) for fid in fams]
    if p["sources"]:
        notes.append("From: " + "; ".join(f"{s['file']} #{s['record']}" for s in p["sources"]))
    for c in p["conflicts"]:
        values = "; ".join(f"{v['value'] if c['field'] == 'sex' else _script(str(v['value']), latin)}"
                           f" ({v['file']} #{v['record']})" for v in c["values"])
        notes.append(f"Records disagree on {c['field']}: {values}")
    if notes:
        out += lines(1, "NOTE", "\n".join(notes))
    return out


def _family(f, latin):
    side = "latin" if latin else "text"
    out = lines(0, "FAM", xref=f"@{f['id']}@")
    if f["husb"]:
        out.append(_pointer(1, "HUSB", f["husb"]))
    if f["wife"]:
        out.append(_pointer(1, "WIFE", f["wife"]))
    out += [_pointer(1, "CHIL", c) for c in f["children"]]
    if f["events"].get("marriage"):
        out += _event("MARR", f["events"]["marriage"], side, latin)
    if f.get("files"):
        out += lines(1, "NOTE", "From: " + "; ".join(f"{s['file']} #{s['record']}" for s in f["files"]))
    return out


def write(tree, fh, latin=False):
    """Write the tree to an open text file (open it with newline="")."""
    famc, fams = collections.defaultdict(list), collections.defaultdict(list)
    for f in tree["families"]:
        for parent in (f["husb"], f["wife"]):
            if parent:
                fams[parent].append(f["id"])
        for c in f["children"]:
            famc[c].append(f["id"])
    out = (lines(0, "HEAD") + lines(1, "SOUR", "UDS2GEDCOM") + lines(2, "VERS", __version__)
           + lines(2, "NAME", "uds2gedcom") + [_pointer(1, "SUBM", "U1")] + lines(1, "GEDC")
           + lines(2, "VERS", "5.5.1") + lines(2, "FORM", "LINEAGE-LINKED") + lines(1, "CHAR", "UTF-8")
           + lines(0, "SUBM", xref="@U1@") + lines(1, "NAME", "uds2gedcom"))
    for p in tree["people"]:
        out += _person(p, famc[p["id"]], fams[p["id"]], latin)
    for f in tree["families"]:
        out += _family(f, latin)
    out += lines(0, "TRLR")
    # the byte order mark helps older Windows programs recognise UTF-8
    fh.write("﻿" + "\r\n".join(out) + "\r\n")
