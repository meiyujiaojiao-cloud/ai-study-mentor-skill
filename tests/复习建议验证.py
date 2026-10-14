"""Read-only suggestion and existing append behavior with synthetic records, not learner tests."""
from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import review_suggestions as advice
import personal_library as library
import learning_store as store
import unit_status as units


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="复习建议测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "学习库"
        library.initialize(self.root, True)
        self.course = library.create_course(self.root, "统计学", "理解与应用", 1, True)["course_id"]
        self.point = library.add_point(self.root, self.course, "第一章", "总体与样本", "区分范围", 2, True)["point_id"]
        self.path = library.record_path(self.root, self.course, self.point)
        record = store.load(self.path)
        record["learning_evidence"] = [{"task_summary": "虚构原题：判断总体与样本", "response_summary": "虚构回答；分项观察：专业表达待验证",
            "reasoning_summary": "虚构用户理由", "correctness": "correct", "assistance": "independent", "task_relation": "original",
            "occurred_at": "2026-01-01T10:00:00+08:00"}]
        record["learning_state"]["verification_status"] = "immediate_passed"
        record["adaptive_review"]["due_date"] = "2026-01-02"
        record["session_state"].update(phase="await_answer", pending_question="原未完成题", resume_note="下一步检查范围变化")
        store.save_confirmed(self.path, record, 1, True)

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_new_learning_has_context_and_checks_without_writes(self):
        before = self.snapshot()
        view = advice.suggestions(root=self.root)["review_suggestions"]
        self.assertEqual(view["knowledge_point"], "总体与样本")
        self.assertEqual(view["unfinished_question"], "原未完成题")
        self.assertEqual(view["recommended_task_types"][0], "主动回忆")
        self.assertEqual(view["suggested_review_date"], "2026-01-02")
        self.assertEqual(before, self.snapshot())

    def test_paused_unit_keeps_original_review_position(self):
        chapter = library._course(library.read_index(self.root), self.course)["chapters"][0]["id"]
        basis = {"learned_point_ids": [self.point], "required_exercises_completed": True, "assessment_path": None, "assessment_completed": False}
        units.save_status(self.root, self.course, chapter, "testing", basis, "单元检测第2题等待回答", 3, 0, True)
        units.save_status(self.root, self.course, chapter, "paused", basis, None, 3, 1, True)
        before = self.snapshot()
        view = advice.suggestions(root=self.root)
        self.assertEqual(view["unit_review_position"]["resume_status"], "testing")
        self.assertEqual(view["unit_review_position"]["position_note"], "单元检测第2题等待回答")
        self.assertEqual(view["review_suggestions"]["unfinished_question"], "原未完成题")
        self.assertEqual(before, self.snapshot())

    def test_wrong_review_preserves_correct_evidence_and_real_test_clock(self):
        old = store.load(self.path)
        task = {"task_summary": "复习检查；维度：应用；知识点：总体与样本；题目：虚构新场景判断研究目的变化",
                "response_summary": "虚构错误回答", "reasoning_summary": "虚构错误理由", "correctness": "incorrect", "assistance": "independent"}
        # Explicit simulated clock: this is not a real cross-day learning result.
        store.record_review(self.path, task, 2, True, now=datetime.fromisoformat("2026-01-02T11:00:00+08:00"))
        new = store.load(self.path)
        self.assertEqual(new["learning_evidence"][0], old["learning_evidence"][0])
        view = advice.suggestions(path=self.path)["review_suggestions"]
        self.assertEqual(view["last_explicit_review_at"], "2026-01-02T11:00:00+08:00")
        self.assertEqual(new["learning_state"]["verification_status"], "needs_review")

    def test_overdue_without_return_does_not_change_state(self):
        before = self.snapshot()
        for _ in range(2):
            advice.suggestions(root=self.root)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(store.load(self.path)["learning_state"]["verification_status"], "immediate_passed")

    def test_no_evidence_or_date_not_invented(self):
        record = store.load(self.path)
        record["learning_evidence"] = []
        record["learning_state"]["verification_status"] = "unverified"
        record["adaptive_review"]["due_date"] = None
        view = advice.record_context(record)
        self.assertIsNone(view["last_actual_answer_at"])
        self.assertIsNone(view["suggested_review_date"])
        self.assertIsNone(view["last_explicit_review_at"])

    def test_legacy_related_not_mislabelled_as_review(self):
        record = store.load(self.path)
        record["learning_evidence"][0]["task_relation"] = "related"
        view = advice.record_context(record)
        self.assertIsNone(view["last_explicit_review_at"])

    def test_missing_or_damaged_explicit_record(self):
        missing = Path(self.temp.name) / "不存在" / "learning-state.json"
        self.assertEqual(advice.suggestions(path=missing)["status"], "unavailable")
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            advice.suggestions(path=self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main(verbosity=2)
