"""Storage, recovery and review tests; no model calls or real learner data."""
import copy
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("learning_store", ROOT / "scripts/learning_store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


def draft():
    return {
        "schema_version": 1, "revision": 0,
        "learning_state": {"goal": "Calculate shopping discounts", "knowledge_point": "Payment from discount rate", "verification_status": "unverified"},
        "learning_evidence": [], "adaptive_review": {"due_date": None},
        "session_state": {"phase": "await_answer", "pending_question": "A 100-unit item is 20% off. What do you pay?", "resume_note": "Explanation completed; answer not yet checked."},
    }


def evidence():
    return {"task_summary": "A 100-unit item is 20% off.", "response_summary": "80", "reasoning_summary": "Pay 80% of the original price.", "correctness": "correct", "assistance": "independent", "task_relation": "original", "occurred_at": "2026-10-12T10:00:00+08:00"}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="存储测试-", dir=os.environ["STUDY_TEST_TEMP"])
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "learning-state.json"

    def test_no_history(self):
        self.assertIsNone(store.load(self.path))
        self.assertFalse(self.path.exists())

    def test_save_restore_and_caller_unchanged(self):
        record = draft()
        saved = store.save(self.path, record, 0)
        self.assertEqual(saved, store.load(self.path))
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(record["revision"], 0)
        saved["session_state"]["phase"] = "paused"
        saved = store.save(self.path, saved, 1)
        self.assertEqual(store.load(self.path)["revision"], 2)
        self.assertEqual(saved["session_state"]["pending_question"], draft()["session_state"]["pending_question"])

    def test_skip_remains_unverified(self):
        record = draft()
        record["session_state"].update(phase="paused", pending_question=None, resume_note="Skipped practice")
        saved = store.save(self.path, record, 0)
        self.assertEqual(saved["learning_evidence"], [])
        self.assertEqual(saved["learning_state"]["verification_status"], "unverified")

    def test_hinted_answer_not_independent_pass(self):
        record = draft()
        item = evidence()
        item["assistance"] = "hinted"
        record["learning_evidence"] = [item]
        store.save(self.path, record, 0)
        record["learning_state"]["verification_status"] = "immediate_passed"
        with self.assertRaises(store.StoreError):
            store.validate(record)

    def test_delayed_record_roundtrip(self):
        record = draft()
        initial = evidence()
        later = evidence()
        later.update(task_summary="A 200-unit item is 30% off.", response_summary="140",
                     reasoning_summary="Pay 70% of 200.", task_relation="delayed", occurred_at="2026-10-13T10:00:00+08:00")
        record["learning_evidence"] = [initial, later]
        record["learning_state"]["verification_status"] = "delayed_passed"
        record["adaptive_review"]["due_date"] = "2026-10-16"
        self.assertEqual(store.load(self.path) if self.path.exists() else None, None)
        self.assertEqual(store.save(self.path, record, 0), store.load(self.path))

    def test_corrupt_file_never_overwritten(self):
        for text in ("{broken", '{"schema_version":1,"schema_version":2}', "[]"):
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaises(store.StoreError):
                store.load(self.path)
            with self.assertRaises(store.StoreError):
                store.save(self.path, draft(), 0)
            self.assertEqual(self.path.read_text(encoding="utf-8"), text)

    def test_unsupported_version(self):
        record = draft()
        record["schema_version"] = 99
        self.path.write_text(json.dumps(record), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(store.StoreError):
            store.save(self.path, draft(), 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_save_failure_retains_old_bytes(self):
        saved = store.save(self.path, draft(), 0)
        before = self.path.read_bytes()
        for target in ("os.replace", "os.fsync"):
            with self.subTest(target=target), patch.object(store.os, target.split(".")[1], side_effect=OSError("injected")):
                with self.assertRaises(store.StoreError):
                    store.save(self.path, saved, 1)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
            self.assertFalse(self.path.with_name(self.path.name + ".lock").exists())

    def test_revision_conflict(self):
        saved = store.save(self.path, draft(), 0)
        store.save(self.path, saved, 1)
        before = self.path.read_bytes()
        with self.assertRaises(store.ConflictError):
            store.save(self.path, saved, 1)
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(store.ConflictError):
            store.save(self.path, draft(), 0)

    def test_lock_conflict(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text("", encoding="utf-8")
        with self.assertRaises(store.ConflictError):
            store.save(self.path, draft(), 0)
        self.assertTrue(lock.exists())
        self.assertFalse(self.path.exists())

    def test_first_save_failure_creates_no_record(self):
        with patch.object(store.os, "replace", side_effect=OSError("injected")):
            with self.assertRaises(store.StoreError):
                store.save(self.path, draft(), 0)
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_two_processes_cannot_both_create(self):
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/learning_store.py"),
                   "save", "--path", str(self.path), "--expected-revision", "0", "--confirmed"]
        def run(_):
            return subprocess.run(command, input=json.dumps(draft()), text=True,
                                  encoding="utf-8", capture_output=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sorted(result.returncode for result in results), [0, 1])
        self.assertEqual(store.load(self.path)["revision"], 1)

    def test_unreadable_record_is_not_missing(self):
        store.save(self.path, draft(), 0)
        before = self.path.read_bytes()
        with patch.object(Path, "read_text", side_effect=PermissionError("injected")):
            with self.assertRaises(store.StoreError):
                store.load(self.path)
            with self.assertRaises(store.StoreError):
                store.save(self.path, draft(), 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_reject_invalid_shape_and_evidence(self):
        for change in (lambda r: r.update(revision=True), lambda r: r.update(extra="future"),
                       lambda r: r["session_state"].update(pending_question=None),
                       lambda r: r["adaptive_review"].update(due_date="not-a-date"),
                       lambda r: r["learning_state"].update(verification_status="delayed_passed")):
            record = draft()
            change(record)
            with self.assertRaises(store.StoreError):
                store.save(self.path, record, 0)
        record = draft()
        record["learning_evidence"] = [evidence()]
        record["learning_evidence"][0]["occurred_at"] = "2026-10-12T10:00:00"
        with self.assertRaises(store.StoreError):
            store.validate(record)

    def test_old_evidence_and_scope_retained(self):
        record = draft()
        record["learning_evidence"] = [evidence()]
        saved = store.save(self.path, record, 0)
        for field in ("goal", "knowledge_point"):
            changed = copy.deepcopy(saved)
            changed["learning_state"][field] = "Different scope"
            with self.assertRaises(store.StoreError):
                store.save(self.path, changed, 1)
        saved["learning_evidence"] = []
        with self.assertRaises(store.StoreError):
            store.save(self.path, saved, 1)

    def test_explicit_external_path(self):
        for path in ("learning-state.json", ROOT / "learning-state.json", self.path.with_name("other.json")):
            with self.assertRaises(store.StoreError):
                store.load(path)

    def test_cli_in_separate_processes(self):
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/learning_store.py")]
        saved = subprocess.run(command + ["save", "--path", str(self.path), "--expected-revision", "0", "--confirmed"],
                               input=json.dumps(draft()), text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        read = subprocess.run(command + ["read", "--path", str(self.path)], text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(json.loads(saved.stdout)["record"], json.loads(read.stdout)["record"])

    def test_resume_missing(self):
        result = store.resume(self.path)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "missing")
        self.assertNotIn("summary", result)

    def test_resume_valid_evidence(self):
        record = draft()
        record["learning_evidence"] = [evidence()]
        record["learning_state"]["verification_status"] = "immediate_passed"
        saved = store.save_confirmed(self.path, record, 0, confirmed=True)
        result = store.resume(self.path)
        self.assertEqual(result["record"], saved)
        self.assertEqual(result["summary"]["verification_status"], "immediate_passed")
        self.assertEqual(result["choices"], ["继续", "复习", "更换目标"])

    def test_resume_pending_question(self):
        store.save_confirmed(self.path, draft(), 0, confirmed=True)
        result = store.resume(self.path)
        self.assertEqual(result["summary"]["pending_question"], draft()["session_state"]["pending_question"])
        self.assertEqual(result["summary"]["verification_status"], "unverified")

    def test_resume_skipped(self):
        record = draft()
        record["session_state"].update(phase="paused", pending_question=None, resume_note="Skipped; offer explanation without forced practice")
        store.save_confirmed(self.path, record, 0, confirmed=True)
        result = store.resume(self.path)
        self.assertEqual(result["summary"]["verification_status"], "unverified")
        self.assertIsNone(result["summary"]["pending_question"])
        self.assertEqual(result["record"]["learning_evidence"], [])

    def test_refused_save_writes_nothing(self):
        for confirmation in (False, None, "yes", 1):
            with self.assertRaises(store.StoreError):
                store.save_confirmed(self.path, draft(), 0, confirmed=confirmation)
        self.assertEqual(list(self.path.parent.iterdir()), [])
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/learning_store.py"),
                   "save", "--path", str(self.path), "--expected-revision", "0"]
        result = subprocess.run(command, input=json.dumps(draft()), text=True, encoding="utf-8", capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.path.exists())

    def test_resume_corrupt_has_no_fictional_history(self):
        self.path.write_text("{broken", encoding="utf-8")
        before = self.path.read_bytes()
        result = store.resume(self.path)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "invalid_or_unreadable")
        self.assertNotIn("summary", result)
        self.assertEqual(self.path.read_bytes(), before)

    def review_record(self):
        record = draft()
        record["learning_evidence"] = [evidence()]
        record["learning_state"]["verification_status"] = "immediate_passed"
        return store.save_confirmed(self.path, record, 0, confirmed=True)

    def review_answer(self):
        return {"task_summary": "A jacket costs 300 units before a 30% discount. What do you pay?",
                "response_summary": "210", "reasoning_summary": "Pay 70% of 300.",
                "correctness": "correct", "assistance": "independent"}

    def test_review_due_and_optional_choices(self):
        initial = self.review_record()
        now = datetime.fromisoformat("2026-10-12T10:00:00+08:00")
        scheduled = store.schedule_review(self.path, 1, True, now)
        self.assertEqual(scheduled["learning_evidence"], initial["learning_evidence"])
        due = store.resume(self.path, datetime.fromisoformat("2026-10-13T10:00:00+08:00"))
        self.assertTrue(due["review"]["due"])
        self.assertTrue(due["review"]["delayed_eligible"])
        self.assertEqual(due["choices"], ["先复习", "继续学习", "更换目标"])

    def test_early_review_not_delayed(self):
        self.review_record()
        result = store.record_review(self.path, self.review_answer(), 1, True,
                                     datetime.fromisoformat("2026-10-12T12:00:00+08:00"))
        self.assertEqual(result["timing"], "related")
        self.assertEqual(result["record"]["learning_state"]["verification_status"], "immediate_passed")
        self.assertFalse(store.review_status(result["record"], datetime.fromisoformat("2026-10-12T13:00:00+08:00"))["due"])

    def test_due_date_alone_does_not_prove_delay(self):
        self.review_record()
        scheduled = store.schedule_review(self.path, 1, True, datetime.fromisoformat("2026-10-12T10:00:00+08:00"))
        status = store.review_status(scheduled, datetime.fromisoformat("2026-10-13T09:00:00+08:00"))
        self.assertTrue(status["due"])
        self.assertFalse(status["delayed_eligible"])

    def test_review_write_failure_preserves_evidence(self):
        self.review_record()
        before = self.path.read_bytes()
        with patch.object(store.os, "replace", side_effect=OSError("injected")):
            with self.assertRaises(store.StoreError):
                store.record_review(self.path, self.review_answer(), 1, True, datetime.fromisoformat("2026-10-14T10:00:00+08:00"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_delayed_independent_pass_preserves_history(self):
        initial = self.review_record()
        result = store.record_review(self.path, self.review_answer(), 1, True,
                                     datetime.fromisoformat("2026-10-14T10:00:00+08:00"))
        saved = result["record"]
        self.assertEqual(saved["learning_state"]["verification_status"], "delayed_passed")
        self.assertEqual(saved["learning_evidence"][:-1], initial["learning_evidence"])
        self.assertEqual(saved["learning_evidence"][-1]["assistance"], "independent")
        self.assertEqual(saved["adaptive_review"]["due_date"], "2026-10-17")

    def test_delayed_hinted_answer_not_passed(self):
        initial = self.review_record()
        answer = self.review_answer()
        answer["assistance"] = "hinted"
        result = store.record_review(self.path, answer, 1, True, datetime.fromisoformat("2026-10-14T10:00:00+08:00"))
        self.assertEqual(result["record"]["learning_state"]["verification_status"], "needs_review")
        self.assertEqual(result["record"]["learning_evidence"][:-1], initial["learning_evidence"])
        self.assertEqual(result["record"]["learning_evidence"][-1]["assistance"], "hinted")
        self.assertEqual(result["next_action"], "check_without_help")

    def test_wrong_review_requests_diagnosis(self):
        initial = self.review_record()
        answer = self.review_answer()
        answer.update(response_summary="90", reasoning_summary="Pay 30%", correctness="incorrect")
        result = store.record_review(self.path, answer, 1, True, datetime.fromisoformat("2026-10-14T10:00:00+08:00"))
        self.assertEqual(result["next_action"], "diagnose")
        self.assertEqual(result["record"]["learning_state"]["verification_status"], "needs_review")
        self.assertEqual(result["record"]["learning_evidence"][:-1], initial["learning_evidence"])

    def test_skip_review_changes_nothing(self):
        self.review_record()
        store.schedule_review(self.path, 1, True, datetime.fromisoformat("2026-10-12T10:00:00+08:00"))
        before = self.path.read_bytes()
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/learning_store.py"), "review-skip", "--path", str(self.path)]
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "skipped")
        self.assertEqual(self.path.read_bytes(), before)

    def test_duplicate_retest_rejected_without_write(self):
        self.review_record()
        before = self.path.read_bytes()
        answer = self.review_answer()
        answer["task_summary"] = evidence()["task_summary"].upper() + "  "
        with self.assertRaises(store.StoreError):
            store.record_review(self.path, answer, 1, True, datetime.fromisoformat("2026-10-14T10:00:00+08:00"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_forged_delayed_evidence_rejected(self):
        record = draft()
        item = evidence()
        item["task_relation"] = "delayed"
        record["learning_evidence"] = [item]
        with self.assertRaises(store.StoreError):
            store.validate(record)
        initial = evidence()
        record["learning_evidence"] = [initial, dict(item, task_summary="A different task", occurred_at="2026-10-12T12:00:00+08:00")]
        with self.assertRaises(store.StoreError):
            store.validate(record)

    def test_review_requires_consent_and_current_revision(self):
        self.review_record()
        before = self.path.read_bytes()
        with self.assertRaises(store.StoreError):
            store.record_review(self.path, self.review_answer(), 1, False)
        with self.assertRaises(store.ConflictError):
            store.record_review(self.path, self.review_answer(), 2, True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_review_result_cli(self):
        self.review_record()
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/learning_store.py"),
                   "review-result", "--path", str(self.path), "--expected-revision", "1", "--confirmed",
                   "--test-now", "2026-10-14T10:00:00+08:00"]
        result = subprocess.run(command, input=json.dumps(self.review_answer()), text=True,
                                encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["timing"], "delayed")
        self.assertEqual(payload["record"], store.load(self.path))


if __name__ == "__main__":
    if "STUDY_TEST_TEMP" not in os.environ:
        raise SystemExit("Set STUDY_TEST_TEMP to an external temporary directory before testing")
    unittest.main(verbosity=2)
