# 00 数据集灌库报告

生成时间: 2026-07-24 15:38:01 UTC
BASE_URL: `http://127.0.0.1:8010`
范围: videos 47–50 (1-based, of 50 total)
模式: subtitle-only (NO ASR)
成功(含已就绪跳过): 3 / 4，失败: 1

| # | 标签 | 状态 | video_id | document_id | chunk_count | 错误/备注 |
|---|------|------|----------|-------------|-------------|-----------|
| 47 | 电力四大赛道 | skipped_ready | `BV1hA7K6jER9` | `9b2d8b5ea83749849b1a003c3de79cda` | 21 | already completed+indexed; reindexed via HTTP after first-pass clean/index contention |
| 48 | 伊斯兰起源 | skipped_ready | `BV1Dm7J6XEEh` | `17888c4cf23c48bf8ac2bbd263384e6e` | 25 | already completed+indexed; reindexed via HTTP after first-pass clean/index contention |
| 49 | 美国梦 MAGA | failed | `BV1JCMw6cEha` | `` | 0 | process returned status=failed: This Bilibili video has no usable soft subtitles. You can transcribe it with ASR instead. |
| 50 | 中国家装变迁 | skipped_ready | `BV1dMGm6xET9` | `f667f8fa51be489b9cddc69e4daf580d` | 21 | already completed+indexed; reindexed via HTTP after first-pass clean/index contention |

## URL 清单

47. [电力四大赛道](https://www.bilibili.com/video/BV1hA7K6jER9/?)
48. [伊斯兰起源](https://www.bilibili.com/video/BV1Dm7J6XEEh/?)
49. [美国梦 MAGA](https://www.bilibili.com/video/BV1JCMw6cEha/?)
50. [中国家装变迁](https://www.bilibili.com/video/BV1dMGm6xET9/?)

## Notes

- #46 进程内存CPU already indexed (skipped, not reprocessed): `BV1mMHyz3Erk` doc=`b9d49ee5172a4bbbb806f061ed2c613a` chunks=10
- First pass process(subtitle) succeeded for 47/48/50; clean failed (Chat 524) and concurrent HTTP index failed (embedding timeout / Qdrant local lock from other batches). Recovered by serial HTTP `/api/documents/{id}/index` only (no ASR, no local_batch_index).
- #49 has no usable soft subtitles; failed as required under subtitle-only mode.
