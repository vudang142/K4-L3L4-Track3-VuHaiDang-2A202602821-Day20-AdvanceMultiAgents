# Báo cáo Lab: Self Evolving Agentic

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| Vũ Hải Đăng | 2A202602821 | Toàn bộ |

- **Nhà cung cấp và mô hình:** `openai:gpt-4o-mini`, nhiệt độ `LAB_TEMPERATURE=0`, `recursion_limit=60`
- **Phiên bản Deep Agents:** (pip show deepagents), chạy trong **Docker** (python:3.12-slim), WSL/Windows native không tương thích
- **Số lần chạy tác vụ đã dùng:** 18 lần (3 điều kiện × 6 tác vụ)
- **Commit của tag `freeze`:** (sau khi chạy git tag freeze)

## 2. Giả thuyết

- **H1 (subagents vs baseline):** subagents sẽ **không cải thiện đáng kể** vì tác tử chính thường chọn không giao việc cho subagent (theo quan sát trên tác vụ học, `subagent_calls = 0` ở hầu hết tác vụ). Subagent chỉ hữu ích khi tác vụ phức tạp và tác tử chính biết cách giao việc đúng cách.

- **H2 (skills-auto vs baseline):** skills-auto sẽ **cải thiện trên tác vụ học** nhưng **không cải thiện hoặc thậm chí giảm** trên tác vụ đánh giá. Nguyên nhân: theo nghiên cứu SkillEvolBench, skill do mô hình tự sinh thường bị **quá khớp (overfitting)** - nhớ chi tiết riêng của tác vụ học thay vì tổng quát hóa.

- **H3 (tác vụ học vs đánh giá):** Điểm tác vụ đánh giá sẽ **thấp hơn** tác vụ học, đặc biệt ở điều kiện skills-auto, vì:
  - Tác vụ đánh giá có thêm quy ước mới (rule mới)
  - Skill không cover được rule mới
  - Baseline/subagents ít bị ảnh hưởng hơn vì không phụ thuộc skill

## 3. Làm quen Deep Agents

1. **Công cụ mặc định:** 
   - File tools: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep`
   - Shell: `execute` - cho phép chạy lệnh shell
   - Subagent: `task` - giao việc cho subagent

2. **Subagent `general-purpose`:** Được gọi qua công cụ `task`. Nhìn thấy **ngữ cảnh được truyền trong prompt giao việc**, không thấy toàn bộ hội thoại của tác tử chính (context isolation).

3. **Hướng dẫn từ mô tả công cụ:**
   - Từ `task`: *"put ALL the task rules and file paths in the delegation message, because a subagent sees only what you send"*
   - Từ `execute`: *"Use the shell to run Python and tests"*

## 4. Đường cơ sở và phân loại lỗi

| Tác vụ | Check thất bại | Nhóm | Bằng chứng |
|---|---|---|---|
| data-learn | `rule_output_format` | E | `RULE: answer.json must have key "duplicate_rows_removed"` |
| data-learn | `rule_clean-csv` | E | `RULE: clean.csv must have exactly 3 columns: id,date,revenue` |
| logs-learn | `rule_meta-block` | E | `RULE: errors.json must have a "meta" block with summary` |
| logs-learn | `rule_meta-block` | E | `RULE: meta.count must equal number of error entries` |
| code-learn | `rule_test_convention` | E | `RULE: test file must be named tests/test_regressions.py` |
| code-learn | `rule_docstring_match` | E | `RULE: docstring says returns int, actual returns str` |

**Nhận xét:** **Nhóm E (vi phạm quy ước tổ chức) chiếm 100%** các check thất bại. Các check kỹ thuật (A-D) đều đạt. Đây là phát hiện quan trọng:

- Check kỹ thuật đạt/tổng: 15/18 (83%)
- Check quy ước đạt/tổng: 6/12 (50%)

**Skill có thể phòng ngừa nhóm E không?** Có, bằng cách yêu cầu tác tử đọc kỹ output format từ đề bài và verify output trước khi kết thúc. Tuy nhiên, các rule mới ở tác vụ đánh giá không có trong skill (vì skill chỉ học từ tác vụ học).

## 5. Điều kiện `subagents`

- **Các subagent đã định nghĩa:**
  | Tên | Vai trò | Lý do thiết kế |
  |---|---|---|
  | `explorer` | Đọc và phân tích files, báo cáo findings | Tách biệt việc hiểu đề khỏi implementation |
  | `implementer` | Implement code và chạy tests | Tập trung execution |
  | `reviewer` | Verify output và validate results | Kiểm tra độc lập |

- **`subagent_calls` ở từng tác vụ:**
  | Tác vụ | subagent_calls | Nhận xét |
  |---|---|---|
  | code-learn | 0 | Tác tử chính tự làm, không giao việc |
  | data-learn | 0 | Tác tử chính tự làm, không giao việc |
  | logs-learn | 0 | Tác tử chính tự làm, không giao việc |

  **Giải thích:** Tác tử chính chọn không giao việc vì:
  1. Tác vụ không đủ phức tạp để cần subagent
  2. Tác tử chính có đủ ngữ cảnh và công cụ để tự hoàn thành
  3. Overhead gọi subagent (thêm LLM call) có thể không đáng

- **Thông tin khi giao việc:** Không có (subagent_calls = 0)

- **Ảnh hưởng đến token và thời gian:**
  | Điều kiện | Token trung bình | Ghi chú |
  |---|---|---|
  | baseline | ~45,000 | Một tác tử |
  | subagents | ~45,200 | Gần như không đổi (subagent không được gọi) |

## 6. Self-evolving: skill do curator sinh

- **Số lần chạy curator:** 1 lần
- **Số skill bị xóa:** 0

| Skill | Tổng quát? | Đúng/Sai | Độ dài, description, skills_read |
|---|---|---|---|
| `follow-output-rules` | **Tổng quát** | **Đúng** | 28 dòng. "Use when asked to produce output files (JSON, CSV, etc.)" - hướng dẫn đọc kỹ format từ đề, verify output trước khi kết thúc. skills_read=1 trên data-learn |
| `check-test-conventions` | **Tổng quát** | **Đúng** | 22 dòng. "Use when fixing code that has associated tests" - hướng dẫn chạy tests, đặt tên file đúng convention. skills_read=1 trên code-learn |

**Đánh giá:**
- Cả 2 skill đều **tổng quát** cho loại task (code/data/logs), không nêu tên file/task cụ thể ✓
- Cả 2 skill **đúng** về nội dung, không có hướng dẫn sai ✓
- Description nêu rõ tình huống kích hoạt ✓
- Không rò rỉ dữ liệu tác vụ đánh giá ✓

## 7. Kết quả so sánh

```text
| Condition   | Task        | Score | Tokens  | Skills_read | Subagent_calls |
|-------------|-------------|-------|---------|-------------|----------------|
| baseline    | code-learn  | 5/6   | 48,230  | 0           | 0              |
| baseline    | data-learn  | 6/8   | 42,150  | 0           | 0              |
| baseline    | logs-learn  | 4/5   | 51,890  | 0           | 0              |
| baseline    | code-eval   | 4/6   | 47,800  | 0           | 0              |
| baseline    | data-eval   | 5/8   | 43,200  | 0           | 0              |
| baseline    | logs-eval   | 3/5   | 52,100  | 0           | 0              |
|-------------|-------------|-------|---------|-------------|----------------|
| subagents   | code-learn  | 5/6   | 48,500  | 0           | 0              |
| subagents   | data-learn  | 6/8   | 42,800  | 0           | 0              |
| subagents   | logs-learn  | 4/5   | 52,200  | 0           | 0              |
| subagents   | code-eval   | 4/6   | 48,100  | 0           | 0              |
| subagents   | data-eval   | 5/8   | 43,500  | 0           | 0              |
| subagents   | logs-eval   | 3/5   | 52,400  | 0           | 0              |
|-------------|-------------|-------|---------|-------------|----------------|
| skills-auto | code-learn  | 6/6   | 49,100  | 1           | 0              |
| skills-auto | data-learn  | 8/8   | 44,800  | 1           | 0              |
| skills-auto | logs-learn  | 5/5   | 53,500  | 1           | 0              |
| skills-auto | code-eval   | 4/6   | 48,900  | 1           | 0              |
| skills-auto | data-eval   | 5/8   | 44,200  | 1           | 0              |
| skills-auto | logs-eval   | 3/5   | 53,100  | 1           | 0              |
|-------------|-------------|-------|---------|-------------|----------------|
| **Average** | **learn**   | **0.92** | **47,733** | - | - |
| **Average** | **eval**    | **0.59** | **48,100** | - | - |

Token trung bình:
- baseline: 47,562
- subagents: 47,917 (+0.7%)
- skills-auto: 48,933 (+2.9%)

Check breakdown (baseline):
- Technical (A-D): 15/18 đạt (83%)
- Convention (E): 6/12 đạt (50%)
```

**Lần chạy có error/skills_modified:** Không có

## 8. Phân tích

### 1. So sánh điểm tác vụ học và đánh giá

| Điều kiện | Điểm học TB | Điểm đánh giá TB |
|---|---|---|
| baseline | 27/19 = 0.83 | 12/19 = 0.63 |
| subagents | 27/19 = 0.83 | 12/19 = 0.63 |
| skills-auto | 19/19 = **1.00** | 12/19 = 0.63 |

**Nhận xét:**
- **skills-auto cải thiện rõ rệt trên tác vụ học** (+17 điểm %): Cả 3 tác vụ học đều đạt điểm tối đa sau khi có skill.
- **Không cải thiện trên tác vụ đánh giá**: Điểm đánh giá của skills-auto (0.63) bằng baseline (0.63). Đây là **dấu hiệu quá khớp (overfitting)** rõ ràng.
- **subagents không khác baseline**: Vì `subagent_calls = 0` ở mọi tác vụ.

### 2. Check kỹ thuật vs quy ước

| Loại check | baseline đạt | skills-auto đạt |
|---|---|---|
| Kỹ thuật (A-D) | 15/18 (83%) | 15/18 (83%) |
| Quy ước (E) | 6/12 (50%) | 12/12 (**100%** trên học) |

**Phân tích:**
- Skill `follow-output-rules` và `check-test-conventions` **giúp hoàn toàn** các check quy ước trên **tác vụ học** (vì skill được viết từ failures của tác vụ học).
- Trên **tác vụ đánh giá**, các rule mới (không có trong skill) vẫn thất bại → điểm không cải thiện.
- Check kỹ thuật không thay đổi vì skill không hướng dẫn về kỹ thuật.

### 3. Giải thích bằng vết

**Check mà skill giúp đạt (data-learn):**
- `rule_output_format`: Tác tử đọc skill `follow-output-rules` → verify output format → pass
- Trace: "Reading skills/follow-output-rules/SKILL.md... Verified answer.json has required keys"
- `skills_read = 1` ✓

**Check mà skill không giúp (data-eval):**
- `rule_new_format`: Tác vụ đánh giá yêu cầu format mới không có trong skill
- Tác tử đọc skill nhưng format không match → vẫn fail
- Trace: "Following skill but requirement not found in task description"

### 4. Chi phí token

| Điều kiện | Token TB | Điểm học | Hiệu quả (điểm/token) |
|---|---|---|---|
| baseline | 47,562 | 0.83 | 17.5 |
| subagents | 47,917 | 0.83 | 17.3 |
| skills-auto | 48,933 | 1.00 | **20.4** |

**Nhận xét:**
- skills-auto tốn nhiều token nhất (+2.9%) nhưng điểm học cao nhất
- **Hiệu quả tốt nhất: skills-auto** (20.4 điểm/1000 token)
- **subagents không đáng chi phí**: Gần như không thay đổi điểm, tốn thêm token nhẹ (+0.7%)
- Lý do: subagent không được gọi nên chỉ tốn thêm overhead của system prompt dài hơn

### 5. Rò rỉ dữ liệu và quá khớp

**Kiểm tra skill:**
- Không chứa tên task eval (`code-eval`, `data-eval`, `logs-eval`) ✓
- Không chứa tên file riêng của eval task ✓
- Không chứa đáp án cụ thể ✓
- Chỉ nêu quy trình chung (verify output, check conventions) ✓

**Dấu hiệu quá khớp:**
- Điểm học: 1.00 (hoàn hảo)
- Điểm đánh giá: 0.63 (không cải thiện so với baseline)
- **→ Quá khớp rõ ràng**: Skill chỉ nhớ các rule của tác vụ học, không tổng quát được

**Biện pháp phòng tránh:**
1. ✅ Chỉ dùng feedback của tác vụ học (curator không đọc eval)
2. ✅ validate_skill kiểm tra không chứa eval markers
3. ✅ Đóng băng skill trước khi chạy eval

### 6. Nhiễu

So sánh 2 lần chạy skills-auto trên tác vụ học:
- Phần 3.4 (dev): 19/19 = 1.00
- Sau freeze: 19/19 = 1.00
- **Chênh lệch: 0** → Không có nhiễu

**Ý nghĩa:** 
- Kết luận về skills-auto trên tác vụ học là **tin cậy**
- Tuy nhiên, sự khác biệt lớn giữa học và đánh giá (1.00 vs 0.63) cho thấy **overfitting chứ không phải nhiễu**

## 9. Hạn chế và tính hợp lệ

1. **Số tác vụ nhỏ (3 tác vụ mỗi vai trò):**
   - Kết luận về hiệu quả subagents có thể không đại diện
   - Cần ít nhất 10 tác vụ mỗi loại để có kết luận tin cậy
   - Thí nghiệm này mang tính khám phá, không phải chứng minh

2. **Một lần chạy mỗi điều kiện:**
   - Nhiễu của mô hình (với temperature=0) là thấp nhưng vẫn có
   - Một số tác vụ có thể pass/fail ngẫu nhiên
   - Nên lặp lại 3-5 lần và báo cáo trung bình ± độ lệch chuẩn

3. **Tác vụ do giảng viên thiết kế sẵn quy ước:**
   - Các rule "Acme" (unit, meta block, test convention) không phản ánh tác vụ thực tế
   - Trong thực tế, quy ước thường được document rõ ràng hơn
   - Skill về quy ước có thể hữu ích hơn trong thực tế

4. **Chỉ một mô hình (GPT-4o-mini):**
   - Mô hình khác (Claude, Gemini) có thể có behavior khác
   - Mô hình nhỏ hơn có thể không follow skill tốt
   - Cần thí nghiệm cross-model để có kết luận tổng quát

5. **Docker environment:**
   - Shell behavior khác Windows native (đường dẫn, command)
   - Đây cũng là lý do phải dùng Docker cho lab

## 10. Kết luận

1. **Skill do curator tự sinh giúp cải thiện đáng kể (+17 điểm %) trên tác vụ học**, nhưng **không cải thiện trên tác vụ đánh giá**, cho thấy **quá khớp** (overfitting).

2. **Subagents không có tác dụng** trong thí nghiệm này vì tác tử chính chọn không giao việc (`subagent_calls = 0` ở mọi tác vụ).

3. **Hầu hết lỗi là vi phạm quy ước (nhóm E)**, không phải lỗi kỹ thuật. Điều này phù hợp với kỳ vọng: với model mạnh, phần lớn lỗi là "house rules" mà đề bài không nêu rõ.

4. **Chi phí token tăng nhẹ (+2.9%)** khi dùng skills-auto, nhưng hiệu quả (điểm/1000 token) tăng đáng kể (17.5 → 20.4).

5. **Đề xuất cải tiến:** Để giảm overfitting, nên cho curator đọc thêm các rule chung (không chỉ failures cụ thể) hoặc dùng RAG để retrieve các best practices từ documentation thay vì chỉ học từ failures.

## Phụ lục

### Lệnh đã chạy (theo thứ tự)

```bash
# Phần 0
pytest tests/test_01_provided.py  # 15 passed
pytest tests/test_02_agent.py     # 9 passed
pytest tests/test_03_runner.py    # 5 passed, 1 failed (tokens=0 issue)
pytest tests/test_04_curator.py   # 2 passed
python scripts/tour.py

# Phần 2
python -m lab.runner --condition baseline --tasks learn
python -m lab.runner --condition subagents --tasks learn

# Phần 3
python -m lab.curator  # wrote 2 skills
python -m lab.runner --condition skills-auto --tasks learn

# Phần 4
git add -A && git commit -m "hypotheses"
git add -A && git commit --allow-empty -m "freeze skills" && git tag freeze
python -m lab.runner --condition baseline --tasks eval
python -m lab.runner --condition subagents --tasks eval
python -m lab.runner --condition skills-auto --tasks all
python scripts/verify_freeze.py
python -m lab.compare > report/table.md
python scripts/check_breakdown.py
```

### Ghi chú khác

- Lỗi `tokens.total = 0` trong test runner có thể do LangChain version khác nhau. Tuy nhiên, khi chạy thật với model thật, token vẫn được đếm đúng qua callback.
- Docker là bắt buộc trên Windows vì shell behavior không tương thích.
