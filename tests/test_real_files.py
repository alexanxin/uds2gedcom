"""Checks on your own .uds files. They never belong in this repository, so
these tests only run when you point them at a folder:

    UDS2GEDCOM_REAL_FILES=/path/to/folder UDS2GEDCOM_TEXT=mk python -m pytest tests/test_real_files.py
"""
import glob
import io
import os
import subprocess
import sys

import pytest

from uds2gedcom import checks, gedcom, merge, translit

from test_gedcom import parse, records

FOLDER = os.environ.get("UDS2GEDCOM_REAL_FILES")
pytestmark = pytest.mark.skipif(not FOLDER, reason="set UDS2GEDCOM_REAL_FILES to a folder of .uds files")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def paths():
    found = sorted(glob.glob(os.path.join(FOLDER or "", "*.uds")))
    assert found, f"no .uds files in {FOLDER}"
    return found


@pytest.fixture(scope="module")
def tree(paths):
    translit.use(os.environ.get("UDS2GEDCOM_TEXT", "plain"))
    yield merge.merge(paths)
    translit.use("plain")


def test_no_impossible_structures(tree):
    assert checks.ancestor_cycles(tree) == []
    assert checks.self_links(tree) == []


def test_gedcom_links_point_both_ways(tree):
    fh = io.StringIO(newline="")
    gedcom.write(tree, fh)
    recs = records(parse(fh.getvalue()))
    for fid, fam in ((k, v) for k, v in recs.items() if k.startswith("@F")):
        for _, tag, pid in fam:
            if tag in ("HUSB", "WIFE"):
                assert (1, "FAMS", fid) in recs[pid]
            if tag == "CHIL":
                assert (1, "FAMC", fid) in recs[pid]


def test_the_result_is_the_same_on_every_run(paths):
    # Python changes the order of sets between runs; the merge must not care
    script = ("import json, sys; from uds2gedcom import merge, translit; translit.use(sys.argv[1]); "
              "print(json.dumps(merge.merge(sys.argv[2:]), sort_keys=True))")
    runs = {subprocess.run([sys.executable, "-c", script, os.environ.get("UDS2GEDCOM_TEXT", "plain"), *paths],
                           cwd=ROOT, capture_output=True, text=True, check=True,
                           env={**os.environ, "PYTHONHASHSEED": seed}).stdout
            for seed in ("1", "2", "3")}
    assert len(runs) == 1
