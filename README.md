# Kyoki

Kyoki is a two-player browser card game with fast rounds, simple rules, and a dramatic reveal. It is basically a japan-themed version of the original game "Coup de Grace", also known as "King, Knight, Assassin".

It runs on FastAPI with WebSocket matchmaking and a static front end.

## Gameplay

- Each player has one Empress, two Samurai, and two Ninja cards.
- Reveal is simultaneous.
- Matchups:
  - Empress defeats Samurai
  - Samurai defeats Ninja
  - Ninja defeats Empress
- A match ends when the Empress is defeated.

## Modes

- Arena: queue up and get matched with a random opponent.
- VS Battle: generate a 6-letter code and play with a friend.

## Tech Stack

- FastAPI + Uvicorn for the server
- WebSockets for realtime play
- Jinja2 templates + vanilla HTML/CSS/JS

## Operational Note

Kyoki runs with a single FastAPI worker in production. Matchmaking and VS battle
codes are kept in memory, as this is a small toy project rather than a
commercial game. A single worker keeps the behavior predictable without adding
external state.

## Local Development

This project uses Docker by default.

```bash
make setup-dev
make run-dev
```

Then open `http://localhost:1337`.

The provided `docker-compose.yml` expects a Docker network named `breathnet`.
If you do not have it, create one or adjust the compose file:

```bash
docker network create breathnet
```

## Project Layout

- `app/main.py`: FastAPI app and game logic
- `app/templates/index.html`: UI and client logic
- `app/static/`: styles, images, and celebration effects

## License

MIT. See `LICENSE`.