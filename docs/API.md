# 数据库与 API

## 核心表

| 表 | 用途与关键字段 |
| --- | --- |
| `users` | 登录身份、PBKDF2 密码哈希、角色、MicroLens 用户映射 |
| `sessions` | SHA-256 会话 token 哈希、用户、过期时间；原始 token 只存在于 HttpOnly Cookie |
| `items` | 标题、来源 likes/views、服务端权威上下线状态 |
| `recommendation_requests` | request ID、用户、Feed 类型、模型版本、时间 |
| `exposures` | request/用户/物品/位置/来源/分数；request-item 唯一 |
| `events` | 幂等 event ID、request/用户/物品/类型/位置/来源/时间 |
| `boosts` | 物品、可选用户/Feed 目标、优先级、原因、有效期 |
| `operations` | 管理员、操作、物品、前后状态、原因和时间 |
| `model_versions` | 版本、算法、指标、发布状态和训练时间 |

SQLite 外键和服务层归属校验把推荐请求、曝光和行为连接起来。只有当前登录用户拥有完全匹配的 request、item、position 曝光时，行为才会被接受。

## 认证与权限

密码使用 PBKDF2-HMAC-SHA256、每用户随机盐和 310,000 次迭代。注册只创建无 MicroLens 映射的普通冷启动用户。注册或登录成功后创建随机 12 小时服务端会话，数据库仅保存 SHA-256 哈希，原始 token 通过 HttpOnly、SameSite=Lax Cookie 返回。

普通用户访问管理员接口返回 403；权限由 FastAPI 依赖在服务端执行，不依赖前端按钮是否可见。

## 接口

交互式 OpenAPI 位于 `http://127.0.0.1:8000/docs`。

| 方法与路径 | 角色 | 行为 |
| --- | --- | --- |
| `POST /api/auth/register` | 公开 | 创建普通冷启动用户和会话 |
| `POST /api/auth/login` | 公开 | 校验账号并创建会话 |
| `POST /api/auth/logout` | 已登录 | 删除服务端会话与 Cookie |
| `GET /api/auth/me` | 用户 | 返回服务端识别的当前身份 |
| `GET /api/feed?type=...` | 用户 | 返回 personalized/popular/explore 分页及曝光 |
| `POST /api/events` | 用户 | 幂等提交 click/like/favorite/not_interested |
| `GET /api/profile` | 用户 | 去重后的观看、点赞、收藏、不感兴趣历史及物品详情 |
| `GET /api/items/{id}` | 用户 | 返回在线物品；下线物品返回 404 |
| `GET /api/admin/dashboard?range=24h` | 管理员 | 指定时间范围的指标、趋势、Feed 占比、热门内容和近期请求 |
| `GET /api/admin/dashboard/export?range=24h` | 管理员 | 导出 UTF-8、可回连 request 的事件 CSV |
| `GET /api/admin/requests/{request_id}` | 管理员 | 查看请求、曝光和事件链路 |
| `GET /api/admin/users` | 管理员 | 列出账号及请求/行为数量 |
| `GET /api/admin/users/{id}/profile` | 管理员 | 调试历史、反馈和推荐预览 |
| `GET /api/admin/items?status=offline` | 管理员 | 按 ID/标题搜索并筛选上下线状态 |
| `PATCH /api/admin/items/{id}/status` | 管理员 | 上线、下线或恢复并写审计记录 |
| `GET /api/admin/boosts` | 管理员 | 查看强推范围、优先级、时段和生效状态 |
| `POST /api/admin/boosts` | 管理员 | 创建定向、定时、带优先级的服务端强推 |

每个 Feed 响应包含 `request_id`、Feed 类型、模型版本，以及每个物品的来源、分数、位置、标题、可空 `cover_url` 和来源统计。生成 Feed 时，request、exposure 和 impression 在同一数据库事务中写入。

Dashboard 时间范围为 `1h`、`24h`、`7d`、`30d`、`all`。活跃用户是所选范围内产生推荐请求或行为的去重登录用户；Feed 占比按请求数计算；热门内容按点赞/收藏、点击、曝光排序。CSV 保留 request、用户、模型、位置、来源和事件字段。

## 请求/响应示例

```http
POST /api/auth/login
Content-Type: application/json

{"username":"alice","password":"alice123"}
```

```json
{
  "request_id": "uuid",
  "feed_type": "personalized",
  "model_version": "itemcf-0022f60b5e4b",
  "items": [{"item_id": 1, "position": 1, "source": "itemcf", "score": 0.42}]
}
```

```http
POST /api/events
Content-Type: application/json

{"event_id":"client-uuid","request_id":"uuid","item_id":1,"position":1,"event_type":"like"}
```

## 错误与冲突

- 登录缺失或过期：401。
- 普通用户访问管理员接口：403。
- 行为与本人曝光不匹配：400。
- 物品不存在或已下线：404。
- 强推已下线内容：409。
- 事件类型、状态或时间范围无效：422。
- 重复 `event_id`：幂等返回 200，`duplicate=true`。
