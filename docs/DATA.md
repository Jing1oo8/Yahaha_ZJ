# MicroLens-50K 数据处理

本文记录原始文件来源约定、字段语义、数据审计、时间切分和防止未来信息泄漏的规则。原始数据和所有生成文件只保留在本地，并由 Git 忽略。

## 原始文件来源与目录

数据来源为 [MicroLens 官方仓库](https://github.com/westlake-repl/MicroLens)。由于仓库不得提交数据集，复现者需要自行下载 MicroLens-50K，将以下文件放入 `data/raw/` 并保持文件名不变：

```text
data/raw/MicroLens-50k_pairs.csv
data/raw/MicroLens-50k_titles.csv
data/raw/MicroLens-50k_likes_and_views.txt
```

以下命令会读取文件、核对哈希和质量，再生成确定性的时间切分：

```powershell
python pipeline/inspect_raw.py --output data/artifacts/raw_audit.json
python pipeline/prepare_data.py --output-dir data/processed
```

## 原始文件与 SHA-256

下列值于 2026-09-02 在本地实测，用于确认复现时拿到的是同一版本，而不是只依赖文件名。

| 文件 | 字节数 | 行数 | SHA-256 |
| --- | ---: | ---: | --- |
| `MicroLens-50k_pairs.csv` | 9,431,093 | 359,708 | `7ff8b91bcc84f5434ac2c5be7d0b7d7730f5e84f79f9648b5ae67a7641f97bbd` |
| `MicroLens-50k_titles.csv` | 2,392,145 | 19,220 | `244aad5380cbbe0fb43458cfcda5ebe820f534384602f80a64dbbcd07dd30e49` |
| `MicroLens-50k_likes_and_views.txt` | 386,787 | 19,220 | `9031dcd6fd575abc28776b6fe55a9b5a5a6446ff1d25bbb97d0e9437f480dfb2` |

## 字段与统计

`MicroLens-50k_pairs.csv` 包含 `user`、`item`、Unix 毫秒 `timestamp`。实测为 50,000 个用户、19,220 个物品、359,708 条隐式正反馈，时间范围为 `2020-03-05T03:23:49.552Z` 至 `2022-09-12T12:02:12.429Z`。

- 每用户交互数：最小 5，中位数 6，P90 11，P95 13，最大 218，均值 7.1942。
- 每物品交互数：最小 1，中位数 11，P90 44，P95 59，最大 342，均值 18.7153。

`MicroLens-50k_titles.csv` 把 `item` 映射到 `title`，共 19,220 个唯一物品。标题长度最小 4、中位数 109、P95 205、最大 6,293 个字符。

`MicroLens-50k_likes_and_views.txt` 无表头、制表符分隔，列顺序为 `item`、`likes`、`views`。likes 范围为 10,000–4,731,000，views 范围为 44,000–93,373,000，没有 likes 大于 views 的记录。

likes/views 没有观测时间，可能包含全时间段信息。因此它们不能进入时间切分的模型特征和离线 baseline；线上热门/冷启动 Feed 可以把它作为明确标注的静态目录先验。离线热门 baseline 只能统计拟合分区中的交互。

## 数据质量结论

- 三个文件均无缺失值或非法值。
- 交互表没有完全重复行，也没有重复 `(user, item)`。
- 标题表与展示统计表没有重复物品键。
- 三个文件的物品集合完全一致，均为 19,220 个。
- 当前数据无需删除记录；脚本仍会在未来数据出现重复用户-物品时防御性保留最早事件。

## 时间切分与采样策略

随机切分会让未来行为参与训练并虚高指标。本项目使用确定性全局时间切分：

1. 按 `(timestamp, user, item)` 排序。
2. 在约 80% 和 90% 事件位置选择全局时间边界。
3. 第一边界前进入 train；第一至第二边界进入 validation；第二边界及以后进入 test。
4. 相同毫秒的所有事件进入同一分区。
5. 验证阶段只用 train 拟合并评估 `validation_eval.csv`。
6. 配置固定后，用 train+validation 重训一次并评估 `test_eval.csv`。

评估文件只包含拟合时已知的用户和物品；被排除的冷启动事件不会丢弃，而是在完整时间窗中保留用于覆盖率分析和线上 fallback 测试。测试集不得在调参过程中反复查看。

## 实测切分结果

| 分区 | 行数 | 用户数 | 物品数 | UTC 时间范围 |
| --- | ---: | ---: | ---: | --- |
| Train | 287,766 | 49,416 | 16,907 | 2020-03-05 03:23:49 至 2022-08-26 14:27:57 |
| Validation | 35,971 | 21,612 | 5,929 | 2022-08-26 14:28:16 至 2022-09-04 00:45:37 |
| Test | 35,971 | 20,862 | 5,503 | 2022-09-04 00:46:18 至 2022-09-12 12:02:12 |
| Validation eval | 16,004 | 11,909 | 4,474 | validation 时间窗内 |
| Test eval | 16,499 | 11,774 | 4,403 | test 时间窗内 |

验证协同事件覆盖率为 `16,004 / 35,971 = 44.49%`；最终测试覆盖率为 `16,499 / 35,971 = 45.87%`。其余事件含拟合时间点未知的用户或物品。

## 生成文件

`pipeline/prepare_data.py` 在 `data/processed/` 写入：

| 文件 | 用途 |
| --- | --- |
| `train.csv` | 模型拟合和训练窗热门 baseline |
| `validation.csv` | 完整验证窗及最终重训输入 |
| `validation_eval.csv` | train 模型可评估的验证事件 |
| `test.csv` | 完整测试窗与覆盖率分析 |
| `test_eval.csv` | train+validation 重训后可评估的测试事件 |
| `items.csv` | 标题与受限使用的来源 likes/views |
| `user_history.jsonl` | train+validation 的用户时间序列历史，共 49,887 用户 |
| `split_manifest.json` | 原始哈希、边界、行数和特征使用策略 |

manifest 把后续模型版本和评估报告连接到确切原始文件及切分边界。
