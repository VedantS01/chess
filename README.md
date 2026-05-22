# chesslab

Chess engine wrapper, bot framework, RL training, and an online platform — all built on top of [`python-chess`](https://github.com/niklasf/python-chess) so the rules engine is trustworthy and battle-tested.

- **Offline**: a CLI for pass-and-play, human-vs-bot, bot-vs-bot, vs Stockfish, plus a round-robin tournament runner.
- **Bot framework**: subclass `Bot`, register your name, get picked up everywhere — CLI, sandboxed online matches, tournament runner.
- **RL framework**: PyTorch actor-critic with self-play, legal-move masking, PPO-style update, checkpointing. `MLBot` plays from a checkpoint.
- **Online platform**: FastAPI backend + Next.js frontend on Vercel. GitHub OAuth, upload your bot as a `.zip`, play online (h2h, vs-bot, bot-vs-bot spectate), global ELO ladder.
- **Sandbox**: each user-bot match runs in a per-match Docker container (`--network=none --read-only --cap-drop=ALL --pids-limit=64 --cpus=1 --memory=512m`).

## Repo layout

```
src/chesslab/         shared package (engine, bots, RL, tournament, sandbox shim, CLI)
backend/              FastAPI app + match orchestrator + tests
frontend/             Next.js app (Vercel target)
Dockerfile.backend    backend image
Dockerfile.runner     untrusted-bot sandbox image
docker-compose.yml    local dev stack (postgres + backend + runner-builder + frontend)
.github/workflows/    CI + 3 release pipelines
```

## Offline quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[rl,dev]"
chesslab list-bots
chesslab play --white human --black random           # pass-and-play vs random
chesslab play --white human --black heuristic:max_depth=3
chesslab match --white heuristic --black random --games 10 --pgn /tmp/m.pgn
chesslab tournament --bots random,heuristic --rounds 4
```

Stockfish too (apt install `stockfish`):

```bash
chesslab match --white stockfish:depth=10 --black heuristic --games 1
```

## Write your own bot

```python
# my_bot.py
from chesslab.bots.base import Bot, register

@register("aggressive")
class MyBot(Bot):
    name = "aggressive"

    def choose_move(self, game, time_limit_s=None):
        # game.board is a chess.Board; return any chess.Move from game.legal_moves().
        for move in game.legal_moves():
            if game.board.is_capture(move):
                return move
        return next(iter(game.legal_moves()))
```

Wire it up:

```bash
PYTHONPATH=. chesslab match --white aggressive --black random --games 5
```

For the online sandbox: zip a directory with `bot.py` at the root that exposes a top-level `BOT` (either a `Bot` instance or a zero-arg factory). Upload through the frontend or POST to `/api/bots`.

## Train an RL bot

```bash
chesslab train --steps 2000 --checkpoint /tmp/ac.pt
chesslab match --white "ml:checkpoint=/tmp/ac.pt" --black random --games 5
```

The default actor-critic is small enough to train on CPU. See `src/chesslab/rl/trainer.py` for hyperparameters.

## Online platform — local dev

```bash
docker compose up --build
# backend  -> http://localhost:8000  (FastAPI + websocket)
# frontend -> http://localhost:3000  (Next.js)
# postgres -> localhost:5432         (chesslab/chesslab/chesslab)
```

The compose stack mounts your `docker.sock` into the backend so it can spawn `chesslab-runner` sandboxes for each match. Set `NEXTAUTH_SECRET` to something ≥32 bytes in production.

### Dev-mode auth

For local testing you can mint a backend JWT without going through GitHub:

```bash
curl -X POST http://localhost:8000/api/auth/dev-token \
  -H 'Content-Type: application/json' \
  -d '{"github_id": 1, "login": "alice"}'
```

This endpoint is only available when `CHESSLAB_DEV_AUTH=1`.

## Self-hosting

The frontend ships to Vercel; the backend ships as a Docker image to GHCR. **Vercel cannot host the backend** — it needs long-lived WebSockets and access to a Docker socket for sandboxing.

```bash
docker run -d --name chesslab-backend \
  -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v chesslab-data:/data \
  -e NEXTAUTH_SECRET=$(openssl rand -base64 48) \
  -e CHESSLAB_CORS_ORIGINS=https://your-frontend.vercel.app \
  -e CHESSLAB_DATABASE_URL=postgresql+psycopg://... \
  -e CHESSLAB_RUNNER_IMAGE=ghcr.io/<owner>/chesslab-runner:latest \
  ghcr.io/<owner>/chesslab-backend:latest
```

Pull the runner image too so the backend can `docker run` it:

```bash
docker pull ghcr.io/<owner>/chesslab-runner:latest
```

## Required GitHub repo secrets

CI passes without any secrets configured (the deploy job self-gates). To enable each pipeline:

| pipeline                  | secret                              |
|--------------------------|-------------------------------------|
| Vercel deploy             | `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` |
| Runtime GitHub OAuth      | configure NextAuth env on Vercel: `GITHUB_OAUTH_ID`, `GITHUB_OAUTH_SECRET`, `NEXTAUTH_SECRET` |
| GHCR images               | (uses `GITHUB_TOKEN` automatically) |
| Python wheel release      | (uses `GITHUB_TOKEN` automatically) |

## Testing

```bash
ruff check .
pytest -q                # Python: engine + bots + RL + backend + WS = 79+ tests
cd frontend && pnpm test # Frontend: api client, ws URL, page render = 7 tests
```

## Architecture sketch

```
Browser ─►  Vercel (Next.js, GitHub OAuth via NextAuth)
                │  ──REST/WS──►  chesslab-backend (Docker, FastAPI + Postgres)
                                       │  spawns
                                       ▼
                           chesslab-runner (Docker, --network=none)
                            └─ loads /bot/bot.py, speaks UCI on stdio
```

The runner image bundles `chesslab` so any `Bot` subclass works inside it — the same code that runs locally runs in the sandbox.

## License

MIT.
