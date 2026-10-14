"""Compatibility of text-only task labels with unchanged V0.3 storage; no learner/model tests."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import learning_store as store


def question():
    return "类型：情境应用；来源：统计学/第一章，知识点原创（未核对教材）；迁移：否。题目：研究某校本科生自习时间，访问120名住宿生。研究目标总体与实际调查对象是什么？说明理由。"


def record():
    return {"schema_version": 1, "revision": 0,
        "learning_state": {"goal": "区分研究对象", "knowledge_point": "总体与样本", "verification_status": "unverified"},
        "learning_evidence": [], "adaptive_review": {"due_date": None},
        "session_state": {"phase": "await_answer", "pending_question": question(), "resume_note": "等待实际回答"}}


def answer():
    return {"task_summary": question(), "response_summary": "虚构测试：总体是全校本科生，样本是受访者",
        "reasoning_summary": "虚构测试：按研究范围与实际调查范围区分", "correctness": "correct", "assistance": "independent",
        "task_relation": "original", "occurred_at": "2026-01-01T10:00:00+08:00"}


class Compatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="体验兼容测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learning-state.json"

    def test_task_labels_roundtrip_without_new_fields(self):
        data = record()
        data["learning_evidence"] = [answer()]
        saved = store.save_confirmed(self.path, data, 0, True)
        self.assertEqual(store.load(self.path), saved)
        self.assertEqual(saved["learning_evidence"][0], answer())
        self.assertEqual(set(saved), set(record()))

    def test_extra_metadata_field_still_rejected(self):
        data = record()
        item = answer()
        item["question_type"] = "application"
        data["learning_evidence"] = [item]
        with self.assertRaises(ValueError):
            store.save_confirmed(self.path, data, 0, True)
        self.assertFalse(self.path.exists())

    def test_hint_label_cannot_create_independent_pass(self):
        data = record()
        item = answer()
        item["assistance"] = "hinted"
        data["learning_evidence"] = [item]
        data["learning_state"]["verification_status"] = "immediate_passed"
        with self.assertRaises(ValueError):
            store.save_confirmed(self.path, data, 0, True)

    def test_old_evidence_not_retagged(self):
        data = record()
        data["learning_evidence"] = [answer()]
        saved = store.save_confirmed(self.path, data, 0, True)
        before = self.path.read_bytes()
        draft = copy.deepcopy(saved)
        draft["learning_evidence"][0]["task_summary"] = "新增标签：" + question()
        with self.assertRaises(ValueError):
            store.save_confirmed(self.path, draft, 1, True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_unanswered_recovery_and_summary_do_not_create_evidence(self):
        store.save_confirmed(self.path, record(), 0, True)
        before = self.path.read_bytes()
        view = store.resume(self.path)
        self.assertEqual(view["record"]["session_state"]["pending_question"], question())
        self.assertEqual(view["record"]["learning_evidence"], [])
        self.assertEqual(view["record"]["learning_state"]["verification_status"], "unverified")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
