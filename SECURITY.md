# Security

The app is intended for local use. It listens on `127.0.0.1`, checks request hosts
and browser POST origins, and runs one shared game. It has no authentication,
rate limits, or separate sessions for different users.

Public hosting would need those controls. Keep the app on the local address
and avoid exposing it through a public tunnel.

Inference runs locally. The first use of each model downloads files from Hugging Face,
and dependency sources are recorded in `uv.lock`. The browser can select only the
built-in models and the server's `DECIDER_MODEL` override. Use trusted checkpoints and
model directories. No API keys or cloud credentials are needed. Keep weights,
logs, and runtime reports out of Git.

## Reporting a problem

Use **Security → Report a vulnerability** if that private reporting option is
available in the published repository. Otherwise, open an issue asking the
maintainer for a private contact. Include sensitive details only in the private
report.

Please include the affected commit, environment, steps to reproduce the problem,
and expected impact. Do not post credentials, tokens, or private logs publicly.
Fixes target the current main branch.
