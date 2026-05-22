"""Apply Elo updates and persist rating history."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session

from backend.app.models import Bot, Match, MatchResult, RatingHistory, User
from chesslab.tournament.elo import result_to_scores, update_ratings


def apply_match_result(session: Session, match: Match) -> None:
    """Update Elo ratings of the participants of `match` and persist history.

    Called when a finished match transitions from `running` to `finished`.
    No-op if the result is unfinished.
    """
    if match.result == MatchResult.unfinished:
        return

    white_user = session.get(User, match.white_user_id) if match.white_user_id else None
    black_user = session.get(User, match.black_user_id) if match.black_user_id else None
    white_bot = session.get(Bot, match.white_bot_id) if match.white_bot_id else None
    black_bot = session.get(Bot, match.black_bot_id) if match.black_bot_id else None

    white_rating, black_rating = _rating_of(white_user, white_bot), _rating_of(black_user, black_bot)
    if white_rating is None or black_rating is None:
        return

    w_score, _ = result_to_scores(match.result.value)
    new_white, new_black = update_ratings(white_rating, black_rating, w_score)

    if white_user is not None:
        _record_history(session, match, white_rating, new_white, user=white_user)
        white_user.elo = new_white
    if white_bot is not None:
        _record_history(session, match, white_rating, new_white, bot=white_bot)
        white_bot.elo = new_white
    if black_user is not None:
        _record_history(session, match, black_rating, new_black, user=black_user)
        black_user.elo = new_black
    if black_bot is not None:
        _record_history(session, match, black_rating, new_black, bot=black_bot)
        black_bot.elo = new_black

    match.finished_at = dt.datetime.now(dt.UTC)
    session.add(match)
    session.commit()


def _rating_of(user: User | None, bot: Bot | None) -> float | None:
    if bot is not None:
        return bot.elo
    if user is not None:
        return user.elo
    return None


def _record_history(
    session: Session,
    match: Match,
    before: float,
    after: float,
    *,
    user: User | None = None,
    bot: Bot | None = None,
) -> None:
    if match.id is None:
        return
    entry = RatingHistory(
        bot_id=bot.id if bot is not None else None,
        user_id=user.id if user is not None else None,
        match_id=match.id,
        rating_before=before,
        rating_after=after,
    )
    session.add(entry)
