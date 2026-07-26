# 00 数据集灌库报告

生成时间: 2026-07-24 14:18:36 UTC
BASE_URL: `http://127.0.0.1:8010`
范围: videos 31–40 (1-based, of 50 total)
模式: subtitle-only (NO ASR)
成功(含已就绪跳过): 6 / 10，失败: 4

| # | 标签 | 状态 | video_id | document_id | chunk_count | 错误/备注 |
|---|------|------|----------|-------------|-------------|-----------|
| 31 | Nobel Nordhaus | skipped_ready | `h1RkSuAs03Q` | `64cc7a9e88c7458192f5cdd598931d77` | 12 | already completed+indexed |
| 32 | Yale Shiller 金融 | success | `D3aHciiVdvQ` | `09e282f47b0b4d529d7cb9aa40e2165c` | 16 | clean_failed_indexed_raw: clean failed: 502 {"detail":"Chat API failed: HTTP 524: {'type': 'https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/', 'title': 'Error 524: A timeout occurred', 'status': 524, 'detail': 'The origin web server did not return a complete respons |
| 33 | MIT 宏观 L1 | skipped_ready | `heBErnN3ZPk` | `04d701f5fdd440bdb8f6ab371578c202` | 46 | already completed+indexed |
| 34 | MIT 宏观 L4 | skipped_ready | `b5H8D_wD2AY` | `1147b03ff8f04e11850d0f6b2c98fa7a` | 19 | already completed+indexed |
| 35 | FRONTLINE 2008 P1 | skipped_ready | `W-Q9AOp2FW8` | `48b2c69261c84596bffde9472f52369e` | 67 | already completed+indexed |
| 36 | Dalio 经济机器 | skipped_ready | `PHe0bXAIuk0` | `d4dd99cebe3d4f31b41a03040c7fe4c4` | 40 | already completed+indexed |
| 37 | 新手健身忠告 | failed | `BV1654y1F7fZ` | `` | 0 | process returned status=failed: This Bilibili video has no usable soft subtitles. You can transcribe it with ASR instead. |
| 38 | 背部训练私教 | failed | `BV1HR7o6CE8q` | `` | 0 | process returned status=failed: This Bilibili video has no usable soft subtitles. You can transcribe it with ASR instead. |
| 39 | 三分化饮食 | failed | `BV1z8zPYjE4j` | `` | 0 | process returned status=failed: This Bilibili video has no usable soft subtitles. You can transcribe it with ASR instead. |
| 40 | 蛋白质营养 | failed | `BV1LAVh6UEQz` | `` | 0 | process returned status=failed: This Bilibili video has no usable soft subtitles. You can transcribe it with ASR instead. |

## URL 清单

31. [Nobel Nordhaus](https://www.youtube.com/watch?v=h1RkSuAs03Q)
32. [Yale Shiller 金融](https://www.youtube.com/watch?v=D3aHciiVdvQ)
33. [MIT 宏观 L1](https://www.youtube.com/watch?v=heBErnN3ZPk)
34. [MIT 宏观 L4](https://www.youtube.com/watch?v=b5H8D_wD2AY)
35. [FRONTLINE 2008 P1](https://www.youtube.com/watch?v=W-Q9AOp2FW8)
36. [Dalio 经济机器](https://www.youtube.com/watch?v=PHe0bXAIuk0)
37. [新手健身忠告](https://www.bilibili.com/video/BV1654y1F7fZ/?)
38. [背部训练私教](https://www.bilibili.com/video/BV1HR7o6CE8q/?)
39. [三分化饮食](https://www.bilibili.com/video/BV1z8zPYjE4j/?)
40. [蛋白质营养](https://www.bilibili.com/video/BV1LAVh6UEQz/?)
