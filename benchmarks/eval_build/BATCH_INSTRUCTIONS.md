# 批量出题指令（所有批量子代理必读）

## 必读文件
1. `benchmarks/EVAL_SPEC.md` — **唯一规范**，尤其 §3.0 点名总表、§4 schema、§6 清单、§7 泄漏
2. `benchmarks/eval_build/samples.jsonl` — 质量样板（已按最新规范修订）
3. 你负责的各视频：`benchmarks/eval_build/corpus_manifest/<video_id>.md`

## 禁止
- 不要读/改 `samples_review.md`（给人看的，不是标准）
- 不要读/改其他批次的 jsonl
- 不要写数据库、不要跑评测脚本
- 不要覆盖 `samples.jsonl`

## 每视频配额（本批只做单视频题）
对清单中的**每个** video_id：
1. **必须** 1 道 `detail`（禁止点名视频；全库事实尽量唯一；题面改写）
2. 若 `chunk_count >= 40`：再加 1 道 `detail` **或** 1 道 `multi_evidence`（二选一，优先 multi_evidence 若能找到真跨 chunk 叙事）
3. 若 L2/L3 主题看起来正确：再加 1 道 `summary`（**必须点名**可消歧锚点；`reference_points` 3–7 条；`summary_eligible=true`）
4. 若 video_id 为 `oYxTTirKY8M`：可出 detail/multi_evidence；summary 若出则 **必须** `summary_eligible=false`（L2 已知坏）
5. 健身/饮食/增肌同簇视频：detail 尽量用**本视频独有数字/术语**，并打 `tags: ["hard_negative"]`

**本批不要写** multi_hop / unanswerable / memory（全局另做）。

## 字段
严格 EVAL_SPEC §4。`source`: `"llm_draft+human_edit"`。  
`id`: `q_<type>_<video_id>_01`（同视频第二道 detail 用 `_02`）。

## 自检（写入前）
对每题过 §6；detail/multi_evidence 过 §7（禁止 ≥8 汉字或 ≥5 英文实词连续照抄 gold）。  
打开 manifest 确认 gold `chunk_index` 存在且含答案；在 `notes` 写一句支撑句摘录。

## 产出
只写一个文件：`benchmarks/eval_build/batches/<BATCH_ID>.jsonl`  
一行一题 JSON，UTF-8，无 markdown 包裹。

完成后在最终回复列出：n_questions、by_type 计数、跳过 summary 的视频及原因、拿不准的题 id。
