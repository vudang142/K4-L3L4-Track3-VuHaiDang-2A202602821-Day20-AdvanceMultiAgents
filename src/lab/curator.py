"""GUIDE Phần 3 - Người tuyển chọn skill (skill curator): tự viết skill từ các lần chạy thất bại.   >>> SINH VIÊN CÀI ĐẶT curate_skills <<<

Pseudo-code: guides/pseudocode/04_curator.md
Kiểm tra:    pytest tests/test_04_curator.py
Chạy thật:   python -m lab.curator
"""
import json
import re
from pathlib import Path

from .model import make_model
from .tasks import ROOT, eval_markers   # có sẵn: định danh của tác vụ đánh giá, tính lúc chạy

# ---- CÓ SẴN, KHÔNG SỬA: kiểm tra và tách khối skill (phần dễ sai và liên quan bảo mật) ----------------
SAFE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_skill(text: str, expected_name: str | None = None) -> list[str]:
    """Kiểm tra nội dung một SKILL.md. Trả về danh sách vấn đề (rỗng = hợp lệ).

    Quy tắc: có khối YAML frontmatter; `name` chữ thường/số/gạch ngang (tối đa 64 ký tự) và bằng `expected_name`
    nếu được truyền; có `description` (tối đa 1024 ký tự); phần thân tối đa 80 dòng; không chứa chuỗi nào của
    `eval_markers()`. Quy tắc về `name` cũng là biện pháp bảo mật: tên khối do LLM sinh ra được dùng để tạo
    đường dẫn, nên `../evil` không được lọt qua.
    """
    problems = []
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text.strip() + "\n", re.S)
    if not m:
        return ["missing YAML frontmatter"]
    front, body = m.groups()
    name = re.search(r"^name:\s*(.+)$", front, re.M)
    desc = re.search(r"^description:\s*(.+)$", front, re.M)
    n = name.group(1).strip() if name else ""
    if not SAFE_NAME.fullmatch(n) or len(n) > 64:
        problems.append("invalid name")
    elif expected_name is not None and n != expected_name:
        problems.append("name differs from the block name")
    if not desc or len(desc.group(1).strip()) > 1024:
        problems.append("missing or too long description")
    if len(body.strip().splitlines()) > 80:
        problems.append("body longer than 80 lines")
    low = text.lower()
    for marker in eval_markers():
        if marker in low:
            problems.append(f"mentions evaluation material: {marker}")
    return problems


def parse_skill_blocks(reply: str) -> list[tuple[str, str]]:
    """Tách câu trả lời của LLM thành danh sách (name, nội dung SKILL.md).

    Khuôn dạng: `=== SKILL: <name> ===` ... `=== END ===`. Một khối kết thúc ở điểm nào đến trước trong ba điểm:
    `=== END ===`, tiêu đề `=== SKILL:` kế tiếp, hoặc cuối văn bản (LLM đôi khi quên dòng END).
    """
    pattern = re.compile(r"^=== SKILL: (\S+) ===[ \t]*\n(.*?)(?=^=== END ===|^=== SKILL: |\Z)", re.S | re.M)
    return [(name, text.strip()) for name, text in pattern.findall(str(reply))]
# --------------------------------------------------------------------------------------------------


# Prompt template for the curator
CURATOR_PROMPT = """You write SKILLs for a programming and data analysis agent.

Below are failed checks (check name and review bot feedback) and traces from several runs.
Find common PROCESS errors (not specific answers) and write up to {max_skills} short skills
to help avoid these errors on NEW tasks of the same type.

Rules:
- Skills must be GENERAL: do not mention task IDs, do not mention file names unique to one task,
  do not mention answers or specific numbers.
- Each skill has YAML frontmatter with `name` (lowercase, kebab-case) and `description` (one sentence: WHEN TO USE),
  then up to 40 lines of imperative instructions (checklist works well).
- Output format, exactly:
=== SKILL: <name> ===
---
name: <name>
description: <when to use>
---
<content>
=== END ===

{failed_runs}
"""


def curate_skills(results_dir="results", source_condition="baseline", out_dir=None, model=None, max_skills: int = 3) -> list[Path]:
    """Đọc các lần chạy của TÁC VỤ HỌC (role == "learn") trong `source_condition`, nhờ LLM viết skill, ghi file.

    Các bước: nạp run.json + trace.md -> (nếu không có check nào thất bại: in cảnh báo và trả về [] mà KHÔNG gọi LLM)
    -> dựng prompt -> model.invoke(prompt) -> parse_skill_blocks -> validate_skill(text, expected_name=name)
    -> ghi `<out_dir>/<name>/SKILL.md`. Mặc định `out_dir` = <gốc lab>/skills/auto (dùng `ROOT` từ lab.tasks).
    Giữ tối đa `max_skills` skill hợp lệ; skill không hợp lệ bị bỏ qua.
    Prompt chứa, với mỗi check thất bại, TÊN và trường `detail` (lời nhận xét của bot đánh giá: phát biểu quy tắc bị vi phạm)
    cùng phần cuối của vết (trace). Với tác vụ học, `detail` chỉ phát biểu quy tắc, không chứa đáp án.
    Tuyệt đối KHÔNG đưa dữ liệu của tác vụ đánh giá (role == "eval") vào prompt.
    model mặc định: make_model() (lab.model).
    Trả về: danh sách đường dẫn SKILL.md đã ghi.
    """
    if out_dir is None:
        out_dir = ROOT / "skills" / "auto"
    else:
        out_dir = Path(out_dir)

    results_path = Path(results_dir)

    # Collect failed runs (only learning tasks)
    runs = []
    for task_dir in sorted((results_path / source_condition).iterdir()):
        if not task_dir.is_dir():
            continue
        run_json = task_dir / "run.json"
        if not run_json.exists():
            continue

        with open(run_json, encoding="utf-8") as f:
            r = json.load(f)

        # Only use learning tasks (NOT evaluation tasks)
        if r.get("role") != "learn":
            continue

        task_id = r.get("task", task_dir.name)

        # Get failed checks
        failed = []
        for check in r.get("checks", []):
            if not check.get("passed", False):
                failed.append({
                    "name": check.get("name", "unknown"),
                    "detail": check.get("detail", ""),
                })

        # Get trace (last ~6000 chars)
        trace_md = task_dir / "trace.md"
        trace = ""
        if trace_md.exists():
            trace = trace_md.read_text(encoding="utf-8")[-6000:]

        runs.append({
            "task": task_id,
            "failed": failed,
            "trace": trace,
        })

    # Check if there are any failures
    has_failures = any(run["failed"] for run in runs)
    if not has_failures:
        print("WARNING: No failed checks found in learning tasks. Skipping skill generation.")
        return []

    # Build the prompt
    failed_runs_text = ""
    for run in runs:
        failed_runs_text += f"\n## Task: {run['task']}\n"
        if run["failed"]:
            failed_runs_text += "Failed checks:\n"
            for check in run["failed"]:
                failed_runs_text += f"  - {check['name']}: {check['detail']}\n"
        if run["trace"]:
            failed_runs_text += f"\nTrace (last part):\n{run['trace']}\n"
        failed_runs_text += "\n---\n"

    prompt = CURATOR_PROMPT.format(
        max_skills=max_skills,
        failed_runs=failed_runs_text,
    )

    # Call the model
    if model is None:
        model = make_model()

    reply = model.invoke(prompt)
    reply_text = reply.content if hasattr(reply, "content") else str(reply)

    # Parse and validate skills
    written = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, text in parse_skill_blocks(reply_text):
        # Check if we already have enough skills
        if len(written) >= max_skills:
            break

        # Validate the skill
        problems = validate_skill(text, expected_name=name)
        if problems:
            print(f"WARNING: Skill '{name}' rejected: {problems}")
            continue

        # Write the skill file
        skill_dir = out_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(text, encoding="utf-8")
        written.append(skill_file)
        print(f"Wrote skill: {skill_file}")

    return written


if __name__ == "__main__":
    for p in curate_skills():
        print("wrote", p)
