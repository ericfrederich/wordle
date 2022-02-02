import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from string import ascii_lowercase, digits
from typing import ClassVar, Dict, List, Optional, Set, Type, Union

from wordle.nerdle_equations import get_all_equations
from wordle.wordle_words import SECRET_WORDS


class TileFeedback(Enum):
    correct = auto()
    wrong = auto()
    wrong_place = auto()


@dataclass
class ResultPiece:
    character: str
    feedback: Optional[TileFeedback]


@dataclass
class ResultBase:
    """
    The result of a single guess at the game.
    """

    allowed_characters: ClassVar[str]
    pieces: List[ResultPiece]

    @classmethod
    def from_str(cls, result_str: str):
        """
        Load a result from a string representation.
        * Character followed by @       - correct char in correct position
        * Character followed by ?       - char is in solution but at another position
        * Character followed by nothing - wrong char (not in solution)
        """
        pieces: List[ResultPiece] = []
        previous = None
        for c in result_str:
            if c in cls.allowed_characters:
                pieces.append(ResultPiece(c, TileFeedback.wrong))
            elif c in "?@":
                if previous not in cls.allowed_characters or pieces[-1].feedback != TileFeedback.wrong:
                    raise ValueError(f"Unexpected {c!r} found in {result_str}")
                if c == "?":
                    pieces[-1].feedback = TileFeedback.wrong_place
                elif c == "@":
                    pieces[-1].feedback = TileFeedback.correct
                else:
                    raise ValueError("Should never get here")
            else:
                raise ValueError(f"Unexpected {c!r} in {result_str!r}")
            previous = c
        return cls(pieces)

    @classmethod
    def get(cls, *, answer: str, guess: str) -> "ResultBase":
        """
        Given the answer the the guess string return a result
        """

        pieces: List[ResultPiece] = []

        # Mark the obvious correct and wrong
        for a, g in zip(answer, guess):
            if g == a:
                # if it's correct, it's always correct, don't need to look any deeper
                pieces.append(ResultPiece(character=g, feedback=TileFeedback.correct))
            elif g not in answer:
                # if it's not in the word, it's always wrong, don't need to look any deeper
                pieces.append(ResultPiece(character=g, feedback=TileFeedback.wrong))
            else:
                pieces.append(ResultPiece(character=g, feedback=None))

        # duplicates make things difficult, things can be marked as wrong or wrong position
        for piece in pieces:
            if piece.feedback is not None:
                continue
            # how many of this letter are in the answer
            in_answer = answer.count(piece.character)
            # how many of this letter in this particular guess are already marked as correct or wrong place
            already_marked = sum(
                1
                for p in pieces
                if p.character == piece.character and p.feedback in (TileFeedback.correct, TileFeedback.wrong_place)
            )
            if in_answer > already_marked:
                piece.feedback = TileFeedback.wrong_place
            else:
                piece.feedback = TileFeedback.wrong

        return WordleResult(pieces)

    def __str__(self) -> str:
        return "".join(
            {
                TileFeedback.correct: piece.character + "@",
                TileFeedback.wrong: piece.character,
                TileFeedback.wrong_place: piece.character + "?",
            }[piece.feedback]
            for piece in self
        )

    def __iter__(self):
        return iter(self.pieces)

    @cached_property
    def correct_chars(self):
        ret = []
        for i, piece in enumerate(self):
            if piece.feedback == TileFeedback.correct:
                ret.append((i, piece.character))
        return ret

    @cached_property
    def char_mins(self) -> Dict[str, int]:
        ret = {}
        # just once for each char
        for char in set(piece.character for piece in self):
            # find all occurrences of this char that are not wrong
            min_required = sum(1 for piece in self if piece.character == char and piece.feedback != TileFeedback.wrong)
            if min_required:
                ret[char] = min_required
        return ret

    @cached_property
    def char_maxes(self):
        ret = {}
        # just once for each wrong char
        for char in set(piece.character for piece in self if piece.feedback == TileFeedback.wrong):
            # The maximum is equal to the minimum
            ret[char] = self.char_mins.get(char, 0)
        return ret

    @cached_property
    def wrong_positions(self):
        return {i: r.character for i, r in enumerate(self) if r.feedback == TileFeedback.wrong_place}


@dataclass
class WordleResult(ResultBase):
    allowed_characters: ClassVar[str] = ascii_lowercase


@dataclass
class NerdleResult(ResultBase):
    allowed_characters: ClassVar[str] = digits + "+-*/="


@dataclass
class KnowledgeBase(ABC):
    """
    Everything known so far within a game
    """

    ANSWER_LENGTH: ClassVar[int]
    result_cls: ClassVar[Type[ResultBase]]
    # minimum and maximum number of occurrences for each char (max of 0 means it's not in the solution)
    char_mins: Dict[str, int] = field(default_factory=dict)
    char_maxes: Dict[str, int] = field(default_factory=dict)
    wrong_positions: List[Set[str]] = field(default_factory=list)  # actually initialized in __post_init__
    answer: List = field(default_factory=list)  # actually initialized in __post_init__

    def __post_init__(self):
        for _ in range(self.ANSWER_LENGTH):
            self.wrong_positions.append(set())
            self.answer.append(None)

    def copy(self):
        return copy.deepcopy(self)

    @classmethod
    def from_results(cls, *results: Union[ResultBase, str]):
        ret = cls()
        for r in results:
            if isinstance(r, str):
                r = cls.result_cls.from_str(r)
            ret.add_result(r)
        return ret

    def is_valid_solution(self, word: str) -> bool:
        # if it's not using all the correct letter counts it's wrong
        for l, c in self.char_mins.items():
            if word.count(l) < c:
                return False
        for l, c in self.char_maxes.items():
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

    @abstractmethod
    def valid_solutions(self, solution_list: List[str] = None) -> List[str]:
        pass

    def add_result(self, result: ResultBase):
        # merge the correct letters
        for i, l in result.correct_chars:
            if self.answer[i]:
                assert self.answer[i] == l
            self.answer[i] = l
        # merge the min letter counts
        for l, c in result.char_mins.items():
            # if we've established a max for this letter, make sure it's less than it
            if l in self.char_maxes:
                assert c <= self.char_maxes[l]
            if c > self.char_mins.get(l, 0):
                self.char_mins[l] = c
        # merge the max letter counts
        for l, c in result.char_maxes.items():
            if l in self.char_mins:
                assert c >= self.char_mins[l]
            # once we know the max it should never change
            if l in self.char_maxes:
                assert c == self.char_maxes[l]
            else:
                self.char_maxes[l] = c
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
            k.add_result(self.result_cls.get(answer=pretend_answer, guess=guess))
            total += len(k.valid_solutions())
        avg = total / len(pretend_answers)
        return len(pretend_answers) - avg


@dataclass
class WordleKnowledge(KnowledgeBase):
    ANSWER_LENGTH: ClassVar[int] = 5
    result_cls = WordleResult

    def valid_solutions(self, solution_list: List[str] = SECRET_WORDS) -> List[str]:
        # Should we limit this to list of secret words or also include anything
        # that wordle allows as a guess
        return [w for w in solution_list if self.is_valid_solution(w)]


@dataclass
class NerdleKnowledge(KnowledgeBase):
    ANSWER_LENGTH: ClassVar[int] = 8
    result_cls = NerdleResult

    def valid_solutions(self, solution_list: List[str] = None) -> List[str]:
        if solution_list is None:
            solution_list = get_all_equations()
        return [w for w in solution_list if self.is_valid_solution(w)]
