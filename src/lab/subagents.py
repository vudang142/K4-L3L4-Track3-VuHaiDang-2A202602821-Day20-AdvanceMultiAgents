"""GUIDE Phần 1 - Định nghĩa subagent (tác tử con).   >>> SINH VIÊN CÀI ĐẶT <<<

Pseudo-code: guides/pseudocode/02_subagents.md
Kiểm tra:    pytest tests/test_02_agent.py
"""


def get_subagents() -> list[dict]:
    """Trả về danh sách subagent (ít nhất 2, tên khác nhau).

    Mỗi phần tử là một dict có các khóa bắt buộc:
      "name":          tên duy nhất (chữ thường, có thể có dấu gạch ngang)
      "description":   khi nào tác tử chính nên giao việc cho subagent này (viết như một hướng dẫn hành động)
      "system_prompt": chỉ dẫn cho subagent
    Gợi ý vai trò: explorer (đọc và báo cáo), implementer (thực hiện), reviewer (kiểm tra độc lập).
    """
    return [
        {
            "name": "explorer",
            "description": "Use when you need to understand the structure, read documentation, or explore files before making changes. Delegate reading README files, docstrings, or sample data to this subagent.",
            "system_prompt": (
                "You are an explorer subagent. Your job is to READ and ANALYZE files, then report your findings.\n"
                "- Read workspace/README.md, docstrings, sample data files, or any documentation.\n"
                "- Report what you find accurately and completely.\n"
                "- Do NOT modify or create any files.\n"
                "- Return a clear summary of your findings."
            ),
        },
        {
            "name": "implementer",
            "description": "Use when you need to make code changes, implement fixes, or run tests. Delegate implementation tasks to this subagent.",
            "system_prompt": (
                "You are an implementer subagent. Your job is to IMPLEMENT changes and RUN tests.\n"
                "- Make the necessary code changes as specified.\n"
                "- Run tests to verify your changes work correctly.\n"
                "- Report what you did and the test results.\n"
                "- If tests fail, explain what failed and what needs to be fixed."
            ),
        },
        {
            "name": "reviewer",
            "description": "Use when you need to verify output correctness, check if results match requirements, or validate changes independently.",
            "system_prompt": (
                "You are a reviewer subagent. Your job is to VERIFY and VALIDATE results.\n"
                "- Check if the output files match the requirements.\n"
                "- Verify file formats, contents, and structure.\n"
                "- Report any discrepancies or issues found.\n"
                "- Do NOT make changes; only report findings."
            ),
        },
    ]
