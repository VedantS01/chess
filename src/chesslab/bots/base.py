"""Bot framework: abstract base class + name registry.

Users implementing a bot subclass `Bot`, override `choose_move`, and register
their bot via `register_bot("name", cls)` or the `@register` decorator. The
registry is consulted by the CLI, the sandbox runner, the backend, and the
tournament runner — write your bot once, run it everywhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

import chess

from chesslab.engine import Game


class Bot(ABC):
    """Abstract base for chess bots.

    Subclasses must implement :meth:`choose_move`. They may override
    :meth:`reset` (called once before a new game) and :meth:`close` (called when
    a session ends, used to release resources like Stockfish subprocesses).
    """

    name: ClassVar[str] = "bot"

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    @abstractmethod
    def choose_move(self, game: Game, time_limit_s: float | None = None) -> chess.Move:
        """Return a legal move for `game.turn`. Must not mutate `game`."""

    def reset(self) -> None:  # noqa: B027  (intentional empty default; override if needed)
        """Hook called before a new game starts. Override if needed."""

    def close(self) -> None:  # noqa: B027  (intentional empty default; override if needed)
        """Hook called when the bot is no longer needed. Override if needed."""

    def __enter__(self) -> Bot:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


BOT_REGISTRY: dict[str, type[Bot]] = {}


def register_bot(name: str, cls: type[Bot]) -> type[Bot]:
    """Register `cls` under `name`. Re-registering the same name is an error."""
    if name in BOT_REGISTRY and BOT_REGISTRY[name] is not cls:
        raise ValueError(f"bot name already registered: {name}")
    BOT_REGISTRY[name] = cls
    return cls


def register(name: str) -> Callable[[type[Bot]], type[Bot]]:
    def deco(cls: type[Bot]) -> type[Bot]:
        return register_bot(name, cls)

    return deco


_LAZY_LOADERS: dict[str, Callable[[], None]] = {}


def register_lazy(name: str, loader: Callable[[], None]) -> None:
    """Register a deferred loader. Called the first time `get_bot(name)` is requested."""
    _LAZY_LOADERS[name] = loader


def get_bot(name: str, **kwargs: object) -> Bot:
    """Construct a bot by registered name. Raises `KeyError` if unknown."""
    if name not in BOT_REGISTRY and name in _LAZY_LOADERS:
        _LAZY_LOADERS.pop(name)()
    if name not in BOT_REGISTRY:
        raise KeyError(f"unknown bot: {name!r}. Known: {sorted(BOT_REGISTRY)}")
    return BOT_REGISTRY[name](**kwargs)


def list_bots() -> list[str]:
    return sorted(set(BOT_REGISTRY) | set(_LAZY_LOADERS))
