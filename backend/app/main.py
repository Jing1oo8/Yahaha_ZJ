from __future__ import annotations

import hashlib
import uuid
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
from .security import new_session_token, token_hash, verify_password


app = FastAPI(title="YAHAHA Recommendation MVP", version="0.1.0")
Base.metadata.create_all(engine)
SESSION_COOKIE = "yahaha_session"
EVENT_TYPES = {"impression", "click", "like", "favorite", "not_interested"}


class LoginInput(BaseModel):
    username: str
    password: str


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


@app.post("/api/auth/login")
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
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


def feedback_sets(db: Session, user: User) -> tuple[list[int], set[int], set[int]]:
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
    exposed = set(db.scalars(select(Exposure.item_id).where(Exposure.user_id == user.id)))
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


@app.get("/api/feed")
def feed(
    feed_type: Literal["personalized", "popular", "explore"] = Query(alias="type"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    positive, negative, exposed = feedback_sets(db, user)
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
    boost_entries = [
        (boost.item_id, float(boost.priority), "operator_boost")
        for boost in active_boosts(db, user, feed_type)
    ]
    boost_ids = {item_id for item_id, _, _ in boost_entries}
    merged = boost_entries + [entry for entry in filtered if entry[0] not in boost_ids]
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


@app.get("/api/profile")
def profile(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
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
    positive = [event.item_id for event in recent if event.event_type in {"like", "favorite"}]
    negative = [event.item_id for event in recent if event.event_type == "not_interested"]
    return {
        "user_id": user.id,
        "dataset_user_id": user.dataset_user_id,
        "positive_items": positive,
        "not_interested_items": negative,
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


@app.get("/api/items/{item_id}")
def get_item(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    del user
    item = db.scalar(select(Item).where(Item.id == item_id, Item.status == "online"))
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not available")
    return {"item_id": item.id, "title": item.title, "status": item.status}


@app.get("/api/admin/dashboard")
def dashboard(admin: User = Depends(admin_user), db: Session = Depends(get_db)) -> dict[str, object]:
    del admin
    event_counts = dict(
        db.execute(select(Event.event_type, func.count(Event.id)).group_by(Event.event_type)).all()
    )
    exposures = db.scalar(select(func.count()).select_from(Exposure)) or 0
    clicks = event_counts.get("click", 0)
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "requests": db.scalar(select(func.count()).select_from(RecommendationRequest)) or 0,
        "exposures": exposures,
        "clicks": clicks,
        "ctr": round(clicks / exposures, 6) if exposures else 0.0,
        "likes": event_counts.get("like", 0) + event_counts.get("favorite", 0),
        "offline_items": db.scalar(select(func.count()).select_from(Item).where(Item.status == "offline")) or 0,
        "model_version": runtime.version,
        "events": event_counts,
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


@app.get("/api/admin/items")
def search_items(
    query: str = "",
    limit: int = Query(default=50, ge=1, le=100),
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    del admin
    statement = select(Item)
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
