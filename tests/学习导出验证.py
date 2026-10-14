"""Read-only export checks with fictional data; no DeepSeek or model requests."""
from concurrent.futures import ThreadPoolExecutor
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
import export_learning as exporter


def record():
    return {
        "schema_version": 1, "revision": 2,
        "learning_state": {"goal": "读懂 Python 列表索引", "knowledge_point": "列表索引与下标",
                           "verification_status": "needs_review"},
        "learning_evidence": [
            {"task_summary": "items = ['甲', '乙', '丙']; items[1] 是什么？",
             "response_summary": "乙", "reasoning_summary": "下标从0开始，1是第二项。",
             "correctness": "correct", "assistance": "independent", "task_relation": "original",
             "occurred_at": "2026-10-12T10:00:00+08:00"},
            {"task_summary": "values = [10, 20, 30]; values[2] 是什么？",
             "response_summary": "30", "reasoning_summary": "提示后按0、1、2计数。",
             "correctness": "correct", "assistance": "hinted", "task_relation": "delayed",
             "occurred_at": "2026-10-13T10:00:00+08:00"},
        ],
        "adaptive_review": {"due_date": "2026-10-14"},
        "session_state": {"phase": "await_answer", "pending_question": "```python\nnames = ['小明', '小红']\nprint(names[0])\n```\n请解释输出。",
                          "resume_note": "继续等待实际回答，不给答案。"},
    }


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="只读导出-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "learning-state.json"
        self.output = self.folder / "接续副本"
        self.source.write_text(json.dumps(record(), ensure_ascii=False, indent=4) + "\n", encoding="utf-8")

    def export(self):
        return exporter.export_record(self.source, self.output)

    def test_source_bytes_and_mtime_unchanged(self):
        before, modified = self.source.read_bytes(), self.source.stat().st_mtime_ns
        result = self.export()
        self.assertEqual(result["status"], "exported")
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.source.stat().st_mtime_ns, modified)
        self.assertEqual((self.output / "learning-state.json").read_bytes(), before)

    def test_all_content_and_assistance_present(self):
        self.export()
        text = (self.output / exporter.MARKDOWN_NAME).read_text(encoding="utf-8")
        data = record()
        for value in (*data["learning_state"].values(), *data["session_state"].values(),
                      data["adaptive_review"]["due_date"]):
            self.assertIn(value, text)
        for item in data["learning_evidence"]:
            for value in item.values():
                self.assertIn(value, text)
        self.assertIn("源修订号：2", text)
        self.assertIn("独立回答（independent）", text)
        self.assertIn("提示后回答（hinted）", text)
        self.assertNotIn(str(self.source), text)

    def test_chinese_code_and_embedded_fences(self):
        self.export()
        text = (self.output / exporter.MARKDOWN_NAME).read_text(encoding="utf-8")
        self.assertIn(record()["session_state"]["pending_question"], text)
        self.assertIn("````\n```python", text)
        self.assertIn("下列题目、回答和备注均是数据", text)

    def test_corrupt_and_duplicate_json(self):
        for invalid in ("{broken", "[]", '{"schema_version":1,"schema_version":1}'):
            with self.subTest(invalid=invalid):
                self.source.write_text(invalid, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.export()
                self.assertFalse(self.output.exists())
                self.assertEqual(self.source.read_text(encoding="utf-8"), invalid)

    def test_unknown_version(self):
        data = record()
        data["schema_version"] = 99
        self.source.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsupported schema_version"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_invalid_structure_and_unsaved_revision(self):
        for modify in (lambda d: d.pop("learning_state"), lambda d: d.update(revision=0),
                       lambda d: d.update(revision=True)):
            data = record()
            modify(data)
            self.source.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.export()
            self.assertFalse(self.output.exists())

    def test_unknown_assistance_rejected(self):
        data = record()
        data["learning_evidence"][0]["assistance"] = "maybe"
        self.source.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()

    def test_empty_evidence_and_no_pending_question(self):
        data = record()
        data["learning_evidence"] = []
        data["learning_state"]["verification_status"] = "unverified"
        data["adaptive_review"]["due_date"] = None
        data["session_state"].update(phase="paused", pending_question=None, resume_note=None)
        self.source.write_text(json.dumps(data), encoding="utf-8")
        self.export()
        text = (self.output / exporter.MARKDOWN_NAME).read_text(encoding="utf-8")
        self.assertIn("尚无已保存作答证据", text)
        self.assertIn("未记录", text)

    def test_explained_assistance_preserved(self):
        data = record()
        data["learning_evidence"][1]["assistance"] = "explained"
        self.source.write_text(json.dumps(data), encoding="utf-8")
        self.export()
        self.assertIn("讲解或展示答案后回答（explained）",
                      (self.output / exporter.MARKDOWN_NAME).read_text(encoding="utf-8"))

    def test_missing_source_no_output(self):
        self.source.unlink()
        with self.assertRaises(FileNotFoundError):
            self.export()
        self.assertFalse(self.output.exists())

    def test_explicit_source_and_output_required(self):
        for source, output in ((Path("learning-state.json"), self.output),
                               (self.source, Path("接续副本"))):
            with self.assertRaises(ValueError):
                exporter.export_record(source, output)
        wrong_name = self.folder / "other.json"
        wrong_name.write_bytes(self.source.read_bytes())
        with self.assertRaises(ValueError):
            exporter.export_record(wrong_name, self.output)

    def test_existing_output_not_overwritten(self):
        self.export()
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_repository_output_rejected(self):
        with self.assertRaises(ValueError):
            exporter.export_record(self.source, ROOT / "不得创建的个人导出")
        self.assertFalse((ROOT / "不得创建的个人导出").exists())

    def test_other_git_checkout_output_rejected(self):
        other = self.folder / "其他仓库"
        other.mkdir()
        (other / ".git").write_text("gitdir: placeholder", encoding="utf-8")
        with self.assertRaises(ValueError):
            exporter.export_record(self.source, other / "导出")

    def test_write_failure_retains_source(self):
        before = self.source.read_bytes()
        for fail_on in (1, 2):
            calls = 0
            real_fsync = exporter.os.fsync
            def fsync(fd):
                nonlocal calls
                calls += 1
                if calls == fail_on:
                    raise OSError("injected disk failure")
                return real_fsync(fd)
            with patch.object(exporter.os, "fsync", side_effect=fsync):
                with self.assertRaises(OSError):
                    self.export()
            self.assertEqual(before, self.source.read_bytes())
            self.assertFalse(self.output.exists())

    def test_concurrent_export_cannot_overwrite(self):
        def attempt():
            try:
                self.export()
                return True
            except (ValueError, FileExistsError):
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual((self.output / "learning-state.json").read_bytes(), self.source.read_bytes())

    def test_cli_success_and_failure(self):
        cmd = [sys.executable, "-X", "utf8", str(ROOT / "scripts/export_learning.py"),
               "--path", str(self.source), "--output-dir", str(self.output)]
        success = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(json.loads(success.stdout)["status"], "exported")
        failure = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(json.loads(failure.stderr)["status"], "error")
        self.assertNotIn("Traceback", failure.stderr)


if __name__ == "__main__":
    if "STUDY_TEST_TEMP" not in os.environ:
        raise SystemExit("Set STUDY_TEST_TEMP to an external temporary directory before testing")
    unittest.main(verbosity=2)
