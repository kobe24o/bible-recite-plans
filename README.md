# 背诵助手公开计划

这是“背诵助手”App 默认读取的公共计划清单，无需登录或付费服务器。

- 数据文件：[`cloud-plans.json`](cloud-plans.json)
- 协议版本：`1`
- 当前预置：《圣经经典篇章》20 段、《每卷书钥节》66 段

App 只导入 `push: true` 的计划。已导入手机的计划不会因为后续取消推送而自动删除；云端经文范围只读，用户仍可在本机修改译本和日期。

其他团队可以复制本仓库结构，发布同协议的 JSON，然后在 App 中填写自己的公开 HTTPS Raw 地址；也可以直接下载 JSON 后通过文件导入。

## 答题题库工具

题库文件（`quiz-bank-*.json`）只保存题目元数据，**不保存经文原文、答题记录或 API Key**；App 与批量工具都以本仓库的本地原文 SQLite 为唯一经文来源。题库必须拆分成小于 10MB 的分片（参见「分片规则」）。

```text
scripture/cmn-cu89s/scripture.sqlite  新标点和合本（简体）原文数据库
scripture/cmn-cu89s/LICENSE.txt       上游授权与来源
tools/generate_quiz_bank.py           串行批量调用 OpenAI 兼容模型并严格校验
tools/merge_quiz_banks.py             合并多个导出题库、按位置去重
tools/publish_quiz_snapshot.py        暂存整套 replace 分片后一次发布稳定快照
tools/split_quiz_bank.py              兼容旧命令名，转发至稳定快照发布器
tools/update_quiz_bank_index.py       更新 SHA-256、大小与 revision
tools/quiz_bank_stats.py              按译本统计节覆盖率与平均题数
tools/quiz_lexicon.py                 发布端词典、完整词条边界与每节长度配额
tools/audit_quiz_bank_quality.py      审计残词、释义泄漏和笼统释义并输出 JSON/Markdown
tools/repair_quiz_bank_quality.py     仅确定性修复唯一词典词条，其余问题题目剔除
tools/validate_quiz_bank.py           校验格式、重复位置、原文 UTF-16 下标、索引和质量规则
tools/sanitize_quiz_meanings.py       清理会泄露答案词的既有释义
tools/prune_unimportable_quiz_questions.py 移除本机原文无法导入的题目
```

原文为 eBible 提供的 `cmn-cu89s`，公共领域；来源、SHA-256 与获取日期记录在同目录的 `LICENSE.txt`、`manifest.json`。SQLite 的 `verse_unit` 表包含卷、章、起止节、经文及状态；工具只使用 `present` 且一节对应一个 unit 的经文。

### 批量生成

Python 标准库即可运行。API Key 只通过环境变量传入，绝不可写进命令、代码、Git 或 JSON：

```powershell
$env:QUIZ_MODEL_API_KEY = '你的密钥'
python tools/generate_quiz_bank.py `
  --base-url https://open.bigmodel.cn/api/paas/v4 `
  --model glm-4.7-flash `
  --from GEN:1:1
```

先预览而不请求模型：

```powershell
python tools/generate_quiz_bank.py --dry-run `
  --base-url https://open.bigmodel.cn/api/paas/v4 --model glm-4.7-flash `
  --from GEN:1:1
```

脚本默认使用简体和合本 `cmn-cu89s`，一次发送 5 节、**严格串行**调用，适合只有 1 并发额度的模型账户。每次成功写入连续的一批题目后，会将最后位置记录到本机 `tools/generation_progress.json`（该文件已被 Git 忽略）。下次不传 `--from` 时，会自动从该位置的下一节继续；可随时用 `--from 卷:章:节` 覆盖进度并指定精确断点，例如 `--from GEN:12:1`。如果一批内出现未通过校验的节，脚本会保存已通过题目但停在断点前，防止跳过失败节。如只想处理固定范围，仍可使用 `--book GEN --chapter 1 --start-verse 1 --end-verse 31`。

模型批处理可以为同一节提供多题，但最终发布只保留完整、不重叠的合格词条：少于 20 个汉字的经文最多 1 题，20–39 最多 2 题，40–69 最多 3 题，70–99 最多 4 题，100 字及以上最多 5 题。短节可以为 0 题；绝不为达到上限而填充残词。输出为题库格式 v2，不会写入经文文本。

### AI 生成与发布规则（必须遵守）

- 选词必须是与该节原文精确匹配、可独立回答的实词；优先人物、地名、专名、具体事物、核心动词和形容词。补题时必须选取与该节已有题目**不同且不重叠**的位置。
- 不得选虚词、代词、数字、标点、残缺字串，也不得选“某人说/回答/吩咐”等发话标签。无法选到合适词时宁可跳过该节。
- `start`、`end` 使用 UTF-16 下标（起始含、结束不含）；写入前必须以 `scripture/cmn-cu89s/scripture.sqlite` 重新切片验证，绝不能相信模型给出的下标或原文。
- `meaning` 必须是具体、独立且不含答案词的释义；不得使用“人名”“地名”“专名”“人物”“地点”等笼统类别，也不得引用、复述或改写该节原文。已收录的词典条目必须采用词典释义。
- 题库中不得保存 `verseText`、API Key、答题记录或其他个人数据。任何新增题目都须通过 `tools/validate_quiz_bank.py`；必要时先运行 `tools/sanitize_quiz_meanings.py` 清理旧释义，或运行 `tools/prune_unimportable_quiz_questions.py` 移除无法被 App 本机原文校验通过的题目。
- 发布前必须先冻结生成任务，运行质量审计、确定性修复和带 `--lexicon`、`--meaning-rules` 的校验。`revision` 是全局单调递增的发布序号，**绝不可回退、重置或复用**；索引只引用仓库内的相对 JSON 分片，禁止 `/tmp`、绝对路径或未提交文件。发布后必须再次校验 SHA-256、字节数和 revision。

### 覆盖率与平均题数

```powershell
python tools/quiz_bank_stats.py --bank quiz-bank.json
```

默认统计简体和合本，输出总节数、已有题目的节覆盖率、题目总数、平均每节题数（按全部节与按已覆盖节各一项）以及达到 5 题的节数。其它译本可以重复指定原文数据库：

```powershell
python tools/quiz_bank_stats.py --bank quiz-bank.json `
  --translation cmn-cu89s=scripture/cmn-cu89s/scripture.sqlite `
  --translation cmn-cu89t=scripture/cmn-cu89t/scripture.sqlite
```

### 分片规则

题库文件（`quiz-bank-*.json`）**每个分片必须小于 10MB**。当单个题库文件超过 10MB 时，必须拆分成多个分片：

```powershell
# 发布质量 v3 稳定快照（revision 必须显式且严格递增）
python tools/publish_quiz_snapshot.py --input quiz-bank.json --output-dir . `
  --index quiz-bank.index.json --revision 702
```

**分片策略**：优先填满序号小的分片。当新增题目时，只有最后的分片会增长，减少 git 中变更的文件数量。例如：
- 初始拆分为 `quiz-bank-01.json` (10MB) 和 `quiz-bank-02.json` (5MB)
- 新增题目后可能变为 `quiz-bank-01.json` (10MB)、`quiz-bank-02.json` (10MB) 和 `quiz-bank-03.json` (3MB)
- 此时只有 `quiz-bank-02.json` 和 `quiz-bank-03.json` 发生变化

拆分后的文件命名为 `quiz-bank-01.json`、`quiz-bank-02.json`、...，索引 `quiz-bank.index.json` 会列出所有分片的路径、SHA-256 和字节数。App 会先下载小索引，然后按需下载各分片。

**重要**：质量 v3 发布必须显式传入新的 `revision`；发布器拒绝复用或回退的 revision。它先在临时目录写完并实际计算每个 UTF-8 分片的大小和 SHA-256，再切换分片和索引。索引写入 `snapshotMode: "replace"`、`qualityVersion: 3`，让 App 在全部下载并校验完成后替换本地活动题库。

### 合并与发布索引

```powershell
# 合并多个题库文件
python tools/merge_quiz_banks.py -o quiz-bank.json bank-a.json bank-b.json

# 冻结生成后：审计、修复并发布一个完整 replace 快照
python tools/audit_quiz_bank_quality.py --bank quiz-bank.json `
  --quality-report reports/audit.json
python tools/repair_quiz_bank_quality.py --input quiz-bank.json --output quiz-bank-v3.json `
  --quality-report reports/repair.json
python tools/validate_quiz_bank.py --bank quiz-bank-v3.json `
  --lexicon lexicon/bible_terms.v1.json --meaning-rules lexicon/meaning_rules.v1.json `
  --quality-report reports/final-audit.json
python tools/publish_quiz_snapshot.py --input quiz-bank-v3.json --output-dir . `
  --index quiz-bank.index.json --revision 702

# 校验所有分片
python tools/validate_quiz_bank.py --bank quiz-bank-01.json
python tools/validate_quiz_bank.py --bank quiz-bank-02.json
python tools/validate_quiz_bank.py --index quiz-bank.index.json

# 提交
rm quiz-bank.json  # 删除合并用的临时文件
git add quiz-bank-*.json quiz-bank.index.json
git commit -m "chore: update quiz bank"
git push
```

合并工具兼容旧版 v1 导出，但会丢弃旧文件中重复的 `verseText`；同一译本、卷、章、节、开始/结束位置视为同一题，按输入顺序保留第一题。校验工具会拒绝 v1 输出、`verseText`、重复位置、无意义功能词、答案词前缀、原文中不存在的节以及不匹配的 UTF-16 切片；可通过重复的 `--translation` 校验其它译本。索引工具会计算文件字节数与 SHA-256，并自动将 `revision` 加一；App 会先检查小索引，只有哈希改变才下载题库。
