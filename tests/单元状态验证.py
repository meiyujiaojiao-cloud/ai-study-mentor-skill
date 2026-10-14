"""Unit workflow persistence tests using fictional records, not real learner evidence."""
import copy
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
import unit_status as units
import personal_library as library
import learning_store as store
import course_entry as entry


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="单元状态测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "学习库"
        library.initialize(self.root, True)
        self.course = library.create_course(self.root, "统计学", "目标", 1, True)["course_id"]
        self.point = library.add_point(self.root, self.course, "第一章", "总体与样本", "区分对象", 2, True)["point_id"]
        self.chapter = library._course(library.read_index(self.root), self.course)["chapters"][0]["id"]
        self.target = library.record_path(self.root, self.course, self.point)
        record = store.load(self.target)
        record["learning_evidence"].append({"task_summary": "虚构题：区分总体与样本", "response_summary": "虚构回答",
            "reasoning_summary": "虚构理由", "correctness": "partial", "assistance": "independent",
            "task_relation": "original", "occurred_at": "2026-01-01T10:00:00+08:00"})
        store.save_confirmed(self.target, record, 1, True)
        self.basis = {"learned_point_ids": [self.point], "required_exercises_completed": True,
                      "assessment_path": None, "assessment_completed": False}
        self.assessment = Path(self.temp.name) / "检测" / "learning-state.json"

    def save(self, status, basis=None, note="当前第一章位置", revision=None, confirmed=True):
        doc = units.read(self.root, self.course)
        return units.save_status(self.root, self.course, self.chapter, status, basis or self.basis, note,
            library.read_index(self.root)["revision"], revision if revision is not None else doc["revision"] if doc else 0, confirmed)

    def make_assessment(self, wrong=True):
        point = store.load(self.target)
        point["revision"] = 0
        point["learning_state"].update(goal="统计学第一章单元检测", knowledge_point="单元综合检测：第一章")
        point["learning_evidence"][0]["correctness"] = "incorrect" if wrong else "correct"
        point["session_state"].update(phase="paused", pending_question=None)
        store.save_confirmed(self.assessment, point, 0, True)
        return {**self.basis, "assessment_path": str(self.assessment), "assessment_completed": True}

    def test_missing_sidecar_read_only_default_not_saved(self):
        before = (self.root / library.INDEX).read_bytes()
        view = units.continue_learning(self.root)
        self.assertFalse(view["current_unit_state"]["saved"])
        self.assertEqual(view["current_unit_state"]["unit_status"], "learning")
        self.assertIsNone(units.read(self.root, self.course))
        self.assertEqual((self.root / library.INDEX).read_bytes(), before)

    def test_learning_pause_and_resume_keep_position(self):
        self.save("learning")
        self.save("paused")
        view = units.continue_learning(self.root)
        self.assertEqual(view["current_unit_state"]["resume_status"], "learning")
        self.assertEqual(view["current_unit_state"]["position_note"], "当前第一章位置")
        self.assertEqual(self.save("resume")["unit"]["unit_status"], "learning")

    def test_ready_without_test_accepts_partial_ability(self):
        result = self.save("ready_for_test")
        self.assertEqual(result["unit"]["unit_status"], "ready_for_test")
        self.assertEqual(result["learned_point_count"], 1)
        self.assertEqual(result["evidence_count"], 1)
        self.assertEqual(store.load(self.target)["learning_state"]["verification_status"], "unverified")

    def test_testing_pause_resumes_testing(self):
        self.save("testing", note="检测第2题待答")
        self.save("paused", note=None)
        self.assertEqual(self.save("resume")["unit"]["unit_status"], "testing")
        self.assertEqual(units.continue_learning(self.root)["current_unit_state"]["position_note"], "检测第2题待答")

    def test_completed_with_wrong_answer_does_not_change_evidence(self):
        basis = self.make_assessment(wrong=True)
        before = {p: p.read_bytes() for p in (self.target, self.assessment, self.root / library.INDEX)}
        result = self.save("completed", basis)
        self.assertEqual(result["unit"]["unit_status"], "completed")
        for p, raw in before.items():
            self.assertEqual(p.read_bytes(), raw)

    def test_completed_rejects_missing_or_unfinished_test(self):
        with self.assertRaises(ValueError):
            self.save("completed")
        basis = self.make_assessment()
        record = store.load(self.assessment)
        record["session_state"].update(phase="await_answer", pending_question="未答题")
        store.save_confirmed(self.assessment, record, 1, True)
        with self.assertRaises(ValueError):
            self.save("completed", basis)

    def test_ready_requires_practice_and_actual_evidence(self):
        with self.assertRaises(ValueError):
            self.save("ready_for_test", {**self.basis, "required_exercises_completed": False})
        with self.assertRaises(ValueError):
            self.save("ready_for_test", {**self.basis, "learned_point_ids": []})

    def test_no_authorization_and_revision_conflict(self):
        with self.assertRaises(ValueError):
            self.save("learning", confirmed=False)
        self.save("learning")
        with self.assertRaises(store.ConflictError):
            self.save("testing", revision=0)

    def test_corrupt_or_unknown_version_not_overwritten(self):
        self.save("learning")
        path = entry._file(self.root, self.course, units.FILE)
        for text in ("{broken", json.dumps({**units.read(self.root, self.course), "schema_version": 99})):
            path.write_text(text, encoding="utf-8")
            view = units.continue_learning(self.root)
            self.assertIsNone(view["unit_states"])
            self.assertIsNotNone(view["record"])
            with self.assertRaises(ValueError):
                units.save_status(self.root, self.course, self.chapter, "learning", self.basis, "位置", 3, 1, True)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_write_failure_preserves_previous_status(self):
        self.save("learning")
        path = entry._file(self.root, self.course, units.FILE)
        before = path.read_bytes()
        with patch.object(library.os, "replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.save("testing")
        self.assertEqual(path.read_bytes(), before)

    def test_other_unit_points_rejected(self):
        point = library.add_point(self.root, self.course, "第二章", "抽样", "目标", 3, True)["point_id"]
        with self.assertRaises(ValueError):
            self.save("learning", {**self.basis, "learned_point_ids": [point]})

    def test_fresh_process_restores_completed(self):
        self.save("completed", self.make_assessment())
        process = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/unit_status.py"),
            "continue", "--root", str(self.root)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["current_unit_state"]["unit_status"], "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
