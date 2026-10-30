"""Merge rules (docs/merge-rules.md). Every person here is invented."""
import pytest

from uds2gedcom import merge, translit

from uds_builder import birth, family, person, write


@pytest.fixture(autouse=True)
def macedonian():
    # most rules were worked out on Macedonian files; spelling folds need mk
    translit.use("mk")
    yield
    translit.use("plain")


def rec(file, rid, given, surname, sex=None, born=None, ts=None):
    # different files get different save times unless a test says otherwise
    ts = ts if ts is not None else 1000 * len(file) + sum(map(ord, file))
    events = []
    if born:
        events.append({"type": "birth", "date": {"year": born, "month": None, "day": None, "text": None},
                       "place": None, "text": []})
    p = {"id": rid, "ts": ts, "given": given, "surname": surname, "sex": sex,
         "famc": [], "fams": [], "events": events}
    return merge.Rec(file, p)


def link(recs, child, father=None, mother=None, fam=None):
    c = recs[child]
    if fam:
        c.famc.add(fam)
    for role, parent in (("fathers", father), ("mothers", mother)):
        if parent:
            getattr(c, role).add(parent)
            recs[parent].children.add(child)
    if father and mother:
        recs[father].spouses.add(mother)
        recs[mother].spouses.add(father)


def build(*rs):
    return {r.key: r for r in rs}


def same(uf, a, b):
    return uf.find(a) == uf.find(b)


def test_exact_copy_merges_without_a_birth_year():
    recs = build(rec("a", 5, "Trajan", "MARKOV", "M", ts=77), rec("b", 5, "Trajan", "MARKOV", "M", ts=77))
    uf, reasons = merge.cluster(recs)
    assert same(uf, ("a", 5), ("b", 5)) and reasons["exact copy"] == 1


def test_same_name_and_birth_year_in_two_files_merge():
    recs = build(rec("a", 1, "Vesna", "MARKOVA", "F", 1941), rec("b", 9, "Vesna", "MARKOVA", "F", 1941))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 1), ("b", 9))


def test_spelling_variants_still_match():
    recs = build(rec("a", 1, "Kalina", "GRN^AR", "F", 1822), rec("b", 2, "Kalina", "GRNCAR", "F", 1822))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 1), ("b", 2))


def test_birth_years_far_apart_do_not_merge():
    recs = build(rec("a", 1, "Stojan", "BOGDANOV", "M", 1820), rec("b", 2, "Stojan", "BOGDANOV", "M", 1873))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 1), ("b", 2))


def test_name_alone_is_not_enough():
    recs = build(rec("a", 1, "Trajan", "MARKOV", "M"), rec("b", 2, "Trajan", "MARKOV", "M"))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 1), ("b", 2))


def test_name_plus_shared_relative_merges():
    recs = build(rec("a", 1, "Trajan", "MARKOV", "M"), rec("a", 2, "Mile", "MARKOV", "M"),
                 rec("b", 1, "Trajan", "MARKOV", "M"), rec("b", 2, "Mile", "MARKOV", "M"))
    link(recs, ("a", 1), father=("a", 2), fam=("a", 50))
    link(recs, ("b", 1), father=("b", 2), fam=("b", 50))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 1), ("b", 1))
    assert same(uf, ("a", 2), ("b", 2))


def test_different_known_fathers_block_a_merge():
    recs = build(rec("a", 1, "Trajan", "MARKOV", "M", 1920), rec("a", 2, "Mile", "MARKOV", "M"),
                 rec("b", 1, "Trajan", "MARKOV", "M", 1920), rec("b", 2, "Kiro", "MARKOV", "M"))
    link(recs, ("a", 1), father=("a", 2))
    link(recs, ("b", 1), father=("b", 2))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 1), ("b", 1))


def test_cousins_with_the_same_name_stay_apart():
    # two Spasijas, each a daughter of a different Gligor born 12 years apart
    recs = build(rec("a", 1, "Spasija", "LAZAROSKI", "F", 1899), rec("a", 2, "Gligor", "LAZAROSKI", "M", 1864),
                 rec("b", 1, "Spasija", "LAZAROSKI", "F", 1902), rec("b", 2, "Gligor", "LAZAROSKI", "M", 1876))
    link(recs, ("a", 1), father=("a", 2))
    link(recs, ("b", 1), father=("b", 2))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 1), ("b", 1))


def test_death_years_far_apart_block_a_merge():
    a, b = rec("a", 1, "Spasija", "LAZAROSKI", "F", 1899), rec("b", 1, "Spasija", "LAZAROSKI", "F", 1899)
    a.dy, b.dy = 1946, 1982
    uf, _ = merge.cluster(build(a, b))
    assert not same(uf, ("a", 1), ("b", 1))


def test_different_sex_blocks_a_merge():
    recs = build(rec("a", 1, "Vane", "MARKOV", "M", 1960), rec("b", 1, "Vane", "MARKOV", "F", 1960))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 1), ("b", 1))


def test_placeholder_mothers_of_one_child_merge():
    recs = build(rec("a", 1, "Boris", "ANGELOVSKI", "M", 1945), rec("a", 2, "Lepa", "?", "F", 1926),
                 rec("b", 1, "Boris", "ANGELOVSKI", "M", 1945), rec("b", 2, "?", "LEPA", "F", 1926))
    link(recs, ("a", 1), mother=("a", 2))
    link(recs, ("b", 1), mother=("b", 2))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 2), ("b", 2))


def test_placeholder_spouses_with_the_same_birth_year_merge():
    recs = build(rec("a", 1, "Neda", "ANGELOVSKA", "F", 1871), rec("a", 2, "Ma`", "Neda ?", "M", 1873),
                 rec("b", 1, "Neda", "ANGELOVSKA", "F", 1871), rec("b", 2, "Ma` Neda", "?", "M", 1873))
    for f in ("a", "b"):
        recs[(f, 1)].spouses.add((f, 2))
        recs[(f, 2)].spouses.add((f, 1))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 2), ("b", 2))


def test_two_wives_in_one_file_stay_apart_even_with_one_birth_year():
    recs = build(rec("a", 1, "Kosta", "DIMOV", "M", 1892), rec("a", 2, "Prva `ena Kosta", "?", "F", 1900),
                 rec("a", 3, "Vtora `ena Kosta", "?", "F", 1900))
    for wife in (("a", 2), ("a", 3)):
        recs[("a", 1)].spouses.add(wife)
        recs[wife].spouses.add(("a", 1))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 2), ("a", 3))


def test_siblings_with_the_same_name_in_one_file_stay_apart():
    recs = build(rec("a", 1, "Ilo", "MARKOV", "M", 1900), rec("a", 2, "Trajan", "MARKOV", "M", 1921),
                 rec("a", 3, "Trajan", "MARKOV", "M", 1924), rec("b", 1, "Ilo", "MARKOV", "M", 1900),
                 rec("b", 2, "Trajan", "MARKOV", "M", 1921))
    link(recs, ("a", 2), father=("a", 1), fam=("a", 9))
    link(recs, ("a", 3), father=("a", 1), fam=("a", 9))
    link(recs, ("b", 2), father=("b", 1), fam=("b", 9))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 2), ("a", 3))
    assert same(uf, ("a", 2), ("b", 2))


def test_same_child_entered_twice_in_one_family_merges():
    recs = build(rec("a", 1, "Zoran", "SPASOVSKI", "M", 1955), rec("a", 2, "Darko", "SPASOVSKI", "M", 1991),
                 rec("a", 3, "Darko", "SPASOVSKI", "M", 1991))
    link(recs, ("a", 2), father=("a", 1), fam=("a", 9))
    link(recs, ("a", 3), father=("a", 1), fam=("a", 9))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 2), ("a", 3))


def test_father_name_variants_do_not_block_a_merge():
    recs = build(rec("a", 1, "Dejan", "TO{EV", "M", 1966), rec("a", 2, "Georgi", "TO{EV", "M", 1937),
                 rec("b", 1, "Dejan", "TO{EV", "M", 1966), rec("b", 2, "Gorgi", "TO{EV", "M", 1937))
    link(recs, ("a", 1), father=("a", 2))
    link(recs, ("b", 1), father=("b", 2))
    uf, _ = merge.cluster(recs)
    assert same(uf, ("a", 1), ("b", 1)) and same(uf, ("a", 2), ("b", 2))


def test_names_compatible():
    mite = rec("a", 1, "Mite", "TRP^EVSKI", "M", 1914)
    dimitar = rec("b", 1, "Dimitar", "TRP^EVSKI", "M", 1914)
    assert merge.names_compatible(mite, dimitar)
    assert merge.names_compatible(rec("a", 2, "Vesne", "X", "F", 1944), rec("b", 2, "Vesna", "Y", "F", 1944))
    assert merge.names_compatible(rec("a", 3, "Vtora`ena Kosta", "?"), rec("b", 3, "Marija", "DIMOVA"))
    assert not merge.names_compatible(rec("a", 4, "Marija", "MARKOVA", "F", 1900),
                                      rec("b", 4, "Elena", "LAZAROVA", "F", 1900))


def test_english_placeholders_are_descriptions_not_names():
    translit.use("plain")
    assert merge.names_compatible(rec("a", 1, "Wife of John", "?"), rec("b", 1, "Mary", "BROWN"))
    assert merge.names_compatible(rec("a", 2, "Unknown", "SMITH"), rec("b", 2, "Alice", "SMITH"))


def test_one_typo():
    assert merge.one_typo("kamilla", "kamila")
    assert merge.one_typo("vesne", "vesna")
    assert not merge.one_typo("marija", "elena")


def test_one_child_under_two_names_in_two_files_merges():
    recs = build(rec("a", 1, "Goran", "PETKOV", "M", 1970), rec("a", 2, "Luka", "PETKOV", "M", 2006),
                 rec("b", 1, "Goran", "PETKOV", "M", 1970), rec("b", 2, "Marko", "PETKOV", "M", 2006))
    link(recs, ("a", 2), father=("a", 1), fam=("a", 9))
    link(recs, ("b", 2), father=("b", 1), fam=("b", 9))
    uf, reasons = merge.cluster(recs)
    assert same(uf, ("a", 2), ("b", 2)) and reasons["same child, two names"] == 1


def test_siblings_listed_together_somewhere_stay_apart():
    # twins: file a knows both, file b only one of them
    recs = build(rec("a", 1, "Goran", "PETKOV", "M", 1970), rec("a", 2, "Luka", "PETKOV", "M", 2006),
                 rec("a", 3, "Marko", "PETKOV", "M", 2006), rec("b", 1, "Goran", "PETKOV", "M", 1970),
                 rec("b", 3, "Marko", "PETKOV", "M", 2006))
    for child in (("a", 2), ("a", 3)):
        link(recs, child, father=("a", 1), fam=("a", 9))
    link(recs, ("b", 3), father=("b", 1), fam=("b", 9))
    uf, _ = merge.cluster(recs)
    assert not same(uf, ("a", 2), ("a", 3))
    assert same(uf, ("a", 3), ("b", 3))


def two_overlapping_files(tmp_path):
    a = write(tmp_path / "a.uds", [
        person(1, "Ilo", "MARKOV", "M", events=[birth((1900,))], spouse_in=[10]),
        person(2, "Rada", "MARKOVA", "F", events=[birth((1904,))], spouse_in=[10]),
        person(3, "Trajan", "MARKOV", "M", events=[birth((1925, 2, 1), "Prilep")], child_of=[10]),
        family(10, husband=1, wife=2, children=[3]),
    ])
    b = write(tmp_path / "b.uds", [
        person(7, "Trajan", "MARKOV", "M", events=[birth((1925,), "Prilep")], child_of=[20], ts=1_300_000_000),
        person(8, "Ilo", "MARKOV", "M", events=[birth((1900,))], spouse_in=[20], ts=1_300_000_000),
        person(9, "Vera", "MARKOVA", "F", events=[birth((1927,))], child_of=[20], ts=1_300_000_000),
        family(20, husband=8, children=[7, 9], ts=1_300_000_000),
    ])
    return [a, b]


def test_two_files_become_one_family(tmp_path):
    tree = merge.merge(two_overlapping_files(tmp_path))
    names = sorted(p["given"]["latin"] for p in tree["people"])
    assert names == ["Ilo", "Rada", "Trajan", "Vera"]
    (fam,) = tree["families"]
    by_id = {p["id"]: p for p in tree["people"]}
    assert [by_id[c]["given"]["latin"] for c in fam["children"]] == ["Trajan", "Vera"]
    trajan = next(p for p in tree["people"] if p["given"]["latin"] == "Trajan")
    assert trajan["events"]["birth"]["date"] == "1925-02-01"  # the more precise date is kept
    assert trajan["given"] == {"text": "Трајан", "latin": "Trajan"}


def test_keeping_every_record_apart(tmp_path):
    tree = merge.merge(two_overlapping_files(tmp_path), combine=False)
    assert len(tree["people"]) == 6 and len(tree["families"]) == 2
