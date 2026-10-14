# Gameplay experiments

These results come from four comparisons, with one run per version in each
comparison. They help explain the observation format but do not establish
how reliably the model plays across other boards or devices.

These measurements predate the initial repository snapshot. The earlier
implementations, saved board, and raw reports are not included. Reproducing
the original comparison requires those local development files.

On 13 October 2026, development versions v0.1.0 and v0.2.0 were compared using
`StrandsAgents/strands-decider-2B-hobson-v21` on Apple MPS. Each case had a limit
of 120 moves. Both versions used the same model and four direction choices.
v0.2.0 added the full snake layout and recent move and visit history to the
collision and distance facts supplied by v0.1.0.

Fresh games used the same seed across versions. Different moves leave different
empty squares, so later food positions can differ even with the same seed.

| Starting board | v0.1.0: food collected and result | v0.2.0: food collected and result |
| --- | --- | --- |
| Fresh, seed 7 | 8; active after 120 moves | 9; active after 120 moves |
| Fresh, seed 19 | 4; active after 120 moves | 10; active after 120 moves |
| Fresh, seed 42 | 7; active after 120 moves | 15; collision at move 118 |
| Saved score-14 loop | 0; 96 repeated states in 120 moves | 6; collision after 99 moves, score 20 |

None of the updated runs repeated a complete board state within its move limit.
Median decision times ranged from 138 to 139 ms for v0.1.0 and from 325 to 588 ms
for v0.2.0 as observations grew. A nearly full 12 × 12 board needed
1,304 tokens in one capacity check, below the model's 4,096-token limit. That
sample does not prove the maximum token count for every board.

Both versions started the saved-board replay with empty history. The added
context helped the model escape that loop and collect more food, but collisions
still occurred.

## Run a new measurement

Stop the game server first to avoid loading a second model, then run:

```bash
uv run --locked python evaluate.py --seeds 7 19 42 --moves 120 \
  --output runtime/my-evaluation.json
```

The evaluator records the model ID, device, move limit, a summary for each case,
and every resulting board and decision. Git ignores these reports.

The report uses the following measures:

1. **Food eaten:** additional food collected during the case.
2. **Repeated states:** a repeat of the same ordered snake layout and food
   position. This excludes prompt history and random generator state.
3. **Longest stretch without food:** consecutive moves without eating during
   the case, including a collision move.
4. **Median latency:** time taken by the model call, excluding the browser's
   pause between moves.
5. **Status:** `active` means the run reached its move limit; it does not mean
   the snake filled the board.

Use `--snapshot PATH` to add a saved `/api/game` board to the evaluation. The
replay starts with empty history and seed 7 for later food. It does not restore
the original random generator or continue the original session exactly.

## Comparing results

Keep the observation format, rules, seeds, hardware, and move limit fixed.
Run several cases before making performance claims. Changing model families
changes more than parameter count.

When sharing results, include the repository commit, model checkpoint and
revision, hardware, device, software versions, seeds, and move limit. State
whether the timings include the first inference call. Dependency versions are
locked, but upstream model IDs are not pinned to immutable revisions.
