# Changelog

## 0.3.0 - 2026-10-13

1. Initial repository snapshot, with the local development history consolidated
   for public sharing.
2. Added a local Snake game with a plain HTML/CSS/JavaScript UI and a small
   FastAPI backend. Strands Decider chooses every move from the full board and
   bounded recent history.
3. Included Hobson v21 2B, Qwen 3.5 v1 2B, and Gemma 4 v1 E2B. Switching models
   starts a fresh round and releases the previous model before loading the next.
4. Added decision probabilities, confidence, timing, input inspection, and a
   bounded gameplay evaluator. Included an MIT licence, setup and contribution
   guidance, locked dependencies, and GitHub Actions checks.
5. Validation carried forward from the development snapshot: 36 tests passed on
   Python 3.11 and 3.13; Python lint and formatting, JavaScript syntax, and locked
   installation passed. All three models made real decisions on MPS. Browser
   checks covered model switching, autoplay, pause, and desktop and mobile layouts.
6. Limitations: short live runs establish compatibility, not relative gameplay
   quality. CPU and CUDA gameplay remain unmeasured. Tests retain one upstream
   Starlette/httpx deprecation warning. Simultaneous model races remain future work.
