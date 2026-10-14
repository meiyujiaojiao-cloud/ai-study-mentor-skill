# AI Study Mentor Skill

[English](README.en.md) | [简体中文](README.md)

**[v0.6.5 Stable · Latest Release](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.6.5) · [Historical experimental v0.6.3](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.6.3-experimental.1)**

**AI Study Mentor v0.6.5 is the personal stable-use edition**, a single-user local learning framework for Agents that support Skills, file access and Python tools. Stable is a maintenance designation, not evidence of improved learning, guaranteed grades or universal platform compatibility.

Included capabilities:

- Explicit material registration, outline drafts and confirmed PDF/PPTX/TXT import.
- Course/chapter/point management, goal diagnosis, teaching, exercises and error feedback.
- Separate evidence observations for understanding, technical expression, application and transfer.
- Authorized persistence, fresh-session recovery, unfinished questions and related-task review.
- Optional unit checks and workflow states; assessment completion is not full mastery.
- Read-only review suggestions, distinguishing suggested dates from actual attempts without inferring forgetting from absence.
- Optional actual-session notes, separating materials, learner wording, evidence and AI suggestions; new files preserve history.

**Flow: import → confirm goals → learn/practice → optional unit check/notes → authorize progress saving → restore or view review suggestions.** See the [Chinese user guide](docs/普通学生使用指南.md), [review guide](docs/V0.6.5复习使用指南.md) and [Stable release notes](docs/v0.6.5发布说明.md).

192 automated checks and the official Skill validator passed before release. These validate formats, file safety and compatibility, not teaching semantics or learning outcomes. Large-scale real-user testing remains incomplete; note quality, unit tasks and real-course continuity require real use.

Local features require file permissions and Python3.10+; PDF reading additionally requires pypdf. No OCR/decryption; legacy PPT requires conversion. Outline extraction is not full textbook understanding. Other Agents are not fully validated. DeepSeek retains [manual handoff](docs/DeepSeek使用指南.md), without API integration, automatic sync or local-file access; its standalone instructions do not automatically gain later features. No databases, profiles, background reminders, multi-user or website features. Keep personal data outside Git.

Historical reports retain their original scope; earlier experimental releases and tags are preserved.

## Who this is for

- **AI developers** exploring or integrating error diagnosis, learning evidence and learning continuity.
- **Agent users** loading teaching workflows in Skills-capable environments and evaluating their behavior.
- **People building AI learning assistants** who want to reuse and adapt these rules.

This repository provides a framework and Skill component for users who can configure an Agent environment. **Study Mentor Web is the product entry point for ordinary students.** It is a separate product, not included in this Skill repository; its own documentation defines its features and availability.

The text-based teaching rules are intended for reuse in environments supporting Agent Skills. Installation and behavior have primarily been tested in Codex; compatibility with every Agent has not been verified. Other environments must check skill discovery, reference loading, file permissions and Python execution for local saving.

See the [historical V0.3 notes](docs/V0.3实验版本说明.md); the current scope and limitations are in the Stable notes above.

## Why an explanation may not lead to understanding

An ordinary AI can explain clearly and may adapt its teaching. A single exchange, however, may leave the cause of an error unclear, provide too little evidence of understanding, or lead to continued use of an unsuitable explanation. A correct explanation does not establish that the learner understands it.

V0.2 attempts to make adaptation more explicit:

- **Error classification:** distinguish concept confusion, misreading, calculation errors, prerequisite gaps and reasoning gaps using answers and reasoning; ask for evidence when the cause is uncertain.
- **Targeted explanations:** choose contrasting examples, step-by-step correction or one necessary prerequisite based on the current evidence.
- **Different related retests:** collect new evidence of understanding with a different task.
- **Feedback-driven adjustment:** update the hypothesis and teaching approach as responses arrive, while respecting skipping and changes of goal.

**V0.2 has only been evaluated with simulated cases; it has no real-learner study data.** These rules remain experimental. They do not establish improved real-world learning outcomes, and the preregistered threshold for a clear improvement over the previous version was not met. See the [V0.2 experimental report](tests/V0.2对比报告.md).

## V0.3 Phase 3: save, resume and optional review

Ask to save your progress. The skill explains the necessary summaries and waits for your confirmation and an external data location. It does not save full chats or textbook content. Declining saving preserves ordinary teaching. Storage requires Python 3.10 or later, with no third-party dependencies.

In a new chat, select this skill, ask to continue your previous learning, and provide the complete path to learning-state.json. After reading it, the skill summarizes the goal, verification status and next step, then waits for continue, review or change-goal confirmation. Unanswered questions remain unanswered. When review is due, choose review first, continue learning or change the goal. Review uses a different related task without revealing its answer.

No directory scanning or invented history is permitted. Missing or unreadable records and failed saves are reported explicitly. See [saving and recovery rules](references/学习连续性.md) and the [Phase 2 acceptance record](tests/V0.3连续性验收.md). After an actual attempt, review can be suggested for the next day. Only a new task at least 24 hours after the latest attempt qualifies as delayed. Independent correct reasoning passes that check; hinted answers do not establish independent understanding, errors route to the existing diagnosis rules, and skipping changes nothing. A delayed independent pass suggests another check in three days; other review outcomes suggest the next day. These are experimental intervals, not a validated forgetting model. There are no background reminders, learner profiles or independent strategy recommendations. See the [review rules](references/自适应复习.md) and [Phase 3 acceptance record](tests/V0.3第三阶段验收.md).

Phase 3 checks: 35 storage/recovery/review tests and 7 file checks passed; two fresh-session model cases completed. Delays used an explicit simulated clock, not real cross-day or real-learner evidence. These are historical phase results; see the Phase 3 record.

Additional pre-release checks passed for English teaching, authorized saving, fresh-session recovery, same-day related-task review and switching to Chinese, plus independent Chinese A–E regressions. Real-clock day one is complete; day two awaits 24 actual hours. The three-person usability trial is prepared but not executed. See the [pre-release acceptance report](tests/V0.3发布前验收.md); full acceptance remains incomplete. The maintainer authorized an experimental pre-release with these disclosed limitations; this does not imply all acceptance gates passed.

For the personal pilot, see the [Chinese usage guide](examples/真实使用指南.md) and [blank feedback template](tests/个人真实使用记录模板.md). Keep completed feedback outside the repository. The [V0.3 pre-release](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.3.0-experimental.1) documents historical features; install v0.6.5 from the Release link above; the v0.1.3 stable download does not include them.

## Install

Use your Agent's skill installation mechanism to load the complete folder, preserving the relative layout of SKILL.md, references/ and scripts/. The following is a **tested Codex installation example**; paths and invocation syntax may differ in other clients.

1. Download the v0.6.5 Release linked above. Extract the ZIP and rename the extracted folder to `ai-study-mentor-skill` if it has a branch or version suffix.
2. Copy the complete folder into `~/.agents/skills/`. For a project-only installation, use `.agents/skills/` inside that project. Keep `SKILL.md` directly inside the skill folder, with all references included. Compare an existing installation before replacing it.
3. On Windows, press **Win + R**, enter `%USERPROFILE%`, then create/open `.agents` and its `skills` folder. Copy the whole skill folder there.
4. Start a new Codex chat. Type `$ai-study-mentor-skill`, select the matching skill candidate, and send: **Use $ai-study-mentor-skill to teach me percentage discounts in English.**
5. Answer its goal and baseline questions, then attempt the actual exercise and explain your reasoning. If the skill is missing, check the folder layout and restart Codex. Some clients also scan `~/.codex/skills`; use the location your client's skill list actually recognizes, rather than installing duplicate copies.

No Python is needed for conversation-only teaching; local saving and recovery require Python 3.10 or later. No extra API client is needed. You provide the Agent runtime, account and model service, subject to their existing limits. Ordinary model replies alone do not prove the skill was loaded.

## Teaching and languages

The rules cover goal/baseline questions, one-concept explanations, exercises, targeted error feedback, different related retests, simpler explanations, occasional off-topic questions, and skipping without marking mastery.
The default teaching language follows the user's input; an explicit language request takes priority. Language switches preserve the current task and evidence. Examples should be natural and culturally appropriate, not mechanically translated.

Chinese has historical CLI and maintainer-operated desktop A–E evidence. After the language update, a new Chinese A–E regression and an English core teaching loop passed, including error correction and retesting. Explicit English preference and an English-to-Chinese switch preserved the task state. English-only simplification and off-topic scenarios were not separately tested. See the [multilingual test record](tests/多语言教学验收.md) for the latest English and language-switch results and their exact scope. Japanese and other languages have not been behavior-tested. This is not a claim of universal multilingual support.

Without authorized saving, state exists only within the current conversation. Recovery uses only the last successfully saved local record. Full textbook semantic understanding, automatically generated complete curricula, separate teaching interfaces, cloud storage, a knowledge memory library and a callable API are not implemented. Local outline import is provided in this experimental release. This repository does not include the Study Mentor Web implementation. [V0.2](docs/V0.2设计规划.md) now focuses solely on error diagnosis: concept confusion, misreading, local calculation errors, prerequisite gaps, reasoning gaps and insufficient evidence. When the cause is unclear, ask one diagnostic question and update the hypothesis when new evidence arrives. See [diagnosis rules](references/错因诊断.md). Curiosity-led courses and memory features are deferred.

## Validation

Optional maintainer checks (Python standard library):

```sh
python tests/验证文件.py
```

These check structure, local links and common secret/path patterns; they do not execute teaching or guarantee detection of every secret. The official skill-creator validator separately requires PyYAML. On Windows, run it with Python's `-X utf8` option for UTF-8 Chinese files.

[CLI record](tests/真实教学验收记录.md) and [desktop record](tests/桌面教学验收记录.md) cover percentage discounts, not all topics/models or long-term learning outcomes. Implicit activation and false-positive activation remain untested; explicit selection is recommended. Supporting reference documents are currently in Chinese, although teaching output follows the language rules.

## License

[MIT](LICENSE) — Copyright (c) 2026 AI Study Mentor.
No third-party textbooks, model code or runtime libraries are bundled. Do not commit personal study records, credentials or API keys. The first public release, [v0.1.3](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.1.3), is available.

## V0.2 comparison

See the [comparison report](tests/V0.2对比报告.md), [12 frozen cases](tests/V0.2案例.json), [rubric](tests/V0.2评分标准.md) and [standard-library runner](tests/运行对照测试.py). The same existing model is used for ordinary Codex, a frozen v0.1.3 snapshot and V0.2; scoring answers are not sent to the tested model. Four cases are held out from development-output review.

These are developer-simulated learner responses, not new real-learner evidence. One run per case and a developer-involved evaluator limit confidence. Retest design is assessed separately from actual learning improvement. Updated rules alone do not establish superiority over ordinary Codex. File checks now include dataset integrity and CLI completion parsing (7 checks); see the report for actual results.

Installation is unchanged. This separate review workspace does not replace the current installed stable copy. Compare and back up before replacing an existing installation, and avoid duplicate same-name skills. This candidate is not a V0.2 Release.

Held-out scores (out of 10): ordinary Codex 8.50, v0.1.3 9.50, V0.2 10.00. **The preregistered threshold of at least +1 versus both baselines was not met.** The official validator and 7 file checks passed. The account usage limit blocked the remaining full Chinese A–E and fresh English/language-switch regressions. Prefer the published stable version while this candidate awaits review.

## V0.4 minimal manual handoff (development branch, unreleased)

After saving in your current Skill environment, use the [read-only exporter](scripts/export_learning.py) to produce a Markdown handoff and an exact JSON copy. Paste the [portable teaching instructions](docs/DeepSeek教学指令.md) and record into DeepSeek. Bring its return summary back for human review and explicit authorization before saving with the original V0.3 tools. See the [Chinese usage guide](docs/DeepSeek使用指南.md) and [acceptance status](tests/V0.4最小接续验收.md).

Codex is a tested environment example, not a requirement. The portable instructions contain no local paths and need no Codex installation. An ordinary DeepSeek chat does not gain local file access or save capability. No API, automatic import, sync, unfinished multi-course system, or new runtime dependencies are included. Export requires Python 3.10+. The V0.3 schema, teaching rules, persistence and review logic remain unchanged. A user-reported statistics session supports manual recovery and return-summary generation, with an observed error: an unanswered follow-up was labeled as completed with a hint. Instructions now clarify the boundary; the fix awaits behavioral retesting. Local save-back and the planned math/Python cases remain unverified; export checks are not teaching evidence. Keep personal exports outside repositories and review them before sharing. The portable instructions and guide are currently in Chinese; this addition does not claim an English DeepSeek regression.

## V0.4.1 first-use usability preparation (unreleased)

Only entry documentation, feedback and test support change; teaching, persistence and review logic remain unchanged. No learning algorithms, profiles, databases or web features are added. The [five-minute protocol](docs/首次使用测试流程.md) separates independent success, assisted success, failure and inconclusive attempts. Full teaching, manual saving and fresh-chat recovery are observed separately, not assumed to fit within five minutes.

Use the [voluntary feedback form](docs/用户反馈收集表.md) and [blank real-user test record](tests/V0.4.1真人测试记录模板.md), both currently in Chinese. Keep completed copies outside the repository; share only consented anonymous observations. No new V0.4.1 human sessions have been run. Prior V0.4 statistics feedback is not counted as new evidence. No broad usability or learning-effect claim follows from this preparation.

## V0.5 Personal Learning Edition

Personal data stays outside Git. Each point retains the unchanged V0.3 record format and persistence/review tools. Courses keep separate evidence, unfinished questions and review state. The V0.5 registration command records only user-provided names, locations, chapters and goals; it does not parse materials. V0.6 adds explicit local outline import as a separate operation. Open the selected data folder as a local project, or explicitly provide its generated entry file, before asking to continue. An arbitrary fresh chat cannot discover the directory automatically. DeepSeek still uses the existing manual handoff.

See the [library contract](references/个人学习库.md), [file-operation checks](tests/个人学习库验证.py) and [personal continuity acceptance](tests/V0.5个人连续使用验收.md). Tests use fictional file fixtures, not model-simulated learners. Real next-day use and course switching await the owner's feedback. No profiles, databases, cloud sync, automatic plans or reminders are added; improved learning outcomes are not established.

## V0.6 course and material entry

Course intake and optional-file registration remain available. When explicitly given a PDF, PPTX or TXT file for import, the local tool extracts outline candidates, presents a private chapter draft and waits for confirmation before adding chapters and material links. Original files and learning evidence are preserved. PDF reading requires pypdf in the selected Python environment; missing dependencies are reported and never installed automatically. Legacy .ppt requires user conversion to .pptx; scanned PDFs have no OCR. Outline extraction is not full textbook understanding. No internet search, download, automatic upload or copyright determination is performed. See the [Chinese import guide](docs/教材导入指南.md).

The V0.5 index and V0.3 records are unchanged. Private course.json and material.json supplements hold intake and material links; 教材导入记录.json links confirmed chapters to their source. The existing index remains authoritative for goals/chapters, and original records for evidence. Stale projections and partial saves are reported. See the [contract](references/教材与课程入口.md) and [acceptance record](tests/V0.6教材课程入口验收.md). Actual textbook import, owner learning and next-day restoration await real use. Synthetic file checks are not learning evidence. DeepSeek handoff is unchanged; no databases, profiles, reminders, cloud sync or automatic yearly plans are added.

## V0.6.1 learning experience refinement

Exercises use the current knowledge point and actually read chapter content when available. Application, contextual and transfer tasks require reasoning; source claims must distinguish textbook adaptation from original tasks. Type, chapter source and transfer labels stay in existing task_summary text, without new schema fields or changes to prior evidence. Feedback shows observable findings, necessary explanations and next steps rather than internal drafts. Optional eight-item learning summaries preserve errors and unverified content; summaries are not evidence or saved progress. Recovery shows a factual welcome-back view and waits for confirmation, keeping unfinished questions.

Exam, understanding and exploration are user-selected conversational emphases, not learner profiles; preference persistence is not added. See the [experience rules](references/学习体验.md) and [pending real-user acceptance](tests/V0.6.1真实体验验收.md). Storage, diagnosis principles, import structures and manual DeepSeek handoff instructions are unchanged; the independently copied DeepSeek instructions do not automatically gain these refinements. File compatibility checks do not demonstrate exercise quality, actual model behavior or improved learning.

## V0.6.2 evidence assessment

Conceptual understanding, technical expression, application and transfer are observed separately from actual answers, with item-specific verified/pending evidence rather than a total mastery judgment. Exam focus checks formal wording, personal explanations and applications across tasks. A wording omission can remain an open check for a naturally related task; real errors still use existing diagnosis. Earlier correct evidence is retained, and untested dimensions are not downgraded. Task use is explained honestly when asked, without hidden profiling.

Observations stay in response_summary text; reasoning_summary contains only the learner's actual reasoning or null. Original verification_status remains the existing item/retest status, not a four-dimensional score. Persistence, material import and manual DeepSeek handoff are unchanged. See [assessment rules](references/教学评估.md) and [acceptance record](tests/V0.6.2教学评估验收.md). This is Agent guidance, not an automatic grading engine; standalone DeepSeek instructions are unchanged and real-course validation is pending.

## V0.6.3 optional learning notes

At session end, offer one choice: generate review notes, continue learning, or skip notes. No automatic generation or saving. Notes cover actual session concepts, learner explanations, observed errors, verified/pending abilities, real questions and answers, and review suggestions. AI additions must not be presented as the learner's understanding. Course/chapter/point and evidence references use actual context; unsaved work is clearly identified.

Authorized file saving creates a separate Markdown file without overwriting earlier notes or changing learning state. Deleting notes cannot delete evidence. Existing teaching, assessment, import, persistence and manual DeepSeek handoff remain unchanged. See [rules](references/学习笔记.md), [template](examples/学习笔记模板.md) and [acceptance](tests/V0.6.3学习笔记验收.md). The saver does not generate or semantically validate notes; real-user content quality remains pending, and standalone DeepSeek instructions are unchanged.

## V0.6.4 optional unit checks (included in v0.6.5)

After explicitly finishing a unit stage, users may choose a check, notes or stopping. Three to five tasks cover understanding, technical expression, application and combined transfer, one real answer at a time. Reports describe supported strengths, open checks and next-step choices rather than scores or total mastery. Authorized saving uses a separate record through existing tools, preserving point evidence and notes. Restoring the check requires its explicit record path; no automatic unit index is added. See [rules](references/单元检测.md), [template](examples/单元检测报告模板.md) and [acceptance](tests/V0.6.4单元检测验收.md). Model behavior and real-user task quality remain untested; standalone DeepSeek instructions are unchanged.
