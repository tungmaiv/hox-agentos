Việc tích hợp Keycloak vào Copilot Runtime là một bước quan trọng để đảm bảo an ninh cho hệ thống Agentic của bạn, đặc biệt là trong môi trường doanh nghiệp yêu cầu kiểm soát truy cập dựa trên vai trò (RBAC). Dựa trên kiến trúc của CopilotKit và giao thức AG-UI, quá trình tích hợp này sẽ tập trung vào lớp Runtime đóng vai trò là cổng bảo mật trung tâm.
Dưới đây là các bước chi tiết để triển khai:
1. Luồng xác thực tổng thể (Authentication Flow)
1. Người dùng đăng nhập trên Frontend thông qua Keycloak (sử dụng OIDC).
2. Frontend nhận JWT (JSON Web Token) từ Keycloak sau khi đăng nhập thành công.
3. Frontend gửi JWT này trong header của mọi yêu cầu đến Copilot Runtime thông qua giao diện AG-UI.
4. Copilot Runtime xác thực JWT với Keycloak, sau đó trích xuất thông tin người dùng và vai trò để thực hiện logic RBAC/ACL trước khi chuyển tiếp yêu cầu đến Agent LangGraph.
2. Triển khai tại Frontend (Next.js / React)
Bạn cần cấu hình để CopilotKit đính kèm token xác thực vào các yêu cầu gửi đến backend.
• Cấu hình Provider: Sử dụng thuộc tính headers hoặc properties trong <CopilotKit> provider để truyền token từ session của người dùng (thường lấy từ thư viện như next-auth hoặc Keycloak JS SDK).
• Token Management: Đảm bảo token được làm mới (refresh) tự động để tránh ngắt quãng phiên làm việc của Agent.
3. Triển khai tại Copilot Runtime (Python / FastAPI)
Vì bạn ưu tiên sử dụng Python, lớp Runtime sẽ được xây dựng bằng FastAPI. Đây là nơi logic bảo mật chính được thực thi:
• Middleware xác thực: Xây dựng một lớp middleware hoặc sử dụng FastAPI Dependencies để kiểm tra JWT token trong header của mỗi yêu cầu AG-UI.
• Xác thực với Keycloak: Sử dụng các thư viện như python-keycloak hoặc jose để:
    ◦ Kiểm tra chữ ký của JWT bằng Public Key từ Keycloak.
    ◦ Kiểm tra thời hạn (expiration) và các thông tin định danh (claims).
• Trusted Environment: Việc thực hiện này ở phía server đảm bảo các API key và quy tắc phân quyền không bị can thiệp bởi phía client.
4. Quản lý RBAC và ACL cho Agent
Sau khi xác thực người dùng, bạn cần áp dụng các quyền truy cập cụ thể:
• Trích xuất vai trò (Roles): Lấy danh sách roles từ token của Keycloak.
• Gán ngữ cảnh người dùng: Sử dụng hệ thống Dependency Injection của PydanticAI hoặc LangGraph để nạp thông tin người dùng (User ID, Roles) vào Agent.
• Kiểm soát tại cấp độ Công cụ (Tool-level ACL):
    ◦ Trước khi Agent thực thi một Skill hoặc gọi một MCP Tool, hệ thống sẽ kiểm tra xem vai trò của người dùng có quyền gọi công cụ đó hay không.
    ◦ Ví dụ: Chỉ người dùng có role admin mới được kích hoạt tool "Xóa tài liệu" trong workflow thiết kế trên canvas.
5. Lợi ích kiến trúc
• An toàn mặc định (Safe Defaults): Copilot Runtime ngăn chặn các truy cập không xác thực vào các endpoint của Agent.
• Khả năng giám sát (Observability): Việc tích hợp xác thực tại Runtime cho phép bạn ghi lại nhật ký (audit logs) chi tiết: "Ai đã yêu cầu Agent thực hiện hành động gì".
• Cô lập bộ nhớ: Dựa trên User ID từ Keycloak, Runtime sẽ đảm bảo Agent chỉ truy cập vào đúng phân vùng bộ nhớ (Per-user memory) của người dùng đó, ngăn chặn rò rỉ dữ liệu giữa các nhân viên trong doanh nghiệp.
Kiến nghị triển khai: Bạn nên bắt đầu bằng việc dựng một server FastAPI làm Runtime, tích hợp middleware kiểm tra JWT đơn giản, sau đó mới mở rộng sang các logic ACL phức tạp cho từng node trong biểu đồ LangGraph.
