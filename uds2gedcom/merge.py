"""Merge several .uds family files into one de-duplicated tree (docs/merge-rules.md)."""
import collections
import itertools
import os
import time

from . import translit, uds

YEAR_TOLERANCE = 5   # max birth-year spread inside one merged person
SEED_YEAR_GAP = 1    # same full name + birth years this close = same person
MIN_PARENT_AGE = 13  # a family saved before a parent reached this age is a mis-entry
ROLES = ("fathers", "mothers", "spouses", "children")


class Rec:
    """One person record from one file, with its relatives inside that file."""

    def __init__(self, file, p):
        self.key = (file, p["id"])
        self.file, self.p, self.ts = file, p, p["ts"]
        self.sex, self.by = p["sex"], uds.birth_year(p)
        birth = uds.event(p, "birth")
        d = birth["date"] if birth and birth["date"] else None
        self.bdate = (d["year"], d["month"], d["day"]) if d and d["year"] and d["month"] and d["day"] else None
        death = uds.event(p, "death")
        self.dy = death["date"]["year"] if death and death["date"] else None
        self.gkey, self.skey = translit.key(p["given"]), translit.key(p["surname"])
        self.seedable = bool(self.gkey and self.skey) and "?" not in p["given"] + p["surname"]
        self.fathers, self.mothers, self.spouses, self.children = set(), set(), set(), set()
        self.famc = set()
        self.married_in = {}  # spouse key -> marriage year

    def relatives(self):
        return self.fathers | self.mothers | self.spouses | self.children


def _first(people, pid):
    words = translit.key(people[pid]["given"]).split()
    return words[0] if words else ""


def _misfiled(file, parent, children, people, kids, child_of):
    """Children recorded under a parent who was too young to have them are
    usually the parent and the parent's siblings entered a second time.
    Pair each such child with the one relative of the same first name."""
    family = [parent] + [s for fid in child_of[parent] for s in kids[fid] if s != parent]
    pairs = []
    for c in children:
        same = [r for r in dict.fromkeys(family)
                if _first(people, r) == _first(people, c) and people[c]["sex"] in (None, people[r]["sex"])]
        if len(same) == 1:
            pairs.append(((file, c), (file, same[0])))
    return pairs


def read_files(paths):
    """Person records with in-file relatives, plus the family records.
    Family records whose links are impossible are left out and listed;
    `hints` pairs records that such a family shows to be the same person."""
    recs, fams, ignored, hints = {}, {}, [], []
    for path in paths:
        name = os.path.basename(path)
        db = uds.load(path)
        for p in db["people"].values():
            recs[(name, p["id"])] = Rec(name, p)
        kids = collections.defaultdict(list)
        for f in db["families"].values():
            kids[f["id"]] += f["children"]
        for p in db["people"].values():
            for fid in p["famc"]:
                kids[fid].append(p["id"])
        married = collections.defaultdict(set)
        for f in db["families"].values():
            if f["husb"] and f["wife"]:
                married[f["husb"]].add(f["wife"])
                married[f["wife"]].add(f["husb"])
        child_of = collections.defaultdict(list)
        for fid, ks in kids.items():
            for c in ks:
                child_of[c].append(fid)
        for f in db["families"].values():
            children = list(dict.fromkeys(kids[f["id"]]))
            if set(children) & (married[f["husb"]] | married[f["wife"]]):
                # a child who is married to its own parent: stale record ids
                ignored.append((name, f["id"]))
                continue
            saved = time.gmtime(f["ts"]).tm_year
            too_young = [x for x in (f["husb"], f["wife"]) if x and uds.birth_year(db["people"][x])
                         and saved - uds.birth_year(db["people"][x]) < MIN_PARENT_AGE]
            if too_young and children:
                ignored.append((name, f["id"]))
                for x in too_young:
                    hints += _misfiled(name, x, children, db["people"], kids, child_of)
                continue
            h = (name, f["husb"]) if f["husb"] else None
            w = (name, f["wife"]) if f["wife"] else None
            children = [(name, c) for c in children]
            fams[(name, f["id"])] = {"husb": h, "wife": w, "children": children,
                                     "events": f["events"], "ts": f["ts"]}
            for c in children:
                rc = recs[c]
                rc.famc.add((name, f["id"]))
                if h: rc.fathers.add(h); recs[h].children.add(c)
                if w: rc.mothers.add(w); recs[w].children.add(c)
            if h and w:
                recs[h].spouses.add(w)
                recs[w].spouses.add(h)
                m = next((e for e in f["events"] if e["type"] == "marriage" and e["date"] and e["date"]["year"]), None)
                if m:
                    recs[h].married_in[w] = recs[w].married_in[h] = m["date"]["year"]
    return recs, fams, ignored, hints


class Clusters:
    def __init__(self, recs):
        self.recs = recs
        self.root = {k: k for k in recs}
        self.members = {k: [k] for k in recs}

    def find(self, k):
        while self.root[k] != k:
            self.root[k] = self.root[self.root[k]]
            k = self.root[k]
        return k

    def compatible(self, a, b, check_death=True):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        A, B = self.members[ra], self.members[rb]
        both = [self.recs[k] for k in A + B]
        if len({r.sex for r in both if r.sex}) > 1:
            return False
        spans = [[r.by for r in both if r.by]] + ([[r.dy for r in both if r.dy]] if check_death else [])
        for years in spans:
            if years and max(years) - min(years) > YEAR_TOLERANCE:
                return False
        for x in A:
            rx = self.recs[x]
            if any(self.find(y) == rb for y in rx.relatives()):
                return False
            for y in B:
                ry = self.recs[y]
                if rx.file != ry.file:
                    continue
                if rx.spouses & ry.spouses:
                    return False
                # same-name siblings: a child who died young and a later one,
                # unless the birth year is the same (entered twice)
                if rx.famc & ry.famc and not (rx.by and rx.by == ry.by):
                    return False
        return True

    def union(self, a, b, check_death=True):
        if not self.compatible(a, b, check_death):
            return False
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if len(self.members[ra]) < len(self.members[rb]):
            ra, rb = rb, ra
        self.root[rb] = ra
        self.members[ra] += self.members.pop(rb)
        return True

    def groups(self):
        return list(self.members.values())


def _could_be_same(rx, ry):
    """Names compatible and birth years not contradicting."""
    return names_compatible(rx, ry) and not (rx.by and ry.by and abs(rx.by - ry.by) > YEAR_TOLERANCE)


def same_by_name(recs, a, b):
    ra, rb = recs[a], recs[b]
    for role in ("fathers", "mothers"):
        xa, xb = getattr(ra, role), getattr(rb, role)
        if xa and xb and not any(_could_be_same(recs[x], recs[y]) for x in xa for y in xb):
            return False
    gap = abs(ra.by - rb.by) if ra.by and rb.by else None
    if gap is not None and gap <= SEED_YEAR_GAP:
        return True
    shared = any(recs[x].gkey and recs[x].gkey == recs[y].gkey and _could_be_same(recs[x], recs[y])
                 for role in ROLES for x in getattr(ra, role) for y in getattr(rb, role))
    return shared and (gap is None or gap <= YEAR_TOLERANCE)


# first words that describe someone instead of naming them ("Žena na Risto",
# "Vtora žena Ivan", "Wife of John", "Unknown")
PLACEHOLDER_WORDS = {"", "zena", "maz", "sin", "kerka", "erka", "dete", "prva", "vtora",
                     "treta", "nepoznat", "nepoznata", "nn",
                     "unknown", "wife", "husband", "son", "daughter", "child", "baby",
                     "infant", "unnamed", "mrs", "mr"}


def first_name(r):
    words = r.gkey.split()
    return words[0] if words else ""


def is_placeholder(word):
    return word in PLACEHOLDER_WORDS or "zena" in word


def names_compatible(x, y):
    """For two records already known to fill the same role (say, the mother of
    one merged person): do their names allow them to be the same person?"""
    a, b = first_name(x), first_name(y)
    if is_placeholder(a) or is_placeholder(b) or a == b:
        return True
    years_agree = not (x.by and y.by) or abs(x.by - y.by) <= SEED_YEAR_GAP
    if min(len(a), len(b)) >= 4 and one_typo(a, b) and years_agree:  # Rodne / Rodna
        return True
    # nicknames (Mite = Dimitar): same surname and birth year
    return bool(x.skey and x.skey == y.skey and x.by and y.by and abs(x.by - y.by) <= SEED_YEAR_GAP)


def one_typo(a, b):
    """True if a and b differ by at most one inserted, deleted or changed letter."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + (len(a) == len(b)):] == b[i + 1:]


def _spread(uf, recs, members, role):
    """Merge relatives in one role across the records of one merged person."""
    # sorted: set order changes from run to run, and so would the result
    rel = list(dict.fromkeys(x for m in members for x in sorted(getattr(recs[m], role))))
    wed = {x: recs[m].married_in[x] for m in members for x in recs[m].married_in} if role == "spouses" else {}
    changed = False
    for i, x in enumerate(rel):
        for y in rel[i + 1:]:
            if uf.find(x) == uf.find(y):
                continue
            rx, ry = recs[x], recs[y]
            if role in ("fathers", "mothers"):
                ok = names_compatible(rx, ry)
            elif role == "spouses":
                # a person can marry twice, so a spouse needs more than a
                # compatible name: the same first name, a matching birth year
                # ("Husband of Neda", born 1873, in three files) or the same
                # wedding year without contradicting birth years
                fx = first_name(rx)
                same_year = bool(rx.by and ry.by and abs(rx.by - ry.by) <= SEED_YEAR_GAP)
                same_wedding = bool(wed.get(x) and wed.get(x) == wed.get(y))
                years_fit = not (rx.by and ry.by and abs(rx.by - ry.by) > YEAR_TOLERANCE)
                ok = (not is_placeholder(fx) and fx == first_name(ry)) or (
                    names_compatible(rx, ry) and (same_year or (same_wedding and years_fit)))
            else:
                ok = bool(rx.gkey) and rx.gkey == ry.gkey
            if ok and uf.union(x, y):
                changed = True
    return changed


def _same_child_twice(uf, recs):
    """Children of one parent who never appear together in any file, with the
    same birth year and no conflicting sex or full birth date, are one child
    recorded under two names (Luka / Marko, Kire / Kiril, "Son 1" / "Ivan").
    A real pair of siblings is listed together in at least one file."""
    kids = collections.defaultdict(set)
    for k, r in recs.items():
        for parent in r.fathers | r.mothers:
            kids[uf.find(parent)].add(uf.find(k))
    merged = 0
    for children in kids.values():
        for a, b in itertools.combinations(sorted(children), 2):
            ra, rb = uf.find(a), uf.find(b)
            if ra == rb:
                continue
            A, B = [recs[k] for k in uf.members[ra]], [recs[k] for k in uf.members[rb]]
            if {r.file for r in A} & {r.file for r in B}:
                continue
            years = {r.by for r in A + B if r.by}
            if len(years) != 1 or not all(any(r.by for r in group) for group in (A, B)):
                continue
            dates = {r.bdate for r in A + B if r.bdate}
            if len(dates) > 1:
                continue
            mothers = [{uf.find(m) for r in group for m in r.mothers} for group in (A, B)]
            if all(mothers) and not mothers[0] & mothers[1]:
                continue  # half-siblings from different mothers
            # death years may disagree between files: that becomes a conflict
            merged += uf.union(ra, rb, check_death=False)
    return merged


def cluster(recs, hints=()):
    uf = Clusters(recs)
    reasons = collections.Counter()
    for a, b in hints:
        reasons["misfiled entry"] += uf.union(a, b)
    copies = collections.defaultdict(list)
    for k, r in recs.items():
        copies[(r.p["id"], r.ts, r.gkey, r.skey)].append(k)
    for keys in copies.values():
        for k in keys[1:]:
            reasons["exact copy"] += uf.union(keys[0], k)
    by_name = collections.defaultdict(list)
    for k, r in recs.items():
        if r.seedable:
            by_name[(r.gkey, r.skey)].append(k)
    for keys in by_name.values():
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if uf.find(a) != uf.find(b) and same_by_name(recs, a, b):
                    reasons["name seed"] += uf.union(a, b)
    changed = True
    while changed:
        changed = False
        before = len(uf.members)
        for members in uf.groups():
            for role in ROLES:
                changed |= _spread(uf, recs, members, role)
        reasons["through family"] += before - len(uf.members)
        twice = _same_child_twice(uf, recs)
        reasons["same child, two names"] += twice
        changed |= bool(twice)
    return uf, reasons


def _text(raw):
    return {"text": translit.native(raw), "latin": translit.latin(raw)} if raw else None


def _date_str(d):
    if not d:
        return None
    if d["year"] and d["month"] and d["day"]:
        s = f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}"
    elif d["year"] and d["month"]:
        s = f"{d['year']:04d}-{d['month']:02d}"
    else:
        s = str(d["year"]) if d["year"] else ""
    if d["text"]:
        s = f"{s} ({d['text']})" if s else d["text"]
    return s or None


def _agree(kind, a, b):
    if kind == "date":  # "1974" and "1974-03-06" agree; the precise one is kept
        return a.startswith(b) or b.startswith(a)
    if kind == "place":  # "Ohrid" and "Ohrid, Makedonija" agree
        ka, kb = translit.key(a), translit.key(b)
        return ka.startswith(kb) or kb.startswith(ka)
    if kind == "name":
        return translit.key(a) == translit.key(b)
    return a == b


def merge_person(recs, members):
    rs = sorted((recs[k] for k in members), key=lambda r: (r.ts, r.key), reverse=True)
    conflicts = []

    def pick(label, kind, values):
        """values: [(value, rec)] newest first. Newest wins; among values that
        agree with it, the most detailed one. Real disagreements are reported."""
        found = [(v, r) for v, r in values if v]
        if not found:
            return None
        newest = found[0][0]
        agreeing = [v for v, _ in found if _agree(kind, v, newest)]
        chosen = max(agreeing, key=len) if kind in ("date", "place") else newest
        if any(not _agree(kind, v, chosen) for v, _ in found):
            conflicts.append({"field": label, "chosen": chosen,
                              "values": [{"value": v, "file": r.file, "record": r.p["id"]} for v, r in found]})
        return chosen

    real = [r for r in rs if r.seedable] or rs
    given = pick("given name", "name", [(r.p["given"], r) for r in real])
    surname = pick("surname", "name", [(r.p["surname"], r) for r in real])
    sex = pick("sex", "sex", [(r.sex, r) for r in rs])
    events = {}
    for etype in ("birth", "death", "burial", "christening", "baptism"):
        evs = [(uds.event(r.p, etype), r) for r in rs]
        date = pick(f"{etype} date", "date", [(_date_str(e["date"]) if e else None, r) for e, r in evs])
        place = pick(f"{etype} place", "place", [(e["place"] if e else None, r) for e, r in evs])
        if date or place:
            events[etype] = {"date": date, "place": _text(place)}
    facts = []
    for r in rs:
        for e in r.p["events"]:
            if e["type"] in ("birth", "death", "burial", "christening", "baptism"):
                continue
            for t in e["text"]:
                fact = {"type": e["type"], "text": _text(t)}
                if fact not in facts:
                    facts.append(fact)
    return {"given": _text(given), "surname": _text(surname), "sex": sex,
            "events": events, "facts": facts,
            "sources": [{"file": r.file, "record": r.p["id"]} for r in sorted(rs, key=lambda r: r.key)],
            "conflicts": conflicts}


def merge(paths, combine=True):
    """combine=False keeps every person record as its own person."""
    recs, fams, ignored, hints = read_files(paths)
    uf, reasons = cluster(recs, hints) if combine else (Clusters(recs), collections.Counter())
    groups = uf.groups()

    def sort_key(members):
        r = max((recs[k] for k in members), key=lambda r: r.ts)
        return (translit.key(r.p["surname"]), r.by or 0, translit.key(r.p["given"]), min(members))

    groups.sort(key=sort_key)
    pid_of, people = {}, []
    for n, members in enumerate(groups, 1):
        pid = f"I{n}"
        for k in members:
            pid_of[k] = pid
        person = merge_person(recs, members)
        person["id"] = pid
        people.append(person)

    families, fam_of_pair = [], {}
    single = []
    for fk, f in sorted(fams.items()):
        h = pid_of[f["husb"]] if f["husb"] else None
        w = pid_of[f["wife"]] if f["wife"] else None
        kids = [pid_of[c] for c in f["children"]]
        if h and w:
            key = (h, w)
            if key not in fam_of_pair:
                fam_of_pair[key] = {"husb": h, "wife": w, "children": [], "events": [], "files": []}
                families.append(fam_of_pair[key])
            _add(fam_of_pair[key], kids, f, fk)
        elif h or w or kids:
            single.append((h, w, kids, f, fk))
    for h, w, kids, f, fk in single:
        parent = h or w
        if parent:
            options = [fam for fam in families if parent in (fam["husb"], fam["wife"])]
        else:
            options = [fam for fam in families if set(kids) & set(fam["children"])]
        sharing = [fam for fam in options if set(kids) & set(fam["children"])]
        target = sharing[0] if sharing else (options[0] if len(options) == 1 and not kids else None)
        if target is None:
            target = {"husb": h, "wife": w, "children": [], "events": [], "files": []}
            families.append(target)
        _add(target, kids, f, fk)

    by_id = {p["id"]: p for p in people}
    for n, fam in enumerate(families, 1):
        fam["id"] = f"F{n}"
        fam["children"].sort(key=lambda c: _birth_sort(by_id[c]))
        fam["events"] = _family_events(fam.pop("raw_events"))
    stats = {"input_records": len(recs), "people": len(people), "families": len(families),
             "merged_by": dict(reasons),
             "ignored_family_records": [{"file": f, "record": r} for f, r in ignored]}
    return {"people": people, "families": families, "stats": stats}


def _add(fam, kids, f, fk):
    for c in kids:
        if c not in fam["children"]:
            fam["children"].append(c)
    fam.setdefault("raw_events", []).append((f["ts"], f["events"]))
    fam["files"].append({"file": fk[0], "record": fk[1]})


def _family_events(raw):
    for ts, evs in sorted(raw, key=lambda x: -x[0]):
        for e in evs:
            if e["type"] == "marriage" and (e["date"] or e["place"]):
                return {"marriage": {"date": _date_str(e["date"]), "place": _text(e["place"])}}
    return {}


def _birth_sort(person):
    d = (person["events"].get("birth") or {}).get("date") or ""
    return (d[:10] or "9999", person["given"]["latin"] if person["given"] else "")
