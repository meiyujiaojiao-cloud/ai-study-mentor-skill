"""Synthetic annotations round-trip through unchanged store; not a semantic grading test."""
import copy
from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import learning_store as store


def record():
    return {"schema_version": 1, "revision": 0,
        "learning_state": {"goal": "备考：区分总体与样本", "knowledge_point": "总体与样本", "verification_status": "unverified"},
        "learning_evidence": [], "adaptive_review": {"due_date": None},
        "session_state": {"phase": "paused", "pending_question": None,
                          "resume_note": "下一步按用户要求练专业表达；总体范围留到抽样情境检查"}}


def initial():
    return {"task_summary": "知识点：总体与样本；任务：研究全校本科生，调查120名住宿生。指出总体和样本，说明原因，并复述专业定义。",
        "response_summary": "用户回答：总体是全校本科生，样本是这120人，因为研究目标包括全校，而实际只访问这120人；总体就是全部研究对象。\n分项观察：概念理解=已验证（本题研究范围判断及理由）；专业表达=待验证（专业定义限定尚待补充）。",
        "reasoning_summary": "研究目标是全校，实际只访问120人", "correctness": "partial", "assistance": "independent",
        "task_relation": "original", "occurred_at": "2026-01-01T10:00:00+08:00"}


class Compatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="评估兼容测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "learning-state.json"

    def test_distinct_observations_saved_and_restored_without_schema_change(self):
        draft = record()
        draft["learning_evidence"] = [initial()]
        saved = store.save_confirmed(self.path, draft, 0, True)
        restored = store.resume(self.path)["record"]
        self.assertEqual(restored, saved)
        self.assertEqual(restored["learning_evidence"][0], initial())
        self.assertEqual(set(restored), set(record()))

    def test_later_related_task_preserves_history(self):
        draft = record()
        draft["learning_evidence"] = [initial()]
        saved = store.save_confirmed(self.path, draft, 0, True)
        later = {"task_summary": "知识点：总体与样本；任务：研究目标改为住宿本科生，应如何限定抽样对象？为什么？",
            "response_summary": "用户回答：按新研究目的限定为住宿本科生，再在其范围抽取对象。\n分项观察：应用能力=已验证（本题限定调查范围）；概念理解=已验证（新目标下的范围界定）。",
            "reasoning_summary": "总体范围由新研究目的限定，抽样对象应在此范围内", "correctness": "correct", "assistance": "independent"}
        result = store.record_review(self.path, later, saved["revision"], True,
                                     now=datetime.fromisoformat("2026-01-01T11:00:00+08:00"))
        self.assertEqual(result["record"]["learning_evidence"][0], initial())
        self.assertEqual(result["timing"], "related")
        self.assertEqual(result["record"]["learning_evidence"][1]["response_summary"], later["response_summary"])

    def test_observation_text_cannot_replace_missing_learner_reasoning(self):
        draft = record()
        item = initial()
        item.update(correctness="correct", reasoning_summary=None)
        draft["learning_evidence"] = [item]
        draft["learning_state"]["verification_status"] = "immediate_passed"
        with self.assertRaises(ValueError):
            store.save_confirmed(self.path, draft, 0, True)
        self.assertFalse(self.path.exists())

    def test_pending_point_without_answer_is_not_evidence(self):
        saved = store.save_confirmed(self.path, record(), 0, True)
        self.assertEqual(store.resume(self.path)["record"]["learning_evidence"], [])
        self.assertEqual(saved["learning_state"]["verification_status"], "unverified")
        self.assertIsNone(saved["adaptive_review"]["due_date"])

    def test_past_observations_cannot_be_rewritten(self):
        draft = record()
        draft["learning_evidence"] = [initial()]
        saved = store.save_confirmed(self.path, draft, 0, True)
        before = self.path.read_bytes()
        changed = copy.deepcopy(saved)
        changed["learning_evidence"][0]["response_summary"] = "全部维度已验证"
        with self.assertRaises(ValueError):
            store.save_confirmed(self.path, changed, 1, True)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
