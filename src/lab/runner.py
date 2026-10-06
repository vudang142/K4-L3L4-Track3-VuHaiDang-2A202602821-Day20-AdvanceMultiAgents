"""GUIDE Phần 1 - Chạy một tác vụ (task) và ghi kết quả.   >>> SINH VIÊN CÀI ĐẶT run_task <<<

Pseudo-code: guides/pseudocode/03_runner.md
Kiểm tra:    pytest tests/test_03_runner.py
Chạy thật:   python -m lab.runner --condition baseline --tasks learn
"""
import argparse
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage

from .agent import build_agent
from .grading import grade                                                      # có sẵn
from .model import make_model
from .tasks import ROOT, get_task, hash_dir, list_tasks, prepare_sandbox         # có sẵn

# Ba điều kiện thí nghiệm (condition). `skills_dir` là thư mục skill nguồn (tính từ thư mục gốc của lab).
CONDITIONS = {
    "baseline": {"mode": "single", "skills_dir": None},
    "subagents": {"mode": "subagents", "skills_dir": None},
    "skills-auto": {"mode": "single", "skills_dir": "skills/auto"},
}


class UsageMetadataCallbackHandler(BaseCallbackHandler):
    """Callback handler để đếm token từ mọi LLM call (kể cả subagent)."""

    def __init__(self):
        super().__init__()
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response, **kwargs):
        # LLMResult chứa generations, mỗi generation có message với usage_metadata
        print(f"DEBUG LLMResult type: {type(response)}")
        print(f"DEBUG LLMResult attrs: {dir(response)}")
        if hasattr(response, 'generations'):
            print(f"DEBUG generations: {response.generations}")
            for i, gen in enumerate(response.generations):
                print(f"DEBUG gen[{i}]: {gen}")
                if hasattr(gen, 'message'):
                    print(f"DEBUG gen[{i}].message: {gen.message}")
                    print(f"DEBUG gen[{i}].message attrs: {dir(gen.message) if gen.message else None}")
                    if gen.message and hasattr(gen.message, 'usage_metadata'):
                        print(f"DEBUG gen[{i}].message.usage_metadata: {gen.message.usage_metadata}")
                        self.input_tokens += gen.message.usage_metadata.get('input_tokens', 0)
                        self.output_tokens += gen.message.usage_metadata.get('output_tokens', 0)

    def on_chat_model_end(self, response, **kwargs):
        # Same approach for chat model
        if hasattr(response, 'generations') and response.generations:
            for gen in response.generations:
                if hasattr(gen, 'message') and gen.message:
                    msg = gen.message
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        self.input_tokens += msg.usage_metadata.get('input_tokens', 0)
                        self.output_tokens += msg.usage_metadata.get('output_tokens', 0)

    def _extract_usage(self, response):
        """Extract usage metadata from response object."""
        usage = None

        # Way 1: Direct attribute on response (newer LangChain)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
        # Way 2: In generations
        elif hasattr(response, "generations") and response.generations:
            for gen in response.generations:
                if hasattr(gen, "message") and hasattr(gen.message, "usage_metadata"):
                    usage = gen.message.usage_metadata
                    break

        if usage:
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)


def render_trace(messages) -> str:
    """CÓ SẴN, KHÔNG SỬA. Chuyển danh sách message của luồng chính thành Markdown (vết - trace).

    Lưu ý: chỉ gồm luồng chính. Việc subagent làm bên trong KHÔNG hiện trong vết;
    chỉ thấy lệnh gọi `task` và báo cáo cuối của subagent.
    """
    home = str(Path.home())

    def clean(text) -> str:
        return str(text).replace(home, "~")[:1500]

    parts = []
    for m in messages:
        if isinstance(m, AIMessage):
            if m.content:
                parts.append(f"### Assistant\n{clean(m.content)}")
            for tc in getattr(m, "tool_calls", []) or []:
                parts.append(f"### Tool call: {tc['name']}\n{clean(json.dumps(tc['args'], ensure_ascii=False))}")
        elif isinstance(m, ToolMessage):
            parts.append(f"### Tool result\n{clean(m.content)}")
        else:
            parts.append(f"### {m.type.capitalize()}\n{clean(getattr(m, 'content', ''))}")
    return "\n\n".join(parts)


def run_task(task_id: str, condition: str, results_dir="results", model=None, recursion_limit: int = 60) -> dict:
    """Chạy MỘT tác vụ dưới MỘT điều kiện, chấm điểm, ghi kết quả, và trả về bản ghi (record).

    Ghi vào: <results_dir>/<condition>/<task_id>/run.json và trace.md  (trace.md = render_trace(messages)).
    Bản ghi `run.json` phải có các khóa:
      task, condition, role, score, passed, total, checks,
      tokens {input, output, total}       - cộng dồn mọi lần gọi LLM, kể cả subagent (dùng UsageMetadataCallbackHandler)
      tool_calls                          - số tool call trong các AIMessage của luồng chính (không gồm việc bên trong subagent)
      subagent_calls                      - số tool call có tên "task" (giao việc cho subagent)
      skills_read                         - số skill KHÁC NHAU đã được đọc: với mỗi tool call "read_file" có file_path chứa
                                            "skills/", lấy tên thư mục ngay sau "skills/" rồi đếm các tên khác nhau
                                            (đọc lại cùng một skill chỉ tính một lần)
      skills_modified (bool)              - thư mục skills trong sandbox bị đổi trong lúc chạy (so hash_dir trước/sau)
      skills_sha256                       - hash_dir(sandbox/"skills") TRƯỚC khi chạy (để đối chiếu với skill đã đóng băng)
      timestamp                           - thời điểm bắt đầu, UTC, dạng ISO-8601
      seconds, final_message, error (None nếu không lỗi)
    Lỗi khi chạy tác tử KHÔNG được làm chương trình dừng: ghi vào `error` và vẫn chấm điểm.
    Sandbox là thư mục tạm NGOÀI kho mã nguồn và phải được xóa sau khi chạy.
    """
    cfg = CONDITIONS[condition]
    task = get_task(task_id)
    skills_dir = ROOT / cfg["skills_dir"] if cfg["skills_dir"] else None

    # Output directory
    out_dir = Path(results_dir) / condition / task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create sandbox (temporary directory outside the repo)
    sandbox = Path(tempfile.mkdtemp())

    # Initialize record
    record = {
        "task": task_id,
        "condition": condition,
        "role": task.role,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    messages = []
    final_message = ""
    usage_handler = UsageMetadataCallbackHandler()

    # Prepare sandbox
    prepare_sandbox(task, sandbox, skills_dir)

    # Hash skills before run (to detect modification and for freeze verification)
    skills_hash_before = hash_dir(sandbox / "skills")
    record["skills_sha256"] = skills_hash_before

    # Build agent
    agent_model = model if model is not None else make_model()
    agent = build_agent(
        sandbox,
        mode=cfg["mode"],
        use_skills=(skills_dir is not None),
        model=agent_model,
    )

    # Run agent
    t0 = time.time()
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": task.instruction}]},
            config={"callbacks": [usage_handler], "recursion_limit": recursion_limit},
        )
        messages = result["messages"]
        final_message = messages[-1].content if messages else ""
    except Exception as e:
        # Record error but continue grading
        record["error"] = f"{type(e).__name__}: {e}"
        messages = []

    record["seconds"] = round(time.time() - t0, 1)

    # Check if skills were modified AFTER agent run
    skills_hash_after = hash_dir(sandbox / "skills")
    record["skills_modified"] = (skills_hash_after != skills_hash_before)

    # Calculate token usage
    record["tokens"] = {
        "input": usage_handler.input_tokens,
        "output": usage_handler.output_tokens,
        "total": usage_handler.input_tokens + usage_handler.output_tokens,
    }

    # Count tool calls and subagent calls from AIMessage in main flow
    tool_calls_count = 0
    subagent_calls_count = 0
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", []) or []:
                tool_calls_count += 1
                if tc.get("name") == "task":
                    subagent_calls_count += 1

    record["tool_calls"] = tool_calls_count
    record["subagent_calls"] = subagent_calls_count

    # Count unique skills read (from read_file calls to skills/ directory)
    skills_read_names = set()
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", []) or []:
                if tc.get("name") == "read_file":
                    file_path = tc.get("args", {}).get("file_path", "")
                    if "skills/" in file_path:
                        # Extract skill name: path is like "skills/skill-name/SKILL.md"
                        parts = file_path.split("skills/")[1].split("/")[0]
                        if parts:
                            skills_read_names.add(parts)

    record["skills_read"] = len(skills_read_names)
    record["final_message"] = final_message

    # Grade the task (using the same sandbox that the agent worked on)
    try:
        g = grade(task, sandbox / "workspace")
        record["score"] = g["score"]
        record["passed"] = g["passed"]
        record["total"] = g["total"]
        record["checks"] = g["checks"]
    except Exception as e:
        # If grading fails, record error
        if record["error"] is None:
            record["error"] = f"grading: {type(e).__name__}: {e}"
        record["score"] = 0
        record["passed"] = 0
        record["total"] = 0
        record["checks"] = []

    # Write trace
    trace_content = render_trace(messages)
    (out_dir / "trace.md").write_text(trace_content, encoding="utf-8")

    # Clean up sandbox
    try:
        shutil.rmtree(sandbox)
    except Exception:
        pass

    # Write run.json
    (out_dir / "run.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return record


def main(argv=None):
    """CÓ SẴN, KHÔNG SỬA. Giao diện dòng lệnh (CLI): --condition, --tasks (id... | all | learn | eval), --results, --recursion-limit.

    In mỗi lần chạy một dòng: điều kiện, id, passed/total, token, số tool call, số giây, lỗi (nếu có).
    """
    ap = argparse.ArgumentParser(description="Run tasks under one condition.")
    ap.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    ap.add_argument("--tasks", nargs="+", default=["all"], help="task ids, or 'all', 'learn', 'eval'")
    ap.add_argument("--results", default="results")
    ap.add_argument("--recursion-limit", type=int, default=60)
    args = ap.parse_args(argv)
    if args.tasks == ["all"]:
        ids = [t.id for t in list_tasks()]
    elif args.tasks in (["learn"], ["eval"]):
        ids = [t.id for t in list_tasks(args.tasks[0])]
    else:
        ids = args.tasks
    for tid in ids:
        try:
            r = run_task(tid, args.condition, args.results, recursion_limit=args.recursion_limit)
        except Exception as exc:  # noqa: BLE001
            print(f"{args.condition:13s} {tid:11s} CRASH {type(exc).__name__}: {exc}", flush=True)
            continue
        print(f"{args.condition:13s} {tid:11s} score={r['passed']}/{r['total']} tokens={r['tokens']['total']} "
              f"calls={r['tool_calls']} {r['seconds']}s" + (f" ERROR={r['error']}" if r["error"] else ""), flush=True)


if __name__ == "__main__":
    main()
