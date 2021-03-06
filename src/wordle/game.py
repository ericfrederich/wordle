import copy
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from string import ascii_lowercase, ascii_uppercase
from typing import Dict, List, Optional, Set, Union

from wordle.wordle_words import SECRET_WORDS

WORD_LENGTH = 5


class LetterFeedback(Enum):
    correct = auto()
    wrong = auto()
    wrong_place = auto()


@dataclass
class ResultPiece:
    letter: str
    feedback: Optional[LetterFeedback]


@dataclass
class Result:
    """
    The result of a single guess at the game.
    """

    pieces: List[ResultPiece]

    @classmethod
    def from_str(cls, result_str: str):
        """
        Load a result from a string representation.
        * Upper case: correct letter in correct position
        * Lower case: wrong letter (not in word)
        * Lower case followed by ?: letter is in word but at another position
        """
        pieces: List[ResultPiece] = []
        previous = None
        for c in result_str:
            if c in ascii_lowercase:
                pieces.append(ResultPiece(c, LetterFeedback.wrong))
            elif c in ascii_uppercase:
                pieces.append(ResultPiece(c.lower(), LetterFeedback.correct))
            elif c == "?":
                if previous not in ascii_lowercase or pieces[-1].feedback != LetterFeedback.wrong:
                    raise ValueError(f"Unexpected `?` found in {result_str}")
                pieces[-1].feedback = LetterFeedback.wrong_place
            previous = c
        return cls(pieces)

    def __str__(self) -> str:
        return "".join(
            {
                LetterFeedback.correct: piece.letter.upper(),
                LetterFeedback.wrong: piece.letter,
                LetterFeedback.wrong_place: piece.letter + "?",
            }[piece.feedback]
            for piece in self
        )

    def __iter__(self):
        return iter(self.pieces)

    @cached_property
    def correct_letters(self):
        ret = []
        for i, piece in enumerate(self):
            if piece.feedback == LetterFeedback.correct:
                ret.append((i, piece.letter))
        return ret

    @cached_property
    def letter_mins(self) -> Dict[str, int]:
        ret = {}
        # just once for each letter
        for letter in set(piece.letter for piece in self):
            # find all occurrences of this letter that are not wrong
            min_required = sum(1 for piece in self if piece.letter == letter and piece.feedback != LetterFeedback.wrong)
            if min_required:
                ret[letter] = min_required
        return ret

    @cached_property
    def letter_maxes(self):
        ret = {}
        # just once for each wrong letter
        for letter in set(piece.letter for piece in self if piece.feedback == LetterFeedback.wrong):
            # The maximum is equal to the minimum
            ret[letter] = self.letter_mins.get(letter, 0)
        return ret

    @cached_property
    def wrong_positions(self):
        return {i: r.letter for i, r in enumerate(self) if r.feedback == LetterFeedback.wrong_place}


@dataclass
class Knowledge:
    """
    Everything known so far within a game
    """

    # required letters
    #  letters that must be used (perhaps we even know where if they've ever been green)
    #  need to keep a count, not just a set of letters.
    #  for instance, if word is abbey and you guess blobs
    #  you'll get back b?lob?s ...  need 2 "b"s
    #  do not remove from list once their location is found
    letter_min: Dict[str, int] = field(default_factory=dict)
    # Maximum occurrences of each letter (also handles wrong letters, max 0)
    letter_max: Dict[str, int] = field(default_factory=dict)
    wrong_positions: List[Set[str]] = field(default_factory=lambda: [set() for _ in range(WORD_LENGTH)])
    answer: List = field(default_factory=lambda: [None] * WORD_LENGTH)

    def copy(self):
        return copy.deepcopy(self)

    @classmethod
    def from_results(cls, *results: Union[Result, str]):
        ret = cls()
        for r in results:
            if isinstance(r, str):
                r = Result.from_str(r)
            ret.add_result(r)
        return ret

    def is_valid_solution(self, word: str) -> bool:
        # if it's not using all the correct letter counts it's wrong
        for l, c in self.letter_min.items():
            if word.count(l) < c:
                return False
        for l, c in self.letter_max.items():
            if word.count(l) > c:
                return False
        # if the known positions are not correct it's false
        for a, l in zip(self.answer, word):
            if a and a != l:
                return False
        # if a letter is in the wrong position it's wrong
        for i, l in enumerate(word):
            if l in self.wrong_positions[i]:
                return False
        return True

    def valid_solutions(self, word_list: List[str] = SECRET_WORDS) -> List[str]:
        # Should we limit this to list of secret words or also include anything
        # that wordle allows as a guess
        return [w for w in word_list if self.is_valid_solution(w)]

    def add_result(self, result: Result):
        # merge the correct letters
        for i, l in result.correct_letters:
            if self.answer[i]:
                assert self.answer[i] == l
            self.answer[i] = l
        # merge the min letter counts
        for l, c in result.letter_mins.items():
            # if we've established a max for this letter, make sure it's less than it
            if l in self.letter_max:
                assert c <= self.letter_max[l]
            if c > self.letter_min.get(l, 0):
                self.letter_min[l] = c
        # merge the max letter counts
        for l, c in result.letter_maxes.items():
            if l in self.letter_min:
                assert c >= self.letter_min[l]
            # once we know the max it should never change
            if l in self.letter_max:
                assert c == self.letter_max[l]
            else:
                self.letter_max[l] = c
        # merge the wrong positions
        for i, l in result.wrong_positions.items():
            self.wrong_positions[i].add(l)

    def guess_reduction(self, guess: str, pretend_answers: List[str] = None) -> float:
        total = 0
        # pretend each thing that can be correct is and gather average reduction valid solutions
        if pretend_answers is None:
            pretend_answers = self.valid_solutions()
        for pretend_answer in pretend_answers:
            k = self.copy()
            k.add_result(get_result(answer=pretend_answer, guess=guess))
            total += len(k.valid_solutions())
        avg = total / len(pretend_answers)
        return len(pretend_answers) - avg


def get_result(*, answer: str, guess: str) -> Result:
    """
    Given the answer the the guess string return a result
    """

    pieces: List[ResultPiece] = []

    # Mark the obvious correct and wrong
    for a, g in zip(answer, guess):
        if g == a:
            # if it's correct, it's always correct, don't need to look any deeper
            pieces.append(ResultPiece(letter=g, feedback=LetterFeedback.correct))
        elif g not in answer:
            # if it's not in the word, it's always wrong, don't need to look any deeper
            pieces.append(ResultPiece(letter=g, feedback=LetterFeedback.wrong))
        else:
            pieces.append(ResultPiece(letter=g, feedback=None))

    # duplicates make things difficult, things can be marked as wrong or wrong position
    for piece in pieces:
        if piece.feedback is not None:
            continue
        # how many of this letter are in the answer
        in_answer = answer.count(piece.letter)
        # how many of this letter in this particular guess are already marked as correct or wrong place
        already_marked = sum(
            1
            for p in pieces
            if p.letter == piece.letter and p.feedback in (LetterFeedback.correct, LetterFeedback.wrong_place)
        )
        if in_answer > already_marked:
            piece.feedback = LetterFeedback.wrong_place
        else:
            piece.feedback = LetterFeedback.wrong

    return Result(pieces)


class Game:
    knowledge: Knowledge

    def __init__(self):
        self.knowledge = Knowledge()
