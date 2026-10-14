import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import create_app
from decider import MODEL_OPTIONS


class TestPlayer:
    """An explicit test double, never selectable by the application."""

    __test__ = False
    model_id = "test-only"
    device = "cpu"

    def __init__(self):
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.fail = False

    def load(self):
        pass

    def unload(self):
        pass

    def choose(self, observation):
        self.calls += 1
        self.started.set()
        assert self.release.wait(5), "test failed to release inference"
        if self.fail:
            raise RuntimeError("test model error")
        return {
            "choice": "RIGHT",
            "confidence": 0.6,
            "probabilities": {"UP": 0.1, "RIGHT": 0.7, "DOWN": 0.1, "LEFT": 0.1},
            "latency_ms": 10,
            "input_tokens": 120,
        }


def wait_ready(client):
    for _ in range(200):
        if client.get("/api/status").json()["status"] != "loading":
            return
        time.sleep(0.005)
    pytest.fail("model did not finish loading")


def step_body(client):
    game = client.get("/api/game").json()["game"]
    return {"game_id": game["id"], "moves": game["moves"]}


def test_one_model_call_causes_exactly_one_move_and_rejects_replay():
    player = TestPlayer()
    with TestClient(create_app(player)) as client:
        wait_ready(client)
        body = step_body(client)
        result = client.post("/api/step", json=body)
        assert result.status_code == 200
        assert result.json()["game"]["snake"][0] == [6, 6]
        assert result.json()["game"]["moves"] == 1
        assert result.json()["decision"]["choice"] == "RIGHT"
        assert client.post("/api/step", json=body).status_code == 409
        assert player.calls == 1


def test_reset_discards_pending_decision_and_overlap_is_rejected():
    player = TestPlayer()
    player.release.clear()
    with TestClient(create_app(player)) as client, ThreadPoolExecutor() as requests:
        wait_ready(client)
        body = step_body(client)
        pending = requests.submit(client.post, "/api/step", json=body)
        try:
            assert player.started.wait(2)
            assert client.post("/api/step", json=body).status_code == 409
            reset = client.post("/api/reset").json()
            assert reset["game"]["id"] != body["game_id"]
        finally:
            player.release.set()
        assert pending.result().status_code == 409
        assert client.get("/api/game").json() == reset
        assert player.calls == 1


def test_model_failure_leaves_board_unchanged_and_allows_retry():
    player = TestPlayer()
    with TestClient(create_app(player)) as client:
        wait_ready(client)
        before = client.get("/api/game").json()
        player.fail = True
        assert client.post("/api/step", json=step_body(client)).status_code == 502
        assert client.get("/api/game").json() == before
        assert not client.get("/api/status").json()["busy"]
        player.fail = False
        assert client.post("/api/step", json=step_body(client)).status_code == 200


def test_timeout_does_not_move_or_queue_more_inference():
    player = TestPlayer()
    player.release.clear()
    with TestClient(create_app(player, decision_timeout=0.03)) as client:
        wait_ready(client)
        body = step_body(client)
        try:
            assert client.post("/api/step", json=body).status_code == 504
            assert client.get("/api/game").json()["game"]["moves"] == 0
            assert client.get("/api/status").json()["busy"]
            assert client.post("/api/step", json=body).status_code == 409
            assert player.calls == 1
        finally:
            player.release.set()
        for _ in range(100):
            if not client.get("/api/status").json()["busy"]:
                break
            time.sleep(0.005)
        assert not client.get("/api/status").json()["busy"]
        assert client.get("/api/game").json()["game"]["moves"] == 0


def test_load_failure_is_visible_and_does_not_substitute_a_bot():
    class FailingPlayer(TestPlayer):
        def load(self):
            raise RuntimeError("test download error")

    player = FailingPlayer()
    with TestClient(create_app(player)) as client:
        wait_ready(client)
        status = client.get("/api/status").json()
        assert status["status"] == "error"
        assert status["error"]
        assert client.post("/api/step", json=step_body(client)).status_code == 503
        assert player.calls == 0


def test_cross_origin_model_calls_and_bad_hosts_are_blocked():
    with TestClient(create_app(TestPlayer())) as client:
        assert (
            client.post("/api/reset", headers={"Origin": "https://example.com"}).status_code == 403
        )
        assert client.get("/api/status", headers={"Host": "example.com"}).status_code == 400
        assert client.post("/api/step", json={}).status_code == 422


def test_model_switch_resets_board_and_blocks_steps_and_overlapping_loads():
    class SwitchingPlayer(TestPlayer):
        def __init__(self):
            super().__init__()
            self.loaded = []
            self.load_started = threading.Event()
            self.load_release = threading.Event()
            self.load_release.set()

        def load(self):
            self.loaded.append(self.model_id)
            self.load_started.set()
            assert self.load_release.wait(5)

    player = SwitchingPlayer()
    with TestClient(create_app(player)) as client:
        wait_ready(client)
        assert client.post("/api/step", json=step_body(client)).status_code == 200
        previous = step_body(client)
        player.load_release.clear()
        player.load_started.clear()
        target = MODEL_OPTIONS[1]["id"]
        try:
            switched = client.post("/api/model", json={"model": target})
            assert switched.status_code == 202
            assert player.load_started.wait(2)
            snapshot = switched.json()
            assert snapshot["game"]["id"] != previous["game_id"]
            assert snapshot["game"]["moves"] == 0
            assert snapshot["decision"] is None
            status = client.get("/api/status").json()
            assert status["status"] == "loading"
            assert status["model"] == target
            assert status["game_id"] == snapshot["game"]["id"]
            assert client.post("/api/step", json=step_body(client)).status_code == 503
            assert client.post("/api/model", json={"model": target}).status_code == 409
        finally:
            player.load_release.set()
        wait_ready(client)
        assert player.loaded == ["test-only", target]
        assert client.post("/api/step", json=previous).status_code == 409
        assert client.post("/api/step", json=step_body(client)).status_code == 200
        before = client.get("/api/game").json()
        assert client.post("/api/model", json={"model": target}).json() == before
        assert player.loaded == ["test-only", target]


def test_switch_rejected_during_timed_out_inference_without_resetting_board():
    player = TestPlayer()
    player.release.clear()
    with TestClient(create_app(player, decision_timeout=0.03)) as client:
        wait_ready(client)
        before = client.get("/api/game").json()
        try:
            assert client.post("/api/step", json=step_body(client)).status_code == 504
            result = client.post("/api/model", json={"model": MODEL_OPTIONS[1]["id"]})
            assert result.status_code == 409
            assert client.get("/api/game").json() == before
            assert player.model_id == "test-only"
        finally:
            player.release.set()


def test_failed_switch_can_retry_or_return_to_previous_model():
    target = MODEL_OPTIONS[2]["id"]

    class FailingSwitch(TestPlayer):
        should_fail = True
        unloaded = 0

        def load(self):
            if self.model_id == target and self.should_fail:
                raise RuntimeError("test failed download")

        def unload(self):
            self.unloaded += 1

    player = FailingSwitch()
    with TestClient(create_app(player)) as client:
        wait_ready(client)
        assert client.post("/api/model", json={"model": target}).status_code == 202
        wait_ready(client)
        assert client.get("/api/status").json()["status"] == "error"
        assert player.unloaded == 1
        assert client.post("/api/step", json=step_body(client)).status_code == 503
        assert player.calls == 0
        player.should_fail = False
        assert client.post("/api/model", json={"model": target}).status_code == 202
        wait_ready(client)
        assert client.get("/api/status").json()["status"] == "ready"
        assert client.post("/api/step", json=step_body(client)).status_code == 200
        assert client.post("/api/model", json={"model": "test-only"}).status_code == 202
        wait_ready(client)
        assert client.get("/api/status").json()["model"] == "test-only"


def test_model_catalogue_rejects_arbitrary_paths_ids_and_cross_origin_switches():
    with TestClient(create_app(TestPlayer())) as client:
        wait_ready(client)
        status = client.get("/api/status").json()
        assert {item["id"] for item in status["models"]} == {
            *(item["id"] for item in MODEL_OPTIONS),
            "test-only",
        }
        before = client.get("/api/game").json()
        for model_id in ("/tmp/untrusted", "another/model", ""):
            assert client.post("/api/model", json={"model": model_id}).status_code == 422
        assert (
            client.post(
                "/api/model",
                json={"model": MODEL_OPTIONS[0]["id"]},
                headers={"Origin": "https://example.com"},
            ).status_code
            == 403
        )
        assert client.get("/api/game").json() == before
