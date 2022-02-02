#!/usr/bin/env python

import itertools
from functools import lru_cache
from pathlib import Path
from typing import TextIO

from more_itertools import interleave_longest as ill

# data is kept alongside this file
data_path = Path(__file__).absolute().parent / "nerdle_equations.dat"

ANSWER_SIZE = 8


@lru_cache()
def get_all_equations():
    # print("running the line getter")
    with data_path.open("rt") as f:
        return f.read().splitlines()


def generate(out: TextIO):
    for size_l in range(1, ANSWER_SIZE - 1):
        # calculate size of right side
        size_r = ANSWER_SIZE - size_l - 1
        # based on size of left, figure out min and max operators (assume bare min is 1)
        max_operators = (size_l - 1) // 2
        if not max_operators:
            continue

        for num_operators in range(1, max_operators + 1):
            # calculate total term length (length of all terms added together)
            total_term_length = size_l - num_operators
            num_terms = num_operators + 1

            max_term_size = total_term_length - (num_terms - 1)

            term_sizes_gn = (
                term_sizes
                for term_sizes in itertools.product(*itertools.repeat(range(1, max_term_size + 1), num_terms))
                if sum(term_sizes) == total_term_length
            )
            operators_gn = itertools.product(*(["+-*/"] * num_operators))

            for term_sizes, operators in itertools.product(term_sizes_gn, operators_gn):
                term_generators = [range(10 ** (ts - 1), 10 ** (ts)) for ts in term_sizes]
                for terms in itertools.product(*term_generators):
                    equation = "".join(ill(map(str, terms), operators))
                    answer = eval(equation)
                    if not (isinstance(answer, int) or answer.is_integer()):
                        continue
                    if len(str(int(answer))) == size_r:
                        print(f"{equation}={int(answer)}", file=out)


if __name__ == "__main__":
    generate(data_path.open("wt"))
