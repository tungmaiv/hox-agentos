Dựa trên các tài liệu, việc thực thi **ACL (Access Control List)** cho các chức năng **MCP (Model Context Protocol)** trong stack của bạn nên được thực hiện tại lớp **Copilot Runtime** thông qua cơ chế **AG-UI Middleware** 1, 2\.  
Dưới đây là mô tả chi tiết và ví dụ về cách triển khai middleware backend để kiểm soát quyền truy cập:

### 1\. Cơ chế hoạt động của Middleware ACL

Copilot Runtime đóng vai trò là "Hệ thần kinh trung ương", nơi bạn có thể đăng ký middleware (agent.use) để chặn và kiểm tra mọi sự kiện tương tác giữa người dùng và Agent 1, 2\. Đối với việc thực thi ACL cho các công cụ MCP, middleware sẽ tập trung vào sự kiện **TOOL\_CALL\_START** — tín hiệu cho biết Agent đang cố gắng kích hoạt một công cụ 3\.

### 2\. Ví dụ triển khai Middleware (Python/FastAPI)

Vì bạn ưu tiên sử dụng Python, middleware sẽ được triển khai trong môi trường tin cậy phía server để tránh bị can thiệp bởi client 4, 5\.  
from copilotkit.sdk import CopilotKitSDK  
from fastapi import Request, HTTPException

\# Giả sử bạn có một module quản lý ACL kết nối với DB (PostgreSQL)  
from your\_app.security import check\_permission 

sdk \= CopilotKitSDK()

@sdk.agent.use  
async def acl\_middleware(context, next):  
    \# 1\. Trích xuất thông tin người dùng từ context (đã được xác thực qua Keycloak JWT)  
    user\_id \= context.properties.get("user\_id")  
    user\_roles \= context.properties.get("roles", \[\])  
      
    \# 2\. Kiểm tra nếu sự kiện là bắt đầu gọi một công cụ (Tool Call)  
    if context.event\_type \== "TOOL\_CALL\_START":  
        tool\_name \= context.payload.get("name")  
          
        \# 3\. Thực thi logic ACL: Kiểm tra xem user có quyền gọi tool MCP này không  
        \# Tool MCP thường được đăng ký với tiền tố hoặc định danh cụ thể  
        has\_access \= await check\_permission(user\_id, user\_roles, tool\_name)  
          
        if not has\_access:  
            \# Ngăn chặn thực thi và gửi thông báo lỗi qua giao thức AG-UI  
            raise HTTPException(  
                status\_code=403,   
                detail=f"Quyền truy cập bị từ chối cho công cụ: {tool\_name}"  
            )  
              
    \# 4\. Nếu hợp lệ, chuyển tiếp yêu cầu đến bước xử lý tiếp theo  
    return await next()

### 3\. Các thành phần bổ trợ cho bảo mật doanh nghiệp

Để hệ thống ACL trở nên mạnh mẽ hơn trong môi trường doanh nghiệp, bạn nên cân nhắc các yếu tố sau từ nguồn tài liệu:

* **Delegation Capability Tokens (DCTs):** Đối với các chuỗi ủy quyền phức tạp (ví dụ: Agent A gọi Agent B để dùng công cụ MCP C), bạn có thể sử dụng các công nghệ như **Macaroons** hoặc **Biscuits** 6\. Các token này đính kèm "ràng buộc mã hóa" (cryptographic caveats) để áp dụng nguyên tắc đặc quyền tối thiểu, ví dụ: chỉ cho phép công cụ MCP đọc một thư mục Google Drive cụ thể mà không được quyền ghi 6, 7\.  
* **Tách biệt ranh giới bảo mật:** Mọi cấu hình agent và API key MCP phải được giữ an toàn tại Runtime và không bao giờ lộ ra phía client 5\.  
* **Guardrails tại biên:** Sử dụng middleware để ngăn chặn các cuộc tấn công prompt injection nhắm vào việc lừa agent gọi các công cụ MCP nhạy cảm mà người dùng không có quyền 8\.

### 4\. Kết hợp với Frontend

Ở phía frontend, bạn nên đồng bộ hóa logic này bằng cách sử dụng thuộc tính **available** trong hook useFrontendTool (v2) 9\. Nếu middleware backend của bạn xác định người dùng không có quyền, bạn nên đặt available="disabled" ở frontend để agent thậm chí không "thấy" công cụ đó trong ngữ cảnh, giúp tối ưu hóa cửa sổ ngữ cảnh và giảm độ trễ 10, 11\.  
Việc triển khai này đảm bảo rằng ngay cả khi người dùng cố gắng can thiệp vào mã client để gọi tool, middleware tại **Copilot Runtime** vẫn sẽ chặn đứng yêu cầu trước khi nó chạm tới server MCP 12, 13\.  
