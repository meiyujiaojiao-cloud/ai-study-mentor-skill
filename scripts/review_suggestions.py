"""Read-only review context; teaching Agent selects tasks from actual evidence, no forgetting model."""
import argparse
import json
import sys

import learning_store as store
import unit_status as units


def record_context(record):
    store.validate(record)
    evidence = record["learning_evidence"]
    reviews = [item for item in evidence if item["task_summary"].startswith("复习检查；")]
    return {"goal": record["learning_state"]["goal"],
        "knowledge_point": record["learning_state"]["knowledge_point"],
        "verification_status": record["learning_state"]["verification_status"],
        "last_actual_answer_at": evidence[-1]["occurred_at"] if evidence else None,
        "last_explicit_review_at": reviews[-1]["occurred_at"] if reviews else None,
        "suggested_review_date": record["adaptive_review"]["due_date"],
        "review_date_source": "saved_record" if record["adaptive_review"]["due_date"] else "not_saved",
        "unfinished_question": record["session_state"]["pending_question"],
        "next_step_context": record["session_state"]["resume_note"],
        "evidence_for_interpretation": evidence,
        "recommended_task_types": ["主动回忆", "新情境应用", "综合迁移", "按目标需要的专业表达"],
        "message": "结合真实分项观察选择一个检查；未测不等于薄弱，日期到期不等于遗忘。没有作答时只建议入门理解检查。"}


def suggestions(root=None, path=None, course_id=None, point_id=None):
    store._require((root is None) != (path is None), "Provide one explicit library or record path")
    if path is not None:
        record = store.load(path)
        if record is None:
            return {"status": "unavailable", "message": "没有找到可读取的学习记录，不生成历史或复习时间。"}
        return {"status": "ready", "record_path": str(store._path(path)), "revision": record["revision"],
                "review_suggestions": record_context(record), "choices": ["选择一个检查", "继续学习", "暂不复习"]}
    view = units.continue_learning(root, course_id, point_id)
    record = view.get("record")
    view["review_suggestions"] = record_context(record) if record else None
    state = view.get("current_unit_state")
    view["unit_review_position"] = {"unit_status": state["unit_status"], "resume_status": state["resume_status"],
        "position_note": state["position_note"]} if state else None
    view["review_choices"] = ["选择一个检查", "继续原位置", "暂不复习"]
    # Saved assessment pointers are displayed by the existing unit view, never opened here.
    return view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--root")
    group.add_argument("--path")
    parser.add_argument("--course-id")
    parser.add_argument("--point-id")
    args = parser.parse_args()
    try:
        result = suggestions(args.root, args.path, args.course_id, args.point_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
