# 离线模型评估报告

## 模型与 baseline

必需的可学习 baseline 为 ItemCF。它从拟合窗口的用户-物品共现学习物品相似度，用逆用户频率降低长行为序列的影响，再按物品频率做余弦归一化。预测时累加用户历史物品的邻居分数、移除已看物品，并在候选不足时使用拟合窗口热门物品补齐。

对照组为拟合窗口热门排序和固定随机种子的未看物品抽样。来源 likes/views 因没有观测时间，不参与离线对比，只用于明确标注的线上冷启动先验。

## 可复现命令

先按 [数据处理文档](DATA.md) 生成数据，再执行：

```powershell
python pipeline/train_itemcf.py --stage validation --report data/artifacts/validation_evaluation.json
python pipeline/train_itemcf.py --stage final --report data/artifacts/final_evaluation.json
```

两个命令均只使用 CPU。开发机最终运行拟合 323,737 条交互，为 11,774 个用户评估 3 个推荐器，耗时 148.9 秒，建议至少保留 2 GB 可用内存。压缩模型约 8 MB。

## 训练配置与评估协议

- 配置：`neighbor_limit=100`、`K=20`、随机种子 `20260902`。
- 验证：拟合 `train.csv`，评估 `validation_eval.csv`。
- 最终：拟合 `train.csv + validation.csv`，评估 `test_eval.csv`。
- 聚合单位：至少有一个可评估未来事件的用户，做 macro average。
- 相关集合：该用户在评估窗内的全部可评估未来物品。
- 所有推荐器均移除拟合历史中的已看物品。
- Recall@20：召回的相关未来物品比例。
- HitRate@20：至少命中一个相关物品的用户比例。
- NDCG@20：越靠前的命中获得越高权重。
- Catalog Coverage@20：所有用户推荐结果覆盖的唯一物品数 / 拟合目录物品数。

## 指标结果

### 验证集

| 推荐器 | Recall@20 | HitRate@20 | NDCG@20 | Catalog Coverage@20 |
| --- | ---: | ---: | ---: | ---: |
| ItemCF | 0.051297 | 0.060626 | 0.021676 | 1.000000 |
| Popularity | 0.004870 | 0.005626 | 0.001688 | 0.002543 |
| Random | 0.000787 | 0.001176 | 0.000275 | 1.000000 |

### 最终测试集

| 推荐器 | Recall@20 | HitRate@20 | NDCG@20 | Catalog Coverage@20 |
| --- | ---: | ---: | ---: | ---: |
| ItemCF | 0.044269 | 0.053508 | 0.017938 | 1.000000 |
| Popularity | 0.005016 | 0.006370 | 0.001384 | 0.002196 |
| Random | 0.000719 | 0.001104 | 0.000299 | 1.000000 |

ItemCF 在三项排序指标上都明显优于两个 baseline。绝对值不高，符合稀疏隐式反馈、严格全局时间切点和仅使用 ID 共现特征的预期。验证到测试的下降说明存在时间漂移；测试集没有被用于第二轮调参。

ItemCF 与随机推荐的目录覆盖率都很高，但覆盖率不等于质量：Random 覆盖高、相关性极低，所以必须和排序指标一起解读。

## 误差与 Badcase 分析

抽样的 ItemCF 零命中用户通常只有 1 个拟合历史物品。单次交互无法提供足够共现证据，未来物品也可能不是它的邻居。这直接对应线上设计：

1. 短历史和冷启动用户使用 popular/explore fallback。
2. 后续加入标题 TF-IDF 或内容 embedding，尤其改善冷物品召回。
3. 点赞/收藏立即加入线上正反馈，“不感兴趣”立即进入排除集合。
4. 保留 `source`、`score`、模型版本和 `request_id`，便于定位召回来源。

## 可消费模型产物

最终版本为 `itemcf-0022f60b5e4b`，输出到 `models/itemcf-0022f60b5e4b.json.gz`。版本由原始哈希、切分边界、阶段、算法和邻居配置确定性生成。gzip JSON 包含元数据、拟合窗热门物品和 top 相似邻居；用户历史位于 `data/processed/user_history.jsonl`。

线上服务使用同一 `load_model_artifact()` 格式校验并加载。生成产物由 Git 忽略，可通过上述命令重建。
