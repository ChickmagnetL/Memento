# Index raw serial

- time: 2026-07-24 16:18:36 UTC
- total raw queue: 19
- verified indexed: 19
- failed: 0
- method: serial `POST /api/documents/{id}/index` only (no clean, no ASR, no local Qdrant)
- embedding warmed on :8003; worktree embedding HTTP timeout temporarily 300s for large batches

## Result table

| # | video_id | document_id | status | chunks | secs | outcome |
|---|----------|-------------|--------|--------|------|---------|
| 1 | BV1M2421T7qk | `59380011d41f448f9e55653e67182b49` | indexed | 25 | - | skipped_already_indexed |
| 2 | BV1ub421J7jv | `06f4abbb549844a788757fe10c98d6c9` | indexed | 28 | - | skipped_already_indexed |
| 3 | cfXTQmFRjWU | `ebb04accd832482f8597d0ab7c18f5c2` | indexed | 44 | 3.0 | indexed |
| 4 | 2qf6ry-YjwU | `acf4e85089bd4989bb26d761bf008123` | indexed | 68 | 3.1 | indexed |
| 5 | BV1QGXABxEbq | `5fd698d82dc94839a98e3a9b64321fa8` | indexed | 18 | 8.8 | indexed |
| 6 | 64Zp3tzNbpE | `c72da92dfc8e4375bd056c5ad82423c0` | indexed | 101 | 6.0 | indexed |
| 7 | BV1hN596zEas | `6d0acacb84924ed9a3f6bbc1f3714cff` | indexed | 24 | - | skipped_already_indexed |
| 8 | EpIgvowZr00 | `31282017576140cd8231eca72f90849f` | indexed | 104 | 6.0 | indexed |
| 9 | BV11o4y1s7VY | `b199b0778031446384eaaecb0d6680a6` | indexed | 15 | - | skipped_already_indexed |
| 10 | BV1dMGm6xET9 | `f667f8fa51be489b9cddc69e4daf580d` | indexed | 21 | - | skipped_already_indexed |
| 11 | BV1LAVh6UEQz | `30bd49876f5f4632a24ece6cc69b3b26` | indexed | 18 | 3.0 | indexed |
| 12 | Cl0QYkez-BE | `b4309e724a594f8f94621245f955358b` | indexed | 107 | 6.0 | indexed |
| 13 | BV1Dm7J6XEEh | `17888c4cf23c48bf8ac2bbd263384e6e` | indexed | 25 | - | skipped_already_indexed |
| 14 | BV1z8zPYjE4j | `b5e0b56b48c74aec8d0fa551261f65cb` | indexed | 20 | 3.0 | indexed |
| 15 | BV1HR7o6CE8q | `f02984e6ca05481d806123e59d4c372a` | indexed | 35 | 80.9 | indexed |
| 16 | BV1hA7K6jER9 | `9b2d8b5ea83749849b1a003c3de79cda` | indexed | 21 | - | skipped_already_indexed |
| 17 | ej6cygeB2X0 | `418e8370da6c4e43a5a6d864914ddcc5` | indexed | 125 | 166.3 | indexed |
| 18 | 3ub8RBE7BC8 | `f21f689cb37443c685d4100709b4bb19` | indexed | 61 | 69.6 | indexed |
| 19 | cQP8WApzIQQ | `18599259b34241d8ac872db3983b3174` | indexed | 116 | 240.3 | indexed |

## Failed only (raw index queue)

(none)

## Related skips / follow-ups

### #13 / #14 — metadata 422 (human; do not thrash)

- **#13** 银行信贷 Bernanke (`https://www.youtube.com/watch?v=3e-3q0vK9pE`): create failed `422 Could not fetch YouTube video metadata` (see `00_dataset_batch_11_20.md`). Not re-attempted.
- **#14** 国际贸易 Krugman (`https://www.youtube.com/watch?v=9P7wU5s5pYI`): create failed `422 Could not fetch YouTube video metadata` (same). Not re-attempted.

### #49 — subtitle process retry (10x)

- **#49** 美国梦 MAGA (`BV1JCMw6cEha`): `ingest_videos.py --start 49 --end 49` ran 10 subtitle-only process attempts.
- All 10 failed: `This Bilibili video has no usable soft subtitles` / precheck `no_subtitles`.
- **No document created; no index.** Report: `00_dataset_batch_49_49.md`. ASR not used (per policy).

## Notes

- Pre-existing indexed docs among the 19 were skipped (`chunks>0`).
- Stopped competing `ingest_videos` during index to avoid Qdrant/embed contention.
- 28 previously indexed docs left untouched.
