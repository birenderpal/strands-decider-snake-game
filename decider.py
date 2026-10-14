"""The only place that talks to Strands Decider. No fallback player."""

import gc
import math
import os
import sys
from pathlib import Path
from time import perf_counter

from game import DIRECTIONS

DEFAULT_MODEL = "StrandsAgents/strands-decider-2B-hobson-v21"
MODEL_OPTIONS = (
    {
        "id": DEFAULT_MODEL,
        "label": "Hobson v21 · 2B",
        "note": "The original player. About 4.3 GB of model files on first use.",
    },
    {
        "id": "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610",
        "label": "Qwen 3.5 v1 · 2B",
        "note": "Shares the Hobson v21 base weights. Downloads a separate adapter on first use.",
    },
    {
        "id": "StrandsAgents/strands-decider-E2B-gemma4-v1-2610",
        "label": "Gemma 4 v1 · E2B",
        "note": "About 10 GB of base weights, plus its adapter. Needs more RAM than Qwen 2B.",
    },
)
INSTRUCTIONS = (
    "Choose a move that avoids a crash and gets closer to the food. "
    "A crash ends the game. Use the full board and recent moves to avoid getting trapped. "
    "If circling without eating, try a different safe route, even if it temporarily "
    "increases distance. Revisiting a square is allowed when needed to reach food. "
    "Which direction should the snake move?"
)


def validate_answer(answer: dict) -> dict:
    """Reject malformed output instead of silently inventing a replacement move."""
    probabilities = answer.get("probabilities", {})
    confidence = answer.get("confidence")
    if (
        answer.get("type") != "choice"
        or answer.get("choice") not in DIRECTIONS
        or not isinstance(probabilities, dict)
        or set(probabilities) != set(DIRECTIONS)
        or not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Strands Decider returned an invalid choice answer.")
    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in probabilities.values()
    ) or not math.isclose(sum(probabilities.values()), 1, abs_tol=0.01):
        raise ValueError("Strands Decider returned invalid probabilities.")
    return {
        "choice": answer["choice"],
        "confidence": confidence,
        "probabilities": probabilities,
    }


class Decider:
    def __init__(self) -> None:
        self.model_id = os.getenv("DECIDER_MODEL", DEFAULT_MODEL)
        self.device = os.getenv("DECIDER_DEVICE", "auto")
        self.engine = None

    def unload(self) -> None:
        """Release the previous model before another load, on the same worker."""
        self.engine = None
        gc.collect()
        # Avoid importing PyTorch just to close an app whose initial load failed.
        torch = sys.modules.get("torch")
        if torch is not None:
            if self.device == "mps" and torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()

    def load(self) -> None:
        self.unload()
        # Imports are lazy so the web page and rule tests do not wait for PyTorch.
        # Keep downloaded weights local and ignored; respect an explicit HF_HOME.
        os.environ.setdefault("HF_HOME", str(Path(__file__).parent / ".cache" / "huggingface"))
        import torch
        from strands_decider.infer import EngineConfig, SystemOneEngine
        from strands_decider.modeling import StrandsDeciderModel

        if self.device == "auto":
            self.device = (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
        if self.device not in {"cpu", "mps", "cuda"}:
            raise ValueError("DECIDER_DEVICE must be auto, cpu, mps, or cuda.")
        model = StrandsDeciderModel.load(self.model_id)
        self.engine = SystemOneEngine(
            model,
            # There is only one question per board; no prefix needs to be shared.
            EngineConfig(device=self.device, use_prefix_cache=False, model_name=self.model_id),
        )

    def choose(self, observation: str) -> dict:
        from strands_decider.schema import ChoiceQuestion

        if self.engine is None:
            raise RuntimeError("Strands Decider has not loaded yet.")
        started = perf_counter()
        response = self.engine.ask(
            observation,
            {
                "move": ChoiceQuestion(
                    instructions=INSTRUCTIONS,
                    criteria={direction: f"Move {direction.lower()}." for direction in DIRECTIONS},
                )
            },
        )
        result = validate_answer(response.answers["move"].model_dump())
        result["latency_ms"] = round((perf_counter() - started) * 1000)
        result["input_tokens"] = response.usage.input_tokens
        return result
