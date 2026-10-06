# Bảng so sánh kết quả

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

## Tổng hợp theo điều kiện

| Điều kiện | Điểm học TB | Điểm đánh giá TB | Token TB |
|------------|--------------|-------------------|----------|
| baseline   | 0.83         | 0.63              | 47,562   |
| subagents  | 0.83         | 0.63              | 47,917   |
| skills-auto| **1.00**     | 0.63              | 48,933   |

## Check breakdown

| Điều kiện | Technical (A-D) | Convention (E) |
|------------|-----------------|----------------|
| baseline   | 15/18 (83%)    | 6/12 (50%)    |
| subagents  | 15/18 (83%)    | 6/12 (50%)    |
| skills-auto| 15/18 (83%)    | 12/12 (**100%** on learn) |
