"""Run with `uv run python app.py`, then open http://127.0.0.1:8000."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from decider import MODEL_OPTIONS, Decider
from game import Game

logger = logging.getLogger("uvicorn.error")
STATIC = Path(__file__).parent / "static"


class StepRequest(BaseModel):
    game_id: str = Field(min_length=1, max_length=64)
    moves: int = Field(ge=0)


class ModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=256)


def create_app(player=None, *, decision_timeout: float = 60) -> FastAPI:
    player = player or Decider()
    models = list(MODEL_OPTIONS)
    # Only the server's trusted startup override may add a custom checkpoint.
    # Browser requests cannot supply arbitrary Hub IDs or local file paths.
    if player.model_id not in {model["id"] for model in models}:
        models.append(
            {"id": player.model_id, "label": "Startup model", "note": "Set through DECIDER_MODEL."}
        )
    game = Game.new()
    last_decision = None
    model_status = "loading"
    model_error = None
    busy = False
    loading = None

    # Loading, unloading and inference share one worker; concurrent MPS calls can crash Metal.
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="decider")

    async def load_model():
        nonlocal model_status, model_error
        try:
            await asyncio.get_running_loop().run_in_executor(worker, player.load)
            model_status = "ready"
        except Exception:
            logger.exception("Could not load Strands Decider")
            model_error = (
                "Could not load Strands Decider. Check the terminal and your internet "
                "connection, then retry or select another model."
            )
        if model_error:
            # Clean up after the exception frame has released partially loaded weights.
            await asyncio.get_running_loop().run_in_executor(worker, player.unload)
            model_status = "error"

    @asynccontextmanager
    async def lifespan(app):
        nonlocal loading
        loading = asyncio.create_task(load_model())
        yield
        await loading
        await asyncio.get_running_loop().run_in_executor(worker, player.unload)
        worker.shutdown(wait=True)

    app = FastAPI(title="Snake · Strands Decider", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # A random website must not be able to trigger local model work.
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and origin != str(request.base_url).rstrip("/"):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Use the game in its own browser tab."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def snapshot():
        return {"game": game.snapshot(), "decision": last_decision}

    @app.get("/api/status")
    async def status():
        return {
            "status": model_status,
            "model": player.model_id,
            "device": player.device,
            "error": model_error,
            "busy": busy,
            "models": models,
            "game_id": game.id,
        }

    @app.post("/api/model", status_code=202)
    async def select_model(request: ModelRequest):
        nonlocal game, last_decision, model_status, model_error, loading
        if request.model not in {model["id"] for model in models}:
            raise HTTPException(422, "Select one of the available models.")
        if model_status == "loading" or busy:
            raise HTTPException(409, "Wait for the current model operation to finish.")
        if request.model == player.model_id and model_status == "ready":
            return snapshot()

        # Reset synchronously before loading so every old board request becomes stale.
        game = Game.new()
        last_decision = None
        player.model_id = request.model
        model_status = "loading"
        model_error = None
        loading = asyncio.create_task(load_model())
        return snapshot()

    @app.get("/api/game")
    async def current():
        return snapshot()

    @app.post("/api/reset")
    async def reset():
        nonlocal game, last_decision
        game = Game.new()
        last_decision = None
        return snapshot()

    @app.post("/api/step")
    async def step(request: StepRequest):
        nonlocal busy, last_decision
        if model_status != "ready":
            raise HTTPException(503, model_error or "The model is still loading.")
        if busy:
            raise HTTPException(409, "A decision is already in progress.")
        if request.game_id != game.id or request.moves != game.moves:
            raise HTTPException(409, "The board changed. Refresh the game state.")
        if game.status != "active":
            raise HTTPException(409, "This game has ended. Reset to play again.")

        busy = True
        observation = game.observation()
        future = asyncio.get_running_loop().run_in_executor(worker, player.choose, observation)

        def release_worker(completed):
            nonlocal busy
            busy = False
            # Retrieve late failures after a timeout, without applying late moves.
            if not completed.cancelled() and completed.exception():
                logger.error("Discarded inference failed after timeout: %s", completed.exception())

        try:
            # A timeout cannot stop GPU work. Shield it and keep the worker busy until
            # it actually finishes, so repeated clicks never queue more inference.
            decision = await asyncio.wait_for(asyncio.shield(future), timeout=decision_timeout)
            if request.game_id != game.id:
                raise HTTPException(409, "The game was reset; the old decision was discarded.")
            game.advance(decision["choice"])
            last_decision = {**decision, "move": game.moves, "observation": observation}
            return snapshot()
        except TimeoutError as exc:
            raise HTTPException(504, "The model took too long. The board has not moved.") from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Strands Decider failed to choose a move")
            raise HTTPException(
                502, "Strands Decider could not make a move. Check the terminal, then retry."
            ) from exc
        finally:
            if future.done():
                busy = False
            else:
                future.add_done_callback(release_worker)

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")
    return app


if __name__ == "__main__":
    import uvicorn

    # One local session, one model in memory. Do not add reload or multiple workers.
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
