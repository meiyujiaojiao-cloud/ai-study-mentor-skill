"""Local outline preview and confirmed chapter import; no network, OCR or teaching inference."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import course_entry as entry
import export_learning as exporter
import personal_library as library
import learning_store as store

MAX_BYTES = 256 * 1024 * 1024
MAX_ITEMS = 1000
RECEIPT = "教材导入记录.json"
TITLE = re.compile(r"^(?:第[\d一二三四五六七八九十百零〇两]+[章篇部节]|chapter\s+\d+|\d+(?:\.\d+)*[.、．\s])", re.I)
FRONT = {"目录", "目次", "contents", "table of contents"}


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(text):
    return re.sub(r"(?:\.{2,}|…+|·{2,})\s*\d+\s*$", "", text.strip()).strip()


def _lines(text, source):
    items = []
    for number, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip()
        markdown = re.match(r"^(#{1,6})\s+(.+)", raw)
        title = _clean(markdown[2] if markdown else raw)
        if not title or len(title) > 240 or (not markdown and not TITLE.match(title)):
            continue
        level = len(markdown[1]) if markdown else 1
        numeric = re.match(r"^(\d+(?:\.\d+)*)[.、．\s]", title)
        if not markdown and numeric:
            level = numeric[1].count(".") + 1
        if title.startswith("第") and "节" in title[:12] and "章" not in title[:12]:
            level = 2
        items.append({"title": title, "level": level, "source": f"{source}{' Markdown标题' if markdown else ''}，第{number}行"})
    return items


def _pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise store.StoreError("PDF目录读取需要pypdf；请选择已配置该库的Python环境。本工具不会安装依赖。") from exc
    warnings, items = [], []
    reader = PdfReader(str(path))
    store._require(not reader.is_encrypted, "加密PDF暂不读取，请用户提供可读版本或手动目录。")
    def visit(nodes, level=1):
        if level > 12 or len(items) >= MAX_ITEMS:
            warnings.append("PDF书签层级或条目过多，预览已截断；确认前检查是否遗漏。")
            return
        for node in nodes:
            if len(items) >= MAX_ITEMS:
                warnings.append("PDF书签超过预览限制，仅显示部分目录。")
                break
            if isinstance(node, list):
                visit(node, level + 1)
                continue
            title = _clean(str(getattr(node, "title", "")))
            if not title or len(title) > 240:
                continue
            try:
                page = reader.get_destination_page_number(node)
            except (ValueError, TypeError):
                page = None
            items.append({"title": title, "level": level,
                          "source": f"PDF书签，物理页{page + 1}" if page is not None else "PDF书签，页码未知"})
    try:
        visit(reader.outline)
    except Exception as exc:
        warnings.append("PDF书签无法完整读取：" + type(exc).__name__)
    if items:
        return items, warnings, "pdf_bookmarks"
    count = min(len(reader.pages), 40)
    warnings.append(f"没有可用书签；仅检查前{count}个物理页的标题/目录文字，可能遗漏或误识别，并非完整教材理解。")
    for number in range(count):
        try:
            items.extend(_lines(reader.pages[number].extract_text() or "", f"PDF物理页{number + 1}"))
        except Exception as exc:
            warnings.append(f"物理页{number + 1}提取失败：{type(exc).__name__}")
        if len(items) >= MAX_ITEMS:
            warnings.append("目录候选超过限制，仅保留前1000项。")
            break
    if not items:
        warnings.append("没有识别到目录。可能为扫描件或标题格式不支持；无OCR，请用户提供目录文字。")
    return items[:MAX_ITEMS], warnings, "pdf_text_candidates"


def _pptx(path):
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
          "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    warnings, titles, contents = [], [], []
    with zipfile.ZipFile(path) as package:
        total = 0
        def xml(name):
            nonlocal total
            info = package.getinfo(name)
            total += info.file_size
            store._require(info.file_size <= 4 * 1024 * 1024 and total <= 64 * 1024 * 1024,
                           "PPTX目录XML超过安全读取限制。")
            return ET.fromstring(package.read(name))
        presentation = xml("ppt/presentation.xml")
        relationships = xml("ppt/_rels/presentation.xml.rels")
        targets = {item.get("Id"): item.get("Target") for item in relationships
                   if item.get("Type", "").endswith("/slide") and item.get("TargetMode") != "External"}
        slides = presentation.findall("p:sldIdLst/p:sldId", ns)
        store._require(len(slides) <= MAX_ITEMS, "PPTX幻灯片数量超过预览限制。")
        for number, slide in enumerate(slides, 1):
            target = targets.get(slide.get("{" + ns["r"] + "}id"))
            store._require(isinstance(target, str), "PPTX幻灯片关系缺失或为外部链接。")
            name = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "ppt/" + target)
            store._require(re.fullmatch(r"ppt/slides/slide\d+\.xml", name), "PPTX幻灯片路径异常。")
            root = xml(name)
            paragraphs = ["".join(t.text or "" for t in p.findall(".//a:t", ns)).strip()
                          for p in root.findall(".//a:p", ns)]
            title = None
            for shape in root.findall("p:cSld/p:spTree/p:sp", ns):
                placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", ns)
                if placeholder is not None and placeholder.get("type") in ("title", "ctrTitle"):
                    title = " ".join(t.text or "" for t in shape.findall(".//a:t", ns)).strip()
                    break
            title = title or next((p for p in paragraphs if p), "")
            title = _clean(title)
            if title.casefold() in FRONT:
                for line in paragraphs:
                    candidate = _clean(line)
                    if candidate and len(candidate) <= 240 and candidate.casefold() not in FRONT:
                        contents.append({"title": candidate, "level": 1, "source": f"PPTX第{number}张目录段落"})
            elif title and len(title) <= 240:
                titles.append({"title": title, "level": 1, "source": f"PPTX第{number}张标题"})
    warnings.append("PPTX目录段落或幻灯片标题仅是章节候选，需人工确认；未读取备注、图片或外部资源。")
    return contents or titles, warnings, "pptx_contents" if contents else "pptx_titles"


def _txt(path):
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gb18030")
    items = _lines(text, "TXT")
    warnings = ["TXT按章标题、编号或Markdown标题提取候选；不判断正文语义，需检查层级与遗漏。"]
    if len(items) > MAX_ITEMS:
        warnings.append("标题超过1000项，预览已截断。")
    return items[:MAX_ITEMS], warnings, "txt_headings"


def _proposals(outline):
    candidates = [item for item in outline if item["title"].casefold() not in FRONT]
    explicit = [item for item in candidates if re.match(r"^(?:第[\d一二三四五六七八九十百零〇两]+章|chapter\s+\d+)", item["title"], re.I)]
    if any("Markdown标题" in item["source"] for item in candidates):
        explicit = []
    chosen = explicit or [item for item in candidates if item["level"] == min((i["level"] for i in candidates), default=1)]
    return list(dict.fromkeys(item["title"] for item in chosen))


def preview(path, course_id, source, metadata=None):
    root = library.library_root(path)
    index = library.read_index(root)
    library._course(index, course_id)
    previous = entry._read(root, course_id, "course.json")
    registry = entry._read(root, course_id, "material.json")
    source = library._path(source)
    store._require(source.is_file(), "请明确提供当前环境可读取的教材文件。")
    store._require(source.stat().st_size <= MAX_BYTES, "首阶段只处理不超过256MB的文件。")
    extension = source.suffix.lower()
    store._require(extension in (".pdf", ".pptx", ".txt"), "支持PDF、PPTX、TXT；旧PPT请先另存为PPTX，原文件不改。")
    first_hash = _hash(source)
    try:
        outline, warnings, method = {".pdf": _pdf, ".pptx": _pptx, ".txt": _txt}[extension](source)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, UnicodeError) as exc:
        raise store.StoreError("文件格式或编码无法读取，请提供可读版本或手动目录。") from exc
    store._require(_hash(source) == first_hash, "文件在提取过程中改变，请重新预览。")
    details = {"title": source.stem, "author": None, "publication": None, "isbn": None,
               "version": None, "chapter": None, "source": "用户主动提供文件；原始来源未说明"}
    if metadata is not None:
        store._require(isinstance(metadata, dict) and set(metadata).issubset(details), "Unknown material metadata field")
        details.update(metadata)
    for key, value in details.items():
        if key in ("title", "source"):
            store._text(value)
        else:
            entry._optional_text(value)
    chapters = _proposals(outline)
    if len(chapters) > 200:
        warnings.append("章节候选超过200章，草稿只保留前200章；请人工核对遗漏。")
        chapters = chapters[:200]
    if not chapters:
        warnings.append("未生成章节草稿，不编造目录。请用户手动提供章节后再确认。")
    return {"kind": "material_import_draft", "schema_version": 1, "library_root": str(root),
            "course_id": course_id, "index_revision": index["revision"],
            "course_revision": previous["revision"] if previous else 0,
            "material_revision": registry["revision"] if registry else 0,
            "source_path": str(source), "source_sha256": first_hash, "method": method,
            "metadata": {**details, "location": str(source)}, "outline": outline,
            "chapters": chapters, "warnings": warnings,
            "status": "review_required" if chapters else "manual_outline_required"}


def write_preview(draft, output_dir):
    output = exporter._plain_path(output_dir)
    root = library.library_root(draft["library_root"])
    store._require(not output.is_relative_to(root) and not output.is_relative_to(library.REPO),
                   "确认前的草稿放在学习库和代码仓库之外。")
    for parent in (output, *output.parents):
        store._require(not (parent / ".git").exists(), "个人草稿不能写入Git仓库。")
    store._require(not output.exists(), "草稿目录已存在，请选择新目录。")
    text = ["# 教材目录草稿：尚未写入课程", "提取结果只是候选。请检查教材信息、章节顺序、遗漏与来源，确认前不增加章节或学习证据。",
            "## 教材登记信息", exporter._block(json.dumps(draft["metadata"], ensure_ascii=False, indent=2)),
            "## 建议章节", exporter._block("\n".join(f"{i}. {title}" for i, title in enumerate(draft["chapters"], 1)) or "未识别，请手动提供"),
            "## 原始目录候选与来源", exporter._block("\n".join(f"层级{item['level']}：{item['title']} — {item['source']}" for item in draft["outline"]) or "未识别"),
            "## 限制与警告", exporter._block("\n".join(draft["warnings"])),
            "只有用户明确确认后的章节才可写入。允许删改草稿，改名后的标题记为用户确认，不冒称教材原文。"]
    output.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        for name, content in (("教材导入草稿.json", json.dumps(draft, ensure_ascii=False, indent=2)),
                              ("教材目录预览.md", "\n\n".join(text) + "\n")):
            with (output / name).open("x", encoding="utf-8") as stream:
                created.append(output / name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
    except OSError:
        for file in created:
            file.unlink(missing_ok=True)
        output.rmdir()
        raise
    return {"status": draft["status"], "draft": str(output / "教材导入草稿.json"),
            "preview": str(output / "教材目录预览.md"), "chapter_count": len(draft["chapters"]),
            "warnings": draft["warnings"]}


def _receipts(root, course_id):
    target = entry._file(root, course_id, RECEIPT)
    try:
        doc = json.loads(target.read_text(encoding="utf-8"), object_pairs_hook=store._unique_pairs)
    except FileNotFoundError:
        return {"kind": "material_imports", "schema_version": 1, "revision": 0, "course_id": course_id, "imports": []}
    store._fields(doc, "kind schema_version revision course_id imports")
    store._require(doc["kind"] == "material_imports" and type(doc["schema_version"]) is int and doc["schema_version"] == 1,
                   "Unknown import receipt version")
    store._require(doc["course_id"] == course_id and type(doc["revision"]) is int and doc["revision"] >= 1,
                   "Invalid import receipt")
    store._require(isinstance(doc["imports"], list), "Invalid import records")
    keys = set()
    for item in doc["imports"]:
        store._fields(item, "key source_sha256 source_path material_id chapter_ids chapter_titles imported_at")
        store._require(isinstance(item["key"], str) and re.fullmatch(r"[0-9a-f]{64}", item["key"]) and item["key"] not in keys, "Duplicate import receipt")
        keys.add(item["key"])
        store._require(isinstance(item["source_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", item["source_sha256"]), "Invalid source hash")
        store._require(isinstance(item["source_path"], str) and Path(item["source_path"]).is_absolute(), "Invalid receipt source")
        store._require(isinstance(item["imported_at"], str) and
                       datetime.fromisoformat(item["imported_at"]).utcoffset() is not None, "Invalid import time")
        library._id(item["material_id"])
        store._require(isinstance(item["chapter_ids"], list) and isinstance(item["chapter_titles"], list) and
                       len(item["chapter_ids"]) == len(item["chapter_titles"]), "Invalid chapter links")
        for identifier, title in zip(item["chapter_ids"], item["chapter_titles"]):
            library._id(identifier)
            store._text(title)
    return doc


def apply_preview(path, course_id, draft, confirmed=False):
    store._require(confirmed is True, "请先展示章节草稿并取得用户明确确认，不写入学习库。")
    root = library.library_root(path)
    store._fields(draft, "kind schema_version library_root course_id index_revision course_revision material_revision source_path source_sha256 method metadata outline chapters warnings status")
    store._require(draft["kind"] == "material_import_draft" and type(draft["schema_version"]) is int and
                   draft["schema_version"] == 1, "Unknown import draft version")
    store._require(library.library_root(draft["library_root"]) == root and draft["course_id"] == course_id,
                   "Draft belongs to another library or course")
    source = library._path(draft["source_path"])
    store._require(source.is_file() and source.stat().st_size <= MAX_BYTES and
                   source.suffix.lower() in (".pdf", ".pptx", ".txt") and
                   draft["metadata"]["location"] == str(source), "Source does not match the reviewed draft")
    store._require(_hash(source) == draft["source_sha256"], "教材内容已变化，请重新提取并确认。")
    store._require(isinstance(draft["chapters"], list) and 0 < len(draft["chapters"]) <= 200,
                   "请先确认至少一个章节，最多200章；未识别目录不能直接导入。")
    for title in draft["chapters"]:
        store._text(title)
        store._require(len(title) <= 240, "Chapter title too long")
    titles = list(dict.fromkeys(title.strip() for title in draft["chapters"]))
    key = hashlib.sha256(json.dumps([draft["source_sha256"], str(source), titles], ensure_ascii=False).encode()).hexdigest()
    receipts = _receipts(root, course_id)
    view = entry.continue_learning(root, course_id)
    store._require(not view["supplement_errors"], "课程补充信息无法读取，请先处理，不覆盖。")
    for old in receipts["imports"]:
        if old["key"] == key:
            store._require(all(cid in {c["id"] for c in view["chapters"]} for cid in old["chapter_ids"]) and
                           old["material_id"] in {m["id"] for m in view["registered_materials"]},
                           "Receipt links need manual repair")
            return {"status": "already_imported", "receipt": old, "message": "相同教材与章节已导入，没有重复追加。"}
    library._expect(library.read_index(root), draft["index_revision"])
    entry._expect(entry._read(root, course_id, "course.json"), draft["course_revision"])
    entry._expect(entry._read(root, course_id, "material.json"), draft["material_revision"])
    material_id = next((m["id"] for m in view["registered_materials"] if m["location"] == str(source)), None)
    if material_id is None:
        material_id = next((r["material_id"] for r in receipts["imports"] if r["source_sha256"] == draft["source_sha256"]), None)
    registered = entry.register_material(root, course_id, draft["metadata"], draft["index_revision"],
                                        draft["material_revision"], draft["course_revision"], True, material_id)
    if registered["status"] == "partial_saved":
        return {**registered, "chapters_saved": False, "receipt_saved": False}
    material_id = registered["material"]["id"]
    chapters_saved = False
    try:
        with library._writing(root, True):
            index = library.read_index(root)
            library._expect(index, draft["index_revision"])
            previous = entry._read(root, course_id, "course.json")
            registry = entry._read(root, course_id, "material.json")
            entry._expect(previous, registered["course"]["revision"])
            entry._expect(registry, registered["material_revision"])
            current_receipts = _receipts(root, course_id)
            store._require(current_receipts["revision"] == receipts["revision"], "Import receipt changed; reread")
            course = library._course(index, course_id)
            chapters = [library._chapter(course, title) for title in titles]
            index["revision"] += 1
            library._save_index(root, index)
            chapters_saved = True
            snapshot = entry._snapshot(index, course, previous, registry)
            entry._write(root, course_id, "course.json", snapshot)
            receipt = {"key": key, "source_sha256": draft["source_sha256"], "source_path": str(source),
                       "material_id": material_id, "chapter_ids": [c["id"] for c in chapters],
                       "chapter_titles": titles, "imported_at": store._clock().isoformat()}
            current_receipts["imports"].append(receipt)
            current_receipts["revision"] += 1
            target = entry._file(root, course_id, RECEIPT)
            library._backup(root, target)
            library._atomic_json(target, current_receipts)
    except (OSError, ValueError) as exc:
        return {"status": "partial_saved", "material_id": material_id,
                "chapters_saved": chapters_saved, "receipt_saved": False,
                "message": "教材登记已保存，但目录或关联未全部保存。重新预览并核对，不能称导入完成。", "reason": str(exc)}
    return {"status": "imported", "material_id": material_id, "chapters": chapters,
            "receipt": receipt, "message": "仅写入已确认章节及教材关联，没有学习证据或掌握结论。"}


def continue_learning(path, course_id=None, point_id=None):
    root = library.library_root(path)
    view = entry.continue_learning(root, course_id, point_id)
    if view.get("course_id") is None:
        return view
    try:
        receipts = _receipts(root, view["course_id"])
    except (ValueError, OSError) as exc:
        view["supplement_errors"].append({"file": RECEIPT, "message": str(exc)})
        view["chapter_materials"] = None
        return view
    current_chapter = next((p["chapter_id"] for p in view["points"] if p["id"] == view["point_id"]), None)
    view["imported_chapters"] = [{"material_id": r["material_id"], "chapters": r["chapter_titles"]} for r in receipts["imports"]]
    view["chapter_materials"] = [m for m in view["registered_materials"] or [] if any(
        m["id"] == r["material_id"] and current_chapter in r["chapter_ids"] for r in receipts["imports"])]
    return view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preview", "apply", "continue"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--course-id")
    parser.add_argument("--point-id")
    parser.add_argument("--path", help="用户指定教材文件")
    parser.add_argument("--output-dir", help="学习库与仓库之外的新草稿目录")
    parser.add_argument("--draft", help="用户审阅的教材导入草稿.json")
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "preview":
            result = write_preview(preview(args.root, args.course_id, args.path), args.output_dir)
        elif args.operation == "apply":
            draft = json.loads(library._path(args.draft).read_text(encoding="utf-8"), object_pairs_hook=store._unique_pairs)
            result = apply_preview(args.root, args.course_id, draft, args.confirmed)
        else:
            result = continue_learning(args.root, args.course_id, args.point_id)
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result["status"] == "partial_saved" else 0
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
