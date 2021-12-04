import concurrent.futures
import io
import os
from datetime import datetime
from string import ascii_lowercase
from typing import List, Tuple

import click

from wordle.game import Knowledge, LetterFeedback, Result, get_result
from wordle.wordle_words import (
    ALLOWED_GUESSES,
    SECRET_WORDS,
    date_to_word,
    word_to_date,
)


@click.group()
@click.pass_context
def cli_main(ctx: click.Context):
    # force color output in Pycharm
    if "PYCHARM_HOSTED" in os.environ:
        ctx.color = True


class ResultType(click.ParamType):
    name = "result"

    def convert(self, value, param, ctx):
        if isinstance(value, Result):
            # WHEN DOES THIS EVER HAPPEN?
            click.secho("WHEN DOES THIS EVER HAPPEN?", fg="red", bold=True)
            return value

        elif isinstance(value, str):
            return Result.from_str(value)
        else:
            click.secho("?" * 80, fg="red", bold=True)

        try:
            if value[:2].lower() == "0x":
                return int(value[2:], 16)
            elif value[:1] == "0":
                return int(value, 8)
            return int(value, 10)
        except ValueError:
            self.fail(f"{value!r} is not a valid integer", param, ctx)


# Styles
COMMON_S = {"bold": True}
CORRECT_S = {"bg": "green", "fg": "bright_white", **COMMON_S}
WRONG_S = {"bg": "bright_black", "fg": "bright_white", **COMMON_S}
WRONG_PLACE_S = {"bg": "bright_yellow", "fg": "black", **COMMON_S}


def render_result(result: Result):
    return "".join(
        click.style(
            piece.letter.upper(),
            **{
                LetterFeedback.wrong: WRONG_S,
                LetterFeedback.wrong_place: WRONG_PLACE_S,
                LetterFeedback.correct: CORRECT_S,
            }[piece.feedback],
        )
        for piece in result
    )


def render_keyboard(k: Knowledge):
    for row in (
        "q w e r t y u i o p",
        " a s d f g h j k l",
        "   z x c v b n m",
    ):
        for c in row:
            if c in ascii_lowercase:
                if c in k.answer:
                    c = click.style(c, **CORRECT_S)
                elif c in k.letter_min:
                    c = click.style(c, **WRONG_PLACE_S)
                elif c in (l for l, n in k.letter_max.items() if n == 0):
                    c = click.style(c, **WRONG_S)
                click.echo(c, nl=False)
            elif c == " ":
                click.echo(c, nl=False)
        click.echo()


@cli_main.command("valid-solutions")
@click.option("--quiet", "-q", is_flag=True)
@click.argument("results", metavar="result str ...", nargs=-1, type=ResultType())
@click.pass_context
def valid_solutions_cmd(ctx: click.Context, quiet: bool, results: List[Result]):
    """
    Show valid solutions given the supplied previous results/feedback
    """
    if not quiet:
        click.secho(f"{ctx.command.name}(", fg="white", bold=True)
        for r in results:
            click.echo("  " + render_result(r) + ",")
        click.secho(")", fg="white", bold=True)
    k = Knowledge.from_results(*results)
    for p in sorted(k.valid_solutions(word_list=SECRET_WORDS)):
        click.echo(p)


@cli_main.command("best-guess")
@click.option("--hard-mode", is_flag=True, default=False)
@click.option("--only-secret-words", is_flag=True)
@click.option("--guess", "-g", "guess_cli_strs", multiple=True, help="Use only these guesses from CLI")
@click.option("--threads", "n_threads", type=click.types.INT, default=os.cpu_count())
@click.option("--out", "out_file", type=click.types.File("w"))
@click.option("--quiet", "-q", is_flag=True)
@click.argument("results", metavar="result str ...", nargs=-1, type=ResultType())
@click.pass_context
def best_guess_cmd(
    ctx: click.Context,
    hard_mode: bool,
    only_secret_words: bool,
    guess_cli_strs: Tuple[str],
    n_threads: int,
    out_file: io.BytesIO,
    quiet: bool,
    results: List[Result],
    internal_call: bool = False,
    pretend_answers: List[str] = None,
):
    """
    Find the guess word that would reduce the set of legal words the most.
    This is CPU intensive and by default uses all cores of the machine.
    """
    if not quiet:
        click.secho(f"{ctx.command.name}(", fg="white", bold=True)
        for r in results:
            click.echo("  " + render_result(r) + ",")
        click.secho(")", fg="white", bold=True)
    knowledge = Knowledge.from_results(*results)
    data = []
    valid_before = knowledge.valid_solutions()
    if hard_mode:
        if only_secret_words:
            guesses = sorted(knowledge.valid_solutions(word_list=SECRET_WORDS))
        else:
            guesses = sorted(knowledge.valid_solutions(word_list=SECRET_WORDS + ALLOWED_GUESSES))
    else:
        if only_secret_words:
            guesses = sorted(SECRET_WORDS)
        else:
            guesses = sorted(SECRET_WORDS + ALLOWED_GUESSES)
    if guess_cli_strs:
        guesses = sorted(guess_cli_strs)
    with concurrent.futures.ProcessPoolExecutor(max_workers=n_threads) as executor:
        future_to_guess = {
            executor.submit(knowledge.guess_reduction, guess, pretend_answers=pretend_answers): guess
            for guess in guesses
        }
        with click.progressbar(
            concurrent.futures.as_completed(future_to_guess),
            item_show_func=lambda f: future_to_guess.get(f, ""),
            show_pos=True,
            length=len(guesses),
        ) as pb:
            for future in pb:
                guess = future_to_guess[future]
                try:
                    reduction = future.result()
                except Exception as exc:
                    print("%r generated an exception: %s" % (guess, exc))
                else:
                    data.append((reduction, guess))

    data.sort()
    if not internal_call:
        for reduction, guess in data:
            if guess in SECRET_WORDS:
                click.secho(guess, **CORRECT_S, nl=False)
            elif guess in ALLOWED_GUESSES:
                click.secho(guess, **WRONG_PLACE_S, nl=False)
            click.echo(f" reduces average of {reduction} down to average of {len(valid_before) - reduction}")
            if out_file:
                print(
                    f"{guess} reduces average of {reduction} down to average of {len(valid_before) - reduction}",
                    file=out_file,
                )

    return [word for reduction, word in data]


@cli_main.command("get-result")
@click.option("--as-string", is_flag=True)
@click.argument("answer", type=click.types.STRING)
@click.argument("guess", type=click.types.STRING)
def get_result_cmd(as_string: bool, answer: str, guess: str):
    """
    Given an answer and guess give the formatted result
    """
    if not (answer.islower() and guess.islower()):
        raise click.BadArgumentUsage("Need lower case")
    result = get_result(answer=answer, guess=guess)
    if as_string:
        click.echo(str(result))
    else:
        click.echo(render_result(result))


@cli_main.command("answer")
@click.option("--quiet", "-q", is_flag=True, help="Don't show date")
@click.argument("dt", metavar="date", type=click.DateTime(), default=datetime.now())
def answer_cmd(quiet: bool, dt: datetime):
    """
    Get answer for a particular day (default is today's answer)
    """
    d = dt.date()
    answer = date_to_word(d)
    if quiet:
        click.echo(click.style(answer, **CORRECT_S))
    else:
        click.echo(f"{d}: " + click.style(answer, **CORRECT_S))


@cli_main.command("answers")
@click.option("--quiet", "-q", is_flag=True, help="Don't show date")
def answers_cmd(quiet: bool):
    """
    List all answers by date
    """
    for answer in SECRET_WORDS:
        d = word_to_date(answer)
        if quiet:
            click.echo(click.style(answer, **CORRECT_S))
        else:
            click.echo(f"{d}: " + click.style(answer, **CORRECT_S))


@cli_main.command("date")
@click.argument("word", type=click.STRING)
def date_cmd(word: str):
    """
    Get the date for a particular word
    """
    try:
        d = word_to_date(word)
    except ValueError as ve:
        raise click.BadParameter(f"{word} will never be a word")
    click.secho(f"{d}: {word}")


@cli_main.command("bot")
@click.option("--hard-mode", is_flag=True, default=False)
@click.option("--only-secret-words", is_flag=True)
@click.option("--threads", "n_threads", type=click.types.INT, default=os.cpu_count())
@click.option("--quiet", "-q", is_flag=True)
@click.option("--best/--worst", is_flag=True, default=True)
@click.argument("answer", type=click.types.STRING)
@click.argument("initial-guesses", nargs=-1)
@click.pass_context
def bot_cmd(
    ctx: click.Context,
    hard_mode: bool,
    only_secret_words: bool,
    n_threads: int,
    quiet: bool,
    best: bool,
    answer: str,
    initial_guesses: List[str],
):
    knowledge = Knowledge()
    results = []
    for guess in initial_guesses:
        result = get_result(answer=answer, guess=guess)
        print(f"{result!r}")
        print(f"{str(result)=}")
        results.append(result)
        if not quiet:
            click.echo(render_result(result))
        knowledge.add_result(result)

    pretend_answers = None
    if not best:
        pretend_answers = [answer]

    while len(valid_solutions := knowledge.valid_solutions()) > 1:
        click.secho(f"{len(valid_solutions)} valid solutions ({valid_solutions})")
        guesses = ctx.invoke(
            best_guess_cmd,
            hard_mode=hard_mode,
            only_secret_words=only_secret_words,
            n_threads=n_threads,
            quiet=quiet,
            results=results,
            internal_call=True,
            pretend_answers=pretend_answers,
        )
        click.secho(f"{guesses=})", fg="cyan")
        if best:
            guess = guesses[-1]
        else:
            guess = guesses[0]
        result = get_result(answer=answer, guess=guess)
        click.echo(f"Got result {render_result(result)}")
        results.append(result)
        knowledge.add_result(result)

    assert knowledge.valid_solutions() == [answer]
    click.secho(f"Answer {render_result(get_result(answer=answer, guess=answer))}")


@cli_main.command("play")
@click.option("--hard-mode", is_flag=True, default=False)
@click.option("--threads", "n_threads", type=click.types.INT, default=os.cpu_count())
@click.argument("dt", metavar="date", type=click.DateTime(), default=datetime.now())
@click.pass_context
def play(ctx: click.Context, dt: datetime, hard_mode: bool, n_threads: int = os.cpu_count()):
    """
    Get answer for a particular day (default is today's answer)
    """
    d = dt.date()
    click.secho(f"Playing {d}", fg="green", bold=True)
    answer = date_to_word(d)
    knowledge = Knowledge()
    results = []
    while True:
        for r in results:
            click.echo(render_result(r))
        render_keyboard(knowledge)
        guess = click.prompt("Guess")
        if guess.startswith("/"):
            cmd = guess[1:]
            if cmd in ("?", "??"):
                click.secho(f"{len(knowledge.valid_solutions())} valid solutions", fg="cyan", bold=True)
                if cmd == "??":
                    click.secho(f"{knowledge.valid_solutions()!r}", fg="cyan")
            elif cmd in ("k", "knowledge"):
                click.secho(knowledge, fg="cyan", bold=True)
            elif cmd in ("b", "best"):
                if not results and not click.confirm(
                    "This will take like 4 hours and tell you the best guess is 'roate'\n"
                    "Do you really want to do this?"
                ):
                    continue
                guesses = ctx.invoke(
                    best_guess_cmd,
                    hard_mode=hard_mode,
                    n_threads=n_threads,
                    quiet=True,
                    results=results,
                    internal_call=True,
                )
                click.secho(f"Best guesses: {guesses[-10:]}", fg="cyan")
            else:
                click.secho(f"Unrecognized command {cmd}", fg="red", bold=True)
            continue
        if guess.lower() in ("quit", "exit"):
            break
        if guess not in ALLOWED_GUESSES + SECRET_WORDS:
            click.secho(f"{guess} is not a valid guess word", fg="red", bold=True)
            continue
        if hard_mode and not knowledge.is_valid_solution(guess):
            click.secho(f"{guess} is not a valid in hard mode", fg="red", bold=True)
            continue
        result = get_result(answer=answer, guess=guess)
        # click.secho(render_result(result))
        knowledge.add_result(result)
        results.append(result)
        if guess == answer:
            click.echo(render_result(result))
            break
    # if quiet:
    #     click.echo(click.style(answer, **CORRECT_S))
    # else:
    #     click.echo(f"{d}: " + click.style(answer, **CORRECT_S))
