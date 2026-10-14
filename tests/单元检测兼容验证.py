"""Synthetic unit records with existing storage; does not test model grading or menu behavior."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import learning_store as store
import save_learning_note as notes


def draft():
    return {"schema_version": 1, "revision": 0,
        "learning_state": {"goal": "统计学第一章：理解、专业表达及综合应用检查", "knowledge_point": "单元综合检测：统计学第一章", "verification_status": "unverified"},
        "learning_evidence": [], "adaptive_review": {"due_date": None},
        "session_state": {"phase": "await_answer", "pending_question": "第1题：用总体与样本解释实际调查范围，并用术语说明区别。",
                          "resume_note": "3题蓝图：理解/表达、应用、综合迁移；当前第1题未答"}}


def answer(number=1, correct=True):
    return {"task_summary": f"单元：统计学第一章；第{number}题；知识点：总体/样本/抽样；虚构情境{number}，说明调查范围与抽样选择。",
        "response_summary": "虚构测试回答；实际反馈：" + ("本题范围与依据成立" if correct else "将受访者当作全部研究对象，范围需检查"),
        "reasoning_summary": "虚构测试用户理由", "correctness": "correct" if correct else "incorrect", "assistance": "independent",
        "task_relation": "original", "occurred_at": f"2026-01-01T10:0{number}:00+08:00"}


class UnitCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="单元检测测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.path = self.base / "单元检测" / "learning-state.json"
        self.point = self.base / "原知识点" / "learning-state.json"
        old = draft()
        old["learning_state"].update(goal="区分总体与样本", knowledge_point="总体与样本")
        store.save_confirmed(self.point, old, 0, True)
        self.point_before = self.point.read_bytes()

    def test_no_write_on_declined_entry(self):
        # The documented skip path performs no write operation; model compliance is a manual test.
        self.assertIsNone(store.load(self.path))
        self.assertFalse(self.path.exists())
        self.assertEqual(self.point.read_bytes(), self.point_before)

    def test_wrong_answer_appends_without_deleting_history(self):
        record = draft()
        record["learning_evidence"] = [answer()]
        saved = store.save_confirmed(self.path, record, 0, True)
        next_record = copy.deepcopy(saved)
        next_record["learning_evidence"].append(answer(2, False))
        result = store.save_confirmed(self.path, next_record, 1, True)
        self.assertEqual(result["learning_evidence"][0], answer())
        self.assertEqual(result["learning_evidence"][1]["correctness"], "incorrect")
        self.assertEqual(self.point.read_bytes(), self.point_before)

    def test_multiple_correct_items_do_not_set_total_mastery(self):
        record = draft()
        record["learning_evidence"] = [answer(1), answer(2), answer(3)]
        record["session_state"].update(phase="paused", pending_question=None,
            resume_note="本次已检查内容可选择进入下一单元；未检测范围保留待验证，等待用户选择")
        saved = store.save_confirmed(self.path, record, 0, True)
        self.assertEqual(store.resume(self.path)["record"], saved)
        self.assertEqual(saved["learning_state"]["verification_status"], "unverified")
        self.assertEqual(self.point.read_bytes(), self.point_before)

    def test_unanswered_question_restores_without_evidence(self):
        saved = store.save_confirmed(self.path, draft(), 0, True)
        self.assertEqual(store.resume(self.path)["record"]["session_state"], saved["session_state"])
        self.assertEqual(saved["learning_evidence"], [])

    def test_note_save_and_deletion_preserve_unit_record(self):
        store.save_confirmed(self.path, draft(), 0, True)
        before = self.path.read_bytes()
        note = notes.save_note("# 学习笔记\n本次检测未回答，保留待验证。", self.base / "笔记", True)
        Path(note["path"]).unlink()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.point.read_bytes(), self.point_before)

    def test_unanswered_cannot_be_marked_passed(self):
        record = draft()
        record["learning_state"]["verification_status"] = "immediate_passed"
        with self.assertRaises(ValueError):
            store.save_confirmed(self.path, record, 0, True)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
