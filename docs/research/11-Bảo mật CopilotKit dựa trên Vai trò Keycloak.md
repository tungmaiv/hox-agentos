Để kết nối các vai trò từ **Keycloak** với quyền hạn của công cụ (tools) trong **CopilotKit**, bạn cần triển khai một hệ thống bảo mật đa lớp phối hợp giữa **Copilot Runtime** (phía backend) và các **React Hooks** (phía frontend).  
Dưới đây là các bước chi tiết để thực hiện dựa trên các nguồn tài liệu:

### 1\. Xác thực tại ranh giới (Copilot Runtime)

**Copilot Runtime** đóng vai trò là "Hệ thần kinh trung ương" và cổng bảo mật cho ứng dụng của bạn 1, 2\.

* **Môi trường tin cậy:** Runtime chạy trên máy chủ của bạn, tạo ra một môi trường an toàn để thực thi xác thực, kiểm tra các yêu cầu và giữ an toàn cho các API key 3, 4\.  
* **Xác thực JWT:** Khi người dùng đăng nhập qua Keycloak, frontend sẽ nhận được một mã JWT. Mã này phải được gửi kèm trong header của các yêu cầu **AG-UI** đến Copilot Runtime 5\.  
* **Safe Defaults:** Khi sử dụng Runtime, các thiết lập an toàn mặc định sẽ được áp dụng để đảm bảo các endpoint của agent không bị truy cập bởi người dùng chưa xác thực 3, 4\.

### 2\. Kiểm soát quyền hiển thị công cụ ở Frontend

Bạn có thể quản lý quyền truy cập của người dùng đối với các công cụ, kỹ năng (skills) hoặc hàm MCP thông qua các thuộc tính có sẵn trong các hook của CopilotKit.

* **Sử dụng thuộc tính available:** Cả hook useFrontendTool (v2) và useCopilotAction (v1) đều hỗ trợ thuộc tính **available** 6, 7\.  
* **Cơ chế hoạt động:** Bạn có thể thiết lập giá trị này là **"enabled"** hoặc **"disabled"** dựa trên vai trò của người dùng được trích xuất từ token Keycloak 6, 7\.  
* Nếu một công cụ được đặt là "disabled", AI agent sẽ không thấy công cụ đó trong ngữ cảnh của nó và không thể kích hoạt hành động đó, giúp ẩn các khả năng nhạy cảm khỏi người dùng không có quyền 7\.  
* **Ví dụ logic:** Trong thành phần React, bạn kiểm tra vai trò từ Keycloak (ví dụ: user.roles.includes('admin')) và truyền kết quả vào tham số available của hook 7\.

### 3\. Thực thi ACL tại Backend thông qua Middleware

Vì logic phía frontend có thể bị bỏ qua, bạn phải thực thi việc kiểm tra quyền (ACL) một cách nghiêm ngặt tại **Copilot Runtime**.

* **AG-UI Middleware:** Sử dụng lớp middleware (agent.use) trong Runtime để chặn các sự kiện như **TOOL\_CALL\_START** 2, 8, 9\.  
* **Kiểm tra vai trò:** Middleware này sẽ trích xuất User ID và vai trò từ JWT và đối chiếu với cơ sở dữ liệu quyền hạn của bạn trước khi cho phép agent thực thi bất kỳ công cụ hoặc hàm MCP nào 8, 10\.  
* **Lọc ngữ cảnh dựa trên vai trò (Role-Based Context Filtering):** Bạn có thể cấu hình để mỗi vai trò agent chỉ nhận được các ngữ cảnh và tài liệu liên quan đến chức năng của họ, giúp tối ưu hóa cửa sổ ngữ cảnh và tăng tính bảo mật 10, 11\.

### 4\. Quản lý dữ liệu với useCopilotReadable

Để AI agent có nhận thức về quyền hạn của người dùng, bạn có thể sử dụng hook **useCopilotReadable** 12, 13\.

* **Cung cấp thông tin quyền:** Bạn có thể nạp các thông tin về vai trò hoặc danh sách các quyền hạn hiện tại của người dùng vào ngữ cảnh của agent 12\.  
* **Phân loại (Categories):** Sử dụng tham số categories để kiểm soát phần nào của trạng thái ứng dụng sẽ hiển thị cho agent dựa trên cấp độ truy cập của người dùng 14\.

### 5\. Tách biệt Hành động Frontend và Backend

Một mô hình thiết kế quan trọng trong CopilotKit là tách biệt giữa các hành động được định nghĩa ở frontend và backend 15\.

* **Frontend actions:** Dùng để thao tác UI (như mở modal, thay đổi sắp xếp) dựa trên quyền hạn hiển thị 16\.  
* **Backend actions:** Thực hiện các thao tác dữ liệu an toàn hoặc tính toán nặng (như truy vấn DB, gọi API bảo mật) và luôn phải được xác thực lại vai trò người dùng tại Runtime 4, 16\.

**Tóm lại:** Để kết nối vai trò Keycloak, bạn trích xuất vai trò từ mã xác thực tại **Copilot Runtime**, sau đó điều khiển trạng thái **available** của các công cụ ở frontend và sử dụng **middleware AG-UI** ở backend để ngăn chặn các nỗ lực thực thi trái phép 7, 8\.  
