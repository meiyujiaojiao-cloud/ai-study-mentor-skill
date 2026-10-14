"""File safety tests only; note content is a synthetic fixture, not generated learner evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import save_learning_note as notes

CONTENT = "# 学习笔记\n\n我的原话：总体是我想研究的全部对象。\n\n待验证：抽样方案设计；未完成题未回答。\n"


class NoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="笔记保存测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.output = self.base / "学习笔记"

    def test_confirmation_required_and_blank_content_rejected(self):
        with self.assertRaises(ValueError):
            notes.save_note(CONTENT, self.output)
        with self.assertRaises(ValueError):
            notes.save_note(" ", self.output, True)
        self.assertFalse(self.output.exists())

    def test_new_file_keeps_unicode_answers_exactly(self):
        result = notes.save_note(CONTENT + "\n```python\nvalues[0]\n```\n", self.output, True)
        self.assertEqual(result["status"], "note_saved")
        self.assertEqual(Path(result["path"]).read_text(encoding="utf-8"), CONTENT + "\n```python\nvalues[0]\n```\n")

    def test_repeated_learning_adds_notes_and_deletion_does_not_touch_evidence(self):
        record = self.base / "learning-state.json"
        record.write_bytes(b"synthetic record sentinel; note saver must not read or change it")
        first = Path(notes.save_note(CONTENT, self.output, True)["path"])
        before = first.read_bytes()
        second = Path(notes.save_note(CONTENT + "\n本次第二份笔记\n", self.output, True)["path"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(len(list(self.output.glob("*.md"))), 2)
        second.unlink()
        self.assertEqual(record.read_bytes(), b"synthetic record sentinel; note saver must not read or change it")

    def test_repository_and_relative_paths_rejected(self):
        repo = self.base / "其他代码仓库"
        (repo / ".git").mkdir(parents=True)
        for output in (ROOT / "私人笔记", repo / "笔记", Path("relative")):
            with self.subTest(output=output), self.assertRaises(ValueError):
                notes.save_note(CONTENT, output, True)

    def test_save_failure_keeps_older_note(self):
        first = Path(notes.save_note(CONTENT, self.output, True)["path"])
        before = first.read_bytes()
        with patch.object(notes.os, "fsync", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                notes.save_note(CONTENT + "未完成新文件", self.output, True)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(list(self.output.glob("*.md")), [first])

    def test_cli_success_reports_only_note_saved(self):
        process = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/save_learning_note.py"),
                                  "--output-dir", str(self.output), "--confirmed"], input=CONTENT,
                                 text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "note_saved")
        self.assertNotIn("我的原话", process.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
