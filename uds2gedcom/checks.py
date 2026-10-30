"""Sanity checks on a merged tree: impossible structures point at bad merges."""
import collections


def ancestor_cycles(tree):
    """People who end up as their own ancestor."""
    kids = collections.defaultdict(set)
    for f in tree["families"]:
        for parent in (f["husb"], f["wife"]):
            if parent:
                kids[parent].update(f["children"])
    state, stuck = {}, set()
    for start in list(kids):
        if start in state:
            continue
        stack = [(start, iter(kids[start]))]
        state[start] = "open"
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = "done"
                stack.pop()
            elif state.get(nxt) == "open":
                stuck.update(n for n, _ in stack[[n for n, _ in stack].index(nxt):])
            elif nxt not in state:
                state[nxt] = "open"
                stack.append((nxt, iter(kids.get(nxt, ()))))
    return sorted(stuck)


def multiple_parent_families(tree):
    seen = collections.defaultdict(list)
    for f in tree["families"]:
        for c in f["children"]:
            seen[c].append(f["id"])
    return {c: fs for c, fs in seen.items() if len(fs) > 1}


def self_links(tree):
    bad = []
    for f in tree["families"]:
        spouses = {f["husb"], f["wife"]} - {None}
        if f["husb"] and f["husb"] == f["wife"]:
            bad.append((f["id"], "husband is wife"))
        if spouses & set(f["children"]):
            bad.append((f["id"], "parent is own child"))
    return bad


def components(tree):
    """Groups of people connected through any family link, largest first."""
    root = {p["id"]: p["id"] for p in tree["people"]}

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    for f in tree["families"]:
        members = [m for m in (f["husb"], f["wife"], *f["children"]) if m]
        for m in members[1:]:
            root[find(m)] = find(members[0])
    groups = collections.defaultdict(list)
    for pid in root:
        groups[find(pid)].append(pid)
    return sorted(groups.values(), key=len, reverse=True)
