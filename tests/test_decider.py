import math
import weakref
from types import SimpleNamespace

import pytest

from decider import Decider, validate_answer
from game import DIRECTIONS


def answer():
    return {
        "type": "choice",
        "choice": "RIGHT",
        "confidence": 0.6,
        "probabilities": {"UP": 0.1, "RIGHT": 0.7, "DOWN": 0.1, "LEFT": 0.1},
    }


@pytest.mark.parametrize(
    "change",
    [
        {"choice": "NORTH"},
        {"type": "score"},
        {"confidence": math.nan},
        {"confidence": True},
        {"probabilities": {"RIGHT": 1}},
        {"probabilities": dict.fromkeys(DIRECTIONS, 0.9)},
        {"probabilities": {"UP": -0.1, "RIGHT": 0.9, "DOWN": 0.1, "LEFT": 0.1}},
    ],
)
def test_rejects_invalid_answers(change):
    with pytest.raises(ValueError):
        validate_answer(answer() | change)


def test_adapter_uses_real_choice_schema_and_preserves_model_choice():
    calls = []

    class Engine:
        def ask(self, state, questions):
            calls.append((state, questions))
            return SimpleNamespace(
                answers={"move": SimpleNamespace(model_dump=answer)},
                usage=SimpleNamespace(input_tokens=120),
            )

    player = Decider()
    player.engine = Engine()
    result = player.choose("the board")
    assert calls[0][0] == "the board"
    assert calls[0][1]["move"].type == "choice"
    assert set(calls[0][1]["move"].criteria) == set(DIRECTIONS)
    assert result["choice"] == "RIGHT"
    assert result["probabilities"] == answer()["probabilities"]
    assert result["input_tokens"] == 120
    assert result["latency_ms"] >= 0


def test_reload_releases_previous_engine_before_loading_next_weights(monkeypatch):
    from strands_decider import infer, modeling

    class Engine:
        def __init__(self, model, config):
            self.model = model

    player = Decider()
    player.device = "cpu"
    player.engine = Engine(object(), None)
    previous = weakref.ref(player.engine)
    calls = []

    def load(model_id):
        assert previous() is None, "the old engine must be released before allocating new weights"
        calls.append(model_id)
        return object()

    monkeypatch.setattr(modeling.StrandsDeciderModel, "load", load)
    monkeypatch.setattr(infer, "SystemOneEngine", Engine)
    player.model_id = "new-test-model"
    player.load()
    assert calls == ["new-test-model"]
    assert player.engine is not None
    player.unload()
    assert player.engine is None
