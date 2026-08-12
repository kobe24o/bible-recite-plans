# User Instruction Memory

This file records user instructions, preferences, and teachings for reference in future interactions.

## Format

### User Instruction Entry
User instruction entries should follow this format:

[User Instruction Summary]
- Date: [YYYY-MM-DD]
- Context: [Mentioned scenario or time]
- Instructions:
  - [Content of user teaching or instruction, described line by line]

### Project Knowledge Entry
Entries discovered by the Agent during task execution should follow this format:

[Project Knowledge Summary]
- Date: [YYYY-MM-DD]
- Context: Discovered by Agent while performing [specific task description]
- Category: [Operations & Deployment|Build Methods|Testing Methods|Troubleshooting & Debugging|Workflow & Collaboration|Environment Configuration]
- Instructions:
  - [Specific knowledge points, described line by line]

## Deduplication Strategy
- Before adding a new entry, check for similar or identical instructions.
- If a duplicate is found, skip the new entry or merge it with the existing one.
- When merging, update the context or date information.
- This helps avoid redundant entries and keeps the memory file tidy.

## Entries

[Project Knowledge Summary]
- Date: 2026-08-12
- Context: Discovered by Agent while serializing quiz-bank generation across GEN/EXO/LEV/NUM
- Category: Build Methods
- Instructions:
  - 题库生成流程：读经文（cmn-cu89s 单节）→ 手写候选脚本到 /tmp/opencode/gen_candidates_*.py → 运行生成 /tmp/opencode/gen-bank-*.json → 单批校验 → 合并主库 quiz-bank.json → update_quiz_bank_index.py revision+1 → 双校验 → stats → git 提交推送。
  - 词条必须是原文实际存在的连续 UTF-16 切片，不得以 BOUNDARY_WORDS（generate_quiz_bank.py 内定义，含 上/下/不/以/会/但/到/等 等）开头或结尾；含复原字（如 法[柜]）或不连续的词（如 是强是弱 中的"强弱"）不可选。
  - 每批两章、每节一题（词+词性+释义+start/end），合并时同位置首次出现优先，去重应为 0。

[Project Knowledge Summary]
- Date: 2026-08-12
- Context: Discovered by Agent while pushing quiz-bank batches to remote
- Category: Workflow & Collaboration
- Instructions:
  - 远端 https://github.com/kobe24o/bible-recite-plans，默认分支 main；每批提交格式 `feat: add <BOOK> X-Y quiz bank questions and refresh index`，commit 尾附 `Co-authored-by: monkeycode-ai <monkeycode-ai@chaitin.com>`。
  - 用户要求串行逐批生成并追加到主库 quiz-bank.json，从上次结束处继续。
