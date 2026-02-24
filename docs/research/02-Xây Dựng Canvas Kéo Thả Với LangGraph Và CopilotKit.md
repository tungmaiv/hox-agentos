Để xây dựng một sơ đồ kéo thả (thường được gọi là ứng dụng **Canvas**) kết hợp giữa **LangGraph** và **CopilotKit**, bạn cần triển khai một kiến trúc "Shared State" (trạng thái chia sẻ) mạnh mẽ, nơi Agent và giao diện người dùng luôn đồng bộ hóa trong thời gian thực thông qua giao thức **AG-UI** 1, 2\.  
Dưới đây là các bước chi tiết để xây dựng hệ thống này dựa trên các nguồn tài liệu:

### 1\. Kiến trúc tổng thể (Architecture Overview)

Hệ thống Canvas được xây dựng dựa trên ba thành phần chính 3, 4:

* **Frontend (Next.js \+ CopilotKit):** Quản lý giao diện kéo thả, sử dụng các hook để giao tiếp với AI.  
* **Backend (Python \+ LangGraph):** Chứa logic điều phối Agent, quản lý các nút (nodes) và cạnh (edges) của sơ đồ thông qua một biểu đồ trạng thái (StateGraph).  
* **Giao thức AG-UI:** Đóng vai trò là lớp kết nối sự kiện, cho phép stream các thay đổi trạng thái và hành động giữa hai đầu 5, 6\.

### 2\. Triển khai Shared State (Đồng bộ hóa trạng thái)

Đây là phần quan trọng nhất để AI có thể "hiểu" và "tương tác" với sơ đồ của bạn 7, 8:

* **Sử dụng hook useCoAgent:** Hook này cho phép frontend đăng ký vào trạng thái của Agent phía backend 9, 10\. Khi người dùng kéo thả một thẻ trên canvas, trạng thái này sẽ được cập nhật lên backend; ngược lại, khi Agent thay đổi sơ đồ, frontend sẽ tự động render lại các thành phần tương ứng 7, 11\.  
* **Định nghĩa Schema trạng thái:** Bạn cần mở rộng CopilotKitState trong LangGraph để bao gồm các trường dữ liệu cụ thể cho canvas, chẳng hạn như danh sách các nút, vị trí tọa độ, và nội dung của từng thẻ 12\.

### 3\. Cung cấp "Đôi mắt" cho AI (useCopilotReadable)

Để Agent có thể đưa ra các lời khuyên về sơ đồ hoặc giúp bạn thiết kế, nó cần "nhìn" thấy dữ liệu hiện có 13:

* Sử dụng hook **useCopilotReadable** để đưa toàn bộ cấu trúc sơ đồ hiện tại vào ngữ cảnh (context) của AI 14\.  
* Ví dụ: Bạn có thể gửi danh sách các nhiệm vụ đang có trên sơ đồ kèm theo mô tả để AI biết cần phải thêm bước nào tiếp theo 14, 15\.

### 4\. Cung cấp "Đôi tay" cho AI (useFrontendTool / useCopilotAction)

Để AI có thể tự tay tạo mới, xóa hoặc di chuyển các nút trên sơ đồ, bạn cần đăng ký các công cụ phía client 16, 17:

* **Đăng ký Action:** Sử dụng useFrontendTool (v2) hoặc useCopilotAction (v1) để định nghĩa các hàm như addNode, updateNodePosition, hoặc deleteEdge 18, 19\.  
* **Thực thi từ Backend:** Khi Agent LangGraph quyết định cần thay đổi sơ đồ, nó sẽ gọi các công cụ này thông qua giao thức AG-UI. Logic thực thi sẽ chạy trực tiếp trên trình duyệt của người dùng để cập nhật giao diện React 16, 17\.

### 5\. Xây dựng logic lập kế hoạch đa bước (Multi-step Planning)

Với các sơ đồ phức tạp, bạn nên sử dụng mô hình **Deep Agents** 20, 21:

* **Tự động tạo sơ đồ:** Thay vì chỉ thực hiện một lệnh duy nhất, Agent có thể lập một danh sách các việc cần làm (to-do list) như: "1. Tạo nút khởi đầu; 2\. Tạo 3 nút xử lý song song; 3\. Kết nối chúng lại" 22, 23\.  
* **Visual Progress:** CopilotKit hỗ trợ hiển thị tiến trình thực hiện các bước này trực tiếp trên giao diện để người dùng theo dõi AI đang làm đến đâu 1, 3\.

### 6\. Cơ chế Human-in-the-Loop (HITL)

Trong thiết kế sơ đồ, việc AI tự ý thay đổi có thể gây sai sót. Bạn nên tích hợp các điểm dừng phê duyệt 24, 25:

* Sử dụng thuộc tính **renderAndWaitForResponse** trong các hành động quan trọng 26\.  
* Khi AI muốn thay đổi cấu trúc lớn của sơ đồ, nó sẽ hiển thị một widget yêu cầu người dùng xác nhận ( Approve/Reject). Agent sẽ tạm dừng thực thi cho đến khi nhận được phản hồi từ con người 8, 27\.

### 7\. Mẫu Starter để bắt đầu ngay (Starter Template)

Bạn có thể sử dụng mẫu **CopilotKit \<\> LangGraph AG-UI Canvas Starter** có sẵn trên GitHub để tiết kiệm thời gian 1:

* **Tính năng sẵn có:** Canvas không ràng buộc (drag-free) hiển thị các thẻ theo lưới phản hồi, hỗ trợ 4 loại thẻ mặc định (Dự án, Thực thể, Ghi chú, Biểu đồ) 1\.  
* **Đồng bộ thực:** Hỗ trợ chế độ xem JSON để gỡ lỗi và đồng bộ hóa hai chiều hoàn chỉnh giữa Agent Python và Canvas UI 1, 22\.

**Tóm lại**, quy trình triển khai bao gồm việc cài đặt **Next.js** cho giao diện, sử dụng **LangGraph** để quản lý biểu đồ logic ở backend, và dùng **CopilotKit** làm "keo dán" để đồng bộ hóa dữ liệu và hành động thông qua hook useCoAgent và các client-side tools 3, 4, 28\.  
