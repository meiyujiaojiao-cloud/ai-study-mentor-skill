"""Save an explicitly authorized Markdown note as a new file; never update learning state."""
import argparse
from datetime import datetime, timezone
import json
import os
import sys
from uuid import uuid4

import export_learning as exporter
import learning_store as store


def save_note(content, output_dir, confirmed=False):
    store._require(confirmed is True, "请先确认笔记内容、保存位置与文件写入授权。")
    store._text(content)
    output = exporter._plain_path(output_dir)
    store._require(not output.is_relative_to(exporter.REPO), "私人笔记不能保存到代码仓库。")
    for parent in (output, *output.parents):
        store._require(not (parent / ".git").exists(), "私人笔记不能保存到Git仓库。")
    output.mkdir(parents=True, exist_ok=True)
    name = "学习笔记-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-UTC") + "-" + uuid4().hex[:8] + ".md"
    target = output / name
    created = False
    try:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        raise
    return {"status": "note_saved", "path": str(target),
            "message": "仅保存新的笔记文件，没有保存或更改学习状态、作答证据和复习日期。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    try:
        result = save_note(sys.stdin.read(), args.output_dir, args.confirmed)
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
