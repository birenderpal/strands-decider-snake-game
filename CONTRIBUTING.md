# Contributing

Keep the repo simple: plain HTML, CSS, and JavaScript, a small Python backend,
and Strands Decider choosing every move. Add a framework or dependency only
when the change needs it.

## Setup and checks

Install uv and Git as described in [README.md](README.md). From the repository
root, run:

```bash
uv sync --locked --python 3.13
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
node --check static/app.js
```

Tests use simulated model responses, so they need no GPU, credentials, or model
weights. Installing the dependencies still installs PyTorch. CI uses macOS to
match the tested development environment and avoid unused Linux CUDA downloads.

For a manual check, run `uv run --locked python app.py` and open
`http://127.0.0.1:8000/` in a web browser. Please verify Step, Start/Pause, Reset,
model selection, the decision panel, and the layout in a narrow window. Switching
models should clear the board and decisions, and release the previous model.
The first use of a checkpoint downloads its files. Live gameplay checks are described in
[docs/experiments.md](docs/experiments.md).

## Making changes

1. Keep rules and observations in `game.py`, and model calls in `decider.py`.
2. Preserve the safeguards in `app.py` for resets, timeouts, stale requests, and
   overlapping model calls. Keep loading, unloading, and inference on one worker.
3. Apply the model's exact choice. Do not filter directions, choose a route,
   replace a low-confidence decision, or add a fallback bot.
4. Insert model output as text, not HTML.
5. Add focused tests for behaviour changes and record what was checked. Compare
   live gameplay when changing the model prompt.
6. Record major changes in `CHANGELOG.md`. Include an updated `uv.lock` when
   changing dependencies.

For a bug report, include the model ID, device, Python version, and steps to
reproduce the problem. Remove private information from errors and logs before
sharing them. For a pull request, explain the problem, the change, and the checks.

Keep model weights, caches, runtime reports, credentials, local settings, and
generated files out of Git. Review the staged diff before committing.
See [SECURITY.md](SECURITY.md) for private reporting guidance.

Contributions use this repository's [MIT licence](LICENSE).
