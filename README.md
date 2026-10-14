# Snake with Strands Decider

Strands Decider plays Snake and chooses every move. You can let it play or step
through one decision at a time, then have a look at the board state, probabilities,
and time taken for each decision.

The UI uses plain HTML, CSS, and JavaScript in your browser. A small Python backend
uses FastAPI and Uvicorn to serve the game and run the model locally. No API key,
AWS account, or frontend build is needed.

This is an independent experiment using
[Strands Decider](https://github.com/strands-labs/strands-decider).

## Run locally

Clone or download this repository, then open a terminal in its root directory.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Git](https://git-scm.com/downloads), then run:

```bash
uv sync --locked --python 3.13
uv run --locked python app.py
```

The second command starts the Python server. Keep that terminal running.
Open a web browser, paste the following address into its address bar, and press Enter:

```text
http://127.0.0.1:8000/
```

This address connects to the server on your computer. Wait for **Model online**,
then select **Start game**. To stop the server, return to the terminal and press
**Ctrl+C**.

The first launch downloads about 4.3 GB of Hobson v21 files from Hugging Face. The files
are cached in `.cache/huggingface/` and reused on later launches. Python dependencies
need additional disk space. Allow several GB of free RAM; CPU inference uses more
memory than MPS or CUDA. The page remains available while the model loads.

Python 3.11 to 3.13 is supported by the dependency configuration. Use 3.13 to get
started. Live gameplay has been tested on Apple Silicon with MPS. CPU and CUDA
are available, but their gameplay performance has not been measured here. Use a
current version of Chrome, Edge, Firefox, or Safari.

## Choose a local model

Use **Local model** above the board to select a checkpoint:

| Model | First use |
| --- | --- |
| [Hobson v21 · 2B](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v21) | Default player; about 4.3 GB of model files |
| [Qwen 3.5 v1 · 2B](https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610) | Reuses the Hobson v21 base weights and downloads a separate adapter |
| [Gemma 4 v1 · E2B](https://huggingface.co/StrandsAgents/strands-decider-E2B-gemma4-v1-2610) | Downloads about 10 GB of base weights, plus its adapter; needs more RAM |

1. Pause the game and wait for the current decision to finish.
2. Select a model and click **Load model**. This starts a fresh round and clears
   the previous decisions.
3. Wait for **Model online**, then select **Step** or **Start game**.

Only one model is loaded at a time. The app releases the previous model before
loading the next one. Downloads stay cached on disk; switching back does not
download the same files again. The server terminal shows download progress.
If loading fails, use **Retry load** or select another model.

The E2B name does not mean Gemma uses the same memory as Qwen 2B. Its base
checkpoint contains about 5.1 billion parameters, including components outside
the text decoder. Allow room for loading as well as inference; CPU uses more RAM.

Qwen 3.5 v1 and Gemma E2B both score 77.9% on the model cards' 231-task JevBench
public evaluation at 4,096 tokens, compared with 76.2% for Hobson v21. These
results make them worth comparing, but do not establish which plays Snake better.
The game uses the same observations, instructions, and four choices for every
model. Simultaneous games and model races are not included.

## Controls

1. **Start / Resume:** let the model choose and apply one move at a time.
2. **Pause:** finish the current decision, then stop requesting moves.
3. **Step:** request one decision while the game is paused.
4. **Reset:** start a fresh board and discard any pending decision for the old board.
5. **Pause between moves:** add viewing time after each decision. This is separate
   from the time the model takes to respond.

Hiding the browser tab pauses play. Eating food adds one point and one snake
segment. A wall or body collision ends the round; filling the board wins.
The snake can move into the tail's current square when the tail moves away.

The board stays 12 × 12, and the game does not automatically increase its speed.
Finding a route gets harder as the snake grows.

The decision panel shows the chosen direction, all four probabilities, confidence,
decision time, and input tokens. It also shows recent moves, moves since food,
and revisits to the current square. Expand **What the model saw** to read the
observation used for the latest decision.

## How decisions work

Each turn follows the same sequence:

1. The browser requests a move.
2. Python describes the current board.
3. Strands Decider chooses `UP`, `RIGHT`, `DOWN`, or `LEFT`.
4. Python applies that choice and returns the updated board.
5. The browser displays the result.

The default model is
[`StrandsAgents/strands-decider-2B-hobson-v21`](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v21).
The app calls `SystemOneEngine.ask()` with a `ChoiceQuestion`. Inference runs
locally, with the package versions recorded in `uv.lock`.
Gemma 4 support comes from a fixed
[Strands Decider revision](https://github.com/strands-labs/strands-decider/commit/8b6faa553038a59e73fa7f16c4081f8ceb21d27e).
Git is needed to install that dependency.

Each request contains the food direction, immediate collision facts, and the
distance to food after each possible move. The distance is measured horizontally
and vertically and ignores obstacles; it is not a planned route. The request also
includes the full snake layout, food coordinates, board dimensions, the last eight
moves, and visit counts from up to 64 recent head positions. Visit counts reset
when food is eaten.

This is a fresh snapshot on each turn. The coordinate list grows when the snake
eats, while recent move history stays limited to eight directions. The model does
not receive an accumulating conversation or learn during play. The instructions
and choice descriptions are in [`decider.py`](decider.py).

All four directions remain available, including moves that cause a collision.
The app applies the model's choice without replacing it with a pathfinding rule
or fallback bot. Model errors pause play. Confidence shows the model's certainty;
it is not a measured probability of making a safe move or winning.

The model can still circle, miss food, or become trapped. The
[experiment notes](docs/experiments.md) describe the results and their limits.

## Project layout

```text
app.py             FastAPI server, shared game state, and one model worker
game.py            Snake rules and board observations
decider.py         Model loading and one choice per turn
evaluate.py        Live gameplay checks with fixed seeds and a move limit
static/index.html  Browser interface
static/style.css   Layout and colours
static/app.js      Board drawing, controls, and decision display
tests/             Rules, model interface, and API checks
```

There is one shared game, so every tab uses the same board. The server listens
only on `127.0.0.1`. Run one process without reload or extra workers to load the
model once. Model changes apply to every tab; other tabs pause and refresh the
board when they detect a change. Restarting the server clears the game state and
returns to the startup model.

## Configuration

The app selects CUDA first, then Apple MPS, then CPU. To select CPU explicitly
in a macOS or Linux shell:

```bash
DECIDER_DEVICE=cpu uv run --locked python app.py
```

In PowerShell, set `$env:DECIDER_DEVICE = "cpu"` before running the app.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DECIDER_DEVICE` | `auto` | Select `auto`, `mps`, `cuda`, or `cpu` |
| `DECIDER_MODEL` | `StrandsAgents/strands-decider-2B-hobson-v21` | Choose the startup checkpoint ID or a trusted local model directory |
| `HF_HOME` | `.cache/huggingface/` in this repo | Set the model cache location |
| `HF_HUB_OFFLINE` | Unset | Set to `1` to use already cached model files |

The app reads environment variables from the shell. It does not load a `.env` file.
An override outside the three built-in choices appears as **Startup model**.
The browser accepts only these choices and the configured startup override.
Larger models are not offered or validated here.

## Checks

```bash
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
node --check static/app.js
```

Tests use a simulated model response and do not download or run model weights.
Node is needed only for the JavaScript syntax check.
[GitHub Actions](.github/workflows/checks.yml) is configured to run these checks
on macOS with Python 3.11 and 3.13, with model downloads disabled. Live checks are
recorded in [CHANGELOG.md](CHANGELOG.md).

## Evaluate gameplay

Stop the game server first to avoid loading a second model, then run:

```bash
uv run --locked python evaluate.py --seeds 7 19 42 --moves 120
```

Results are saved to `runtime/evaluation.json`, which Git ignores. The report
includes food collected, repeated board states, moves without food, decision
time, and each chosen move. Fixed seeds make the starting conditions repeatable,
but hardware and numerical differences can still change the decisions.
See [docs/experiments.md](docs/experiments.md) for replay options and measurement limits.
To check another model, set `DECIDER_MODEL` for the evaluator too. For example:

```bash
DECIDER_MODEL=StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 \
  uv run --locked python evaluate.py --seeds 7 19 42 --moves 120 \
  --output runtime/qwen-v1.json
```

## Troubleshooting

1. **Model unavailable:** read the error in the server terminal. Check access to
   Hugging Face and available disk space and RAM, then select **Retry load** or
   another model. If `HF_HUB_OFFLINE=1`, only cached models can load.
2. **MPS or CUDA error:** try `DECIDER_DEVICE=cpu`. CPU decisions can take longer.
3. **Slow moves:** the model's response time and the pause between moves are
   separate. Larger board observations also take more work to process.
4. **Decision timeout:** the timeout is 60 seconds. The board stays unchanged,
   and the result is discarded. Inference must finish before another step can run.
5. **Port 8000 in use:** stop the other process using that port before starting.
6. **Board changed in another tab:** use one active game tab and reload it to
   see the current state.

Keep the app local. It has no authentication or separate sessions for different
users. See [SECURITY.md](SECURITY.md).

## Contributing and licence

Have a look at [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process.
Code in this repository is licensed under [MIT](LICENSE).

Model weights are downloaded separately. Strands Decider, the checkpoints linked
above, the [Qwen base model](https://huggingface.co/Qwen/Qwen3.5-2B-Base), and the
[Gemma base model](https://huggingface.co/google/gemma-4-E2B-it) retain their own
licences and notices.
