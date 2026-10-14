"""V0.6 course intake and material metadata; no parsing, downloads or evidence changes."""
import argparse
import copy
from datetime import date, datetime
import json
from pathlib import Path
import sys

import personal_library as library
import learning_store as store

SUPPORTED = {".pdf", ".ppt", ".pptx", ".txt"}


def _optional_text(value):
    if value is not None:
        store._text(value)


def validate_intake(value):
    if value is None:
        return
    store._fields(value, "has_material exam_date baseline target")
    store._require(value["has_material"] is None or type(value["has_material"]) is bool, "Invalid material answer")
    for field in ("exam_date", "baseline", "target"):
        _optional_text(value[field])
    if value["exam_date"] is not None:
        store._require(date.fromisoformat(value["exam_date"]).isoformat() == value["exam_date"],
                       "Use an explicit YYYY-MM-DD examination date or null")


def _header(doc, kind, course_id):
    store._require(doc["kind"] == kind and type(doc["schema_version"]) is int and
                   doc["schema_version"] == 1, "Unsupported course entry version")
    store._require(doc["course_id"] == course_id, "Supplement belongs to another course")
    library._id(course_id)
    store._require(type(doc["revision"]) is int and doc["revision"] >= 1, "Invalid supplement revision")


def validate_course(doc, course_id):
    store._fields(doc, "kind schema_version revision course_id index_revision goal material_ids chapters intake")
    _header(doc, "course_entry", course_id)
    store._require(type(doc["index_revision"]) is int and doc["index_revision"] >= 1, "Invalid index revision")
    store._text(doc["goal"])
    store._require(isinstance(doc["material_ids"], list) and isinstance(doc["chapters"], list), "Invalid directory snapshot")
    seen = set()
    for identifier in doc["material_ids"]:
        library._id(identifier)
        store._require(identifier not in seen, "Duplicate material link")
        seen.add(identifier)
    seen = set()
    for chapter in doc["chapters"]:
        store._fields(chapter, "id title")
        library._id(chapter["id"])
        store._text(chapter["title"])
        store._require(chapter["id"] not in seen, "Duplicate chapter")
        seen.add(chapter["id"])
    validate_intake(doc["intake"])
    return doc


def validate_materials(doc, course_id):
    store._fields(doc, "kind schema_version revision course_id materials")
    _header(doc, "material_registry", course_id)
    store._require(isinstance(doc["materials"], list), "Invalid material registry")
    seen = set()
    for material in doc["materials"]:
        store._fields(material, "id title author publication isbn location file_name version file_updated_at chapter status source updated_at")
        library._id(material["id"])
        store._require(material["id"] not in seen, "Duplicate material ID")
        seen.add(material["id"])
        for field in ("title", "source"):
            store._text(material[field])
        for field in ("author", "publication", "isbn", "location", "file_name", "version", "file_updated_at", "chapter"):
            _optional_text(material[field])
        store._require(datetime.fromisoformat(material["updated_at"]).utcoffset() is not None, "Missing metadata timezone")
        if material["location"] is None:
            store._require(material["status"] == "no_file" and material["file_name"] is None and
                           material["file_updated_at"] is None, "No-file metadata cannot invent file properties")
        else:
            location = Path(material["location"])
            store._require(location.is_absolute() and location.suffix.lower() in SUPPORTED and
                           location.name == material["file_name"] and material["status"] == "available",
                           "Invalid registered file metadata")
            store._require(material["file_updated_at"] is not None and
                           datetime.fromisoformat(material["file_updated_at"]).utcoffset() is not None,
                           "Missing file modification time")
    return doc


def _file(root, course_id, name):
    return library._inside(root, "课程", library._id(course_id), name)


def _read(root, course_id, name):
    path = _file(root, course_id, name)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=store._unique_pairs)
    except FileNotFoundError:
        return None
    return validate_course(doc, course_id) if name == "course.json" else validate_materials(doc, course_id)


def _expect(doc, expected):
    actual = doc["revision"] if doc else 0
    store._require(type(expected) is int and expected >= 0, "Expected supplement revision required")
    if actual != expected:
        raise store.ConflictError("Supplement revision conflict; reread before writing")


def _write(root, course_id, name, doc):
    if name == "course.json":
        validate_course(doc, course_id)
    else:
        validate_materials(doc, course_id)
    path = _file(root, course_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    library._backup(root, path)
    library._atomic_json(path, doc)


def _snapshot(index, course, previous, materials, intake=None):
    return {"kind": "course_entry", "schema_version": 1,
            "revision": previous["revision"] + 1 if previous else 1, "course_id": course["id"],
            "index_revision": index["revision"], "goal": course["goal"],
            "material_ids": [m["id"] for m in materials["materials"]] if materials else [],
            "chapters": copy.deepcopy(course["chapters"]),
            "intake": copy.deepcopy(intake if intake is not None else previous["intake"] if previous else None)}


def wizard(path, title, goal=None):
    root = library.library_root(path)
    store._text(title)
    _optional_text(goal)
    index = library.read_index(root)
    candidates = [c for c in index["courses"] if c["title"].casefold() == title.strip().casefold()]
    questions = ["有没有教材？没有也可以先建立课程。", "有没有考试日期？没有可明确回答暂无。",
                 "当前基础怎样？不知道可以直接说不知道。", "希望达到什么程度，例如读懂概念、会做题或能独立应用？"]
    if not candidates and goal is None:
        questions.insert(0, "学习这门课的目标是什么？")
    entries = []
    for course in candidates:
        supplement = _read(root, course["id"], "course.json")
        entries.append({"course_id": course["id"], "title": course["title"], "goal": course["goal"],
                        "intake": supplement["intake"] if supplement else None,
                        "course_revision": supplement["revision"] if supplement else 0})
    if len(entries) == 1 and entries[0]["intake"] is not None:
        questions = []
    elif len(entries) > 1:
        questions = ["存在同名课程，请先选择实际课程编号，不自动合并。"]
    return {"status": "intake", "index_revision": index["revision"], "existing_courses": entries,
            "questions": questions, "provided_goal": goal,
            "message": "先补问缺失信息；已有课程先选择，不重复创建。不保存未确认的回答。"}


def setup_course(path, title, goal, intake, expected_index_revision, expected_course_revision,
                 confirmed=False, course_id=None):
    root = library.library_root(path)
    store._text(title)
    store._text(goal)
    store._require(intake is not None, "Obtain the user's intake answers before saving")
    validate_intake(intake)
    with library._writing(root, confirmed):
        index = library.read_index(root)
        library._expect(index, expected_index_revision)
        if course_id is None:
            matches = [c for c in index["courses"] if c["title"].casefold() == title.strip().casefold()]
            if matches:
                return {"status": "choose_existing", "courses": [{"id": c["id"], "title": c["title"]} for c in matches]}
            course_id = library._new_id()
            course = {"id": course_id, "title": title, "goal": goal, "chapters": [],
                      "points": [], "materials": [], "current_point_id": None}
            index["courses"].append(course)
        else:
            course = library._course(index, course_id)
            store._require(course["title"] == title, "Choose the actual course; renaming is not part of intake")
            course["goal"] = goal
        previous = _read(root, course_id, "course.json")
        materials = _read(root, course_id, "material.json")
        _expect(previous, expected_course_revision)
        index["current"] = {"course_id": course_id, "point_id": course["current_point_id"]}
        index["revision"] += 1
        snapshot = _snapshot(index, course, previous, materials, intake)
        validate_course(snapshot, course_id)
        library._save_index(root, index)
        try:
            _write(root, course_id, "course.json", snapshot)
        except OSError:
            return {"status": "partial_saved", "course_id": course_id, "index_revision": index["revision"],
                    "message": "课程目录已保存，但向导补充信息未保存。重新读取后选择同一course-id重试，不重复创建。"}
        return {"status": "saved", "course_id": course_id, "index_revision": index["revision"], "course": snapshot}


def add_chapter(path, course_id, title, expected_index_revision, expected_course_revision, confirmed=False):
    root = library.library_root(path)
    store._text(title)
    with library._writing(root, confirmed):
        index = library.read_index(root)
        library._expect(index, expected_index_revision)
        course = library._course(index, course_id)
        previous = _read(root, course_id, "course.json")
        materials = _read(root, course_id, "material.json")
        _expect(previous, expected_course_revision)
        chapter = library._chapter(course, title)
        index["revision"] += 1
        snapshot = _snapshot(index, course, previous, materials)
        library._save_index(root, index)
        try:
            _write(root, course_id, "course.json", snapshot)
        except OSError:
            return {"status": "partial_saved", "chapter": chapter, "index_revision": index["revision"],
                    "message": "章节目录已保存，course.json投影未更新。旧数据保留，读取时以索引为准。"}
        return {"status": "saved", "chapter": chapter, "index_revision": index["revision"], "course": snapshot}


def register_material(path, course_id, metadata, expected_index_revision, expected_material_revision,
                      expected_course_revision, confirmed=False, material_id=None):
    root = library.library_root(path)
    store._fields(metadata, "title author publication isbn location version chapter source")
    for field in ("title", "source"):
        store._text(metadata[field])
    for field in ("author", "publication", "isbn", "location", "version", "chapter"):
        _optional_text(metadata[field])
    # Only stat the exact user-specified file. Never open, copy, parse or discover documents.
    file_name, file_updated = None, None
    location = metadata["location"]
    if location is not None:
        selected = library._path(location)
        store._require(selected.suffix.lower() in SUPPORTED and selected.is_file(),
                       "Select an existing PDF, PPT/PPTX or TXT file, or register without a file")
        location = str(selected)
        file_name = selected.name
        file_updated = datetime.fromtimestamp(selected.stat().st_mtime).astimezone().isoformat()
    with library._writing(root, confirmed):
        index = library.read_index(root)
        library._expect(index, expected_index_revision)
        course = library._course(index, course_id)
        previous = _read(root, course_id, "course.json")
        registry = _read(root, course_id, "material.json")
        _expect(previous, expected_course_revision)
        _expect(registry, expected_material_revision)
        if registry is None:
            registry = {"kind": "material_registry", "schema_version": 1,
                        "revision": 0, "course_id": course_id, "materials": []}
        item = {**metadata, "id": library._id(material_id) if material_id else library._new_id(),
                "location": location, "file_name": file_name, "file_updated_at": file_updated,
                "status": "available" if location else "no_file", "updated_at": store._clock().isoformat()}
        if material_id:
            positions = [i for i, m in enumerate(registry["materials"]) if m["id"] == material_id]
            store._require(len(positions) == 1, "Material not in this course")
            registry["materials"][positions[0]] = item
        else:
            registry["materials"].append(item)
        registry["revision"] += 1
        snapshot = _snapshot(index, course, previous, registry)
        validate_materials(registry, course_id)
        validate_course(snapshot, course_id)
        _write(root, course_id, "material.json", registry)
        try:
            _write(root, course_id, "course.json", snapshot)
        except OSError:
            return {"status": "partial_saved", "material_id": item["id"], "material_revision": registry["revision"],
                    "message": "教材详情已保存，course.json关联投影未更新。重新读取，按同一material-id更新；不要重复追加。"}
        return {"status": "registered", "material": item, "material_revision": registry["revision"], "course": snapshot,
                "message": "仅登记教材元数据；没有读取正文、复制上传、联网搜索或验证来源授权。"}


def continue_learning(path, course_id=None, point_id=None):
    root = library.library_root(path)
    view = library.continue_learning(root, course_id, point_id)
    if view.get("course_id") is None:
        return view
    course_id = view["course_id"]
    supplements, errors = {}, []
    for name in ("course.json", "material.json"):
        try:
            supplements[name] = _read(root, course_id, name)
        except (ValueError, OSError) as exc:
            supplements[name] = None
            errors.append({"file": name, "message": str(exc)})
    supplement, registry = supplements["course.json"], supplements["material.json"]
    actual = library._course(library.read_index(root), course_id)
    materials = registry["materials"] if registry else []
    stale = supplement is not None and (supplement["goal"] != actual["goal"] or
            supplement["chapters"] != actual["chapters"] or
            supplement["material_ids"] != [m["id"] for m in materials])
    view.update(course_entry=supplement, registered_materials=None if any(e["file"] == "material.json" for e in errors) else materials,
                course_revision=supplement["revision"] if supplement else 0,
                material_revision=registry["revision"] if registry else 0,
                directory_snapshot_stale=stale, supplement_errors=errors)
    view["summary"]["last_position"] = view["summary"]["knowledge_point"]
    phase = view["summary"]["phase"]
    view["summary"]["position_status"] = "问题尚未完成" if view["summary"]["pending_question"] else "尚未开始作答验证" if phase == "intake" else "以已保存状态为准"
    return view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("wizard", "setup", "chapter", "material", "continue"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--course-id")
    parser.add_argument("--point-id")
    parser.add_argument("--material-id")
    parser.add_argument("--title")
    parser.add_argument("--goal")
    parser.add_argument("--expected-index-revision", type=int)
    parser.add_argument("--expected-course-revision", type=int)
    parser.add_argument("--expected-material-revision", type=int)
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "wizard":
            result = wizard(args.root, args.title, args.goal)
        elif args.operation == "continue":
            result = continue_learning(args.root, args.course_id, args.point_id)
        elif args.operation == "setup":
            intake = json.loads(sys.stdin.read(), object_pairs_hook=store._unique_pairs)
            result = setup_course(args.root, args.title, args.goal, intake, args.expected_index_revision,
                                  args.expected_course_revision, args.confirmed, args.course_id)
        elif args.operation == "chapter":
            result = add_chapter(args.root, args.course_id, args.title, args.expected_index_revision,
                                 args.expected_course_revision, args.confirmed)
        else:
            metadata = json.loads(sys.stdin.read(), object_pairs_hook=store._unique_pairs)
            result = register_material(args.root, args.course_id, metadata, args.expected_index_revision,
                                       args.expected_material_revision, args.expected_course_revision,
                                       args.confirmed, args.material_id)
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result["status"] == "partial_saved" else 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
