import pytest

from uds2gedcom import translit


@pytest.fixture
def mk():
    translit.use("mk")
    yield
    translit.use("plain")


@pytest.fixture
def yu():
    translit.use("yu-latin")
    yield
    translit.use("plain")


def test_plain_text_is_left_alone():
    assert translit.native("Zoë [Smith]") == "Zoë [Smith]"
    assert translit.latin("Wendy Quinn") == "Wendy Quinn"


def test_plain_match_key_ignores_accents_and_case():
    assert translit.key("Zoë  O'Brien") == translit.key("ZOE O BRIEN") == "zoe o brien"


def test_special_keys_become_macedonian_letters(mk):
    assert translit.native("^E{EL") == "ЧЕШЕЛ"
    assert translit.native("KU]A") == "КУЌА"
    assert translit.native("|UVE^") == "ЃУВЕЧ"
    assert translit.native("Qubov") == "Љубов"
    assert translit.native("XEZVA") == "ЏЕЗВА"
    assert translit.native("Yvezda") == "Ѕвезда"
    assert translit.native("@ivot") == "Живот"
    assert translit.native("Sve{teno lice-pop") == "Свештено лице-поп"
    assert translit.native("Ohrid, Makedonija") == "Охрид, Македонија"


def test_lowercase_symbol_inside_capitals_stays_capital(mk):
    assert translit.native("GRN~AR") == "ГРНЧАР"
    assert translit.latin("GRN~AR") == "GRNČAR"


def test_latin_style_digraphs_fold_into_cyrillic_letters(mk):
    assert translit.native("Andjela") == "Анѓела"
    assert translit.native("Ljubomir") == "Љубомир"


def test_macedonian_latin_output(mk):
    assert translit.latin("^E{EL") == "ČEŠEL"
    assert translit.latin("|UVE^") == "ǴUVEČ"
    assert translit.latin("Qubov") == "Ljubov"
    assert translit.latin("XEZVA") == "DŽEZVA"
    assert translit.latin("@ivot") == "Život"


def test_macedonian_match_key_ignores_missing_special_letters(mk):
    assert translit.key("GRN~AR") == translit.key("GRNCAR") == translit.key("GRN^AR")
    assert translit.key("Andjela") == translit.key("An|ela")
    assert translit.key("Qubov") == translit.key("Ljubov")
    assert translit.key("?") == ""


def test_yu_latin(yu):
    assert translit.native("^EVAP^I]I") == "ČEVAPČIĆI"
    assert translit.native("|ur|evak @uta ku}a") == "đurđevak Žuta kuća"
    assert translit.native("[apca, \\akovo") == "Šapca, Đakovo"
    assert translit.native("Quba") == "Quba"  # Q W X Y stay Latin letters
    assert translit.latin("@ELJKO") == "ŽELJKO"
    assert translit.key("@ELJKO") == translit.key("Zeljko")
    assert translit.key("\\URO") == translit.key("Djuro")


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        translit.use("klingon")


def test_yuscii_is_spotted_in_names():
    assert translit.looks_like_yuscii(["PETRE^E", "Bla`e", "Ana", "Goran"])
    assert not translit.looks_like_yuscii(["O'Brien", "Smith [twin]", "Ann", "Jo", "Max", "Lee"])
