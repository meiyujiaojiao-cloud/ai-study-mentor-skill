"""零依赖结构检查；不模拟模型、不证明教学行为。"""
from pathlib import Path
import re
import unittest

SENSITIVE = re.compile(
    r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|/(?:Users|home)/|\\\\[A-Za-z0-9][A-Za-z0-9_.-]*\\)"
)

ROOT = Path(__file__).resolve().parents[1]

class SkillFiles(unittest.TestCase):
    def test_frontmatter(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\nname: ([a-z0-9]+(?:-[a-z0-9]+)*)\ndescription: (.+)\n---\n", text)
        self.assertIsNotNone(match, "本项目使用两字段标量 frontmatter")
        self.assertEqual(match[1], ROOT.name)
        self.assertLessEqual(len(match[1]), 64)
        self.assertLessEqual(len(match[2]), 1024)

    def test_required_files(self):
        for name in ("SKILL.md", "README.md", "README.en.md", "LICENSE", ".gitignore",
                     "docs/新手安装与测试指南.md", "docs/首次发布资料.md",
                     "docs/V0.2设计规划.md", "tests/真实教学验收记录.md",
                     "tests/桌面教学验收记录.md", "tests/多语言教学验收.md",
                     "references/教学流程.md", "references/状态与扩展约定.md",
                     "examples/百分比教学示例.md", "tests/人工教学验证.md"):
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())
                self.assertTrue((ROOT / name).read_text(encoding="utf-8").strip())

    def test_local_links(self):
        count = 0
        for file in ROOT.rglob("*.md"):
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
                if "://" in link or link.startswith("#"):
                    continue
                target = (file.parent / link.split("#")[0]).resolve()
                self.assertTrue(target.is_relative_to(ROOT.resolve()))
                self.assertTrue(target.is_file(), f"{file.name}: {link}")
                count += 1
        self.assertGreater(count, 0)


    def test_public_content(self):
        # 只输出位置，不把可能命中的秘密打印进日志。
        for file in ROOT.rglob("*"):
            if ".git" not in file.relative_to(ROOT).parts and file.is_file() and file.suffix in {".md", ".py", ""}:
                text = file.read_text(encoding="utf-8")
                with self.subTest(file=str(file.relative_to(ROOT))):
                    self.assertIsNone(SENSITIVE.search(text), "疑似凭据或真实本机绝对路径")

    def test_public_scan_examples(self):
        blocked = ["sk-" + "a" * 24, "ghp_" + "a" * 24,
                   "github_pat_" + "a" * 24, "AKIA" + "A" * 16,
                   chr(67) + ":" + "/" + "Users/test/private.txt",
                   "/" + "home/user/secret", chr(92) * 2 + "server" + chr(92) + "private"]
        for sample in blocked:
            self.assertIsNotNone(SENSITIVE.search(sample))
        for sample in ("https://example.org/docs", "~/.agents/skills",
                       "%USERPROFILE%/.codex/skills", "references/教学流程.md"):
            self.assertIsNone(SENSITIVE.search(sample))

if __name__ == "__main__":
    unittest.main(verbosity=2)
