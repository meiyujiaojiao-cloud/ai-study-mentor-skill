"""Unit workflow metadata, separate from point evidence and assessment records."""
import argparse
import copy
import json
import sys

import course_entry as entry
import personal_library as library
import learning_store as store
import material_import as materials

FILE = "单元状态.json"
STATES = {"learning", "ready_for_test", "testing", "completed", "paused"}
LABELS = {"learning": "正在学习", "ready_for_test": "等待单元检测", "testing": "正在检测",
          "completed": "已完成检测（不代表全部能力已验证）", "paused": "已暂停，保留位置"}


def validate(doc, course_id):
    store._fields(doc, "kind schema_version revision course_id units")
    entry._header(doc, "unit_status", course_id)
    store._require(isinstance(doc["units"], list), "Invalid units")
    seen = set()
    for unit in doc["units"]:
        store._fields(unit, "chapter_id unit_status resume_status position_note basis")
        library._id(unit["chapter_id"])
        store._require(unit["chapter_id"] not in seen, "Duplicate unit")
        seen.add(unit["chapter_id"])
        store._require(isinstance(unit["unit_status"], str) and unit["unit_status"] in STATES, "Unknown unit status")
        store._require((unit["unit_status"] == "paused" and isinstance(unit["resume_status"], str) and
                        unit["resume_status"] in STATES - {"paused"}) or
                       (unit["unit_status"] != "paused" and unit["resume_status"] is None), "Invalid resume status")
        store._text(unit["position_note"], nullable=True)
        basis = unit["basis"]
        store._fields(basis, "learned_point_ids required_exercises_completed assessment_path assessment_completed")
        store._require(isinstance(basis["learned_point_ids"], list), "Invalid learned points")
        for point_id in basis["learned_point_ids"]:
            library._id(point_id)
        store._require(len(set(basis["learned_point_ids"])) == len(basis["learned_point_ids"]), "Duplicate learned points")
        store._require(type(basis["required_exercises_completed"]) is bool and
                       type(basis["assessment_completed"]) is bool, "Explicit workflow facts required")
        if basis["assessment_path"] is not None:
            library._path(basis["assessment_path"])
    return doc


def read(root, course_id):
    path = entry._file(root, course_id, FILE)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return validate(json.loads(text, object_pairs_hook=store._unique_pairs), course_id)


def save_status(path, course_id, chapter_id, status, basis, position_note,
                expected_index_revision, expected_revision, confirmed=False):
    root = library.library_root(path)
    store._require(status in STATES | {"resume"}, "Unknown status operation")
    with library._writing(root, confirmed):
        index = library.read_index(root)
        library._expect(index, expected_index_revision)
        course = library._course(index, course_id)
        chapter = next((c for c in course["chapters"] if c["id"] == chapter_id), None)
        store._require(chapter is not None, "Unit is not in the selected course")
        old = read(root, course_id)
        entry._expect(old, expected_revision)
        doc = copy.deepcopy(old) if old else {"kind": "unit_status", "schema_version": 1,
            "revision": 0, "course_id": course_id, "units": []}
        previous = next((u for u in doc["units"] if u["chapter_id"] == chapter_id), None)
        if status == "resume":
            store._require(previous is not None and previous["unit_status"] == "paused", "No paused unit to resume")
            unit = copy.deepcopy(previous)
            unit["unit_status"], unit["resume_status"] = previous["resume_status"], None
        else:
            store._require(status != "paused" or previous is not None, "Save a known position before pausing")
            unit = {"chapter_id": chapter_id, "unit_status": status, "resume_status": None,
                    "position_note": position_note, "basis": copy.deepcopy(basis)}
            if status == "paused":
                unit = copy.deepcopy(previous)
                unit["resume_status"] = previous["resume_status"] if previous["unit_status"] == "paused" else previous["unit_status"]
                unit["unit_status"] = "paused"
                if position_note is not None:
                    unit["position_note"] = position_note
        doc["units"] = [u for u in doc["units"] if u["chapter_id"] != chapter_id] + [unit]
        doc["revision"] += 1
        validate(doc, course_id)
        counts = []
        for point_id in unit["basis"]["learned_point_ids"]:
            point = library._point(course, point_id)
            store._require(point["chapter_id"] == chapter_id, "Learning evidence belongs to another unit")
            _, record = library._record(root, course, point)
            counts.append(len(record["learning_evidence"]))
        if unit["unit_status"] == "ready_for_test":
            store._require(bool(counts) and all(counts) and unit["basis"]["required_exercises_completed"],
                           "Readiness needs actual learning evidence and confirmation of necessary practice")
        assessment = None
        if unit["basis"]["assessment_path"] is not None:
            assessment = store.load(library._path(unit["basis"]["assessment_path"]))
            store._require(assessment is not None and assessment["learning_state"]["knowledge_point"] ==
                           "单元综合检测：" + chapter["title"], "Assessment scope does not match the unit")
        if unit["unit_status"] == "completed":
            store._require(unit["basis"]["assessment_completed"] and assessment is not None and
                           bool(assessment["learning_evidence"]) and assessment["session_state"]["pending_question"] is None,
                           "Completion needs a finished assessment record and explicit confirmation")
        target = entry._file(root, course_id, FILE)
        target.parent.mkdir(parents=True, exist_ok=True)
        library._backup(root, target)
        library._atomic_json(target, doc)
        return {"status": "saved", "revision": doc["revision"], "unit": unit,
                "learned_point_count": len(counts), "evidence_count": sum(counts),
                "message": "只保存单元阶段，没有改写知识点、检测证据、笔记或复习日期。"}


def continue_learning(path, course_id=None, point_id=None):
    root = library.library_root(path)
    view = materials.continue_learning(root, course_id, point_id)
    if view.get("course_id") is None:
        return view
    try:
        doc = read(root, view["course_id"])
        saved = {u["chapter_id"]: u for u in doc["units"]} if doc else {}
        actual_ids = {c["id"] for c in view["chapters"]}
        store._require(set(saved).issubset(actual_ids), "Unit status refers to an unknown chapter")
        view["unit_status_revision"] = doc["revision"] if doc else 0
        view["unit_states"] = [{**c, **saved.get(c["id"], {"unit_status": "learning", "resume_status": None,
            "position_note": None}), "saved": c["id"] in saved,
            "status_label": LABELS[saved[c["id"]]["unit_status"]] if c["id"] in saved else "尚未保存单元状态，默认学习阶段"}
            for c in view["chapters"]]
        current = next((p["chapter_id"] for p in view["points"] if p["id"] == view["point_id"]), None)
        view["current_unit_state"] = next((u for u in view["unit_states"] if u["id"] == current), None)
    except (ValueError, OSError, TypeError) as exc:
        view["supplement_errors"].append({"file": FILE, "message": str(exc)})
        view["unit_states"], view["current_unit_state"] = None, None
    return view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("continue", "set"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--course-id")
    parser.add_argument("--point-id")
    parser.add_argument("--chapter-id")
    parser.add_argument("--status", choices=sorted(STATES | {"resume"}))
    parser.add_argument("--expected-index-revision", type=int)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "continue":
            result = continue_learning(args.root, args.course_id, args.point_id)
        else:
            payload = json.loads(sys.stdin.read(), object_pairs_hook=store._unique_pairs)
            store._fields(payload, "basis position_note")
            result = save_status(args.root, args.course_id, args.chapter_id, args.status,
                payload["basis"], payload["position_note"], args.expected_index_revision, args.expected_revision, args.confirmed)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
