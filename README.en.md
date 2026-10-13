# AI Study Mentor Skill

[English](README.en.md) | [简体中文](README.md)

**v0.3.0-experimental.1 · Pre-release · [Stable v0.1.3 · GitHub Release](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.1.3)**

**AI Study Mentor is an experimental adaptive learning framework for AI developers and Agent users**, organizing teaching workflows as Agent Skills instructions and reference files for building AI learning assistants. This v0.3.0-experimental.1 pre-release adds authorized local saving, recovery and optional related-task review to V0.2 error diagnosis.
The framework uses a loop: topic → goal and baseline → short explanation and example → one exercise → feedback → next step. Reading or skipping practice is not evidence of mastery; one correct answer verifies only that exercise.

## Who this is for

- **AI developers** exploring or integrating error diagnosis, learning evidence and learning continuity.
- **Agent users** loading teaching workflows in Skills-capable environments and evaluating their behavior.
- **People building AI learning assistants** who want to reuse and adapt these rules.

This repository provides a framework and Skill component for users who can configure an Agent environment. **Study Mentor Web is the product entry point for ordinary students.** It is a separate product, not included in this Skill repository; its own documentation defines its features and availability.

The text-based teaching rules are intended for reuse in environments supporting Agent Skills. Installation and behavior have primarily been tested in Codex; compatibility with every Agent has not been verified. Other environments must check skill discovery, reference loading, file permissions and Python execution for local saving.

See the [V0.3 release notes and limitations](docs/V0.3实验版本说明.md). v0.1.3 remains stable. Real-learner trials and real-clock day-two testing remain incomplete.

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

For the personal pilot, see the [Chinese usage guide](examples/真实使用指南.md) and [blank feedback template](tests/个人真实使用记录模板.md). Keep completed feedback outside the repository. Download the [V0.3 pre-release](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.3.0-experimental.1) for these features; the v0.1.3 stable download does not include them.

## Install

Use your Agent's skill installation mechanism to load the complete folder, preserving the relative layout of SKILL.md, references/ and scripts/. The following is a **tested Codex installation example**; paths and invocation syntax may differ in other clients.

1. Download this repository using **Code → Download ZIP**, or clone it. Extract the ZIP and rename the extracted folder to `ai-study-mentor-skill` if it has a branch or version suffix.
2. Copy the complete folder into `~/.agents/skills/`. For a project-only installation, use `.agents/skills/` inside that project. Keep `SKILL.md` directly inside the skill folder, with all references included. Compare an existing installation before replacing it.
3. On Windows, press **Win + R**, enter `%USERPROFILE%`, then create/open `.agents` and its `skills` folder. Copy the whole skill folder there.
4. Start a new Codex chat. Type `$ai-study-mentor-skill`, select the matching skill candidate, and send: **Use $ai-study-mentor-skill to teach me percentage discounts in English.**
5. Answer its goal and baseline questions, then attempt the actual exercise and explain your reasoning. If the skill is missing, check the folder layout and restart Codex. Some clients also scan `~/.codex/skills`; use the location your client's skill list actually recognizes, rather than installing duplicate copies.

No Python is needed for conversation-only teaching; local saving and recovery require Python 3.10 or later. No extra API client is needed. You provide the Agent runtime, account and model service, subject to their existing limits. Ordinary model replies alone do not prove the skill was loaded.

## Teaching and languages

The rules cover goal/baseline questions, one-concept explanations, exercises, targeted error feedback, different related retests, simpler explanations, occasional off-topic questions, and skipping without marking mastery.
The default teaching language follows the user's input; an explicit language request takes priority. Language switches preserve the current task and evidence. Examples should be natural and culturally appropriate, not mechanically translated.

Chinese has historical CLI and maintainer-operated desktop A–E evidence. After the language update, a new Chinese A–E regression and an English core teaching loop passed, including error correction and retesting. Explicit English preference and an English-to-Chinese switch preserved the task state. English-only simplification and off-topic scenarios were not separately tested. See the [multilingual test record](tests/多语言教学验收.md) for the latest English and language-switch results and their exact scope. Japanese and other languages have not been behavior-tested. This is not a claim of universal multilingual support.

Without authorized saving, state exists only within the current conversation. Recovery uses only the last successfully saved local record. Material parsing, full courses, three learning modes, cloud storage, a knowledge memory library and a callable API are not implemented. This repository does not include the Study Mentor Web implementation. [V0.2](docs/V0.2设计规划.md) now focuses solely on error diagnosis: concept confusion, misreading, local calculation errors, prerequisite gaps, reasoning gaps and insufficient evidence. When the cause is unclear, ask one diagnostic question and update the hypothesis when new evidence arrives. See [diagnosis rules](references/错因诊断.md). Curiosity-led courses and memory features are deferred.

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
