"""Local record storage and evidence-based review transitions; no model calls."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile


class StoreError(ValueError):
    pass


class ConflictError(StoreError):
    pass


def _require(condition, message):
    if not condition:
        raise StoreError(message)


def _fields(value, names):
    _require(isinstance(value, dict) and set(value) == set(names.split()),
             "Invalid or missing fields")


def _text(value, nullable=False):
    _require((nullable and value is None) or
             (isinstance(value, str) and bool(value.strip())), "Expected nonempty text")


def _task_key(text):
    return "".join(text.split()).casefold()


def _clock(value=None):
    value = value if value is not None else datetime.now().astimezone()
    _require(isinstance(value, datetime) and value.utcoffset() is not None,
             "Clock must include timezone")
    return value


def validate(record):
    _fields(record, "schema_version revision learning_state learning_evidence adaptive_review session_state")
    _require(type(record["schema_version"]) is int and record["schema_version"] == 1,
             "Unsupported schema_version")
    _require(type(record["revision"]) is int and record["revision"] >= 0, "Invalid revision")
    state = record["learning_state"]
    _fields(state, "goal knowledge_point verification_status")
    _text(state["goal"])
    _text(state["knowledge_point"])
    _require(state["verification_status"] in
             ("unverified", "immediate_passed", "delayed_passed", "needs_review"), "Invalid status")
    evidence = record["learning_evidence"]
    _require(isinstance(evidence, list), "Expected evidence list")
    prior = []
    for item in evidence:
        _fields(item, "task_summary response_summary reasoning_summary correctness assistance task_relation occurred_at")
        _text(item["task_summary"])
        _text(item["response_summary"])
        _text(item["reasoning_summary"], nullable=True)
        _require(item["correctness"] in ("correct", "partial", "incorrect", "unknown"), "Invalid correctness")
        _require(item["assistance"] in ("independent", "hinted", "explained"), "Invalid assistance")
        _require(item["task_relation"] in ("original", "related", "delayed"), "Invalid task relation")
        try:
            timestamp = datetime.fromisoformat(item["occurred_at"])
            _require(timestamp.utcoffset() is not None, "Timestamp must include timezone")
        except (TypeError, ValueError) as exc:
            raise StoreError("Invalid timestamp with timezone") from exc
        if prior:
            _require(timestamp >= datetime.fromisoformat(prior[-1]["occurred_at"]), "Evidence time moved backwards")
        if item["task_relation"] in ("related", "delayed"):
            _require(all(_task_key(item["task_summary"]) != _task_key(old["task_summary"]) for old in prior),
                     "Retest must use a different task")
        if item["task_relation"] == "delayed":
            _require(bool(prior) and timestamp - datetime.fromisoformat(prior[-1]["occurred_at"]) >= timedelta(hours=24),
                     "Delayed retest requires at least 24 hours since the previous attempt")
        prior.append(item)
    status = state["verification_status"]
    if status in ("immediate_passed", "delayed_passed"):
        _require(bool(evidence), "Passed status requires evidence")
        last = evidence[-1]
        _require(last["correctness"] == "correct" and last["assistance"] == "independent"
                 and last["reasoning_summary"] is not None, "Passed status requires independent reasoning")
        _require((last["task_relation"] == "delayed") == (status == "delayed_passed"),
                 "Passed status does not match evidence")
    review = record["adaptive_review"]
    _fields(review, "due_date")
    if review["due_date"] is not None:
        try:
            _require(date.fromisoformat(review["due_date"]).isoformat() == review["due_date"], "Invalid date")
        except (TypeError, ValueError) as exc:
            raise StoreError("Invalid review date") from exc
    session = record["session_state"]
    _fields(session, "phase pending_question resume_note")
    _require(session["phase"] in ("intake", "explain", "await_answer", "await_diagnosis", "paused"), "Invalid phase")
    _text(session["pending_question"], nullable=True)
    _text(session["resume_note"], nullable=True)
    if session["phase"] in ("await_answer", "await_diagnosis"):
        _require(session["pending_question"] is not None, "Waiting phase requires question")
    return record


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _decode(text):
    try:
        return validate(json.loads(text, object_pairs_hook=_unique_pairs))
    except (TypeError, ValueError) as exc:
        if isinstance(exc, StoreError):
            raise
        raise StoreError("Invalid learning record") from exc


def _path(path):
    path = Path(path)
    _require(path.is_absolute(), "Explicit absolute data path required")
    _require(path.name == "learning-state.json", "Use learning-state.json")
    _require(not path.is_symlink(), "Symbolic-link data file is not supported")
    path = path.resolve()
    _require(not path.is_relative_to(Path(__file__).resolve().parents[1]),
             "Learning data must be outside the Skill repository")
    return path


def load(path):
    path = _path(path)
    try:
        record = _decode(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise StoreError("Cannot read learning record; original retained") from exc
    _require(record["revision"] >= 1, "Stored revision must be positive")
    return record


@contextmanager
def _lock(path):
    lock_path = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ConflictError("Store is locked; do not overwrite") from exc
    try:
        os.close(fd)
        yield
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass


def save(path, record, expected_revision):
    """Draft revision must match expected_revision; zero means create only."""
    path = _path(path)
    _require(type(expected_revision) is int and expected_revision >= 0, "Invalid expected revision")
    # Snapshot caller input before validation so later caller mutations cannot affect the write.
    record = _decode(json.dumps(record, ensure_ascii=False, allow_nan=False))
    _require(record["revision"] == expected_revision, "Draft revision mismatch")
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock(path):
            current = load(path)
            actual_revision = current["revision"] if current else 0
            if actual_revision != expected_revision:
                raise ConflictError("Revision conflict; reload before saving")
            if current:
                for field in ("goal", "knowledge_point"):
                    _require(current["learning_state"][field] == record["learning_state"][field],
                             "Keep the old record before starting a different goal or knowledge point")
                old = current["learning_evidence"]
                _require(record["learning_evidence"][:len(old)] == old, "Existing evidence must be retained")
            record["revision"] = actual_revision + 1
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix="learning-state.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            # Same-directory replacement keeps the previous complete file until the final step.
            os.replace(temporary, path)
        return record
    except OSError as exc:
        raise StoreError("Save failed; new progress was not saved") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def save_confirmed(path, record, expected_revision, confirmed=False):
    """Caller must obtain human consent before setting confirmed=True."""
    _require(confirmed is True, "Save not confirmed; no data written")
    return save(path, record, expected_revision)


def review_status(record, now=None):
    validate(record)
    now = _clock(now)
    evidence = record["learning_evidence"]
    eligible = bool(evidence) and now - datetime.fromisoformat(evidence[-1]["occurred_at"]) >= timedelta(hours=24)
    due_date = record["adaptive_review"]["due_date"]
    return {"due": due_date is not None and date.fromisoformat(due_date) <= now.date(),
            "due_date": due_date, "delayed_eligible": eligible,
            "timing": "delayed" if eligible else "early_or_no_evidence"}


def _current(path, expected_revision, confirmed):
    _require(confirmed is True, "Save not confirmed; no data written")
    _require(type(expected_revision) is int and expected_revision >= 1, "Existing revision required")
    record = load(path)
    _require(record is not None, "No learning record to update")
    if record["revision"] != expected_revision:
        raise ConflictError("Revision conflict; reload before saving")
    return record


def schedule_review(path, expected_revision, confirmed=False, now=None):
    record = _current(path, expected_revision, confirmed)
    now = _clock(now)
    _require(bool(record["learning_evidence"]), "Review scheduling requires an actual attempt")
    _require(now >= datetime.fromisoformat(record["learning_evidence"][-1]["occurred_at"]), "Clock precedes evidence")
    days = 3 if record["learning_state"]["verification_status"] == "delayed_passed" else 1
    record["adaptive_review"]["due_date"] = (now.date() + timedelta(days=days)).isoformat()
    return save_confirmed(path, record, expected_revision, confirmed=True)


def record_review(path, answer, expected_revision, confirmed=False, now=None):
    record = _current(path, expected_revision, confirmed)
    _fields(answer, "task_summary response_summary reasoning_summary correctness assistance")
    now = _clock(now)
    timing = review_status(record, now)
    item = dict(answer, task_relation="delayed" if timing["delayed_eligible"] else "related",
                occurred_at=now.isoformat())
    record["learning_evidence"].append(item)
    independent_correct = (item["correctness"] == "correct" and item["assistance"] == "independent"
                           and isinstance(item["reasoning_summary"], str) and bool(item["reasoning_summary"].strip()))
    if independent_correct:
        status = "delayed_passed" if item["task_relation"] == "delayed" else "immediate_passed"
        next_action = "continue_or_review_by_choice"
    else:
        status = "needs_review"
        next_action = "diagnose" if item["correctness"] in ("incorrect", "partial") else "check_without_help"
    record["learning_state"]["verification_status"] = status
    days = 3 if status == "delayed_passed" else 1
    record["adaptive_review"]["due_date"] = (now.date() + timedelta(days=days)).isoformat()
    record["session_state"] = {"phase": "paused", "pending_question": None,
                               "resume_note": "Retest recorded; next action: " + next_action + ". Only this knowledge point was checked."}
    saved = save_confirmed(path, record, expected_revision, confirmed=True)
    return {"status": "saved", "record": saved, "next_action": next_action,
            "timing": item["task_relation"]}


def resume(path, now=None):
    """Return a factual view and optional review choice; never invent history."""
    try:
        record = load(path)
    except (StoreError, OSError):
        return {"status": "unavailable", "reason": "invalid_or_unreadable",
                "message": "没有找到可恢复记录：文件损坏、格式不支持、路径无效或无法读取。原文件未修改。"}
    if record is None:
        return {"status": "unavailable", "reason": "missing",
                "message": "没有找到可恢复记录：指定位置没有记录文件。"}
    state, session = record["learning_state"], record["session_state"]
    review = review_status(record, now)
    return {"status": "recovered", "record": record,
            "summary": {"goal": state["goal"], "knowledge_point": state["knowledge_point"],
                        "verification_status": state["verification_status"],
                        "phase": session["phase"], "pending_question": session["pending_question"],
                        "next_step": session["resume_note"] or "确认继续位置，再选择下一步。"},
            "review": review,
            "choices": ["先复习", "继续学习", "更换目标"] if review["due"] else ["继续", "复习", "更换目标"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("read", "resume", "save", "review-status", "review-schedule", "review-result", "review-skip"))
    parser.add_argument("--path", required=True)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--confirmed", action="store_true", help="Only after the user explicitly authorizes saving to this path")
    parser.add_argument("--test-now", help="Explicit simulated clock for tests only; ISO timestamp with timezone")
    args = parser.parse_args()
    try:
        now = _clock(datetime.fromisoformat(args.test_now)) if args.test_now else None
        if args.operation == "read":
            result = {"status": "ok", "record": load(args.path)}
        elif args.operation == "resume":
            result = resume(args.path, now)
        elif args.operation == "review-status":
            record = load(args.path)
            _require(record is not None, "No learning record")
            result = review_status(record, now)
        elif args.operation == "review-skip":
            _require(load(args.path) is not None, "No learning record")
            result = {"status": "skipped", "message": "No state, evidence or review date changed"}
        elif args.operation == "review-schedule":
            result = {"status": "saved", "record": schedule_review(args.path, args.expected_revision, args.confirmed, now)}
        elif args.operation == "review-result":
            _require(args.confirmed, "Save not confirmed; no data written")
            answer = json.loads(sys.stdin.read(), object_pairs_hook=_unique_pairs)
            result = record_review(args.path, answer, args.expected_revision, args.confirmed, now)
        else:
            _require(args.confirmed, "Save not confirmed; no data written")
            _require(args.expected_revision is not None, "Save requires expected revision")
            result = {"status": "saved", "record": save_confirmed(args.path, _decode(sys.stdin.read()), args.expected_revision, confirmed=True)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
