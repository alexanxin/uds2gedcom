# uds2gedcom

Get your family tree out of old **Sierra Generations** and **EasyTree** files
(`.uds`, Windows 95/98) and into any modern genealogy program.

The `.uds` format was never documented, and the programs that wrote it are no
longer developed. uds2gedcom reads the files directly, without the original
program, and writes a standard **GEDCOM** file that Gramps, MyHeritage,
Ancestry, FamilySearch, webtrees and most other family tree software can import.

- Reads people, families, birth / death / marriage / burial dates and places,
  occupations and notes.
- Merges several overlapping `.uds` files into one tree without duplicate
  people, and tells you where the files disagree.
- Handles names typed with the old Yugoslav **YUSCII** fonts (Macedonian
  Cyrillic, and Croatian / Serbian / Slovenian / Bosnian Latin), where `^`
  meant Č or Ч, `{` meant š or ш, and so on.
- Runs on your own computer. Nothing is uploaded anywhere.

## Quick start

You need **Python 3.9 or newer**. On Windows, get it from
[python.org](https://www.python.org/downloads/) and tick *Add python.exe to PATH*
during setup. macOS and Linux usually have it already (`python3 --version`).

**Without installing anything else:** download this project
(green **Code** button → **Download ZIP**), unzip it, open a terminal in that
folder and run:

```bash
python3 -m uds2gedcom path/to/family.uds
```

On Windows, type `py` instead of `python3`.

**Or install it as a command** (needs [pipx](https://pipx.pypa.io/) or pip,
and git):

```bash
pipx install git+https://github.com/alexanxin/uds2gedcom
```

Then convert:

```bash
uds2gedcom family.uds
```

The results land in a folder called `uds2gedcom-out`:

| File | What it is |
|---|---|
| `family.ged` | the tree as GEDCOM 5.5.1 (UTF-8): import this into your genealogy program |
| `report.md` | what was read, what was merged, and anything that looks wrong |
| `conflicts.csv` | every place where the records disagree (open it in Excel or LibreOffice) |
| `tree.json` | the whole merged tree as JSON, for your own programs |

Try it on the invented example files in [`examples/`](examples/):

```bash
uds2gedcom examples/hayes.uds
```

## Names typed with YUSCII fonts

These programs had no Unicode. In Macedonia, Serbia, Croatia, Slovenia and
Bosnia, people typed with fonts that drew local letters in place of rarely used
ASCII signs. The file only stores the signs, so tell uds2gedcom which alphabet
was meant:

| Option | Alphabet | Example: stored → converted |
|---|---|---|
| `--text plain` (default) | as stored: English and other Western languages | `O'Brien` → `O'Brien` |
| `--text mk` | Macedonian Cyrillic | `GRN^AR`, `Qubica` → `ГРНЧАР`, `Љубица` |
| `--text yu-latin` | Croatian, Serbian, Slovenian, Bosnian Latin | `@uta ku}a` → `Žuta kuća` |

If you leave the option out and the names look like YUSCII, uds2gedcom says
so at the end of its output.

With `--text mk`, names and places are written in Cyrillic, and each name also
gets a romanized form (GEDCOM `ROMN`) for programs that show both. Add
`--latin` to write everything in Latin letters instead.

The Macedonian mapping was checked on nine real family files. The `yu-latin`
mapping follows the YUSCII standard (JUS I.B1.002) but has not been tried on
real files yet: if you have some, please report how it went.

## Several files

Families often kept more than one file: a copy for each branch, or an old copy
next to a newer one. Give them all at once and they become one tree:

```bash
uds2gedcom *.uds --text mk
```

Someone who appears in several files becomes one person. The rules weigh names
(tolerating spelling differences), birth and death years, sex, and relatives,
and they keep apart cousins with the same name, two wives of one man, and
siblings who share a name. When the files disagree, the most recently edited
record wins, and the disagreement goes into `conflicts.csv` and into a note on
that person. The full rules: [docs/merge-rules.md](docs/merge-rules.md).

To convert without any merging (every record stays its own person), add
`--no-merge`.

## All options

```text
uds2gedcom FILE.uds [MORE.uds ...] [-o FOLDER] [--text plain|mk|yu-latin] [--latin] [--no-merge]

  -o, --out FOLDER   folder for the results (default: uds2gedcom-out)
  --text ALPHABET    alphabet the names were typed in (see above)
  --latin            write Cyrillic names and places in Latin letters
  --no-merge         keep every person record apart, even repeats
  --version          show the version
```

## Which files work

uds2gedcom was built from nine real `.uds` files saved between 2003 and 2014
(about 10,500 person records). All people and families in them convert, and
the GEDCOM output reads cleanly in an independent GEDCOM parser. It has not
yet been tried in every genealogy program: if one has trouble importing the
file, please say which.
Other versions of Generations or EasyTree may store things differently. If a
file does not convert, or something is missing, please
[open an issue](https://github.com/alexanxin/uds2gedcom/issues).

**Please do not attach your family files to a public issue**: they hold
personal details of living relatives. Describe what went wrong instead, and if
needed we can arrange a private way to look at a file.

What is not converted yet: source citations. Custom fields keep only their
text, as notes.

## How it works

- [docs/format.md](docs/format.md): the `.uds` file format, as far as it has
  been worked out
- [docs/merge-rules.md](docs/merge-rules.md): how duplicates are found
- `uds2gedcom/uds.py` reads the format, `translit.py` maps the alphabets,
  `merge.py` merges, `gedcom.py` writes GEDCOM

## Development

```bash
python3 -m pip install pytest
python3 -m pytest
```

The tests build small `.uds` files from invented people
(`tests/uds_builder.py`). To check the converter against your own files
without ever adding them to the repository:

```bash
UDS2GEDCOM_REAL_FILES=/path/to/your/files UDS2GEDCOM_TEXT=mk python3 -m pytest tests/test_real_files.py
```

`.gitignore` blocks `*.uds` and `*.ged` files outside `examples/`, so family
data is not committed by accident.

## License

MIT. See [LICENSE](LICENSE).
