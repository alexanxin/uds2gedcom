"""uds2gedcom FILE.uds [MORE.uds ...] [-o FOLDER] [--text mk] [--latin] [--no-merge]"""
import argparse
import collections
import csv
import glob
import json
import os
import sys

from . import __version__, checks, gedcom, merge, translit, uds

ALPHABETS = """alphabet the names were typed in:
  plain     as stored (default; English and other Western languages)
  mk        Macedonian Cyrillic typed with a YUSCII font (^ = Ч, { = ш, Q = Љ ...)
  yu-latin  Croatian/Serbian/Slovenian/Bosnian Latin typed with YUSCII (^ = Č, { = š ...)"""


def fail(message):
    print(f"uds2gedcom: {message}", file=sys.stderr)
    sys.exit(1)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="uds2gedcom", formatter_class=argparse.RawTextHelpFormatter,
        description="Convert Sierra Generations / EasyTree .uds family files to GEDCOM.\n"
                    "Several files are merged into one tree, without duplicate people.")
    ap.add_argument("files", nargs="+", metavar="FILE.uds")
    ap.add_argument("-o", "--out", default="uds2gedcom-out", help="folder for the results (default: %(default)s)")
    ap.add_argument("--text", choices=translit.MODES, default="plain", metavar="ALPHABET", help=ALPHABETS)
    ap.add_argument("--latin", action="store_true", help="write Cyrillic names and places in Latin letters")
    ap.add_argument("--no-merge", action="store_true", help="keep every person record apart, even repeats")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)
    translit.use(args.text)

    # Windows shells pass *.uds through unexpanded
    paths = sorted({p for arg in args.files for p in (glob.glob(arg) if glob.has_magic(arg) else [arg])})
    if not paths:
        fail(f"no files match {' '.join(args.files)}")
    stored_names = []
    for path in paths:
        if not os.path.isfile(path):
            fail(f"{path}: no such file")
        people = uds.load(path)["people"].values()
        if not people:
            fail(f"{path}: no family records found. Is it a .uds file from Generations or EasyTree?")
        stored_names += [n for p in people for n in (p["given"], p["surname"])]

    tree = merge.merge(paths, combine=not args.no_merge)
    tree["stats"]["checks"] = _checks(tree)
    os.makedirs(args.out, exist_ok=True)
    out = lambda name: os.path.join(args.out, name)
    with open(out("family.ged"), "w", encoding="utf-8", newline="") as fh:
        gedcom.write(tree, fh, latin=args.latin)
    with open(out("tree.json"), "w", encoding="utf-8") as fh:
        json.dump(tree, fh, ensure_ascii=False, indent=1)
    _write_conflicts(tree, out("conflicts.csv"))
    with open(out("report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_report(tree)) + "\n")

    st = tree["stats"]
    print(f"Read {st['input_records']} person records from {len(paths)} file{'s' * (len(paths) > 1)}.")
    print(f"{st['people']} people, {st['families']} families -> {out('family.ged')}")
    conflicts = sum(len(p["conflicts"]) for p in tree["people"])
    if conflicts:
        print(f"{conflicts} places where the records disagree: see {out('conflicts.csv')}")
    print(f"Full report: {out('report.md')}")
    if args.text == "plain" and translit.looks_like_yuscii(stored_names):
        print("\nMany names contain signs such as ^ { ~ @ inside words, so they were probably typed\n"
              "with a YUSCII font. Run again with --text mk (Macedonian Cyrillic) or\n"
              "--text yu-latin (Croatian, Serbian, Slovenian, Bosnian Latin).")


def _checks(tree):
    by_id = {p["id"]: p for p in tree["people"]}
    comps = checks.components(tree)
    files_of = lambda ids: sorted({s["file"] for i in ids for s in by_id[i]["sources"]})
    return {
        "own_ancestor": checks.ancestor_cycles(tree),
        "multiple_parent_families": checks.multiple_parent_families(tree),
        "self_links": checks.self_links(tree),
        "components": [{"people": len(c), "files": files_of(c)} for c in comps if len(c) > 1][:20],
        "unconnected_people": sum(1 for c in comps if len(c) == 1),
    }


def _show(value, field):
    return str(value) if field == "sex" else translit.native(str(value))


def _write_conflicts(tree, path):
    labels = _labels(tree)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["person", "field", "chosen", "all values (file #record)"])
        for p in tree["people"]:
            for c in p["conflicts"]:
                vals = "; ".join(f"{_show(v['value'], c['field'])} ({v['file']} #{v['record']})" for v in c["values"])
                w.writerow([labels[p["id"]], c["field"], _show(c["chosen"], c["field"]), vals])


def _labels(tree):
    def label(p):
        g = p["given"]["text"] if p["given"] else "?"
        s = p["surname"]["text"] if p["surname"] else "?"
        b = (p["events"].get("birth") or {}).get("date") or "?"
        return f"{g} {s} (b. {b}, {p['id']})"
    return {p["id"]: label(p) for p in tree["people"]}


def _report(tree):
    st, ck = tree["stats"], tree["stats"]["checks"]
    label = _labels(tree)
    n_conf = collections.Counter(c["field"] for p in tree["people"] for c in p["conflicts"])
    lines = [
        "# Conversion report", "",
        f"- Input person records: {st['input_records']}",
        f"- People after merging: {st['people']}",
        f"- Families: {st['families']}",
        f"- Merges by rule: {st['merged_by']}",
        f"- Conflicts to review: {sum(n_conf.values())} {dict(n_conf.most_common())}",
        f"- People who are their own ancestor: {len(ck['own_ancestor'])}",
        f"- People with more than one set of parents: {len(ck['multiple_parent_families'])}",
        f"- Impossible family links: {len(ck['self_links'])}",
        f"- Damaged family records left out: {st['ignored_family_records']}",
        f"- People with no family links at all: {ck['unconnected_people']}", "",
        "## Connected groups", "",
    ]
    lines += [f"- {c['people']} people, from: {', '.join(c['files'])}" for c in ck["components"]]
    alike = collections.defaultdict(list)
    for p in tree["people"]:
        b = ((p["events"].get("birth") or {}).get("date") or "")[:4]
        if p["given"] and p["surname"] and b.isdigit() and "?" not in p["given"]["latin"] + p["surname"]["latin"]:
            alike[(translit.key(p["given"]["latin"]), translit.key(p["surname"]["latin"]))].append((int(b), p["id"]))
    maybe = [(x, y) for group in alike.values() for i, x in enumerate(sorted(group))
             for y in sorted(group)[i + 1:] if y[0] - x[0] <= merge.YEAR_TOLERANCE]
    lines += ["", f"## Possible duplicates kept apart ({len(maybe)})", "",
              "Same name, birth years within 5, but something (parents, death year, a sibling",
              "in the same file) said they are different people. Worth a look.", ""]
    lines += [f"- {label[x[1]]} | {label[y[1]]}" for x, y in maybe]
    if ck["multiple_parent_families"]:
        lines += ["", "## People with more than one set of parents", ""]
        fam = {f["id"]: f for f in tree["families"]}
        for pid, fids in list(ck["multiple_parent_families"].items())[:200]:
            parents = [" + ".join(label[x] for x in (fam[f]["husb"], fam[f]["wife"]) if x) or "no parents"
                       for f in fids]
            lines.append(f"- {label[pid]}: " + " | ".join(parents))
    return lines
