# AI Study Mentor Skill

[English](README.en.md) | [简体中文](README.md)

A Codex skill for guided self-study. Version 0.1.3 guides a small learning loop: topic → goal and baseline → short explanation and example → one exercise → feedback → next step.
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

State exists only within the current conversation. Material parsing, full courses, three learning modes, cross-session storage, a knowledge memory library, a website and a callable API are not implemented. [V0.2](docs/V0.2设计规划.md) is a design draft, not an enabled feature.

## Validation

Optional maintainer checks (Python standard library):

```sh
python tests/验证文件.py
```

These check structure, local links and common secret/path patterns; they do not execute teaching or guarantee detection of every secret. The official skill-creator validator separately requires PyYAML. On Windows, run it with Python's `-X utf8` option for UTF-8 Chinese files.

[CLI record](tests/真实教学验收记录.md) and [desktop record](tests/桌面教学验收记录.md) cover percentage discounts, not all topics/models or long-term learning outcomes. Implicit activation and false-positive activation remain untested; explicit selection is recommended. Supporting reference documents are currently in Chinese, although teaching output follows the language rules.

## License

[MIT](LICENSE) — Copyright (c) 2026 AI Study Mentor.
No third-party textbooks, model code or runtime libraries are bundled. Do not commit personal study records, credentials or API keys. Release status is determined by GitHub tags and Releases.
