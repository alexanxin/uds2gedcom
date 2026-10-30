"""The command line, end to end, on small invented files."""
import json

import pytest

from uds2gedcom import cli, translit

from test_gedcom import parse, records
from uds_builder import birth, family, marriage, occupation, person, write


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:  # keep the CRLF line ends
        return fh.read()


@pytest.fixture(autouse=True)
def reset_alphabet():
    yield
    translit.use("plain")


def english(tmp_path):
    return write(tmp_path / "hayes.uds", [
        person(1, "Walter", "HAYES", "M", events=[birth((1921, 4, 2), "Leeds"), occupation("Carpenter")],
               spouse_in=[10]),
        person(2, "Edith", "MOORE", "F", spouse_in=[10]),
        person(3, "Joan", "HAYES", "F", events=[birth((1950,))], child_of=[10]),
        family(10, husband=1, wife=2, children=[3], wedding=marriage((1948, 6, 12), "York")),
    ])


def macedonian(tmp_path):
    return write(tmp_path / "markovi.uds", [
        person(1, "Trajan", "MARKOV", "M", events=[birth((1925, 2, 1), "Prilep")], spouse_in=[10]),
        person(2, "Bla`a", "MARKOVA", "F", spouse_in=[10]),
        person(3, "Bo`idar", "MARKOV", "M", events=[birth((1950,), "Kru{evo")], child_of=[10]),
        family(10, husband=1, wife=2, children=[3]),
    ])


def test_converts_a_file(tmp_path, capsys):
    out = tmp_path / "out"
    cli.main([english(tmp_path), "-o", str(out)])
    recs = records(parse(read(out / "family.ged")))
    assert sum(1 for k in recs if k.startswith("@I")) == 3
    walter = next(r for r in recs.values() if (1, "NAME", "Walter /HAYES/") in r)
    assert (2, "DATE", "2 APR 1921") in walter and (1, "OCCU", "Carpenter") in walter
    (fam,) = [r for k, r in recs.items() if k.startswith("@F")]
    assert (2, "DATE", "12 JUN 1948") in fam
    tree = json.loads((out / "tree.json").read_text(encoding="utf-8"))
    assert len(tree["people"]) == 3
    assert (out / "report.md").exists() and (out / "conflicts.csv").exists()
    assert "3 people" in capsys.readouterr().out


def test_macedonian_files_need_the_alphabet_option(tmp_path, capsys):
    path = macedonian(tmp_path)
    cli.main([path, "-o", str(tmp_path / "plain")])
    assert "--text mk" in capsys.readouterr().out  # the hint
    cli.main([path, "-o", str(tmp_path / "mk"), "--text", "mk"])
    ged = read(tmp_path / "mk" / "family.ged")
    assert "1 NAME Божидар /МАРКОВ/" in ged and "2 PLAC Крушево" in ged and "2 ROMN Božidar /MARKOV/" in ged
    assert "--text mk" not in capsys.readouterr().out
    cli.main([path, "-o", str(tmp_path / "lat"), "--text", "mk", "--latin"])
    assert "1 NAME Božidar /MARKOV/" in read(tmp_path / "lat" / "family.ged")


def test_several_files_merge_unless_asked_not_to(tmp_path):
    a = english(tmp_path)
    b = write(tmp_path / "copy.uds", [
        person(5, "Joan", "HAYES", "F", events=[birth((1950, 8, 1))], child_of=[30]),
        person(6, "Walter", "HAYES", "M", events=[birth((1921,))], spouse_in=[30]),
        family(30, husband=6, children=[5]),
    ])
    cli.main([a, b, "-o", str(tmp_path / "merged")])
    tree = json.loads((tmp_path / "merged" / "tree.json").read_text(encoding="utf-8"))
    assert len(tree["people"]) == 3
    joan = next(p for p in tree["people"] if p["given"]["text"] == "Joan")
    assert joan["events"]["birth"]["date"] == "1950-08-01"
    assert {s["file"] for s in joan["sources"]} == {"hayes.uds", "copy.uds"}
    cli.main([a, b, "-o", str(tmp_path / "apart"), "--no-merge"])
    tree = json.loads((tmp_path / "apart" / "tree.json").read_text(encoding="utf-8"))
    assert len(tree["people"]) == 5


def test_wildcards_work_where_the_shell_does_not_expand_them(tmp_path):
    english(tmp_path)
    macedonian(tmp_path)
    cli.main([str(tmp_path / "*.uds"), "-o", str(tmp_path / "out")])
    tree = json.loads((tmp_path / "out" / "tree.json").read_text(encoding="utf-8"))
    assert {s["file"] for p in tree["people"] for s in p["sources"]} == {"hayes.uds", "markovi.uds"}
    with pytest.raises(SystemExit):
        cli.main([str(tmp_path / "*.nothing"), "-o", str(tmp_path / "none")])


def test_a_file_that_is_not_uds_is_reported(tmp_path, capsys):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    with pytest.raises(SystemExit) as exit_:
        cli.main([str(bad), "-o", str(tmp_path / "out")])
    assert exit_.value.code == 1
    assert "no family records" in capsys.readouterr().err
