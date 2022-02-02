from datetime import date

from wordle import __version__
from wordle.game import WordleKnowledge, WordleResult
from wordle.wordle_words import SECRET_WORDS, date_to_word, word_to_date


def test_version():
    assert __version__ == "0.1.0"


def test_get_result():
    assert str(WordleResult.get(answer="point", guess="title")) == "t?i?tle"
    assert str(WordleResult.get(answer="point", guess="trout")) == "tro?ut@"
    assert str(WordleResult.get(answer="abbey", guess="blobs")) == "b?lob?s"
    assert str(WordleResult.get(answer="abbey", guess="blurb")) == "b?lurb?"
    assert str(WordleResult.get(answer="abbey", guess="bobby")) == "b?ob@by@"


def test_from_str():
    assert WordleResult.get(answer="point", guess="title") == WordleResult.from_str("t?i?tle")
    assert WordleResult.get(answer="point", guess="trout") == WordleResult.from_str("tro?ut@")
    assert WordleResult.get(answer="abbey", guess="blobs") == WordleResult.from_str("b?lob?s")
    assert WordleResult.get(answer="abbey", guess="blurb") == WordleResult.from_str("b?lurb?")
    assert WordleResult.get(answer="abbey", guess="bobby") == WordleResult.from_str("b?ob@by@")


def test_knowledge():
    k = WordleKnowledge()
    k.add_result(WordleResult.get(answer="abbey", guess="blobs"))
    assert k.char_mins == {"b": 2}
    assert k.answer == [None, None, None, None, None]
    assert k.char_maxes == {"l": 0, "o": 0, "s": 0}
    k.add_result(WordleResult.get(answer="abbey", guess="blurb"))
    assert k.char_mins == {"b": 2}
    assert k.answer == [None, None, None, None, None]
    assert k.char_maxes == {"l": 0, "o": 0, "s": 0, "u": 0, "r": 0}
    k.add_result(WordleResult.get(answer="abbey", guess="bobby"))
    assert k.char_mins == {"b": 2, "y": 1}
    assert k.answer == [None, None, "b", None, "y"]
    assert k.char_maxes == {"l": 0, "o": 0, "s": 0, "u": 0, "r": 0, "b": 2}


def test_dates():
    for word in SECRET_WORDS:
        assert date_to_word(word_to_date(word)) == word
    assert date_to_word(date(2022, 1, 20)) == "robot"
    assert date_to_word(date(2022, 1, 21)) == "prick"


def test_some_bug_i_found():
    """
    This test will fail unless game is also keeping track of maximum letter counts as well
    """
    k = WordleKnowledge()
    k.add_result(WordleResult.get(answer="odder", guess="order"))
    assert "order" not in k.valid_solutions()
    assert "odder" in k.valid_solutions()
    k = WordleKnowledge()
    k.add_result(WordleResult.get(answer="order", guess="odder"))
    assert "odder" not in k.valid_solutions()
    assert "order" in k.valid_solutions()
