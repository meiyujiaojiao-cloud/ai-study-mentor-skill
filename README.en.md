# AI Study Mentor Skill

[English](README.en.md) | [简体中文](README.md)

**V0.2 development review (not released) · [Stable v0.1.3 · GitHub Release](https://github.com/meiyujiaojiao-cloud/ai-study-mentor-skill/releases/tag/v0.1.3)**

A Codex skill for guided self-study. This branch is a V0.2 review candidate for evidence-based error diagnosis and targeted strategy selection. It retains the learning loop: topic → goal and baseline → short explanation and example → one exercise → feedback → next step.
It is a set of Markdown instructions, not a standalone app. Reading or skipping practice is not evidence of mastery; one correct answer verifies only that exercise.

## Install

1. Download this repository using **Code → Download ZIP**, or clone it. Extract the ZIP and rename the extracted folder to `ai-study-mentor-skill` if it has a branch or version suffix.
2. Copy the complete folder into `~/.agents/skills/`. For a project-only installation, use `.agents/skills/` inside that project. Keep `SKILL.md` directly inside the skill folder, with all references included. Compare an existing installation before replacing it.
3. On Windows, press **Win + R**, enter `%USERPROFILE%`, then create/open `.agents` and its `skills` folder. Copy the whole skill folder there.
4. Start a new Codex chat. Type `$ai-study-mentor-skill`, select the matching skill candidate, and send: **Use $ai-study-mentor-skill to teach me percentage discounts in English.**
5. Answer its goal and baseline questions, then attempt the actual exercise and explain your reasoning. If the skill is missing, check the folder layout and restart Codex. Some clients also scan `~/.codex/skills`; use the location your client's skill list actually recognizes, rather than installing duplicate copies.

No Python or extra API client is needed to use the skill. Your own Codex account and model service provide execution and are subject to their existing limits. Ordinary model replies alone do not prove the skill was loaded.

## Teaching and languages

The rules cover goal/baseline questions, one-concept explanations, exercises, targeted error feedback, different related retests, simpler explanations, occasional off-topic questions, and skipping without marking mastery.
The default teaching language follows the user's input; an explicit language request takes priority. Language switches preserve the current task and evidence. Examples should be natural and culturally appropriate, not mechanically translated.

Chinese has historical CLI and maintainer-operated desktop A–E evidence. After the language update, a new Chinese A–E regression and an English core teaching loop passed, including error correction and retesting. Explicit English preference and an English-to-Chinese switch preserved the task state. English-only simplification and off-topic scenarios were not separately tested. See the [multilingual test record](tests/多语言教学验收.md) for the latest English and language-switch results and their exact scope. Japanese and other languages have not been behavior-tested. This is not a claim of universal multilingual support.

State exists only within the current conversation. Material parsing, full courses, three learning modes, cross-session storage, a knowledge memory library, a website and a callable API are not implemented. [V0.2](docs/V0.2设计规划.md) now focuses solely on error diagnosis: concept confusion, misreading, local calculation errors, prerequisite gaps, reasoning gaps and insufficient evidence. When the cause is unclear, ask one diagnostic question and update the hypothesis when new evidence arrives. See [diagnosis rules](references/错因诊断.md). Curiosity-led courses and memory features are deferred.

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
