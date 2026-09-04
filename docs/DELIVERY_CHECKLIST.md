# 交付核对表

本表逐项映射提交要求。`[x]` 表示仓库内已具备并有可执行验证方式。

## 必需交付物

- [x] 源码仓库：`https://github.com/Jing1oo8/Yahaha_ZJ`，当前已有 5 次有意义提交
- [x] Demo 地址：本地 `http://127.0.0.1:5173/`，README 提供完整启动方式、端口、路径和测试账号
- [x] 启动命令：前端、后端、SQLite 初始化、CPU 训练及 smoke 均已说明
- [x] 数据处理脚本：从 3 个原始文件生成时间切分、内容元数据与用户历史
- [x] 模型与评估报告：固定配置、可消费 gzip 模型、2 个 baseline、3 个排序指标和 Badcase
- [x] 测试账号与种子：Alice、Bob、Carol 和管理员，可演示隔离信息流、行为变化、强推和下线
- [x] 数据库与 API 文档：核心表、认证、Feed、事件、Dashboard、强推/下线的请求响应与错误行为
- [x] 系统设计文档：架构、离线到线上流、召回/排序/混排、fallback、模型发布、权限、恢复和限制
- [x] README 与环境变量：从放置数据到启动、登录、训练、Dashboard 和运营均有步骤；无真实密钥
- [x] 完成度说明：明确已完成、延期/Mock、最大风险和一周计划
- [ ] 3–5 分钟演示视频

## 功能验收

- [x] 时间切分 train/validation/test，无未来泄漏
- [x] ItemCF 与 Popularity、Random baseline 对比
- [x] 报告 Recall@20、HitRate@20、NDCG@20 和 Coverage@20
- [x] Personalized、Popular、Explore 三种 Feed
- [x] Alice 与 Bob 的个性化结果不同
- [x] 分页、去重、已看过滤和 fallback
- [x] 响应携带 source、score、model_version、request_id
- [x] 保存 impression、click、like/favorite、not_interested
- [x] request_id 回连 recommendation_requests、exposures、events
- [x] 用户行为改变画像或后续排序
- [x] Dashboard 指标由真实请求和事件计算
- [x] 时间筛选、趋势、Feed 占比、热门内容、请求链路和 CSV 导出
- [x] 单条/批量强推、下线和恢复影响 Feed
- [x] 下线内容不能通过绕过前端的方式访问
- [x] 普通用户不能访问他人数据或管理员接口
- [x] 注册创建隔离的普通冷启动账号
- [x] 管理员可调试用户历史、反馈和推荐预览
- [x] 强推可配置用户/Feed、时间窗、优先级和原因
- [x] 独立 Python 虚拟环境和锁定前端依赖可执行核心测试/构建（见 `VERIFICATION.md`）

## 视频录制脚本

1. 从 README 展示数据目录和一键核验命令。
2. 展示最终评估表和模型版本。
3. 分别登录 Alice、Bob，对比不同个性化信息流。
4. 注册新用户，展示冷启动 fallback。
5. 上报播放/点赞/收藏/不感兴趣，展示个人画像与 Dashboard 变化。
6. 管理员配置定向强推、批量下线并验证线上结果。
