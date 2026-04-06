# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Bá Hào
- **Student ID**:  2A202600133
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

Phần đóng góp chính của tôi tập trung vào **thiết kế tool** và **tối ưu hóa prompt** cho hệ thống ReAct Agent.

### 1. Tạo và tối ưu Tools

- **Modules đã làm**:
  - `src/tools/catalog_tools.py`
  - `src/tools/pricing_tools.py`
  - `src/tools/shipping_tools.py`
  - `src/tools/registry.py`

- **Tools mới được thêm**:
  - `search_products(keyword)`: Tìm kiếm sản phẩm theo từ khóa (fuzzy, case-insensitive). Giúp agent tìm sản phẩm khi người dùng mô tả không chính xác.
  - `compare_products(product_id_1, product_id_2)`: So sánh 2 sản phẩm side-by-side, trả về chi tiết và chênh lệch giá. Hữu ích khi người dùng phân vân giữa 2 sản phẩm.
  - `list_coupons()`: Liệt kê tất cả mã giảm giá. Trước đây agent chỉ có `get_discount` (cần biết mã trước), giờ có thể tự khám phá coupon.

- **Tools đã tối ưu**:
  - `list_all_products`: Thêm trường `price` và `stock` vào kết quả trả về. Trước đây chỉ trả `id` + `name`, agent phải gọi thêm tool mới biết giá.
  - `calc_shipping`: Mở rộng bảng surcharge cho nhiều thành phố (HCM +20%, Đà Nẵng/Hải Phòng +10%, Cần Thơ +15%). Trả về thêm `weight_kg` và `surcharge_multiplier` giúp agent giải thích rõ hơn.
  - `get_discount`: Thêm `strip()` để chuẩn hóa input, tránh lỗi khi có khoảng trắng thừa.

- **Registry** (`registry.py`):
  - Cập nhật mô tả tất cả tools với thông tin arguments rõ ràng (ví dụ: `Args: keyword (str)`).
  - Tổ chức tools theo nhóm (Discovery, Product detail, Stock, Pricing, Shipping & Order).
  - Tổng số tools: 7 → **10 tools**.

### 2. Tạo và tối ưu Prompts

- **Module đã làm**:
  - `src/prompts/system_prompts.py`
  - `run_agent.py` (phần gọi prompt)

- **Thay đổi cụ thể**:
  - Viết lại `AGENT_V1_SYSTEM_PROMPT`: Cấu trúc rõ ràng với job description, rules, format, và tool call examples cụ thể.
  - Viết lại `AGENT_V2_SYSTEM_PROMPT`: Thêm strict rules (gọi `list_all_products` trước, mỗi step chỉ 1 tool, dừng ngay khi có Final Answer). Thêm concrete example hoàn chỉnh để LLM học theo.
  - Đồng bộ tất cả prompts sử dụng `"""` (triple quotes) thay vì `()`.
  - Thêm `CRITICAL RULE` vào cả v1 và v2: ngăn LLM tự sinh block `Observation:`.
  - Thêm `{tool_descriptions}` placeholder, được inject runtime qua hàm `_format_prompt()` trong `run_agent.py`.

- **Sửa `run_agent.py`**:
  - Thêm hàm `_format_prompt(template, tools)` để inject tool descriptions vào prompt template.
  - Loại bỏ nối thô `PROMPT + agent.get_system_prompt()` (trước gây trùng lặp tool descriptions).

---

## II. Debugging Case Study (10 Points)

- **Problem Description**:
  - Trước khi tối ưu, hệ thống prompt cũ nối `AGENT_V1_SYSTEM_PROMPT + agent.__class__.get_system_prompt(agent)` trong `run_agent.py`. Cách này gây ra **tool descriptions bị lặp 2 lần** trong system prompt gửi cho LLM, khiến prompt dài hơn cần thiết và tốn thêm tokens.
  - Ngoài ra, `CHATBOT_SYSTEM_PROMPT` dùng `()` trong khi v1/v2 dùng `"""`, gây **không đồng bộ** về coding style.

- **Diagnosis**:
  - Root cause: Prompt cũ (dạng `()`) không có `{tool_descriptions}` placeholder. Agent class tự generate tool list trong `get_system_prompt()`. Khi nối cả hai, LLM nhận 2 bản tool list giống nhau.
  - Hệ quả: Tăng token count ~30-40%, tăng chi phí API, và có thể khiến LLM confused khi thấy 2 format instructions khác nhau.

- **Solution**:
  - Chuyển tất cả prompt sang `"""` với `{tool_descriptions}` placeholder.
  - Tạo hàm `_format_prompt()` format prompt 1 lần duy nhất tại runtime.
  - Override `agent.get_system_prompt` chỉ trả về prompt đã format, không nối thêm.
  - Kết quả: Prompt gọn hơn, tool list chỉ xuất hiện 1 lần, tiết kiệm tokens.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**:
   - Tool descriptions đóng vai trò rất quan trọng. LLM chỉ biết tool qua mô tả text, nên mô tả càng rõ ràng (kèm args, use case) thì agent càng ít gọi sai tool.
   - Concrete examples trong prompt v2 giúp LLM tuân thủ format tốt hơn so với chỉ liệt kê rules.

2. **Reliability**:
   - Agent hoạt động tệ hơn chatbot ở câu hỏi đơn giản (chào hỏi) vì mất thêm bước gọi tool không cần thiết.
   - Nhưng với câu hỏi multi-step (tính tổng giá + shipping + discount), agent đáng tin cậy hơn hẳn vì mỗi con số đều có tool observation backing.

3. **Tool Design ảnh hưởng đến Agent**:
   - Thêm `search_products` giúp agent xử lý tốt hơn các mô tả mơ hồ từ người dùng (ví dụ: "airpod" thay vì "airpods pro").
   - Thêm `list_coupons` cho phép agent tự khám phá coupon, thay vì chỉ validate coupon người dùng đã biết.
   - `list_all_products` trả thêm `price` + `stock` giúp agent trả lời nhanh hơn (giảm 1 bước gọi `get_product_by_id`).

---

## IV. Future Improvements (5 Points)

- **Scalability**:
  - Thêm tool `add_to_cart` và `place_order` để agent hỗ trợ cả luồng mua hàng, không chỉ tư vấn.
  - Thiết kế tool schema validation (JSON Schema) để tự động validate arguments trước khi gọi tool.

- **Safety**:
  - Thêm rate limiting per tool để ngăn agent lạm dụng gọi tool liên tục.
  - Thêm response verifier: kiểm tra Final Answer chỉ chứa thông tin đã xuất hiện trong Observations.

- **Performance**:
  - Cache kết quả `list_all_products` và `list_coupons` trong session để tránh gọi lại.
  - Nén context (summarize scratchpad) khi vượt quá token limit, giảm chi phí API cho conversation dài.
