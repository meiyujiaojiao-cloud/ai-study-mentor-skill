"""Synthetic local files only; these checks do not demonstrate actual textbook learning."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import material_import as importer
import course_entry as entry
import personal_library as library


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="教材导入测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "学习库"
        library.initialize(self.root, True)
        self.course = library.create_course(self.root, "测试统计学", "理解概念", 1, True)["course_id"]
        self.file = self.base / "虚构教材.txt"
        self.file.write_text("目录\n第一章 数据\n第一节 总体\n第二章 抽样\n", encoding="utf-8")

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def draft(self):
        return importer.preview(self.root, self.course, self.file)

    def apply(self, draft=None):
        return importer.apply_preview(self.root, self.course, draft or self.draft(), True)

    def test_preview_is_read_only_and_source_unchanged(self):
        before, source = self.snapshot(), self.file.read_bytes()
        draft = self.draft()
        self.assertEqual(draft["chapters"], ["第一章 数据", "第二章 抽样"])
        self.assertEqual(draft["outline"][1]["level"], 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.file.read_bytes(), source)

    def test_text_encodings_and_code(self):
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            with self.subTest(encoding=encoding):
                self.file.write_bytes("# Python列表\n## 索引\nvalues[0]\n# 第二章 中文\n".encode(encoding))
                self.assertEqual(self.draft()["chapters"], ["Python列表", "第二章 中文"])

    def test_plain_text_without_outline_never_invented(self):
        self.file.write_text("这只是正文，没有标题。", encoding="utf-8")
        draft = self.draft()
        self.assertEqual(draft["status"], "manual_outline_required")
        with self.assertRaises(ValueError):
            self.apply(draft)

    def test_manual_outline_after_failed_extraction_is_allowed(self):
        self.file.write_text("正文", encoding="utf-8")
        draft = self.draft()
        draft["chapters"] = ["用户确认的入门章"]
        self.assertEqual(self.apply(draft)["status"], "imported")

    def test_title_limit_warns_about_truncation(self):
        self.file.write_text("\n".join(f"# 主题{i}" for i in range(205)), encoding="utf-8")
        draft = self.draft()
        self.assertEqual(len(draft["chapters"]), 200)
        self.assertTrue(any("200" in warning for warning in draft["warnings"]))

    def test_preview_outputs_new_external_directory(self):
        before = self.snapshot()
        folder = self.base / "草稿"
        result = importer.write_preview(self.draft(), folder)
        self.assertTrue(Path(result["preview"]).is_file())
        self.assertEqual(json.loads(Path(result["draft"]).read_text(encoding="utf-8")), self.draft())
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError):
            importer.write_preview(self.draft(), folder)

    def test_preview_refuses_repository_or_library(self):
        for folder in (self.root / "草稿", ROOT / "测试草稿"):
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                importer.write_preview(self.draft(), folder)
        repo = self.base / "其他仓库"
        (repo / ".git").mkdir(parents=True)
        with self.assertRaises(ValueError):
            importer.write_preview(self.draft(), repo / "草稿")

    def test_preview_write_failure_not_reported_as_success(self):
        folder = self.base / "失败草稿"
        with patch.object(importer.os, "fsync", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                importer.write_preview(self.draft(), folder)
        self.assertFalse(folder.exists())

    def test_confirmation_required_no_writes(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            importer.apply_preview(self.root, self.course, self.draft())
        self.assertEqual(self.snapshot(), before)

    def test_only_confirmed_titles_added_no_learning_evidence(self):
        draft = self.draft()
        draft["chapters"] = ["第一章 数据", "用户修改的第二章", "第一章 数据"]
        result = self.apply(draft)
        self.assertEqual(result["status"], "imported")
        view = importer.continue_learning(self.root, self.course)
        self.assertEqual([c["title"] for c in view["chapters"]], ["第一章 数据", "用户修改的第二章"])
        self.assertEqual(view["points"], [])
        self.assertIsNone(view["record"])
        self.assertEqual(view["registered_materials"][0]["title"], self.file.stem)

    def test_repeat_import_is_idempotent(self):
        draft = self.draft()
        self.apply(draft)
        before = self.snapshot()
        self.assertEqual(self.apply(draft)["status"], "already_imported")
        self.assertEqual(self.snapshot(), before)

    def test_source_change_rejected_before_writes(self):
        draft = self.draft()
        self.file.write_text("第一章 已变化", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply(draft)
        self.assertEqual(self.snapshot(), before)

    def test_stale_index_revision_rejected(self):
        draft = self.draft()
        library.create_course(self.root, "另一个课程", "目标", library.read_index(self.root)["revision"], True)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply(draft)
        self.assertEqual(self.snapshot(), before)

    def test_wrong_course_or_draft_version_rejected(self):
        for field, value in (("course_id", "0" * 32), ("schema_version", 99)):
            draft = self.draft()
            draft[field] = value
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.apply(draft)
            self.assertEqual(self.snapshot(), before)

    def test_pending_record_and_other_course_preserved(self):
        point = library.add_point(self.root, self.course, "第一章 数据", "总体", "理解总体",
                                  library.read_index(self.root)["revision"], True)["point_id"]
        target = library.record_path(self.root, self.course, point)
        record = json.loads(target.read_text(encoding="utf-8"))
        record["session_state"].update(phase="await_answer", pending_question="请判断总体是什么？")
        record["learning_evidence"].append({"task_summary": "虚构旧题：判断研究对象", "response_summary": "测试回答",
            "reasoning_summary": "测试理由", "correctness": "correct", "assistance": "hinted",
            "task_relation": "original", "occurred_at": "2026-01-01T10:00:00+08:00"})
        # This is a synthetic fixture, not a real learner answer.
        target.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        other = library.create_course(self.root, "Python", "学习列表", library.read_index(self.root)["revision"], True)["course_id"]
        other_before = copy.deepcopy(library._course(library.read_index(self.root), other))
        before = target.read_bytes()
        self.apply()
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(library._course(library.read_index(self.root), other), other_before)
        view = importer.continue_learning(self.root, self.course, point)
        self.assertEqual(view["summary"]["pending_question"], "请判断总体是什么？")
        self.assertEqual(len(view["chapter_materials"]), 1)

    def test_failure_after_registration_is_explicit_and_retry_deduplicates(self):
        with patch.object(library, "_save_index", side_effect=OSError("index failure")):
            result = self.apply()
        self.assertEqual(result["status"], "partial_saved")
        self.assertFalse(result["chapters_saved"])
        self.assertEqual(self.apply()["status"], "imported")
        view = importer.continue_learning(self.root, self.course)
        self.assertEqual(len(view["registered_materials"]), 1)
        self.assertEqual(len(view["chapters"]), 2)

    def test_receipt_failure_retains_chapters_and_allows_repair(self):
        real = library._atomic_json
        def write(target, doc):
            if target.name == importer.RECEIPT:
                raise OSError("receipt failure")
            return real(target, doc)
        with patch.object(library, "_atomic_json", side_effect=write):
            result = self.apply()
        self.assertEqual(result["status"], "partial_saved")
        self.assertTrue(result["chapters_saved"])
        self.assertEqual(self.apply()["status"], "imported")
        self.assertEqual(len(importer.continue_learning(self.root, self.course)["chapters"]), 2)

    def test_first_write_failure_preserves_existing_files(self):
        self.apply()
        draft = self.draft()
        draft["chapters"].append("第三章 用户补充")
        before = self.snapshot()
        with patch.object(library.os, "replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.apply(draft)
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_unknown_receipt_version_cannot_be_overwritten(self):
        self.apply()
        path = entry._file(self.root, self.course, importer.RECEIPT)
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["schema_version"] = 99
        path.write_text(json.dumps(doc), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_material_projection_failure_not_reported_as_imported(self):
        real = entry._write
        def write(root, course, name, doc):
            if name == "course.json":
                raise OSError("injected")
            return real(root, course, name, doc)
        with patch.object(entry, "_write", side_effect=write):
            result = self.apply()
        self.assertEqual(result["status"], "partial_saved")
        self.assertFalse(result["chapters_saved"])
        self.assertEqual(self.apply()["status"], "imported")

    def test_corrupt_receipt_reports_problem_without_overwrite(self):
        self.apply()
        path = entry._file(self.root, self.course, importer.RECEIPT)
        path.write_text("{broken", encoding="utf-8")
        before = self.snapshot()
        view = importer.continue_learning(self.root, self.course)
        self.assertIsNone(view["chapter_materials"])
        self.assertTrue(view["supplement_errors"])
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_fresh_process_material_links_recover(self):
        self.apply()
        process = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/material_import.py"),
                                  "continue", "--root", str(self.root), "--course-id", self.course],
                                 capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["imported_chapters"][0]["chapters"], ["第一章 数据", "第二章 抽样"])

    def test_old_ppt_missing_and_url_rejected(self):
        old = self.base / "旧格式.ppt"
        old.write_bytes(b"synthetic")
        for source in (old, self.base / "missing.pdf", "https://example.invalid/book.pdf"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                importer.preview(self.root, self.course, source)

    def test_pdf_bookmarks_and_blank_scan_limit(self):
        from pypdf import PdfWriter
        pdf = self.base / "虚构书签.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        parent = writer.add_outline_item("第一章 数据", 0)
        writer.add_outline_item("第一节 总体", 0, parent=parent)
        writer.add_outline_item("第二章 抽样", 0)
        writer.write(pdf)
        draft = importer.preview(self.root, self.course, pdf)
        self.assertEqual(draft["method"], "pdf_bookmarks")
        self.assertEqual(draft["chapters"], ["第一章 数据", "第二章 抽样"])
        blank = PdfWriter()
        blank.add_blank_page(width=100, height=100)
        blank.write(pdf)
        self.assertEqual(importer.preview(self.root, self.course, pdf)["status"], "manual_outline_required")

    def test_pdf_text_fallback_candidates(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        pdf = self.base / "虚构文字.pdf"
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 250 Td (Chapter 1 Data) Tj 0 -20 Td (Chapter 2 Sampling) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.write(pdf)
        draft = importer.preview(self.root, self.course, pdf)
        self.assertEqual(draft["method"], "pdf_text_candidates")
        self.assertEqual(draft["chapters"], ["Chapter 1 Data", "Chapter 2 Sampling"])

    def test_encrypted_pdf_rejected(self):
        from pypdf import PdfWriter
        pdf = self.base / "加密夹具.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("fixture-password")
        writer.write(pdf)
        with self.assertRaisesRegex(ValueError, "加密"):
            importer.preview(self.root, self.course, pdf)

    def test_missing_pdf_dependency_explained(self):
        original = __import__
        def no_pdf(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("injected")
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=no_pdf), self.assertRaisesRegex(ValueError, "pypdf"):
            importer._pdf(self.file)

    def pptx(self, external=False, contents=False):
        file = self.base / "虚构课件.pptx"
        p = "http://schemas.openxmlformats.org/presentationml/2006/main"
        a = "http://schemas.openxmlformats.org/drawingml/2006/main"
        r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        mode = 'TargetMode="External"' if external else ''
        with zipfile.ZipFile(file, "w") as package:
            package.writestr("ppt/presentation.xml", f'<p:presentation xmlns:p="{p}" xmlns:r="{r}"><p:sldIdLst><p:sldId r:id="r2"/><p:sldId r:id="r1"/></p:sldIdLst></p:presentation>')
            package.writestr("ppt/_rels/presentation.xml.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="{r}/slide" Target="slides/slide1.xml"/><Relationship Id="r2" Type="{r}/slide" Target="slides/slide2.xml" {mode}/></Relationships>')
            for number, title in ((1, "第二章 抽样"), (2, "目录" if contents else "第一章 数据")):
                extra = "<a:p><a:r><a:t>第一章 数据</a:t></a:r></a:p><a:p><a:r><a:t>第二章 抽样</a:t></a:r></a:p>" if contents and number == 2 else ""
                package.writestr(f"ppt/slides/slide{number}.xml", f'<p:sld xmlns:p="{p}" xmlns:a="{a}"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>{extra}</p:spTree></p:cSld></p:sld>')
        return file

    def test_pptx_uses_presentation_order(self):
        draft = importer.preview(self.root, self.course, self.pptx())
        self.assertEqual(draft["chapters"], ["第一章 数据", "第二章 抽样"])
        self.assertEqual(draft["method"], "pptx_titles")

    def test_pptx_contents_page_preferred(self):
        draft = importer.preview(self.root, self.course, self.pptx(contents=True))
        self.assertEqual(draft["method"], "pptx_contents")
        self.assertEqual(draft["chapters"], ["第一章 数据", "第二章 抽样"])

    def test_pptx_external_relationship_not_followed(self):
        with self.assertRaises(ValueError):
            importer.preview(self.root, self.course, self.pptx(external=True))

    def test_broken_pptx_rejected_without_writes(self):
        file = self.base / "损坏.pptx"
        file.write_bytes(b"not a zip")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            importer.preview(self.root, self.course, file)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
