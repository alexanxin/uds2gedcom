"""Writes the example .uds files. Every person in them is invented.

    python examples/make_examples.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tests"))

from uds_builder import birth, death, event, family, marriage, occupation, person, write  # noqa: E402

LATER = 1_400_000_000  # saved in 2014: newer than the default

# An English family in one file.
write(os.path.join(HERE, "hayes.uds"), [
    person(1, "Arthur", "HAYES", "M", events=[birth((1890, None, None, "about 1890"), "Leeds"),
                                              death((1961, 11, 3), "Leeds"), occupation("Coal miner")],
           spouse_in=[10]),
    person(2, "Mary", "CLARKE", "F", events=[birth((1894,), "Wakefield"), death((1970,))], spouse_in=[10]),
    person(3, "Walter", "HAYES", "M", events=[birth((1921, 4, 2), "Leeds"), death((1990, 1, 15), "York"),
                                              occupation("Carpenter")], child_of=[10], spouse_in=[20]),
    person(4, "Edith", "MOORE", "F", events=[birth((1924, 9, 30), "York")], spouse_in=[20]),
    person(5, "Joan", "HAYES", "F", events=[birth((1950, 7, 21), "York")], child_of=[20], spouse_in=[30]),
    person(6, "Peter", "HAYES", "M", events=[birth((1953,), "York")], child_of=[20]),
    person(7, "David", "WRIGHT", "M", events=[birth((1948,))], spouse_in=[30]),
    person(8, "Sarah", "WRIGHT", "F", events=[birth((1975, 2, 14), "Leeds")], child_of=[30]),
    family(10, husband=1, wife=2, children=[3]),
    family(20, husband=3, wife=4, children=[5, 6], wedding=marriage((1948, 6, 12), "York")),
    family(30, husband=7, wife=5, children=[8], wedding=marriage((1972,), "Leeds")),
])

# A Macedonian family in two overlapping files, typed with a YUSCII font:
# ^ = Ч, ` = ж, { = ш, Q = Љ ...  Convert with --text mk.
write(os.path.join(HERE, "markovi-1.uds"), [
    person(1, "Ilo", "MARKOV", "M", events=[birth((1900, None, None, "okolu 1900"), "Kru{evo")], spouse_in=[10]),
    person(2, "Rada", "MARKOVA", "F", events=[birth((1904,))], spouse_in=[10]),
    person(3, "Trajan", "MARKOV", "M", events=[birth((1925, 2, 1), "Prilep"), occupation("Zemjodelec")],
           child_of=[10], spouse_in=[20]),
    person(4, "Bla`a", "MARKOVA", "F", events=[birth((1928,), "Prilep")], spouse_in=[20]),
    person(5, "Bo`idar", "MARKOV", "M", events=[birth((1950, 5, 9), "Prilep")], child_of=[20]),
    family(10, husband=1, wife=2, children=[3]),
    family(20, husband=3, wife=4, children=[5], wedding=marriage((1949,), "Prilep")),
])
write(os.path.join(HERE, "markovi-2.uds"), [
    person(11, "Trajan", "MARKOV", "M", events=[birth((1925,), "Prilep")], spouse_in=[30], ts=LATER),
    person(12, "Bla`a", "MARKOVA", "F", events=[birth((1928,))], spouse_in=[30], ts=LATER),
    person(13, "Bo`idar", "MARKOV", "M", events=[birth((1950,))], child_of=[30], ts=LATER),
    person(14, "Qubica", "MARKOVA", "F", events=[birth((1953, 8, 2), "Prilep"),
                                                 event(60, notes=["U~itelka"])], child_of=[30], ts=LATER),
    person(15, "Ne{o", "TRAJ^EVSKI", "M", events=[birth((1951,), "[tip")], spouse_in=[40], ts=LATER),
    person(16, "Elena", "TRAJ^EVSKA", "F", events=[birth((1978,), "Skopje")], child_of=[40], ts=LATER),
    family(30, husband=11, wife=12, children=[13, 14], ts=LATER),
    family(40, husband=15, wife=14, children=[16], wedding=marriage((1976, 9, 18), "[tip"), ts=LATER),
])
print("wrote hayes.uds, markovi-1.uds, markovi-2.uds")
