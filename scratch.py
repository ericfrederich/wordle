#!/usr/bin/env python
import click

from wordle.cli import render_result
from wordle.game import NerdleKnowledge, NerdleResult


def run():
    answer = "10*1-8=2"
    k = NerdleKnowledge()
    for guess in (
        "87-64=23",
        # "28/2-9=5",
    ):
        result = NerdleResult.get(answer=answer, guess=guess)
        click.echo(render_result(result), color=True)
        k.add_result(result)

    valid_solutions = k.valid_solutions()
    for s in valid_solutions:
        print(s)
    print(f"{len(valid_solutions)=}")
    x = k.guess_reduction("28/2-9=5")
    print(f"{x=}")


if __name__ == "__main__":
    run()
