"""Bounded, reproducible gameplay checks with the real local model (not unit tests)."""

import argparse
import json
from pathlib import Path
from random import Random
from statistics import median

from decider import Decider
from game import Game


def play(player: Decider, game: Game, limit: int) -> dict:
    initial_score = game.score
    seen = set()
    repeated_states = 0
    foodless_moves = 0
    longest_foodless_run = 0
    steps = []
    for _ in range(limit):
        key = (tuple(game.snake), game.food)
        repeated_states += key in seen
        seen.add(key)
        score = game.score
        decision = player.choose(game.observation())
        game.advance(decision["choice"])
        foodless_moves = foodless_moves + 1 if game.score == score else 0
        longest_foodless_run = max(longest_foodless_run, foodless_moves)
        steps.append({"game": game.snapshot(), "decision": decision})
        if len(steps) % 30 == 0 or game.status != "active":
            print(f"  {len(steps)} moves: score {game.score}, {game.status}", flush=True)
        if game.status != "active":
            break
    return {
        "moves": len(steps),
        "food_eaten": game.score - initial_score,
        "status": game.status,
        "repeated_states": repeated_states,
        "longest_foodless_run": longest_foodless_run,
        "median_latency_ms": median(step["decision"]["latency_ms"] for step in steps),
        "max_input_tokens": max(step["decision"]["input_tokens"] for step in steps),
        "steps": steps,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 19, 42])
    parser.add_argument("--moves", type=int, default=120)
    parser.add_argument("--snapshot", type=Path, help="Optional saved /api/game JSON to replay.")
    parser.add_argument("--output", type=Path, default=Path("runtime/evaluation.json"))
    args = parser.parse_args()
    if not 1 <= args.moves <= 1000:
        parser.error("--moves must be between 1 and 1000")

    player = Decider()
    player.load()
    cases = [(f"seed-{seed}", Game.new(seed=seed)) for seed in args.seeds]
    if args.snapshot:
        data = json.loads(args.snapshot.read_text())
        data = data.get("game", data)
        cases.append(
            (
                "saved-board",
                Game(
                    size=data["size"],
                    snake=[tuple(cell) for cell in data["snake"]],
                    food=tuple(data["food"]),
                    direction=data["direction"],
                    score=data["score"],
                    moves=data["moves"],
                    random=Random(7),
                ),
            )
        )
    results = {
        "model": player.model_id,
        "device": player.device,
        "move_limit": args.moves,
        "cases": {},
    }
    for name, game in cases:
        print(name, flush=True)
        result = play(player, game, args.moves)
        results["cases"][name] = result
        print(
            json.dumps({key: value for key, value in result.items() if key != "steps"}), flush=True
        )
        # Save after each case so interrupted evaluations still leave useful evidence.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
