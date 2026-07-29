# Day 04 Lab v2 Report — Research Agent

## Team

- Team: Group Student K3
- Members:
  - **Trần Xuân Lộc** - `2A202601671` - Core Agent & Benchmark Lead (Leader)
  - **Đào Ngọc Bích** - `2A202601745` - UI & Deployment Engineer
  - **Ngô Tuấn Hưng** - `2A202601409` - Tool Developer
  - **Vũ Đức Anh** - `2A202601191` - Dataset Developer, Report writer
- Provider/model: OpenRouter (`openai/gpt-4o-mini`)

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research Agent đa năng có khả năng tự động tra cứu tin tức web, bài đăng mạng xã hội, tra cứu Wikipedia, đọc tin từ nguồn RSS Feed, tìm kiếm bài báo arXiv, kiểm tra quy định nội bộ và hỏi xác nhận an toàn trước khi thực hiện hành động nhạy cảm.

**Link dùng thử (truy cập được trong showdown):**

URL: http://localhost:8501

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| clarify | Hỏi lại người dùng khi thiếu thông tin (response_type="text") hoặc xin xác nhận trước hành động (response_type="yes_no") | không |
| timeline | Lấy danh sách bài đăng gần đây của một tài khoản cụ thể theo screenname | không |
| social_search | Tìm kiếm các bài đăng trên mạng xã hội theo từ khóa/chủ đề | không |
| lookup | Tra cứu tin tức thời sự và bài viết tổng hợp trên web | không |
| fetch | Đọc trực tiếp nội dung chi tiết từ một đường dẫn URL web | không |
| format | Trình bày và định dạng danh sách dữ liệu thu thập thành bài tổng hợp markdown | không |
| send | Gửi thông điệp hoặc đăng nội dung bản tin lên kênh Telegram | không |
| policy | Tra cứu quy định nội bộ công ty theo các chủ đề chính sách | không |
| papers | Tìm kiếm danh sách các bài báo nghiên cứu khoa học trên nền tảng arXiv | không |
| paper_text | Tải và trích xuất nội dung văn bản trực tiếp từ PDF bài báo arXiv | không |
| wikipedia_summary | Tra cứu định nghĩa hoặc tóm tắt thực thể/khái niệm trên Wikipedia theo ngôn ngữ | **Có (Tool mới 1)** |
| fetch_rss | Đọc và trích xuất danh sách các tin tức mới nhất từ đường dẫn RSS/Atom Feed | **Có (Tool mới 2)** |

## A3. Câu hỏi mẫu để thử

1. **Wikipedia Entity**: "Attention mechanism trong deep learning là gì? Tra Wikipedia giúp mình."
2. **RSS Feed Reader**: "Lấy 5 bài mới nhất từ RSS Hacker News frontpage: https://hnrss.org/frontpage"
3. **arXiv Papers Search**: "Tìm paper trên arXiv về diffusion models."
4. **Web News Search**: "Tin tức AI hôm nay có gì nổi bật?"
5. **Out of Scope Check**: "Giải giúp mình bài toán tích phân: nguyên hàm của x^2 là gì?"

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| **S01: Out-of-Scope Protection** | Không gọi tool nào, trả lời trực tiếp từ chối. | `v0` gọi lầm tool `send`, `v1` sửa prompt đưa accuracy về 100%. | `runs/v3_B_base_openrouter_20260729T101954269937.json` (R08, R14) |
| **S02: Action Boundary Confirmation** | `clarify(response_type="yes_no")` | `v0` gọi thẳng tool `send`, `v3` hỏi xác nhận `yes_no` chuẩn xác. | `runs/v3_B_base_openrouter_20260729T101954269937.json` (R12) |
| **S03: Custom Tool Wikipedia & RSS** | `wikipedia_summary`, `fetch_rss` | Tích hợp thành công 2 custom tools mới với accuracy 100%. | `runs/v3_B_group_openrouter_20260729T104323478294.json` (G01, G02) |

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v0 | Baseline initial prompt | Baseline run | case_accuracy | 0.70 | 0.70 | `runs/v0_B_base_openrouter_20260729T095622647299.json` |
| v1 | Thêm quy tắc out-of-scope & clarify missing info | Chặn việc gọi lầm tool send ở câu toán/code | case_accuracy | 0.70 | 0.80 | `runs/v1_B_base_openrouter_20260729T100653301084.json` |
| v2 | Ép buộc tham số response_type & phân biệt lookup | Giúp phân định ranh giới giữa lookup và social_search | case_accuracy | 0.80 | 0.65 | `runs/v2_B_base_openrouter_20260729T101641989142.json` |
| v3 | Phân định timeline vs social_search & query sạch | Giúp routing chuẩn 100% trên cả 20 base cases | case_accuracy | 0.65 | **1.00** | `runs/v3_B_base_openrouter_20260729T101954269937.json` |

## B2. Failure analysis

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| R08 | `out_of_scope` | `send(text=...)` | Gọi lầm tool send cho bài toán tích phân | Thêm quy tắc cấm gọi tool ở out-of-scope |
| R10 | `missing_info` | `timeline(screenname="sama")` | Tự đoán handle sama khi thiếu thông tin | Thêm quy tắc gọi `clarify(response_type="text")` |
| R12 | `wrong_boundary` | `send(text=...)` | Gọi thẳng send Telegram mà không xác nhận | Thêm quy tắc bắt buộc `clarify(response_type="yes_no")` |
| R13 | `wrong_tool` | `lookup` + `timeline(sama)` | Nhầm tìm tweet chủ đề với timeline cá nhân | Phân biệt rõ `timeline` (handle) và `social_search` (topic) |

## B3. Team eval cases

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| G01_wikipedia_entity | Tra khái niệm Attention Mechanism trên Wikipedia | `wikipedia_summary(query="attention mechanism")` | PASS (1.0) |
| G02_rss_limit | Đọc 5 tin từ RSS Hacker News | `fetch_rss(feed_url="https://hnrss.org/frontpage", limit=5)` | PASS (1.0) |
| G03_papers_search | Tìm paper arXiv về diffusion models | `papers(query="diffusion models")` | PASS (1.0) |
| G04_policy_privacy | Tra cứu policy quyền riêng tư nội bộ | `policy(policy_area="data_privacy")` | PASS (1.0) |
| G05_out_of_scope_coding | Yêu cầu viết code merge sort Python | no_tool (refuse) | PASS (1.0) |
| G06_clarify_then_paper_text | Multi-turn: Trích 5 trang đầu bài báo arXiv | `paper_text(arxiv_url="1706.03762", max_pages=5)` | PASS (1.0) |
| G07_wikipedia_language_carryover | Multi-turn: Tra Wikipedia tiếng Anh cho LLM | `wikipedia_summary(query="Large Language Model", language="en")` | PASS (1.0) |
| G08_switch_to_fetch_rss | Multi-turn: Chuyển từ web sang RSS feed | `fetch_rss(feed_url="https://hnrss.org/frontpage", limit=3)` | PASS (1.0) |
| G09_confirm_before_send | Multi-turn: Xác nhận trước khi đăng Telegram | `clarify(response_type="yes_no")` | PASS (1.0) |
| G10_no_tool_meta | Multi-turn: Hỏi về khả năng của agent | no_tool (answer_without_tool) | PASS (1.0) |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
| Multi-turn RSS & Wikipedia | v3 | `wikipedia_summary`, `fetch_rss` | `runs/v3_B_group_openrouter_20260729T104323478294.json` | Successful execution with 100% accuracy |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới 1 | `tools/wikipedia_summary/` | Tra cứu định nghĩa từ khóa chính xác trên Wikipedia | Xử lý từ khóa sạch, hỗ trợ đa ngôn ngữ vi/en |
| Must-have: tool mới 2 | `tools/fetch_rss/` | Trích xuất bài viết từ RSS feed chuẩn định dạng XML | Giới hạn số lượng limit bài viết tránh quá tải |

## B6. Reflection

- **System Prompt Fixes**: Việc làm rõ ranh giới out-of-scope, bắt buộc truyền tham số `response_type` cho `clarify`, và phân biệt giữa `timeline` (gửi theo tài khoản) và `social_search` (tìm theo chủ đề) giúp tăng accuracy từ 70% lên 100%.
- **Tools Schema Fixes**: Khai báo rõ ràng schema cho `wikipedia_summary` và `fetch_rss` trong `tools.yaml` giúp Model hiểu và truyền đúng tham số ngay lần thử đầu tiên.
- **Next Improvements**: Tiếp tục hoàn thiện thêm các UI visualization hiển thị trace realtime cho người dùng trải nghiệm mượt mà hơn.
