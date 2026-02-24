Trong ngăn xếp công nghệ (stack) bạn đang xây dựng, việc định nghĩa, đăng ký và thực thi các Agent, công cụ (tools) và kỹ năng (skills) được thực hiện thông qua sự phối hợp giữa **Copilot Runtime**, các framework như **LangGraph** hoặc **PydanticAI**, và giao thức **AG-UI**. Để tận dụng các tài nguyên sẵn có từ Claude Code hay OpenCode, ngăn xếp này sử dụng các giao thức tiêu chuẩn như **MCP (Model Context Protocol)** và **A2A**.  
Dưới đây là chi tiết cách triển khai dựa trên các nguồn tài liệu:

### 1\. Định nghĩa và Đăng ký Agent (Agents)

Việc quản lý Agent diễn ra ở cả hai phía: logic xử lý ở backend và kết nối tương tác ở frontend.

* **Định nghĩa tại Backend:** Bạn có thể sử dụng **LangGraph** để xây dựng các "Deep Agents" — loại agent có khả năng lập kế hoạch, sử dụng hệ thống tệp cho ngữ cảnh và sinh ra các sub-agent 1, 2\. Bạn định nghĩa agent bằng cách gọi hàm create\_deep\_agent(...), hàm này sẽ tạo ra một biểu đồ thực thi (execution graph) có khả năng quản lý trạng thái phức tạp qua nhiều bước 3\. Ngoài ra, **PydanticAI** cho phép định nghĩa Agent dưới dạng một class container chứa system prompt, công cụ và các ràng buộc dữ liệu đầu ra có cấu trúc 4\.  
* **Đăng ký qua Copilot Runtime:** Sau khi định nghĩa agent (ví dụ bằng FastAPI trong Python), bạn đăng ký nó với **Copilot Runtime** 5\. Runtime đóng vai trò là "Hệ thần kinh trung ương", tự động xử lý việc khám phá (discovery) và điều hướng (routing) yêu cầu từ frontend đến đúng agent mà không cần frontend phải biết chi tiết địa chỉ của từng agent 6, 7\.  
* **Kết nối tại Frontend:** Sử dụng hook useAgent hoặc useCoAgent trong React để thiết lập kết nối hai chiều với agent backend thông qua giao thức AG-UI 8-10.

### 2\. Định nghĩa và Thực thi Công cụ (Tools) và Kỹ năng (Skills)

Ngăn xếp này phân biệt rõ rệt giữa công cụ chạy tại backend và kỹ năng tương tác tại frontend.

* **Backend Tools (Công cụ phía server):**  
* Trong Python, bạn sử dụng các decorator như @tool (LangChain/LangGraph) hoặc agent.tool (PydanticAI) để biến các hàm Python thành công cụ mà LLM có thể gọi 11-13.  
* Hệ thống thực thi các công cụ này trên server, đảm bảo an toàn cho các API key và dữ liệu nhạy cảm 14, 15\.  
* **Frontend Skills/Tools (Kỹ năng phía client):**  
* Sử dụng hook **useFrontendTool** (v2) hoặc **useCopilotAction** (v1) để đăng ký các hàm JavaScript/TypeScript trực tiếp trong trình duyệt 16-18.  
* Các kỹ năng này cho phép Agent thực hiện các hành động trực tiếp trên giao diện người dùng như: thay đổi trạng thái React, truy cập browser API (localStorage, cookies), hoặc kích hoạt các hiệu ứng hoạt họa 19, 20\.  
* **Tính kế thừa trạng thái:** Agent backend có thể kế thừa từ CopilotKitState để tự động nhận biết và có quyền gọi tất cả các frontend tools đã được đăng ký tại client 21, 22\.

### 3\. Cơ chế Thực thi và Luồng dữ liệu (Execution via AG-UI)

Quá trình thực thi được chuẩn hóa qua giao thức **AG-UI**, sử dụng **Server-Sent Events (SSE)** để duy trì sự đồng bộ thời gian thực 23-25.

1. **Kích hoạt:** Người dùng gửi yêu cầu qua Chat UI hoặc tương tác trên Canvas 25\.  
2. **Sự kiện:** Giao thức phát đi các sự kiện như TEXT\_MESSAGE\_CONTENT (để stream văn bản) và TOOL\_CALL\_START (để thông báo Agent bắt đầu chạy công cụ) 26, 27\.  
3. **Vòng lặp tương tác:** Agent có thể tạm dừng thực thi để yêu cầu sự xác nhận từ con người (**Human-in-the-Loop**) thông qua các widget tương tác sinh bởi **A2UI** trước khi tiếp tục quy trình 28-31.

### 4\. Tận dụng Agent/Tools từ Claude Code, OpenCode và các nguồn khác

Để không phải "tái phát minh bánh xe", stack này sử dụng các giao thức kết nối mở:

* **MCP (Model Context Protocol):** Đây là chìa khóa để tận dụng các công cụ hiện có. MCP hoạt động như một "cổng USB-C" cho AI 32, 33\. Bạn có thể kết nối Agent của mình với bất kỳ **MCP Server** nào (như các server cung cấp công cụ truy cập GitHub, Google Drive, hoặc các bộ công cụ của Claude Code) 34, 35\. CopilotKit hỗ trợ MCPAppsMiddleware, cho phép nhúng trực tiếp giao diện tương tác của các MCP tools vào ứng dụng của bạn 36\.  
* **Giao thức A2A (Agent-to-Agent):** Nếu bạn muốn sử dụng một Agent có sẵn từ các framework khác (như các agent của Google hay các hệ thống hỗ trợ A2A), ngăn xếp này cho phép Agent của bạn khám phá và ủy quyền nhiệm vụ cho các agent từ xa thông qua **Agent Cards** và JSON-RPC 37, 38\.  
* **Mô hình Deep Agents:** Stack của bạn có thể mô phỏng kiến trúc của các công cụ như Claude Code hay Manus bằng cách sử dụng create\_deep\_agent trong LangGraph, tích hợp sẵn khả năng lập kế hoạch (planning) và quản lý tệp tin ngữ cảnh 3, 39\.  
* **Tích hợp OpenCode:** Tài liệu ghi nhận các khuyến nghị kết nối OpenCode với GitHub Copilot để mở rộng khả năng của hệ thống 40\. Bạn có thể cấu hình Agent trong stack của mình để gọi các hàm từ OpenCode thông qua các wrapper công cụ đã định nghĩa ở backend 13\.

**Tóm lại**, bạn định nghĩa logic và công cụ tại backend (Python/LangGraph), đăng ký kỹ năng UI tại frontend (React Hooks), và sử dụng **MCP** làm cầu nối để "nhập khẩu" toàn bộ hệ sinh thái công cụ từ Claude Code hoặc OpenCode vào ứng dụng của mình 32, 41, 42\.  
