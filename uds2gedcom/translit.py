"""Text in the .uds files -> its proper alphabet, a Latin form, and a match key.

The program had no Unicode. Text was stored as typed, and families outside
Western Europe often typed with a YUSCII font, where plain ASCII keys stand
for local letters. Pick the alphabet with use():

  plain     text is used as stored (English and other Western languages)
  mk        Macedonian Cyrillic: @ [ \\ ] ^ ` { | } ~ are Ж Ш Ѓ Ќ Ч ж ш ѓ ќ ч,
            Q W X Y are Љ Њ Џ Ѕ, and the rest map to the matching letter.
            Entries typed Latin-style ("dj", "nj", "lj") fold into one letter.
  yu-latin  Croatian / Serbian / Slovenian / Bosnian Latin (JUS I.B1.002):
            @ [ \\ ] ^ ` { | } ~ are Ž Š Đ Ć Č ž š đ ć č
"""
import re
import unicodedata

MODES = ("plain", "mk", "yu-latin")
_mode = "plain"

_MK = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "АБЦДЕФГХИЈКЛМНОПЉРСТУВЊЏЅЗ"))
_MK.update({k.lower(): v.lower() for k, v in _MK.items()})
_MK.update({"@": "Ж", "[": "Ш", "\\": "Ѓ", "]": "Ќ", "^": "Ч",
            "`": "ж", "{": "ш", "|": "ѓ", "}": "ќ", "~": "ч"})
_YU = {"@": "Ž", "[": "Š", "\\": "Đ", "]": "Ć", "^": "Č",
       "`": "ž", "{": "š", "|": "đ", "}": "ć", "~": "č"}

_DIGRAPHS = {"дј": "ѓ", "гј": "ѓ", "кј": "ќ", "нј": "њ", "лј": "љ", "дж": "џ"}

_LATIN = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ѓ": "ǵ", "е": "e",
          "ж": "ž", "з": "z", "ѕ": "dz", "и": "i", "ј": "j", "к": "k", "л": "l",
          "љ": "lj", "м": "m", "н": "n", "њ": "nj", "о": "o", "п": "p", "р": "r",
          "с": "s", "т": "t", "ќ": "ḱ", "у": "u", "ф": "f", "х": "h", "ц": "c",
          "ч": "č", "џ": "dž", "ш": "š"}

# letters that people type interchangeably when the special key is skipped
_KEY_FOLD = {"ч": "c", "ц": "c", "ж": "z", "з": "z", "ш": "s", "с": "s",
             "ѓ": "g", "г": "g", "ќ": "k", "к": "k", "џ": "dz", "ѕ": "dz",
             "љ": "l", "њ": "n"}

_WORD = re.compile(r"[A-Za-z@\[\\\]^`{|}~]+")


def use(mode):
    global _mode
    if mode not in MODES:
        raise ValueError(f"unknown alphabet {mode!r}: choose one of {', '.join(MODES)}")
    _mode = mode


def _is_caps(word):
    letters = [c for c in word if c.isascii() and c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _cyr_word(word):
    out = "".join(_MK.get(c, c) for c in word)
    caps = _is_caps(word)
    low = out.lower()
    for pair, letter in _DIGRAPHS.items():
        low = low.replace(pair, letter)
    if caps:
        return low.upper()
    # keep the original capitalisation of the first letter
    return low[:1].upper() + low[1:] if out[:1].isupper() else low


def _yu_word(word):
    out = "".join(_YU.get(c, c) for c in word)
    # a lowercase symbol inside a word typed in capitals is a capital too
    return out.upper() if _is_caps(word) else out


def native(raw):
    """The text in its own alphabet."""
    raw = raw or ""
    if _mode == "mk":
        return _WORD.sub(lambda m: _cyr_word(m.group()), raw)
    if _mode == "yu-latin":
        return _WORD.sub(lambda m: _yu_word(m.group()), raw)
    return raw


def latin(raw):
    """The text in Latin letters (Macedonian is transliterated)."""
    if _mode != "mk":
        return native(raw)

    def word(m):
        cyr = _cyr_word(m.group())
        lat = "".join(_LATIN.get(c.lower(), c.lower()) for c in cyr)
        if _is_caps(m.group()):
            return lat.upper()
        return lat[:1].upper() + lat[1:] if cyr[:1].isupper() else lat
    return _WORD.sub(word, raw or "")


def _ascii_fold(s):
    s = s.lower().replace("đ", "dj").replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def key(raw):
    """Spelling-tolerant comparison key: in mk, GRNČAR, GRN~AR and GRNCAR all match."""
    if _mode == "mk":
        cyr = native(raw).lower()
        folded = "".join(_KEY_FOLD.get(c, _LATIN.get(c, c)) for c in cyr)
    else:
        folded = _ascii_fold(native(raw))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", folded).split())


_YUSCII_SIGN = re.compile(r"[A-Za-z][@\[\\\]^`{|}~]|[@\[\\\]^`{|}~][A-Za-z]")


def looks_like_yuscii(names):
    """Do these stored names look typed with a YUSCII font?"""
    names = [n for n in names if n]
    # [twin], {nickname}: brackets used as brackets
    hits = sum(1 for n in names if _YUSCII_SIGN.search(re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", " ", n)))
    return hits >= max(2, len(names) // 50)
