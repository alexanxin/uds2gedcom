"""Reader for Sierra Generations / EasyTree .uds databases ("UDS2x").

The format is undocumented; this layout was reverse-engineered from real
family files (see docs/format.md).
"""
import re
import struct

HEADER = re.compile(rb"..[\x01-\x06]\x21\x05\x03\x02\x01", re.S)
PERSON, FAMILY, EVENT_TYPE, SOURCE = 1, 2, 3, 4

# event types with no date slot: [type][text]
UNDATED = set(range(60, 91)) | set(range(120, 134))
EVENT_NAMES = {10: "birth", 11: "death", 14: "marriage", 21: "burial",
               31: "christening", 33: "baptism", 60: "occupation",
               62: "education", 63: "religion", 67: "alias"}


def u32(b):
    return struct.unpack("<I", b[:4].ljust(4, b"\0"))[0]


def raw_text(b):
    """Text as stored: Windows-1252 (the program ran on Windows 95/98).
    Files typed in YUSCII are plain ASCII here; translit.py maps them."""
    b = b.split(b"\0")[0]
    try:
        return b.decode("cp1252").strip()
    except UnicodeDecodeError:  # a byte 1252 leaves undefined
        return b.decode("latin1").strip()


def records(buf):
    """Live records keyed by (kind, id); the newest copy wins."""
    recs = {}
    for m in HEADER.finditer(buf):
        s = m.start()
        blocks, kind = struct.unpack_from("<H", buf, s)[0], buf[s + 2]
        _, rid, ts = struct.unpack_from("<III", buf, s + 8)
        off, end, fields = s + 22, s - 8 + blocks * 0x80, []
        while off + 4 <= end:
            ln, tag = struct.unpack_from("<HH", buf, off)
            if ln < 4 or off + ln > end:
                break
            fields.append((tag, buf[off + 4:off + ln]))
            off += ln
        key = (kind, rid)
        if key not in recs or ts >= recs[key]["ts"]:
            recs[key] = {"kind": kind, "id": rid, "ts": ts, "fields": fields}
    return recs


def subfields(d):
    off, out = 12, []
    while off + 4 <= len(d):
        ln = u32(d[off:off + 4])
        if ln < 4 or off + ln > len(d):
            break
        out.append(d[off + 4:off + ln])
        off += ln
    return out


def decode_date(b):
    """4 packed bytes, optionally followed by free text ("okolu 1803")."""
    if len(b) < 4:
        return None
    v = u32(b) >> 8
    year, month, day = (v >> 10) - 8000, (v >> 6) & 0xF, v & 0x1F
    note = raw_text(b[4:]) if len(b) > 4 else ""
    if year < 1000 and not note:
        return None
    return {"year": year if year >= 1000 else None, "month": month or None,
            "day": day or None, "text": note or None}


def decode_event(d, type_names):
    subs = subfields(d)
    etype = u32(d[8:12])
    if etype:  # family events keep the type in a fixed slot
        if subs and len(subs[0]) == 2 and u32(subs[0]) == etype:
            subs = subs[1:]
    elif subs:
        etype, subs = u32(subs[0]), subs[1:]
    else:
        return None
    name = EVENT_NAMES.get(etype) or type_names.get(etype) or f"type {etype}"
    if name.startswith("*New"):  # unnamed user-defined field
        name = "note"
    ev = {"type": name, "date": None, "place": None, "text": []}
    if etype not in UNDATED and subs:
        ev["date"] = decode_date(subs[0])
        subs = subs[1:]
        if etype in (10, 11, 14, 21, 31, 33) and subs:
            ev["place"] = raw_text(subs[0]) or None
            subs = subs[1:]
    ev["text"] = [t for t in (raw_text(s) for s in subs) if t]
    if not (ev["date"] or ev["place"] or ev["text"]):
        return None
    return ev


def load(path):
    recs = records(open(path, "rb").read())
    type_names = {r["id"]: raw_text(dict(r["fields"]).get(0x14, b""))
                  for r in recs.values() if r["kind"] == EVENT_TYPE}
    people, families, sources = {}, {}, {}
    for r in recs.values():
        if r["kind"] == PERSON:
            p = {"id": r["id"], "ts": r["ts"], "given": "", "surname": "", "sex": None,
                 "famc": [], "fams": [], "events": []}
            for tag, d in r["fields"]:
                if tag == 0x1E: p["given"] = raw_text(d)
                elif tag == 0x23: p["surname"] = raw_text(d)
                elif tag == 0x1B: p["sex"] = {1: "M", 2: "F"}.get(u32(d))
                elif tag == 0x3C and len(d) == 4: p["famc"].append(u32(d))
                elif tag == 0x64 and len(d) == 4: p["fams"].append(u32(d))
                elif tag >= 0x3E8:
                    ev = decode_event(d, type_names)
                    if ev: p["events"].append(ev)
            people[r["id"]] = p
        elif r["kind"] == FAMILY:
            f = {"id": r["id"], "ts": r["ts"], "husb": None, "wife": None,
                 "children": [], "events": []}
            for tag, d in r["fields"]:
                if tag == 0x50: f["husb"] = u32(d) or None
                elif tag == 0x51: f["wife"] = u32(d) or None
                elif 0x96 <= tag < 0xC8 and len(d) == 4: f["children"].append(u32(d))
                elif tag == 0x5F:
                    ev = decode_event(d, type_names)
                    if ev: f["events"].append(ev)
            families[r["id"]] = f
        elif r["kind"] == SOURCE:
            parts = []
            for tag, d in r["fields"]:
                if tag >= 0x3E8:
                    parts += [t for t in (raw_text(s) for s in subfields(d)[1:]) if t]
            sources[r["id"]] = parts
    _drop_dangling(people, families)
    return {"people": people, "families": families, "sources": sources}


def _drop_dangling(people, families):
    for f in families.values():
        if f["husb"] not in people: f["husb"] = None
        if f["wife"] not in people: f["wife"] = None
        f["children"] = [c for c in dict.fromkeys(f["children"]) if c in people]
    for p in people.values():
        p["famc"] = [x for x in dict.fromkeys(p["famc"]) if x in families]
        p["fams"] = [x for x in dict.fromkeys(p["fams"]) if x in families]


def event(p, etype):
    return next((e for e in p["events"] if e["type"] == etype), None)


def birth_year(p):
    ev = event(p, "birth")
    return ev["date"]["year"] if ev and ev["date"] else None
