# Merge rules

Families often kept several `.uds` files that overlap: the same person can
appear in several files, and a file copied and edited over the years can hold
2–3 copies of the same person inside itself. uds2gedcom groups every person
record into one merged person, then rebuilds the families from those groups.
Run with `--no-merge` to skip all of this and keep every record as its own
person.

The examples below are invented. The rules were worked out on nine real
Macedonian family files, so a few of them know Macedonian name patterns.

## When two records are the same person

1. **Exact copy.** Same internal record id, same save time and same name in two
   files (one file was copied from the other).
2. **Name seed.** Same given name *and* surname (spelling-tolerant: with
   `--text mk`, GRNČAR = GRN~AR = GRNCAR; with the other alphabets, accents
   and capitals are ignored), and either
   - birth years at most 1 year apart, or
   - at least one relative with the same given name in the same role
     (father, mother, spouse or child), and birth years at most 5 apart or unknown.

   Placeholder names (`?`, empty) never start a match.
3. **Spread through the family.** Once two records are the same person, their
   fathers with the same given name are the same person, and likewise mothers,
   spouses and children. This is what links married women recorded under
   different surnames, and placeholders such as "Wife of Kosta ?".

## What blocks a merge

- Different known sex.
- Birth years more than 5 years apart anywhere inside the merged person.
- Known fathers (or mothers) whose names cannot be the same person. Names are
  compatible when the first names match, are one typo apart (Vesna / Vesne,
  Georgi / Gorgi), are descriptions rather than names ("?", "Wife of John",
  "Unknown", "Žena na Risto", "Vtora žena Ivan"), or are a nickname with the
  same surname and birth year (Mite / Dimitar).
- The two records are each other's relatives (a father and son with the same name).
- Two wives of the same man in one file.
- Two siblings with the same name in one file, unless they also share a birth
  year (then it is the same child entered twice). A family can have two
  children with the same name when the first one died young.

Relatives in the same role of one merged person are merged when their names
are compatible in the sense above: a person has one father and one mother.
Spouses need more, since people remarry: the same first name, or compatible
names plus the same birth year ("Husband of Neda", born 1873, in three files)
or the same wedding year with birth years that do not contradict.

## One child under two names

Two children of the same parent who never appear together in any single file,
with the same birth year, no conflicting sex or full birth date, and no
different mothers, are one child recorded twice: Luka in one file and Marko in
another, both sons of the same Goran and both born in 2006; Kire / Kiril;
"Son 1" / "Ivan". Real siblings, twins included, are listed together in at
least one file. For these merges a disagreeing death year is reported as a
conflict instead of blocking the merge.

## Which value wins

When merged records disagree, the value from the most recently edited record
wins (each record carries its own save time). Every disagreement on name, sex,
birth, death or burial is written to `conflicts.csv` for review, and to a note
on the person in the GEDCOM file.

## Damaged or mis-entered family records

These are left out of the tree and listed in the report:

- A child who is married to one of its own parents (record ids reused after a
  deletion).
- A family saved before one of its parents was 13. In the files studied, its
  "children" were the parent and the parent's siblings entered a second time,
  so each one that shares a first name with exactly one of them is merged into
  that person.

## Families

A child belongs to a family if either the family record or the child's own
record says so. Families are merged when they have the same husband and wife
after the person merge. A family with only one known parent joins that
parent's merged family when they share a child.
