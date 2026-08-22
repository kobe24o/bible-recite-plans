# 历史题库完整词与释义重审 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 151,663 道历史题中生成可追溯的完整词候选，并为通过候选写出具体、无答案泄露、受圣经事实约束的释义。

**Architecture:** 新增纯 Python 候选筛选器和释义审计器；它们复用现有 UTF-16、词典与严格结巴边界校验。重写器只读取通过候选、对应经文窗口与版本化的圣经知识条目，模型输出先落到 JSONL，再由确定性审计决定接收或隔离；第一阶段绝不修改发布分片或索引。

**Tech Stack:** Python 3、unittest、jieba、SQLite scripture、现有 OpenAI-compatible HTTP client、JSON/JSONL。

**Spec:** `docs/superpowers/specs/2026-08-21-historical-quiz-meaning-rewrite-design.md`

## Global Constraints

- 历史输入固定为 `e242fe2` 的索引和索引列出的全部 6 个分片，所有运行产物记录 commit、每个输入 SHA-256、题数和规则版本。
- 未通过完整词、位置、释义或经文事实审计的题必须隔离，不能以泛化释义进入候选输出。
- 释义不得包含 `word` 的规范化文本、不得复述本节原文、不得仅使用“人名”“地名”等泛词。
- 释义中的圣经知识必须来自经文窗口或版本化事实条目；事实不足时隔离。
- 阶段一不写 `quiz-bank-*.json`、`quiz-bank.index.json`，也不发布 revision。

---

### Task 1: 历史输入固定与候选判定接口

**Files:**
- Create: `tools/historical_quiz_candidates.py`
- Create: `tools/test_historical_quiz_candidates.py`
- Modify: `tools/audit_quiz_bank_quality.py`

**Interfaces:**
- Consumes: `validate_quiz_bank.slice_utf16`, `quiz_lexicon.load_terms`, `audit_quiz_bank_quality._is_partial_segmented_term`。
- Produces: `CandidateDecision(key: str, accepted: bool, reasons: tuple[str, ...], question: dict[str, object])` and `classify_question(question, scripture, terms, rules) -> CandidateDecision`。

- [ ] **Step 1: 写出失败测试**

```python
def test_classifier_accepts_exact_complete_dictionary_term():
    decision = classify_question(question("以色列", 0, 3), {"GEN:1:1": "以色列人"}, TERMS, RULES)
    self.assertTrue(decision.accepted)

def test_classifier_quarantines_fragment_and_position_error():
    self.assertEqual(
        classify_question(question("色列", 1, 3), {"GEN:1:1": "以色列人"}, TERMS, RULES).reasons,
        ("partial_lexicon_term",),
    )
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tools.test_historical_quiz_candidates -v`

Expected: FAIL，因为模块和 `classify_question` 尚不存在。

- [ ] **Step 3: 实现最小筛选器**

```python
@dataclass(frozen=True)
class CandidateDecision:
    key: str
    accepted: bool
    reasons: tuple[str, ...]
    question: dict[str, object]

def classify_question(question, scripture, terms, rules):
    findings = audit_questions([question], scripture, terms, rules)
    return CandidateDecision(question_key(question), not findings, tuple(f.code for f in findings), dict(question))
```

在 `audit_quiz_bank_quality.py` 中新增确定性拒绝：空白/标点、停用词、未获词典豁免的单字泛词、重复位置。保留既有“完整结巴 token 不误拒”的规则。

- [ ] **Step 4: 运行候选和原审计测试**

Run: `python -m unittest tools.test_historical_quiz_candidates tools.test_audit_quiz_bank_quality -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add tools/historical_quiz_candidates.py tools/test_historical_quiz_candidates.py tools/audit_quiz_bank_quality.py
git commit -m "feat: classify historical quiz word candidates"
```

### Task 2: 版本化圣经事实条目与释义规则

**Files:**
- Create: `lexicon/bible_context.v1.json`
- Create: `tools/bible_context.py`
- Create: `tools/test_bible_context.py`

**Interfaces:**
- Consumes: `LexiconTerm` 的 `term`、`aliases` 和经文引用。
- Produces: `ContextFact(term: str, kind: str, facts: tuple[str, ...], references: tuple[str, ...], source: str)` and `load_context_facts(path) -> dict[str, ContextFact]`。

- [ ] **Step 1: 写出失败测试**

```python
def test_context_fact_requires_specific_fact_and_reference():
    with self.assertRaises(ValueError):
        load_context_facts(write_json({"entries": [{"term": "某地", "kind": "place", "facts": ["地名"]}]}))

def test_context_fact_resolves_alias():
    facts = load_context_facts(valid_context_file())
    self.assertEqual(facts["法利赛人"].kind, "group")
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tools.test_bible_context -v`

Expected: FAIL，因为事实条目读取器不存在。

- [ ] **Step 3: 实现 schema 与种子条目**

`bible_context.v1.json` 每项包含 `term`、`aliases`、`kind`、至少一个具体 `facts`、至少一处 `references`、`source`。为高频人名、地点、族群、制度和职分加入可核查事实；拒绝泛化事实和无引用事实。`meaning_rules.v1.json` 增加 `forbiddenGenericPatterns`、`minimumMeaningChars`、`requiredKinds`。

- [ ] **Step 4: 运行测试**

Run: `python -m unittest tools.test_bible_context tools.test_quiz_lexicon -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add lexicon/bible_context.v1.json lexicon/meaning_rules.v1.json tools/bible_context.py tools/test_bible_context.py
git commit -m "feat: add sourced Bible context facts"
```

### Task 3: 受约束的释义改写器

**Files:**
- Create: `tools/rewrite_historical_quiz_meanings.py`
- Create: `tools/test_rewrite_historical_quiz_meanings.py`

**Interfaces:**
- Consumes: `CandidateDecision`、`ContextFact`、相邻经文窗口和 `generate_quiz_bank.call_model`。
- Produces: `RewriteDraft(key: str, meaning: str, source: str, evidence_references: tuple[str, ...])` and `rewrite_batch(candidates, context_facts, client) -> list[RewriteDraft]`。

- [ ] **Step 1: 写出失败测试**

```python
def test_prompt_forbids_answer_and_requires_fact_backed_meaning():
    prompt = build_rewrite_prompt(candidate("保罗"), context_fact("保罗"))
    self.assertIn("不得包含答案原文", prompt)
    self.assertIn("事实不足则返回 null", prompt)

def test_context_fact_draft_has_specific_non_leaking_meaning():
    draft = deterministic_draft(candidate("法利赛人"), context_fact("法利赛人"))
    self.assertNotIn("法利赛人", draft.meaning)
    self.assertIn("犹太", draft.meaning)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tools.test_rewrite_historical_quiz_meanings -v`

Expected: FAIL，因为重写模块不存在。

- [ ] **Step 3: 实现重写器**

对有 `ContextFact` 的题优先输出由具体事实组成的确定性草稿；其余题以本节前后各一节和已知事实调用现有兼容模型。系统提示强制 JSON `{key, meaning, evidenceReferences}`，要求只用提供事实、答案未知或不可靠时返回 `meaning: null`。API key 仅由环境变量读取，批次进度和原始模型响应仅写入 `reports/`。

- [ ] **Step 4: 运行测试**

Run: `python -m unittest tools.test_rewrite_historical_quiz_meanings -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add tools/rewrite_historical_quiz_meanings.py tools/test_rewrite_historical_quiz_meanings.py
git commit -m "feat: rewrite meanings with Bible context"
```

### Task 4: 释义审计与隔离输出

**Files:**
- Create: `tools/audit_rewritten_meanings.py`
- Create: `tools/test_audit_rewritten_meanings.py`
- Modify: `lexicon/meaning_rules.v1.json`

**Interfaces:**
- Consumes: `RewriteDraft`、`CandidateDecision`、`meaning_rules.v1.json`、`ContextFact`。
- Produces: `MeaningAudit(key: str, accepted: bool, reasons: tuple[str, ...])` and `audit_rewrite(question, draft, rules, facts) -> MeaningAudit`。

- [ ] **Step 1: 写出失败测试**

```python
def test_rejects_answer_leak_and_bare_category():
    self.assertFalse(audit_rewrite(q("耶路撒冷"), draft("耶路撒冷的城市"), RULES, FACTS).accepted)
    self.assertFalse(audit_rewrite(q("耶路撒冷"), draft("重要地名"), RULES, FACTS).accepted)

def test_accepts_specific_fact_backed_place_meaning():
    self.assertTrue(audit_rewrite(q("耶路撒冷"), draft("犹太人敬拜中心所在的城"), RULES, FACTS).accepted)
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tools.test_audit_rewritten_meanings -v`

Expected: FAIL，因为审计器不存在。

- [ ] **Step 3: 实现确定性审计**

检查规范化答案泄露、经文连续片段泄露、泛化模式、最小长度、必需区分信息、事实条目引用。审计器返回机器可读原因：`answer_leak`、`scripture_leak`、`generic_meaning`、`missing_distinguishing_fact`、`unsupported_bible_fact`。

- [ ] **Step 4: 运行测试**

Run: `python -m unittest tools.test_audit_rewritten_meanings tools.test_audit_quiz_bank_quality -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add tools/audit_rewritten_meanings.py tools/test_audit_rewritten_meanings.py
git commit -m "feat: audit rewritten quiz meanings"
```

### Task 5: 可复跑的 151,663 题阶段一流水线

**Files:**
- Create: `tools/review_historical_quiz_bank.py`
- Create: `tools/test_review_historical_quiz_bank.py`
- Create: `reports/historical-v1/.gitkeep`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 1–4 的模块，以及 `git show e242fe2:quiz-bank.index.json` 列出的 6 个历史分片。
- Produces: `input-manifest.json`、`candidates.jsonl`、`rewritten.jsonl`、`quarantine.jsonl`、`summary.md`。

- [ ] **Step 1: 写出失败测试**

```python
def test_report_assigns_every_input_question_once(tmp_path):
    result = review_questions([valid_question(), fragment_question()], fake_sources(), fake_rewriter())
    self.assertEqual(result.accepted_count + result.quarantine_count, 2)
    self.assertIn("partial_lexicon_term", result.quarantine[0]["reasons"])
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m unittest tools.test_review_historical_quiz_bank -v`

Expected: FAIL，因为端到端审阅器不存在。

- [ ] **Step 3: 实现流水线与报告**

CLI 必须使用 `--historical-revision e242fe2 --output-dir reports/historical-v1 --seed 20260821`；模型连接参数固定为 `--base-url-env QUIZ_MODEL_BASE_URL --model-env QUIZ_MODEL_NAME --api-key-env QUIZ_MODEL_API_KEY`。先读取历史索引及其列出的所有分片并写输入清单，再做候选筛选、可恢复批量重写、释义审计。每题恰好输出到 accepted 或 quarantine；输出按题目位置排序，摘要写明总数、每类原因、书卷、词长、释义来源和固定 100 条分层样本。

- [ ] **Step 4: 运行端到端测试与小批演练**

Run: `python -m unittest tools.test_review_historical_quiz_bank tools.test_historical_quiz_candidates tools.test_bible_context tools.test_rewrite_historical_quiz_meanings tools.test_audit_rewritten_meanings -v`

Run: `python tools/review_historical_quiz_bank.py --historical-revision e242fe2 --output-dir reports/historical-v1-smoke --seed 20260821 --limit 100 --dry-run`

Expected: 所有测试 PASS；小批产物的通过数与隔离数之和为 100，且不写发布题库。

- [ ] **Step 5: 提交**

```bash
git add tools/review_historical_quiz_bank.py tools/test_review_historical_quiz_bank.py reports/historical-v1/.gitkeep README.md
git commit -m "feat: add auditable historical quiz review pipeline"
```

### Task 6: 全量审阅、报告复核与发布门槛

**Files:**
- Create: `reports/historical-v1/input-manifest.json`
- Create: `reports/historical-v1/candidates.jsonl`
- Create: `reports/historical-v1/rewritten.jsonl`
- Create: `reports/historical-v1/quarantine.jsonl`
- Create: `reports/historical-v1/summary.md`

**Interfaces:**
- Consumes: Task 5 CLI 和模型环境变量 `QUIZ_MODEL_API_KEY`。
- Produces: 供用户审阅的完整候选/隔离报告；不产生发布快照。

- [ ] **Step 1: 运行全量候选筛选**

Run: `python tools/review_historical_quiz_bank.py --historical-revision e242fe2 --output-dir reports/historical-v1 --seed 20260821 --phase candidates`

Expected: `accepted + quarantine = 151663`，输入清单记录 `e242fe2` 和历史输入 SHA-256。

- [ ] **Step 2: 审阅高置信候选并批量改写**

Run: `python tools/review_historical_quiz_bank.py --historical-revision e242fe2 --output-dir reports/historical-v1 --seed 20260821 --phase rewrite --base-url-env QUIZ_MODEL_BASE_URL --model-env QUIZ_MODEL_NAME --api-key-env QUIZ_MODEL_API_KEY`

Expected: 所有进入改写阶段的题均得到通过释义或隔离原因；命令行和文件中不记录 API key。

- [ ] **Step 3: 运行全量质量审计**

Run: `python tools/review_historical_quiz_bank.py --historical-revision e242fe2 --output-dir reports/historical-v1 --seed 20260821 --phase audit`

Expected: accepted 题的 `answer_leak`、`scripture_leak`、`generic_meaning`、`unsupported_bible_fact` 均为 0。

- [ ] **Step 4: 复核报告并请求发布确认**

检查 `summary.md` 的统计和 100 条固定分层样本；向用户报告候选数、隔离数、原因分布和样本，不修改在线题库。仅在用户显式批准后另建发布计划。

- [ ] **Step 5: 提交可提交的报告元数据**

```bash
git add reports/historical-v1/input-manifest.json reports/historical-v1/summary.md
git commit -m "docs: record historical quiz review results"
```
