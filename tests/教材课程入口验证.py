"""Metadata/file tests only: no model, internet, textbook parsing or learner simulation."""
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
import course_entry as entry
import personal_library as library
import learning_store as store


def intake():
    return {"has_material": False, "exam_date": None, "baseline": "测试输入：尚未接触", "target": "测试输入：理解概念"}


def metadata():
    return {"title": "测试教材（不是实际教材）", "author": None, "publication": None,
            "isbn": None, "location": None, "version": None, "chapter": "第一章", "source": "用户提供的测试说明"}


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="教材入口测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "学习库"
        library.initialize(self.root, True)
        result = entry.setup_course(self.root, "统计学", "期末考试", intake(), 1, 0, True)
        self.course = result["course_id"]

    def index_revision(self):
        return library.read_index(self.root)["revision"]

    def view(self, course=None):
        return entry.continue_learning(self.root, course or self.course)

    def chapter(self, title="第一章"):
        view = self.view()
        return entry.add_chapter(self.root, self.course, title, self.index_revision(), view["course_revision"], True)

    def register(self, data=None, material_id=None):
        view = self.view()
        return entry.register_material(self.root, self.course, data or metadata(), self.index_revision(),
                                       view["material_revision"], view["course_revision"], True, material_id)

    def test_course_setup_records_only_user_intake(self):
        view = self.view()
        self.assertEqual(view["summary"]["course_goal"], "期末考试")
        self.assertEqual(view["course_entry"]["intake"], intake())
        self.assertIsNone(view["record"])
        self.assertEqual(library.read_index(self.root)["courses"][0]["points"], [])

    def test_wizard_read_only_and_known_intake_not_repeated(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = entry.wizard(self.root, "统计学")
        self.assertEqual(result["questions"], [])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        unknown = entry.wizard(self.root, "新课程")
        self.assertEqual(len(unknown["questions"]), 5)

    def test_legacy_course_can_use_intake_without_migration(self):
        course = library.create_course(self.root, "Python", "学习基础", self.index_revision(), True)["course_id"]
        before = library.read_index(self.root)
        result = entry.wizard(self.root, "Python")
        self.assertEqual(len(result["questions"]), 4)
        self.assertEqual(before, library.read_index(self.root))
        setup = entry.setup_course(self.root, "Python", "学习基础", intake(), self.index_revision(), 0, True, course)
        self.assertEqual(setup["course"]["intake"], intake())

    def test_existing_title_requests_selection_not_duplicate(self):
        before = self.index_revision()
        result = entry.setup_course(self.root, "统计学", "期末考试", intake(), before, 0, True)
        self.assertEqual(result["status"], "choose_existing")
        self.assertEqual(self.index_revision(), before)

    def test_ambiguous_titles_not_merged(self):
        library.create_course(self.root, "统计学", "另一个课程", self.index_revision(), True)
        view = entry.wizard(self.root, "统计学")
        self.assertEqual(len(view["existing_courses"]), 2)
        self.assertEqual(len(view["questions"]), 1)

    def test_refusal_does_not_create_course(self):
        before = (self.root / library.INDEX).read_bytes()
        with self.assertRaises(ValueError):
            entry.setup_course(self.root, "新课", "目标", intake(), self.index_revision(), 0)
        self.assertEqual((self.root / library.INDEX).read_bytes(), before)

    def test_invalid_date_does_not_write(self):
        data = intake()
        data["exam_date"] = "not a date"
        before = self.index_revision()
        with self.assertRaises(ValueError):
            entry.setup_course(self.root, "新课", "目标", data, before, 0, True)
        self.assertEqual(self.index_revision(), before)

    def test_no_file_material_preserves_optional_unknowns(self):
        result = self.register()
        self.assertEqual(result["status"], "registered")
        item = result["material"]
        self.assertEqual(item["status"], "no_file")
        for key in ("location", "file_name", "file_updated_at", "author", "publication", "isbn", "version"):
            self.assertIsNone(item[key])

    def test_material_does_not_change_v05_index(self):
        before = (self.root / library.INDEX).read_bytes()
        self.register()
        self.assertEqual((self.root / library.INDEX).read_bytes(), before)
        library.validate_index(library.read_index(self.root))

    def test_pdf_ppt_pptx_txt_only_stat_no_content_read(self):
        real_open = Path.open
        for suffix in (".pdf", ".ppt", ".pptx", ".txt"):
            with self.subTest(suffix=suffix):
                file = Path(self.temp.name) / ("测试文件" + suffix)
                file.write_bytes(b"metadata fixture only, not an actual textbook")
                before = file.read_bytes()
                def guarded(path, *args, **kwargs):
                    if path == file:
                        raise AssertionError("Textbook content opened")
                    return real_open(path, *args, **kwargs)
                data = metadata()
                data.update(location=str(file), version="用户填写版本1")
                with patch.object(Path, "open", guarded):
                    result = self.register(data)
                self.assertEqual(file.read_bytes(), before)
                self.assertEqual(result["material"]["file_name"], file.name)
                self.assertEqual(result["material"]["status"], "available")
                self.assertEqual(result["material"]["version"], "用户填写版本1")

    def test_unsupported_missing_relative_or_url_rejected(self):
        wrong = Path(self.temp.name) / "不支持.docx"
        wrong.write_bytes(b"fixture")
        for location in (str(wrong), str(Path(self.temp.name) / "不存在.pdf"), "relative.pdf", "https://example.invalid/book.pdf"):
            data = metadata()
            data["location"] = location
            with self.subTest(location=location), self.assertRaises(ValueError):
                self.register(data)

    def test_source_is_recorded_without_repository_integration(self):
        data = metadata()
        data["source"] = "用户说明：ChinaTextbook；只登记，不验证第三方来源。"
        result = self.register(data)
        self.assertEqual(result["material"]["source"], data["source"])
        self.assertEqual(result["material"]["status"], "no_file")

    def test_material_revision_conflict(self):
        self.register()
        with self.assertRaises(store.ConflictError):
            entry.register_material(self.root, self.course, metadata(), self.index_revision(), 0,
                                    self.view()["course_revision"], True)

    def test_course_revision_conflict(self):
        before = (self.root / library.INDEX).read_bytes()
        with self.assertRaises(store.ConflictError):
            entry.add_chapter(self.root, self.course, "第一章", self.index_revision(), 0, True)
        self.assertEqual(before, (self.root / library.INDEX).read_bytes())

    def test_chapter_can_exist_without_knowledge_or_evidence(self):
        self.chapter("第一章 总体与样本")
        course = library.read_index(self.root)["courses"][0]
        self.assertEqual(len(course["chapters"]), 1)
        self.assertEqual(course["points"], [])
        self.assertEqual(self.view()["summary"]["evidence_count"], 0)
        self.chapter("第一章 总体与样本")
        self.assertEqual(len(library.read_index(self.root)["courses"][0]["chapters"]), 1)

    def test_knowledge_directory_uses_existing_v05_command(self):
        self.chapter()
        for title in ("总体", "样本", "抽样方法"):
            library.add_point(self.root, self.course, "第一章", title, "学习" + title, self.index_revision(), True)
        self.assertEqual(len(library.read_index(self.root)["courses"][0]["points"]), 3)
        view = self.view()
        self.assertEqual(view["summary"]["chapter"], "第一章")
        self.assertEqual(view["record"]["learning_evidence"], [])

    def test_intake_does_not_touch_learning_record(self):
        point = library.add_point(self.root, self.course, "第一章", "总体", "理解总体", self.index_revision(), True)["point_id"]
        target = library.record_path(self.root, self.course, point)
        before = target.read_bytes()
        entry.setup_course(self.root, "统计学", "更新课程目标", intake(), self.index_revision(),
                           self.view()["course_revision"], True, self.course)
        self.assertEqual(target.read_bytes(), before)

    def test_other_course_material_and_record_not_changed(self):
        other = library.create_course(self.root, "Python", "目标", self.index_revision(), True)["course_id"]
        point = library.add_point(self.root, other, "列表", "索引", "理解索引", self.index_revision(), True)["point_id"]
        target = library.record_path(self.root, other, point)
        before = target.read_bytes()
        self.register()
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(entry.continue_learning(self.root, other)["registered_materials"], [])

    def test_material_update_retains_previous_backup(self):
        result = self.register()
        before = entry._file(self.root, self.course, "material.json").read_bytes()
        data = metadata()
        data["version"] = "新版本"
        self.register(data, result["material"]["id"])
        self.assertEqual(len(self.view()["registered_materials"]), 1)
        self.assertIn(before, [p.read_bytes() for p in (self.root / "备份").glob("*.json")])

    def test_metadata_write_failure_keeps_previous_file(self):
        self.register()
        path = entry._file(self.root, self.course, "material.json")
        before = path.read_bytes()
        with patch.object(library.os, "replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.register()
        self.assertEqual(path.read_bytes(), before)

    def test_partial_material_save_explicit_and_readable(self):
        real_write = entry._write
        def write(root, course, name, doc):
            if name == "course.json":
                raise OSError("projection failure")
            return real_write(root, course, name, doc)
        with patch.object(entry, "_write", side_effect=write):
            result = self.register()
        self.assertEqual(result["status"], "partial_saved")
        self.assertEqual(len(self.view()["registered_materials"]), 1)
        self.assertTrue(self.view()["directory_snapshot_stale"])

    def test_partial_setup_does_not_duplicate_course_on_retry(self):
        with patch.object(entry, "_write", side_effect=OSError("supplement failure")):
            result = entry.setup_course(self.root, "新课", "目标", intake(), self.index_revision(), 0, True)
        self.assertEqual(result["status"], "partial_saved")
        retry = entry.setup_course(self.root, "新课", "目标", intake(), self.index_revision(), 0, True, result["course_id"])
        self.assertEqual(retry["status"], "saved")
        self.assertEqual(len(library.read_index(self.root)["courses"]), 2)

    def test_bad_material_supplement_does_not_block_legacy_recovery(self):
        point = library.add_point(self.root, self.course, "第一章", "总体", "理解总体", self.index_revision(), True)["point_id"]
        path = entry._file(self.root, self.course, "material.json")
        path.write_text("{broken", encoding="utf-8")
        view = self.view()
        self.assertEqual(view["status"], "ready")
        self.assertEqual(view["point_id"], point)
        self.assertIsNone(view["registered_materials"])
        self.assertEqual(view["supplement_errors"][0]["file"], "material.json")
        with self.assertRaises(ValueError):
            self.register()
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_unknown_version_cannot_be_overwritten(self):
        path = entry._file(self.root, self.course, "course.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["schema_version"] = 99
        path.write_text(json.dumps(doc), encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.chapter()
        self.assertEqual(path.read_bytes(), before)

    def test_live_index_wins_over_old_snapshot(self):
        self.chapter("旧章节")
        library.add_point(self.root, self.course, "新章节", "新知识点", "目标", self.index_revision(), True)
        view = self.view()
        self.assertTrue(view["directory_snapshot_stale"])
        self.assertEqual(view["summary"]["chapter"], "新章节")

    def test_fresh_process_reads_saved_material_metadata(self):
        self.register()
        cmd = [sys.executable, "-X", "utf8", str(ROOT / "scripts/course_entry.py"),
               "continue", "--root", str(self.root), "--course-id", self.course]
        process = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        view = json.loads(process.stdout)
        self.assertEqual(view["registered_materials"][0]["title"], metadata()["title"])


if __name__ == "__main__":
    if "STUDY_TEST_TEMP" not in os.environ:
        raise SystemExit("Set STUDY_TEST_TEMP to an external temporary directory")
    unittest.main(verbosity=2)
