"""Deterministic file-operation tests; no model sessions or simulated learners."""
import copy
from datetime import datetime
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
import personal_library as library
import learning_store as store


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="个人库文件测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "私人学习库"
        library.initialize(self.root, confirmed=True)
        self.stats = self.course("统计学")
        self.math = self.course("高等数学")
        self.python = self.course("Python")
        self.stats_point = self.point(self.stats, "第一章 数据与统计", "总体与样本")
        self.py_point = self.point(self.python, "列表", "列表索引")

    def revision(self):
        return library.read_index(self.root)["revision"]

    def course(self, title):
        return library.create_course(self.root, title, "学习" + title, self.revision(), True)["course_id"]

    def point(self, course, chapter, title):
        return library.add_point(self.root, course, chapter, title, "理解" + title, self.revision(), True)["point_id"]

    def view(self, course=None, point=None):
        return library.continue_learning(self.root, course, point)

    def save(self, course, point, doc):
        return library.update_record(self.root, course, point, "save", doc["revision"], self.revision(), True, doc)

    def attempt(self):
        return {"task_summary": "文件测试夹具：从一组对象抽取部分，谁是样本？",
                "response_summary": "被抽取的部分", "reasoning_summary": "样本是总体的一部分。",
                "correctness": "correct", "assistance": "independent", "task_relation": "original",
                "occurred_at": "2026-10-12T10:00:00+08:00"}

    def answered(self):
        record = self.view(self.stats, self.stats_point)["record"]
        record["learning_evidence"].append(self.attempt())
        record["learning_state"]["verification_status"] = "immediate_passed"
        record["session_state"].update(phase="await_answer", pending_question="另一组抽样的迁移题，等待回答。",
                                       resume_note="确认后继续这道未答题。")
        return self.save(self.stats, self.stats_point, record)["record"]

    def test_empty_library_and_no_history(self):
        other = Path(self.temp.name) / "空库"
        with self.assertRaises(FileNotFoundError):
            library.continue_learning(other)
        library.initialize(other, True)
        self.assertEqual(library.continue_learning(other)["status"], "choose_course")

    def test_refused_setup_and_writes(self):
        other = Path(self.temp.name) / "未授权"
        with self.assertRaises(ValueError):
            library.initialize(other)
        self.assertFalse(other.exists())
        before = (self.root / library.INDEX).read_bytes()
        with self.assertRaises(ValueError):
            library.create_course(self.root, "不应保存", "目标", self.revision())
        self.assertEqual(before, (self.root / library.INDEX).read_bytes())

    def test_courses_are_isolated(self):
        python_path = library.record_path(self.root, self.python, self.py_point)
        before = python_path.read_bytes()
        result = self.answered()
        self.assertEqual(len(result["learning_evidence"]), 1)
        self.assertEqual(python_path.read_bytes(), before)
        self.assertEqual(self.view(self.math)["summary"]["evidence_count"], 0)

    def test_course_switch_preserves_position_and_unanswered_question(self):
        original = self.answered()
        library.select(self.root, self.python, self.py_point, self.revision(), True)
        self.assertEqual(self.view()["summary"]["course"], "Python")
        library.select(self.root, self.stats, None, self.revision(), True)
        summary = self.view()["summary"]
        self.assertEqual(summary["chapter"], "第一章 数据与统计")
        self.assertEqual(summary["goal"], "理解总体与样本")
        self.assertEqual(summary["pending_question"], original["session_state"]["pending_question"])
        self.assertEqual(self.view()["record"]["learning_evidence"], original["learning_evidence"])

    def test_each_point_remembers_its_own_question(self):
        self.answered()
        second = self.point(self.stats, "第一章 数据与统计", "数据类型")
        record = self.view(self.stats, second)["record"]
        record["session_state"].update(phase="await_answer", pending_question="数据类型未答题。")
        self.save(self.stats, second, record)
        library.select(self.root, self.stats, self.stats_point, self.revision(), True)
        self.assertIn("抽样", self.view()["summary"]["pending_question"])
        self.assertEqual(self.view(self.stats, second)["summary"]["pending_question"], "数据类型未答题。")

    def test_explicit_course_selection_does_not_mix_point_ids(self):
        with self.assertRaises(ValueError):
            self.view(self.python, self.stats_point)
        with self.assertRaises(ValueError):
            library.select(self.root, self.python, self.stats_point, self.revision(), True)

    def test_continue_is_read_only(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.view()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_duplicate_titles_have_distinct_ids(self):
        duplicate = self.course("统计学")
        self.assertNotEqual(duplicate, self.stats)
        self.assertEqual(self.view(duplicate)["status"], "choose_point")

    def test_material_registration_does_not_read_material(self):
        material = Path(self.temp.name) / "教材.pdf"
        material.write_bytes(b"material must not be read")
        real_open = Path.open
        def guarded(path, *args, **kwargs):
            if path == material:
                raise AssertionError("Material contents were accessed")
            return real_open(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            result = library.add_material(self.root, self.stats, "统计学基础", str(material),
                                          "第一章 数据与统计", "理解总体与样本", self.revision(), True)
        self.assertEqual(result["status"], "registered")
        self.assertEqual(self.view(self.stats)["materials"][0]["location"], str(material))

    def test_material_can_be_registered_before_available(self):
        path = str(Path(self.temp.name) / "暂不可访问的教材.pdf")
        library.add_material(self.root, self.stats, "教材", path, "第一章", "学习目标", self.revision(), True)
        self.assertFalse(Path(path).exists())

    def test_index_revision_conflict(self):
        with self.assertRaises(store.ConflictError):
            library.create_course(self.root, "冲突", "目标", self.revision() - 1, True)

    def test_record_revision_conflict(self):
        record = self.view(self.stats, self.stats_point)["record"]
        self.save(self.stats, self.stats_point, copy.deepcopy(record))
        with self.assertRaises(store.ConflictError):
            self.save(self.stats, self.stats_point, record)

    def test_old_evidence_cannot_be_removed(self):
        record = self.answered()
        record["learning_evidence"] = []
        record["learning_state"]["verification_status"] = "unverified"
        with self.assertRaises(ValueError):
            self.save(self.stats, self.stats_point, record)

    def test_skip_and_unanswered_do_not_create_evidence(self):
        record = self.view(self.stats, self.stats_point)["record"]
        record["session_state"].update(phase="paused", resume_note="未完成追问，无新增证据。")
        self.save(self.stats, self.stats_point, record)
        view = self.view()
        self.assertEqual(view["summary"]["evidence_count"], 0)
        self.assertEqual(view["summary"]["verification_status"], "unverified")

    def test_due_review_and_independent_delayed_result(self):
        original = self.answered()
        now = datetime.fromisoformat("2026-10-12T11:00:00+08:00")
        result = library.update_record(self.root, self.stats, self.stats_point, "review-schedule",
                                       original["revision"], self.revision(), True, now=now)
        later = datetime.fromisoformat("2026-10-13T12:00:00+08:00")
        self.assertEqual(len(library.continue_learning(self.root, self.stats, now=later)["due_points"]), 1)
        answer = {"task_summary": "文件测试新题：另一组调查的抽取部分是谁？", "response_summary": "被抽取部分",
                  "reasoning_summary": "它属于总体的一部分。", "correctness": "correct", "assistance": "independent"}
        reviewed = library.update_record(self.root, self.stats, self.stats_point, "review-result",
                                         result["record"]["revision"], self.revision(), True, answer, later)
        self.assertEqual(reviewed["record"]["learning_state"]["verification_status"], "delayed_passed")
        self.assertEqual(reviewed["record"]["learning_evidence"][:1], original["learning_evidence"])
        self.assertEqual(self.view(self.python)["record"]["learning_evidence"], [])

    def test_hinted_review_does_not_pass_independently(self):
        original = self.answered()
        answer = {"task_summary": "提示后处理的新题", "response_summary": "部分对象", "reasoning_summary": "根据提示作答",
                  "correctness": "correct", "assistance": "hinted"}
        result = library.update_record(self.root, self.stats, self.stats_point, "review-result", original["revision"],
                                       self.revision(), True, answer, datetime.fromisoformat("2026-10-13T12:00:00+08:00"))
        self.assertEqual(result["record"]["learning_state"]["verification_status"], "needs_review")
        self.assertEqual(result["record"]["learning_evidence"][-1]["assistance"], "hinted")

    def test_corrupt_and_unknown_index_not_recreated(self):
        path = self.root / library.INDEX
        for text in ('{broken', '{"kind":"personal_library","schema_version":99}',
                     '{"kind":"personal_library","kind":"personal_library"}'):
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                library.initialize(self.root, True)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_corrupt_selected_record_is_not_history(self):
        path = library.record_path(self.root, self.python, self.py_point)
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.view()
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_save_failure_preserves_old_record(self):
        record = self.view(self.stats, self.stats_point)["record"]
        path = library.record_path(self.root, self.stats, self.stats_point)
        before = path.read_bytes()
        with patch.object(store.os, "replace", side_effect=OSError("injected disk failure")):
            with self.assertRaises(ValueError):
                self.save(self.stats, self.stats_point, record)
        self.assertEqual(path.read_bytes(), before)

    def test_index_failure_after_save_is_explicit_and_does_not_duplicate(self):
        record = self.view(self.stats, self.stats_point)["record"]
        record["learning_evidence"] = [self.attempt()]
        with patch.object(library, "_save_index", side_effect=OSError("index write failure")):
            result = self.save(self.stats, self.stats_point, record)
        self.assertEqual(result["status"], "partial_saved")
        saved = self.view(self.stats, self.stats_point)["record"]
        self.assertEqual(len(saved["learning_evidence"]), 1)
        library.select(self.root, self.stats, self.stats_point, self.revision(), True)
        self.assertEqual(len(self.view()["record"]["learning_evidence"]), 1)

    def test_point_registration_failure_can_retry_same_id(self):
        with patch.object(library, "_save_index", side_effect=OSError("index write failure")):
            result = library.add_point(self.root, self.stats, "第二章", "变量", "理解变量", self.revision(), True)
        self.assertEqual(result["status"], "partial_saved")
        retry = library.add_point(self.root, self.stats, "第二章", "变量", "理解变量", self.revision(), True, result["point_id"])
        self.assertEqual(retry["status"], "saved")

    def test_backups_match_previous_record(self):
        target = library.record_path(self.root, self.stats, self.stats_point)
        before = target.read_bytes()
        self.answered()
        self.assertIn(before, [p.read_bytes() for p in (self.root / "备份").glob("*.json")])

    def test_path_and_scope_validation(self):
        with self.assertRaises(ValueError):
            library.initialize(ROOT / "私人数据不得进入仓库", True)
        with self.assertRaises(ValueError):
            library.initialize("relative-folder", True)
        with self.assertRaises(ValueError):
            self.view("../../escape")
        doc = library.read_index(self.root)
        doc["current"]["point_id"] = self.stats_point
        with self.assertRaises(ValueError):
            library.validate_index(doc)

    def test_startup_entry_no_overwrite(self):
        result = library.write_entry(self.root, True)
        self.assertEqual(result["status"], "created")
        text = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("continue --root", text)
        self.assertIn("不自动读取教材", text)
        with self.assertRaises(ValueError):
            library.write_entry(self.root, True)

    def test_existing_lock_is_not_removed(self):
        lock = self.root / (library.INDEX + ".lock")
        lock.write_text("active writer", encoding="utf-8")
        with self.assertRaises(store.ConflictError):
            library.create_course(self.root, "冲突课程", "目标", self.revision(), True)
        self.assertEqual(lock.read_text(encoding="utf-8"), "active writer")

    def test_backup_failure_retains_index(self):
        before = (self.root / library.INDEX).read_bytes()
        with patch.object(library, "_backup", side_effect=OSError("backup failure")):
            with self.assertRaises(OSError):
                library.create_course(self.root, "不能提交", "目标", self.revision(), True)
        self.assertEqual((self.root / library.INDEX).read_bytes(), before)

    def test_failed_backup_is_not_left_as_complete_json(self):
        before = set((self.root / "备份").glob("*.json"))
        with patch.object(library.os, "fsync", side_effect=OSError("backup flush failure")):
            with self.assertRaises(OSError):
                library._backup(self.root, self.root / library.INDEX)
        self.assertEqual(before, set((self.root / "备份").glob("*.json")))

    def test_point_cannot_reuse_course_id(self):
        target = library.record_path(self.root, self.stats, self.stats)
        with self.assertRaises(ValueError):
            library.add_point(self.root, self.stats, "第一章", "重复编号", "目标", self.revision(), True, self.stats)
        self.assertFalse(target.exists())

    def test_index_replace_failure_retains_index(self):
        before = (self.root / library.INDEX).read_bytes()
        with patch.object(library.os, "replace", side_effect=OSError("replace failure")):
            with self.assertRaises(OSError):
                library.create_course(self.root, "不能提交", "目标", self.revision(), True)
        self.assertEqual((self.root / library.INDEX).read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_saved_course_position_survives_switch_even_without_learning(self):
        second = self.point(self.stats, "第二章", "新知识点")
        library.select(self.root, self.stats, self.stats_point, self.revision(), True)
        library.select(self.root, self.python, self.py_point, self.revision(), True)
        library.select(self.root, self.stats, None, self.revision(), True)
        self.assertEqual(self.view()["point_id"], self.stats_point)
        self.assertNotEqual(self.view()["point_id"], second)

    def test_unanswered_question_survives_direct_v03_tool(self):
        original = self.answered()
        target = library.record_path(self.root, self.stats, self.stats_point)
        recovered = store.resume(target)
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(recovered["record"], original)

    def test_early_review_not_delayed(self):
        original = self.answered()
        answer = {"task_summary": "当天的新检查问题", "response_summary": "样本", "reasoning_summary": "总体的部分对象",
                  "correctness": "correct", "assistance": "independent"}
        result = library.update_record(self.root, self.stats, self.stats_point, "review-result", original["revision"],
                                       self.revision(), True, answer, datetime.fromisoformat("2026-10-12T12:00:00+08:00"))
        self.assertEqual(result["record"]["learning_state"]["verification_status"], "immediate_passed")
        self.assertEqual(result["record"]["learning_evidence"][-1]["task_relation"], "related")

    def test_wrong_review_retains_history_and_routes_diagnosis(self):
        original = self.answered()
        answer = {"task_summary": "另一道检查问题", "response_summary": "混淆了总体", "reasoning_summary": None,
                  "correctness": "incorrect", "assistance": "independent"}
        result = library.update_record(self.root, self.stats, self.stats_point, "review-result", original["revision"],
                                       self.revision(), True, answer, datetime.fromisoformat("2026-10-13T12:00:00+08:00"))
        self.assertEqual(result["next_action"], "diagnose")
        self.assertEqual(result["record"]["learning_evidence"][:1], original["learning_evidence"])

    def test_linked_data_directory_rejected_by_reparse_attribute(self):
        original_lstat = Path.lstat
        class Linked:
            st_mode = 0
            st_file_attributes = 0x400
        def lstat(path, *args, **kwargs):
            if path == self.root:
                return Linked()
            return original_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", lstat):
            with self.assertRaises(ValueError):
                library.read_index(self.root)

    def test_fresh_process_recovers_without_chat(self):
        original = self.answered()
        cmd = [sys.executable, "-X", "utf8", str(ROOT / "scripts/personal_library.py"),
               "continue", "--root", str(self.root)]
        process = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["record"]["learning_evidence"], original["learning_evidence"])
        self.assertEqual(result["summary"]["pending_question"], original["session_state"]["pending_question"])


if __name__ == "__main__":
    if "STUDY_TEST_TEMP" not in os.environ:
        raise SystemExit("Set STUDY_TEST_TEMP to an external temporary directory")
    unittest.main(verbosity=2)
