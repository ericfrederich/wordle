from datetime import date

from wordle import __version__
from wordle.game import Knowledge, WordleResult, get_result
from wordle.wordle_words import SECRET_WORDS, date_to_word, word_to_date


def test_version():
    assert __version__ == "0.1.0"


def test_get_result():
    assert str(get_result(answer="point", guess="title")) == "t?i?tle"
    assert str(get_result(answer="point", guess="trout")) == "tro?ut+"
    assert str(get_result(answer="abbey", guess="blobs")) == "b?lob?s"
    assert str(get_result(answer="abbey", guess="blurb")) == "b?lurb?"
    assert str(get_result(answer="abbey", guess="bobby")) == "b?ob+by+"


def test_from_str():
    assert get_result(answer="point", guess="title") == WordleResult.from_str("t?i?tle")
    assert get_result(answer="point", guess="trout") == WordleResult.from_str("tro?ut+")
    assert get_result(answer="abbey", guess="blobs") == WordleResult.from_str("b?lob?s")
    assert get_result(answer="abbey", guess="blurb") == WordleResult.from_str("b?lurb?")
    assert get_result(answer="abbey", guess="bobby") == WordleResult.from_str("b?ob+by+")


def test_knowledge():
    k = Knowledge()
    k.add_result(get_result(answer="abbey", guess="blobs"))
    assert k.letter_min == {"b": 2}
    assert k.answer == [None, None, None, None, None]
    assert k.letter_max == {"l": 0, "o": 0, "s": 0}
    k.add_result(get_result(answer="abbey", guess="blurb"))
    assert k.letter_min == {"b": 2}
    assert k.answer == [None, None, None, None, None]
    assert k.letter_max == {"l": 0, "o": 0, "s": 0, "u": 0, "r": 0}
    k.add_result(get_result(answer="abbey", guess="bobby"))
    assert k.letter_min == {"b": 2, "y": 1}
    assert k.answer == [None, None, "b", None, "y"]
    assert k.letter_max == {"l": 0, "o": 0, "s": 0, "u": 0, "r": 0, "b": 2}


def test_dates():
    for word in SECRET_WORDS:
        assert date_to_word(word_to_date(word)) == word
    assert date_to_word(date(2022, 1, 20)) == "robot"
    assert date_to_word(date(2022, 1, 21)) == "prick"


def test_some_bug_i_found():
    """
    This test will fail unless game is also keeping track of maximum letter counts as well
    """
    k = Knowledge()
    k.add_result(get_result(answer="odder", guess="order"))
    assert "order" not in k.valid_solutions()
    assert "odder" in k.valid_solutions()
    k = Knowledge()
    k.add_result(get_result(answer="order", guess="odder"))
    assert "odder" not in k.valid_solutions()
    assert "order" in k.valid_solutions()
