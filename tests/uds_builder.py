"""Writes small .uds files for the tests and examples (layout: docs/format.md).

    write(path, [person(1, "Ana", "LAZAROVA", "F", events=[birth((1950, 3, 6), "Leeds")]),
                 family(10, husband=2, wife=1, children=[3])])
"""
import struct

PERSON, FAMILY = 1, 2
BLOCK = 0x80
SAVED = 1_400_000_000  # May 2014


def _text(s):
    return s.encode("cp1252") + b"\0"


def _tlv(tag, data):
    return struct.pack("<HH", len(data) + 4, tag) + data


def _slot(data):
    return struct.pack("<I", len(data) + 4) + data


def date(year=None, month=None, day=None, text=""):
    v = (((year + 8000) if year else 0) << 10 | (month or 0) << 6 | (day or 0)) << 8
    return struct.pack("<I", v) + (_text(text) if text else b"")


def event(etype, when=None, place=None, notes=(), family=False):
    """when: (year, month, day) or (year, month, day, text) or None."""
    head = b"\0" * 8 + struct.pack("<I", etype if family else 0)
    slots = [] if family else [struct.pack("<H", etype)]
    if when is not None or place is not None:
        slots.append(date(*when) if when else b"")
        slots.append(_text(place or ""))
    slots += [_text(n) for n in notes]
    return head + b"".join(_slot(s) for s in slots)


def birth(when=None, place=None):
    return event(10, when, place)


def death(when=None, place=None):
    return event(11, when, place)


def occupation(text):
    return event(60, notes=[text])


def marriage(when=None, place=None):
    return event(14, when, place, family=True)


def _record(kind, rid, body, ts):
    head = struct.pack("<BB", kind, 0x21) + b"\x05\x03\x02\x01"
    head += struct.pack("<III", len(body), rid, ts) + struct.pack("<H", len(body))
    blocks = -(-(8 + 2 + len(head) + len(body)) // BLOCK)
    return (b"\0" * 8 + struct.pack("<H", blocks) + head + body).ljust(blocks * BLOCK, b"\0")


def person(rid, given, surname, sex=None, events=(), child_of=(), spouse_in=(), ts=SAVED):
    body = _tlv(0x1E, _text(given)) + _tlv(0x23, _text(surname))
    if sex:
        body += _tlv(0x1B, struct.pack("<I", {"M": 1, "F": 2}[sex]))
    body += b"".join(_tlv(0x3C, struct.pack("<I", f)) for f in child_of)
    body += b"".join(_tlv(0x64, struct.pack("<I", f)) for f in spouse_in)
    body += b"".join(_tlv(0x3E8 + n, e) for n, e in enumerate(events))
    return _record(PERSON, rid, body, ts)


def family(rid, husband=None, wife=None, children=(), wedding=None, ts=SAVED):
    body = b""
    if husband:
        body += _tlv(0x50, struct.pack("<I", husband))
    if wife:
        body += _tlv(0x51, struct.pack("<I", wife))
    body += b"".join(_tlv(0x96 + n, struct.pack("<I", c)) for n, c in enumerate(children))
    if wedding:
        body += _tlv(0x5F, wedding)
    return _record(FAMILY, rid, body, ts)


def write(path, records):
    with open(path, "wb") as fh:
        fh.write(b"".join(records))
    return str(path)
