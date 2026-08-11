# 背诵助手公开计划

这是“背诵助手”App 默认读取的公共计划清单，无需登录或付费服务器。

- 数据文件：[`cloud-plans.json`](cloud-plans.json)
- 协议版本：`1`
- 当前预置：《圣经经典篇章》20 段、《每卷书钥节》66 段

App 只导入 `push: true` 的计划。已导入手机的计划不会因为后续取消推送而自动删除；云端经文范围只读，用户仍可在本机修改译本和日期。

其他团队可以复制本仓库结构，发布同协议的 JSON，然后在 App 中填写自己的公开 HTTPS Raw 地址；也可以直接下载 JSON 后通过文件导入。

## 答题题库工具

`quiz-bank.json` 只保存题目元数据，**不保存经文原文、答题记录或 API Key**；App 与批量工具都以本仓库的本地原文 SQLite 为唯一经文来源。

```text
scripture/cmn-cu89s/scripture.sqlite  新标点和合本（简体）原文数据库
scripture/cmn-cu89s/LICENSE.txt       上游授权与来源
tools/generate_quiz_bank.py           串行批量调用 OpenAI 兼容模型并严格校验
tools/merge_quiz_banks.py             合并多个导出题库、按位置去重
tools/update_quiz_bank_index.py       更新 SHA-256、大小与 revision
tools/quiz_bank_stats.py              按译本统计节覆盖率与平均题数
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

脚本默认使用简体和合本 `cmn-cu89s`，一次发送 5 节、**严格串行**调用，适合只有 1 并发额度的模型账户。`--from 卷:章:节` 可以在每次启动时指定精确断点，随后按圣经全书顺序继续；例如完成创世记一部分后，下次可传 `--from GEN:12:1`。如只想处理固定范围，仍可使用 `--book GEN --chapter 1 --start-verse 1 --end-verse 31`。

每节只收一题；模型返回的 UTF-16 下标、答案切片、词性、解释对象和无意义词规则都会在本机原文上重新验证。已有某节 5 题时默认不再请求；可用 `--max-per-verse` 调整。输出为题库格式 v2，不会写入经文文本。

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

### 合并与发布索引

```powershell
python tools/merge_quiz_banks.py -o quiz-bank.json bank-a.json bank-b.json
python tools/update_quiz_bank_index.py --bank quiz-bank.json --index quiz-bank.index.json
git add quiz-bank.json quiz-bank.index.json
git commit -m "chore: update quiz bank"
git push
```

合并工具兼容旧版 v1 导出，但会丢弃旧文件中重复的 `verseText`；同一译本、卷、章、节、开始/结束位置视为同一题，按输入顺序保留第一题。索引工具会计算文件字节数与 SHA-256，并自动将 `revision` 加一；App 会先检查小索引，只有哈希改变才下载题库。
