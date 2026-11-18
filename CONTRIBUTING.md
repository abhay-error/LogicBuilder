# Contributing to LogicBuilder

Thanks for helping people learn to code. The easiest high-impact contributions are **content** (problems and lessons), because the app is built around them.

## Run it and run the tests

```
python3 server.py                 # needs Python 3.9+, no installs
python tests/selftest.py          # content + engine
python tests/api_test.py          # server end to end
python tests/lang_test.py         # languages (skips toolchains you don't have)
```

All three must pass before you open a pull request. CI runs them on Windows, macOS and Linux.

## Add a practice problem (about 10 minutes)

1. In `content/problems.py`, add an entry: `slug`, `title`, `difficulty` (1-5), `level`, `concepts`, `entry` (the Python function name), `complexity`, `statement`, `starter`, `tests` (mark 1-2 as `sample=True`; the rest stay hidden), 3 `hints` (nudge, approach, pseudocode) and a `reference` solution.
2. In `content/signatures.py`, add one line with the argument and return types (`int`, `long`, `str`, `bool`, `list[int]`, `list[str]`). Starter code and test drivers for all 7 languages are generated from it.
3. Run `python tests/selftest.py`. It checks that your reference solution passes every test and that the empty starter does not.

Good problems have a clear statement, edge-case tests (empty input, one element, duplicates, large input), and hints that teach rather than reveal.

## Add or improve a lesson

Lessons live in `content/lessons.py` as data. Block types: `text`, `code` (with `visualize: True`), `quiz`, `predict`, `fill`, `parsons`, `trace_table`, `bug`. Predict answers and trace tables are computed by running the code, so you don't hand-write them. Keep lessons small: one idea, under 15 minutes, with at least one thing the learner must *do*.

## Code changes

- The back end is the Python standard library only. Please don't add dependencies.
- The front end is plain JavaScript with no build step.
- Keep changes focused, and add a test when you fix a bug.
- Match the existing style; there is an `.editorconfig`.

## Reporting bugs and ideas

Open an issue using a template. For security problems, see [SECURITY.md](SECURITY.md) and report privately.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
