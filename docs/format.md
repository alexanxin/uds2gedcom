# The .uds format (Sierra Generations / EasyTree for Windows 95/98)

Undocumented. Reverse-engineered from nine real family files saved between
2003 and 2014; `uds2gedcom/uds.py` implements it. "Checked" below means
checked across all nine files. Files from other program versions may differ:
if yours does not convert, please open an issue.

## Records

The file is a sequence of 128-byte blocks. A record starts 8 bytes into a block:

| Bytes | Meaning |
|---|---|
| u16 | number of 128-byte blocks the record occupies |
| u8 | kind: 1 person, 2 family, 3 event type, 4 source |
| u8 | 0x21 live, 0x31 stale copy (ignored) |
| `05 03 02 01` | magic |
| u32 | length (undercounts; read to the block end instead) |
| u32 | record id |
| u32 | save time (Unix seconds); newest copy of an id wins |
| u16 | length again |

Then fields up to the end of the record's blocks: `[u16 length incl. header][u16 tag][data]`.
All numbers are little-endian.

## Person (kind 1)

| Tag | Meaning |
|---|---|
| 0x1e | given name |
| 0x23 | surname |
| 0x1b | sex (1 male, 2 female) |
| 0x3c | family this person is a child of |
| 0x64 | family this person is a spouse in (repeats) |
| 0x3e8… | events, one per field |

Every entry in a person's 0x64 list is confirmed by the family record. The
lists are sometimes incomplete: about 4% of family spouse slots and 4% of
child links appear only on the other side. A link counts if either side has it.

## Family (kind 2)

| Tag | Meaning |
|---|---|
| 0x50 | husband (person id) |
| 0x51 | wife (person id) |
| 0x96… | children, one tag each |
| 0x5f | marriage event |

## Event type (kind 3)

Tag 0x14 holds the name of a user-defined event type, such as an extra fact
field the user added. Built-in types need no record.

## Events

Body: 12 bytes, then u32-length-prefixed slots in fixed order. In person
events the first slot is the event type id; in family events the type sits in
the u32 at offset 8 instead. After the type:

- dated events (birth 10, death 11, marriage 14, burial 21, christening 31,
  baptism 33, user-defined ≥156): `[date][place][note…]`
- facts without a date (occupation 60, education 62, religion 63, alias 67):
  `[text…]`

Empty slots are present with length 4.

## Dates

4 bytes, optionally followed by free text such as "about 1803".
`v = u32 >> 8`: year = `(v >> 10) − 8000`, month = `(v >> 6) & 15`,
day = `v & 31`. Checked: 13,186 dated events fall in 1700–2014, and all 305
full dates are real calendar dates (the 31st only in 31-day months).

## Text

Stored as typed, one byte per character, with no record of the encoding.
Western files are Windows-1252. The nine files above were typed with a
Macedonian YUSCII font (the stored font name was "Macedonian Helv"), where
`@ [ \ ] ^ ` { | } ~` stand for Ж Ш Ѓ Ќ Ч ж ш ѓ ќ ч and `Q W X Y` for
Љ Њ Џ Ѕ. See `uds2gedcom/translit.py` and the `--text` option.

## Known damage

When a person is deleted, the program can reuse the record id while a family
record still points at it. In one file this made a child the spouse of its own
parent. Such families are left out and listed in the report.
