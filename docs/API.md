# Database and API

## Core tables

| Table | Purpose and key fields |
| --- | --- |
| `users` | Login identity, PBKDF2 password hash, role, MicroLens user mapping |
| `sessions` | SHA-256 session-token hash, user, expiry; raw tokens only live in HttpOnly cookies |
| `items` | MicroLens title, source likes/views, server-authoritative online/offline state |
| `recommendation_requests` | Unique request ID, user, feed type, model version, timestamp |
| `exposures` | Request/user/item/position/source/score; unique request-item pair |
| `events` | Idempotent event ID, request/user/item/type/position/source/timestamp |
| `boosts` | Item, optional user/feed targeting, priority, reason, validity window |
| `operations` | Admin, operation, item, before/after states, reason and timestamp |
| `model_versions` | Version, algorithm, metrics, publish status and training time |

SQLite foreign keys and service-level ownership checks connect recommendation
requests, exposures, and behavior. Event submission is accepted only when the
logged-in user owns a matching exposure with the same request, item, and position.

## Authentication

Passwords use PBKDF2-HMAC-SHA256 with per-user random salt and 310,000 iterations.
Successful login creates a random 12-hour server session. Only its SHA-256 hash
is stored; the raw token is returned in an HttpOnly, SameSite=Lax cookie.

Normal users receive HTTP 403 from admin endpoints. Authorization is enforced in
FastAPI dependencies and is not based on frontend button visibility.

## Endpoints

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

| Method and path | Role | Behavior |
| --- | --- | --- |
| `POST /api/auth/login` | public | Validate credentials and create session cookie |
| `POST /api/auth/logout` | session | Delete server session and cookie |
| `GET /api/auth/me` | user | Current server-recognized identity |
| `GET /api/feed?type=...` | user | Personalized/popular/explore page and exposures |
| `POST /api/events` | user | Idempotent click/like/favorite/not-interested event |
| `GET /api/profile` | user | Recent feedback and simple online profile |
| `GET /api/items/{id}` | user | Online item only; offline returns 404 |
| `GET /api/admin/dashboard?range=24h` | admin | Time-filtered metrics, trends, feed shares, popular content and recent requests |
| `GET /api/admin/dashboard/export?range=24h` | admin | UTF-8 CSV export of request-linked events |
| `GET /api/admin/requests/{request_id}` | admin | Request, exposure and event trace |
| `GET /api/admin/items` | admin | Search content by ID/title |
| `PATCH /api/admin/items/{id}/status` | admin | Online/offline/restore with audit record |
| `POST /api/admin/boosts` | admin | Targeted, timed, prioritized server-side boost |

Every feed response includes `request_id`, feed type, model version, and per-item
source, score, position, title, and source statistics. Feed generation writes the
request, exposures, and impression events in the same database transaction.

Dashboard ranges are `1h`, `24h`, `7d`, `30d`, and `all`. Active users are the
distinct authenticated users with a recommendation request or event in the
selected range. Feed shares use request counts. Popular content is ranked by
likes/favorites, clicks, then exposures from the selected range. CSV rows retain
the request, user, model, position, source and event fields needed for analysis.

## Error and conflict behavior

- Missing/expired login: 401.
- Normal user accessing admin APIs: 403.
- Event not matching an owned exposure: 400.
- Direct access to missing/offline content: 404.
- Boosting offline content: 409.
- Invalid event/status/time range: 422.
- Duplicate client event ID: idempotent 200 response with `duplicate=true`.
