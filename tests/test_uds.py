import struct

from uds2gedcom import uds

from uds_builder import birth, death, family, marriage, occupation, person, write


def test_reads_fields_to_the_end_of_the_block():
    # the stored length undercounts on purpose: real files do this too
    body = (struct.pack("<HH", 10, 0x1E) + b"Goran\0" + struct.pack("<HH", 12, 0x23) + b"PETRE^E\0"
            + struct.pack("<HHH", 6, 0x1B, 1))
    head = struct.pack("<HBB", 1, uds.PERSON, 0x21) + b"\x05\x03\x02\x01"
    head += struct.pack("<III", 20, 7, 1_000_000_000) + struct.pack("<H", 20)
    recs = uds.records((b"\0" * 8 + head + body).ljust(0x80, b"\0"))
    fields = dict(recs[(uds.PERSON, 7)]["fields"])
    assert uds.raw_text(fields[0x1E]) == "Goran"
    assert uds.raw_text(fields[0x23]) == "PETRE^E"
    assert uds.u32(fields[0x1B]) == 1


def test_full_date():
    assert uds.decode_date(bytes.fromhex("00c6d89b")) == {"year": 1974, "month": 3, "day": 6, "text": None}


def test_year_only_date():
    assert uds.decode_date(bytes.fromhex("0000b09a")) == {"year": 1900, "month": None, "day": None, "text": None}


def test_date_with_text():
    d = uds.decode_date(bytes.fromhex("02002c99") + b"okolu 1803\0")
    assert d["year"] == 1803 and d["text"] == "okolu 1803"


def test_empty_date():
    assert uds.decode_date(b"\0\0\0\0") is None
    assert uds.decode_date(b"") is None


def test_text_is_read_as_windows_1252():
    assert uds.raw_text("Šárka".encode("cp1252") + b"\0junk") == "Šárka"
    assert uds.raw_text("Zoë Smith".encode("cp1252")) == "Zoë Smith"
    assert uds.raw_text(b"odd \x81 byte") == "odd \x81 byte"  # undefined in 1252: kept as Latin-1


def test_a_whole_file(tmp_path):
    path = write(tmp_path / "f.uds", [
        person(1, "Walter", "HAYES", "M", events=[birth((1921, 4, 2), "Leeds"), death((1990,)),
                                                 occupation("Carpenter")], spouse_in=[10]),
        person(2, "Edith", "MOORE", "F", spouse_in=[10]),
        person(3, "Joan", "HAYES", "F", events=[birth((1950, None, None, "about 1950"))], child_of=[10]),
        family(10, husband=1, wife=2, children=[3], wedding=marriage((1948, 6, 12), "York")),
    ])
    db = uds.load(path)
    walter, joan = db["people"][1], db["people"][3]
    assert (walter["given"], walter["surname"], walter["sex"]) == ("Walter", "HAYES", "M")
    assert uds.event(walter, "birth") == {"type": "birth", "place": "Leeds", "text": [],
                                         "date": {"year": 1921, "month": 4, "day": 2, "text": None}}
    assert uds.event(walter, "death")["date"]["year"] == 1990
    assert uds.event(walter, "occupation")["text"] == ["Carpenter"]
    assert uds.event(joan, "birth")["date"] == {"year": 1950, "month": None, "day": None, "text": "about 1950"}
    fam = db["families"][10]
    assert (fam["husb"], fam["wife"], fam["children"]) == (1, 2, [3])
    assert fam["events"][0]["date"]["year"] == 1948 and fam["events"][0]["place"] == "York"


def test_links_to_missing_records_are_dropped(tmp_path):
    path = write(tmp_path / "f.uds", [person(1, "Ann", "LEE", "F", child_of=[99]),
                                      family(10, husband=1, wife=55, children=[77])])
    db = uds.load(path)
    assert db["people"][1]["famc"] == []
    assert (db["families"][10]["wife"], db["families"][10]["children"]) == (None, [])
