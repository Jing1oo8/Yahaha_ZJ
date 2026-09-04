from __future__ import annotations

import csv
import hashlib
import io
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import (
    Boost,
    Event,
    Exposure,
    Item,
    ModelVersion,
    Operation,
    RecommendationRequest,
    SessionToken,
    User,
    utcnow,
)
from .recommender import runtime
from .security import hash_password, new_session_token, token_hash, verify_password


app = FastAPI(title="YAHAHA Recommendation MVP", version="0.1.0")
Base.metadata.create_all(engine)
SESSION_COOKIE = "yahaha_session"
EXPOSURE_COOLDOWN = timedelta(hours=24)
EVENT_TYPES = {"impression", "click", "like", "favorite", "not_interested"}
DashboardRange = Literal["1h", "24h", "7d", "30d", "all"]
RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


class LoginInput(BaseModel):
    username: str
    password: str


class RegisterInput(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class EventInput(BaseModel):
    event_id: str = Field(min_length=8, max_length=64)
    request_id: str
    item_id: int
    event_type: str
    position: int = Field(ge=0)


class StatusInput(BaseModel):
    status: Literal["online", "offline"]
    reason: str = Field(min_length=3, max_length=300)


class BoostInput(BaseModel):
    item_id: int
    target_user_id: int | None = None
    feed_type: Literal["personalized", "popular", "explore"] | None = None
    reason: str = Field(min_length=3, max_length=300)
    starts_at: datetime
    ends_at: datetime
    priority: int = Field(default=100, ge=1, le=1000)


def current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    session = db.scalar(
        select(SessionToken).where(SessionToken.token_hash == token_hash(session_token))
    )
    if not session or session.expires_at <= utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return user


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "model_available": runtime.available, "model_version": runtime.version}


def create_session(response: Response, db: Session, user: User) -> dict[str, object]:
    token = new_session_token()
    db.add(
        SessionToken(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(hours=12),
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=12 * 60 * 60,
    )
    return {"id": user.id, "username": user.username, "role": user.role}


@app.post("/api/auth/login")
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    username = data.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    return create_session(response, db, user)


@app.post("/api/auth/register", status_code=201)
def register(
    data: RegisterInput,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    username = data.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    user = User(
        username=username,
        password_hash=hash_password(data.password),
        role="user",
        dataset_user_id=None,
    )
    db.add(user)
    db.flush()
    return create_session(response, db, user)


@app.post("/api/auth/logout", status_code=204)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> None:
    if session_token:
        session = db.scalar(
            select(SessionToken).where(SessionToken.token_hash == token_hash(session_token))
        )
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(SESSION_COOKIE)


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)) -> dict[str, object]:
    return {"id": user.id, "username": user.username, "role": user.role}


def feedback_sets(
    db: Session,
    user: User,
    exposure_since: datetime | None = None,
) -> tuple[list[int], set[int], set[int]]:
    positive = list(
        db.scalars(
            select(Event.item_id).where(
                Event.user_id == user.id, Event.event_type.in_(["like", "favorite"])
            )
        )
    )
    negative = set(
        db.scalars(
            select(Event.item_id).where(
                Event.user_id == user.id, Event.event_type == "not_interested"
            )
        )
    )
    exposure_query = select(Exposure.item_id).where(Exposure.user_id == user.id)
    if exposure_since is not None:
        exposure_query = exposure_query.where(Exposure.created_at >= exposure_since)
    exposed = set(db.scalars(exposure_query))
    return positive, negative, exposed


def active_boosts(db: Session, user: User, feed_type: str) -> list[Boost]:
    now = utcnow()
    return list(
        db.scalars(
            select(Boost)
            .join(Item, Item.id == Boost.item_id)
            .where(
                Boost.active.is_(True),
                Boost.starts_at <= now,
                Boost.ends_at > now,
                Item.status == "online",
                or_(Boost.target_user_id.is_(None), Boost.target_user_id == user.id),
                or_(Boost.feed_type.is_(None), Boost.feed_type == feed_type),
            )
            .order_by(Boost.priority.desc(), Boost.id)
        )
    )


def stable_explore_key(user_id: int, item_id: int) -> str:
    return hashlib.sha256(f"{user_id}:{item_id}".encode()).hexdigest()


def deduplicate_ranked(
    entries: list[tuple[int, float, str]],
) -> list[tuple[int, float, str]]:
    seen_ids: set[int] = set()
    unique_entries: list[tuple[int, float, str]] = []
    for entry in entries:
        item_id = entry[0]
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        unique_entries.append(entry)
    return unique_entries


@app.get("/api/feed")
def feed(
    feed_type: Literal["personalized", "popular", "explore"] = Query(alias="type"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    positive, negative, exposed = feedback_sets(
        db,
        user,
        exposure_since=utcnow() - EXPOSURE_COOLDOWN,
    )
    historical = set(runtime.history(user.dataset_user_id))
    seen = historical | exposed | negative
    online_items = list(db.scalars(select(Item).where(Item.status == "online")))
    item_map = {item.id: item for item in online_items}

    if feed_type == "personalized":
        ranked = runtime.personalized(user.dataset_user_id, positive, negative)
    elif feed_type == "popular":
        ranked = [
            (item.id, float(item.source_views), "source_popularity")
            for item in sorted(
                online_items,
                key=lambda item: (-item.source_views, -item.source_likes, item.id),
            )
            if item.id not in seen
        ]
    else:
        exposure_counts = dict(
            db.execute(
                select(Exposure.item_id, func.count(Exposure.id)).group_by(Exposure.item_id)
            ).all()
        )
        explore_items = sorted(
            (item for item in online_items if item.id not in seen),
            key=lambda item: (
                exposure_counts.get(item.id, 0),
                stable_explore_key(user.id, item.id),
            ),
        )
        ranked = [
            (item.id, 1.0 / (1 + exposure_counts.get(item.id, 0)), "low_exposure")
            for item in explore_items
        ]

    filtered = [entry for entry in ranked if entry[0] in item_map and entry[0] not in seen]
    interacted = set(
        db.scalars(
            select(Event.item_id).where(
                Event.user_id == user.id,
                Event.event_type.in_(["click", "like", "favorite", "not_interested"]),
            )
        )
    )
    boost_entries = deduplicate_ranked(
        [
            (boost.item_id, float(boost.priority), "operator_boost")
            for boost in active_boosts(db, user, feed_type)
            if boost.item_id not in interacted
        ]
    )
    boost_ids = {item_id for item_id, _, _ in boost_entries}
    merged = deduplicate_ranked(
        boost_entries + [entry for entry in filtered if entry[0] not in boost_ids]
    )
    page = merged[cursor : cursor + limit]

    request_id = str(uuid.uuid4())
    db.add(
        RecommendationRequest(
            request_id=request_id,
            user_id=user.id,
            feed_type=feed_type,
            model_version=runtime.version,
        )
    )
    response_items = []
    for position, (item_id, score, source) in enumerate(page, start=cursor):
        item = item_map[item_id]
        db.add(
            Exposure(
                request_id=request_id,
                user_id=user.id,
                item_id=item_id,
                position=position,
                source=source,
                score=score,
            )
        )
        db.add(
            Event(
                event_id=f"impression:{request_id}:{item_id}",
                request_id=request_id,
                user_id=user.id,
                item_id=item_id,
                event_type="impression",
                position=position,
                source=source,
            )
        )
        response_items.append(
            {
                "item_id": item.id,
                "title": item.title,
                "cover_url": None,
                "source_likes": item.source_likes,
                "source_views": item.source_views,
                "source": source,
                "score": round(score, 8),
                "model_version": runtime.version,
                "position": position,
            }
        )
    db.commit()
    next_cursor = cursor + len(page) if cursor + len(page) < len(merged) else None
    return {
        "request_id": request_id,
        "feed_type": feed_type,
        "model_version": runtime.version,
        "items": response_items,
        "next_cursor": next_cursor,
    }


@app.post("/api/events")
def create_event(
    data: EventInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if data.event_type not in EVENT_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported event type")
    existing = db.scalar(select(Event).where(Event.event_id == data.event_id))
    if existing:
        return {"event_id": existing.event_id, "duplicate": True}
    exposure = db.scalar(
        select(Exposure).where(
            Exposure.request_id == data.request_id,
            Exposure.user_id == user.id,
            Exposure.item_id == data.item_id,
            Exposure.position == data.position,
        )
    )
    if not exposure:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Event does not match an owned exposure")
    db.add(
        Event(
            event_id=data.event_id,
            request_id=data.request_id,
            user_id=user.id,
            item_id=data.item_id,
            event_type=data.event_type,
            position=data.position,
            source=exposure.source,
        )
    )
    db.commit()
    return {"event_id": data.event_id, "duplicate": False}


def item_details(db: Session, item_ids: list[int]) -> list[dict[str, object]]:
    if not item_ids:
        return []
    items = {item.id: item for item in db.scalars(select(Item).where(Item.id.in_(set(item_ids))))}
    return [
        {
            "item_id": item_id,
            "title": items[item_id].title if item_id in items else "Unknown item",
            "status": items[item_id].status if item_id in items else "missing",
            "cover_url": None,
            "source_likes": items[item_id].source_likes if item_id in items else 0,
            "source_views": items[item_id].source_views if item_id in items else 0,
        }
        for item_id in item_ids
    ]


def interaction_item_ids(
    db: Session,
    user_id: int,
    event_type: str,
    limit: int | None = None,
) -> list[int]:
    item_ids = db.scalars(
        select(Event.item_id)
        .where(Event.user_id == user_id, Event.event_type == event_type)
        .order_by(Event.created_at.desc(), Event.id.desc())
    )
    unique_ids: list[int] = []
    seen: set[int] = set()
    for item_id in item_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        unique_ids.append(item_id)
        if limit is not None and len(unique_ids) >= limit:
            break
    return unique_ids


def profile_snapshot(db: Session, user: User, include_preview: bool = False) -> dict[str, object]:
    recent = list(
        db.scalars(
            select(Event)
            .where(
                Event.user_id == user.id,
                Event.event_type.in_(["click", "like", "favorite", "not_interested"]),
            )
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(20)
        )
    )
    positive, negative, exposed = feedback_sets(db, user)
    historical = runtime.history(user.dataset_user_id)
    clicked_items = interaction_item_ids(db, user.id, "click")
    liked_items = interaction_item_ids(db, user.id, "like")
    favorite_items = interaction_item_ids(db, user.id, "favorite")
    snapshot: dict[str, object] = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "dataset_user_id": user.dataset_user_id,
        "created_at": user.created_at,
        "history_count": len(historical),
        "positive_items": list(dict.fromkeys(positive)),
        "clicked_items": clicked_items,
        "liked_items": liked_items,
        "favorite_items": favorite_items,
        "not_interested_items": sorted(negative),
        "exposure_count": len(exposed),
        "history_details": item_details(db, historical[-20:]),
        "positive_details": item_details(db, list(dict.fromkeys(positive))[-20:]),
        "clicked_details": item_details(db, clicked_items[:20]),
        "liked_details": item_details(db, liked_items[:20]),
        "favorite_details": item_details(db, favorite_items[:20]),
        "negative_details": item_details(db, sorted(negative)[-20:]),
        "recent_events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "item_id": event.item_id,
                "request_id": event.request_id,
                "created_at": event.created_at,
            }
            for event in recent
        ],
    }
    if include_preview:
        online_ids = set(db.scalars(select(Item.id).where(Item.status == "online")))
        preview = [
            (item_id, score, source)
            for item_id, score, source in runtime.personalized(
                user.dataset_user_id, positive, negative
            )
            if item_id in online_ids and item_id not in exposed
        ][:10]
        details = {item["item_id"]: item for item in item_details(db, [item_id for item_id, _, _ in preview])}
        snapshot["recommendation_preview"] = [
            {
                **details[item_id],
                "score": round(score, 8),
                "source": source,
            }
            for item_id, score, source in preview
        ]
    return snapshot


@app.get("/api/profile")
def profile(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    return profile_snapshot(db, user)


@app.get("/api/items/{item_id}")
def get_item(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    del user
    item = db.scalar(select(Item).where(Item.id == item_id, Item.status == "online"))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not available")
    return item_details(db, [item.id])[0]


def dashboard_start(range_key: DashboardRange) -> datetime | None:
    delta = RANGE_DELTAS.get(range_key)
    return utcnow() - delta if delta else None


def dashboard_snapshot(db: Session, range_key: DashboardRange) -> dict[str, object]:
    start = dashboard_start(range_key)
    request_query = select(RecommendationRequest)
    exposure_query = select(Exposure)
    event_query = select(Event)
    if start:
        request_query = request_query.where(RecommendationRequest.created_at >= start)
        exposure_query = exposure_query.where(Exposure.created_at >= start)
        event_query = event_query.where(Event.created_at >= start)

    requests = list(db.scalars(request_query))
    exposures = list(db.scalars(exposure_query))
    events = list(db.scalars(event_query))
    event_counts = Counter(event.event_type for event in events)
    click_count = event_counts["click"]
    like_count = event_counts["like"] + event_counts["favorite"]
    active_user_ids = {request.user_id for request in requests} | {
        event.user_id for event in events
    }
    feed_counts = Counter(request.feed_type for request in requests)
    feed_shares = [
        {
            "feed_type": feed_type,
            "requests": feed_counts[feed_type],
            "share": round(feed_counts[feed_type] / len(requests), 6) if requests else 0.0,
        }
        for feed_type in ("personalized", "popular", "explore")
    ]

    item_stats: dict[int, Counter[str]] = defaultdict(Counter)
    for exposure in exposures:
        item_stats[exposure.item_id]["exposures"] += 1
    for event in events:
        if event.event_type in {"click", "like", "favorite"}:
            item_stats[event.item_id][event.event_type] += 1
    top_item_ids = sorted(
        item_stats,
        key=lambda item_id: (
            -(item_stats[item_id]["like"] + item_stats[item_id]["favorite"]),
            -item_stats[item_id]["click"],
            -item_stats[item_id]["exposures"],
            item_id,
        ),
    )[:10]
    item_map = {
        item.id: item
        for item in db.scalars(select(Item).where(Item.id.in_(top_item_ids)))
    } if top_item_ids else {}
    popular_items = [
        {
            "item_id": item_id,
            "title": item_map[item_id].title,
            "exposures": item_stats[item_id]["exposures"],
            "clicks": item_stats[item_id]["click"],
            "likes": item_stats[item_id]["like"] + item_stats[item_id]["favorite"],
        }
        for item_id in top_item_ids
        if item_id in item_map
    ]

    use_hour = range_key in {"1h", "24h"}

    def bucket(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:00") if use_hour else value.strftime("%Y-%m-%d")

    trend_values: dict[str, Counter[str]] = defaultdict(Counter)
    for request in requests:
        trend_values[bucket(request.created_at)]["requests"] += 1
    for exposure in exposures:
        trend_values[bucket(exposure.created_at)]["exposures"] += 1
    for event in events:
        if event.event_type == "click":
            trend_values[bucket(event.created_at)]["clicks"] += 1
        elif event.event_type in {"like", "favorite"}:
            trend_values[bucket(event.created_at)]["likes"] += 1
    trend = [
        {"bucket": name, **{metric: values[metric] for metric in ("requests", "exposures", "clicks", "likes")}}
        for name, values in sorted(trend_values.items())
    ]
    if not trend:
        trend = [{"bucket": bucket(utcnow()), "requests": 0, "exposures": 0, "clicks": 0, "likes": 0}]

    recent_query = select(RecommendationRequest)
    if start:
        recent_query = recent_query.where(RecommendationRequest.created_at >= start)
    recent = list(db.scalars(recent_query.order_by(RecommendationRequest.created_at.desc()).limit(12)))
    user_ids = {request.user_id for request in recent}
    usernames = {
        user.id: user.username
        for user in db.scalars(select(User).where(User.id.in_(user_ids)))
    } if user_ids else {}
    recent_requests = []
    for request in recent:
        recent_requests.append(
            {
                "request_id": request.request_id,
                "user_id": request.user_id,
                "username": usernames.get(request.user_id, "unknown"),
                "feed_type": request.feed_type,
                "model_version": request.model_version,
                "created_at": request.created_at,
                "exposures": sum(exposure.request_id == request.request_id for exposure in exposures),
                "events": sum(
                    event.request_id == request.request_id and event.event_type != "impression"
                    for event in events
                ),
            }
        )

    return {
        "range": range_key,
        "range_start": start,
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "active_users": len(active_user_ids),
        "requests": len(requests),
        "exposures": len(exposures),
        "clicks": click_count,
        "ctr": round(click_count / len(exposures), 6) if exposures else 0.0,
        "likes": like_count,
        "offline_items": db.scalar(select(func.count()).select_from(Item).where(Item.status == "offline")) or 0,
        "model_version": runtime.version,
        "events": dict(event_counts),
        "feed_shares": feed_shares,
        "popular_items": popular_items,
        "trend": trend,
        "recent_requests": recent_requests,
    }


@app.get("/api/admin/dashboard")
def dashboard(
    range_key: DashboardRange = Query(default="24h", alias="range"),
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    del admin
    return dashboard_snapshot(db, range_key)


@app.get("/api/admin/users")
def admin_users(
    query: str = "",
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    del admin
    statement = select(User)
    if query.strip():
        statement = statement.where(User.username.ilike(f"%{query.strip()}%"))
    users = list(db.scalars(statement.order_by(User.role.desc(), User.username).limit(100)))
    return [
        {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "dataset_user_id": user.dataset_user_id,
            "created_at": user.created_at,
            "requests": db.scalar(
                select(func.count()).select_from(RecommendationRequest).where(
                    RecommendationRequest.user_id == user.id
                )
            ) or 0,
            "events": db.scalar(
                select(func.count()).select_from(Event).where(
                    Event.user_id == user.id,
                    Event.event_type != "impression",
                )
            ) or 0,
        }
        for user in users
    ]


@app.get("/api/admin/users/{user_id}/profile")
def admin_profile(
    user_id: int,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    del admin
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return profile_snapshot(db, user, include_preview=True)


@app.get("/api/admin/dashboard/export")
def export_dashboard(
    range_key: DashboardRange = Query(default="24h", alias="range"),
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> Response:
    del admin
    start = dashboard_start(range_key)
    statement = select(Event).order_by(Event.created_at, Event.id)
    if start:
        statement = statement.where(Event.created_at >= start)
    events = list(db.scalars(statement))
    request_ids = {event.request_id for event in events}
    requests = {
        request.request_id: request
        for request in db.scalars(
            select(RecommendationRequest).where(RecommendationRequest.request_id.in_(request_ids))
        )
    } if request_ids else {}
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ["timestamp", "request_id", "user_id", "feed_type", "model_version", "item_id", "position", "source", "event_type"]
    )
    for event in events:
        request = requests.get(event.request_id)
        writer.writerow(
            [
                event.created_at.isoformat(),
                event.request_id,
                event.user_id,
                request.feed_type if request else "",
                request.model_version if request else "",
                event.item_id,
                event.position,
                event.source,
                event.event_type,
            ]
        )
    filename = f"yahaha-dashboard-{range_key}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/requests/{request_id}")
def request_trace(
    request_id: str,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    del admin
    request = db.get(RecommendationRequest, request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation request not found")
    user = db.get(User, request.user_id)
    exposures = list(
        db.scalars(select(Exposure).where(Exposure.request_id == request_id).order_by(Exposure.position))
    )
    events = list(
        db.scalars(select(Event).where(Event.request_id == request_id).order_by(Event.created_at, Event.id))
    )
    return {
        "request_id": request.request_id,
        "user_id": request.user_id,
        "username": user.username if user else "unknown",
        "feed_type": request.feed_type,
        "model_version": request.model_version,
        "created_at": request.created_at,
        "exposures": [
            {
                "item_id": exposure.item_id,
                "position": exposure.position,
                "source": exposure.source,
                "score": exposure.score,
                "created_at": exposure.created_at,
            }
            for exposure in exposures
        ],
        "events": [
            {
                "event_id": event.event_id,
                "item_id": event.item_id,
                "position": event.position,
                "event_type": event.event_type,
                "source": event.source,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


@app.patch("/api/admin/items/{item_id}/status")
def set_item_status(
    item_id: int,
    data: StatusInput,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    before = item.status
    item.status = data.status
    db.add(
        Operation(
            admin_id=admin.id,
            item_id=item.id,
            operation=data.status,
            before_state=before,
            after_state=data.status,
            reason=data.reason,
        )
    )
    db.commit()
    return {"item_id": item.id, "status": item.status}


@app.post("/api/admin/boosts", status_code=201)
def create_boost(
    data: BoostInput,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if data.ends_at <= data.starts_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "ends_at must follow starts_at")
    item = db.get(Item, data.item_id)
    if not item or item.status != "online":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only online items can be boosted")
    if data.target_user_id is not None and not db.get(User, data.target_user_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Target user not found")
    boost = Boost(**data.model_dump(), active=True, created_by=admin.id)
    db.add(boost)
    db.flush()
    db.add(
        Operation(
            admin_id=admin.id,
            item_id=item.id,
            operation="boost",
            before_state="none",
            after_state=f"boost:{boost.id}",
            reason=data.reason,
        )
    )
    db.commit()
    return {"boost_id": boost.id, "item_id": item.id, "active": boost.active}


@app.get("/api/admin/boosts")
def list_boosts(
    limit: int = Query(default=100, ge=1, le=200),
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    del admin
    now = utcnow()
    boosts = list(db.scalars(select(Boost).order_by(Boost.created_at.desc(), Boost.id.desc()).limit(limit)))
    result: list[dict[str, object]] = []
    for boost in boosts:
        item = db.get(Item, boost.item_id)
        target_user = db.get(User, boost.target_user_id) if boost.target_user_id else None
        creator = db.get(User, boost.created_by)
        if not boost.active:
            rule_status = "disabled"
        elif item and item.status == "offline":
            rule_status = "item_offline"
        elif boost.starts_at > now:
            rule_status = "scheduled"
        elif boost.ends_at <= now:
            rule_status = "expired"
        else:
            rule_status = "active"
        result.append(
            {
                "boost_id": boost.id,
                "item_id": boost.item_id,
                "title": item.title if item else "Unknown item",
                "item_status": item.status if item else "missing",
                "target_user_id": boost.target_user_id,
                "target_username": target_user.username if target_user else None,
                "feed_type": boost.feed_type,
                "priority": boost.priority,
                "starts_at": boost.starts_at,
                "ends_at": boost.ends_at,
                "duration_seconds": int((boost.ends_at - boost.starts_at).total_seconds()),
                "reason": boost.reason,
                "active": boost.active,
                "rule_status": rule_status,
                "created_by": creator.username if creator else None,
                "created_at": boost.created_at,
            }
        )
    return result


@app.get("/api/admin/items")
def search_items(
    query: str = "",
    item_status: Literal["online", "offline"] | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    del admin
    statement = select(Item)
    if item_status:
        statement = statement.where(Item.status == item_status)
    if query:
        if query.isdigit():
            statement = statement.where(or_(Item.id == int(query), Item.title.contains(query)))
        else:
            statement = statement.where(Item.title.contains(query))
    items = db.scalars(statement.order_by(case((Item.status == "offline", 0), else_=1), Item.id).limit(limit))
    return [
        {
            "item_id": item.id,
            "title": item.title,
            "status": item.status,
            "source_likes": item.source_likes,
            "source_views": item.source_views,
            "updated_at": item.updated_at,
        }
        for item in items
    ]
