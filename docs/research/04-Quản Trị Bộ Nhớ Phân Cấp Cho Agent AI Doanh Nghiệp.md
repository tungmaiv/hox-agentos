Quản lý bộ nhớ phân cấp (Hierarchical Memory Management) cho từng người dùng trong doanh nghiệp là một kỹ thuật then chốt để đảm bảo các Agent AI hoạt động ổn định, duy trì ngữ cảnh dài hạn và tối ưu hóa chi phí vận hành 1, 2\. Trong môi trường doanh nghiệp đa người dùng, hệ thống này không chỉ cần ghi nhớ mà còn phải đảm bảo tính **cô lập, bảo mật** và **hiệu quả về tài nguyên** 3, 4\.  
Dưới đây là phương pháp triển khai bộ nhớ phân cấp dựa trên các nguồn tài liệu:

### 1\. Kiến trúc bộ nhớ ba cấp độ (Three-Tier Architecture)

Một hệ thống bộ nhớ phân cấp hiện đại thường được chia thành ba lớp với các đặc tính lưu trữ khác nhau để cân bằng giữa độ chính xác và giới hạn của cửa sổ ngữ cảnh (context window) 5:

* **Bộ nhớ ngắn hạn (Short-term Memory):** Lưu trữ các lượt hội thoại gần nhất một cách nguyên bản (verbatim) 5\. Điều này giúp Agent duy trì sự mạch lạc ngay lập tức trong phiên làm việc hiện tại 5\. Trong giao thức **AG-UI**, điều này được quản lý thông qua các **Thread ID** để duy trì ngữ cảnh xuyên suốt các yêu cầu 6, 7\.  
* **Bộ nhớ trung hạn (Medium-term Memory):** Chứa các **bản tóm tắt nén** của các phiên làm việc gần đây 5\. Thay vì lưu toàn bộ văn bản, hệ thống tạo ra các tóm tắt ngày càng gọn hơn khi thông tin cũ đi, giúp tiết kiệm dung lượng token mà không làm mất đi các chi tiết quan trọng 8\.  
* **Bộ nhớ dài hạn (Long-term Memory):** Lưu trữ các **sự thật (facts), thực thể và mối quan hệ** cốt lõi được trích xuất từ lịch sử tương tác 5\. Thông tin này thường được lưu trong cơ sở dữ liệu vector (Vector Database) hoặc cơ sở dữ liệu quan hệ như PostgreSQL để truy xuất thông qua tìm kiếm ngữ nghĩa (semantic search) 9, 10\.

### 2\. Quản lý và Cô lập theo Người dùng (Per-User Isolation)

Trong doanh nghiệp, bộ nhớ phải được gắn chặt với danh tính người dùng để tránh rò rỉ dữ liệu 4, 11:

* **Xác thực và Ủy quyền:** Sử dụng **Copilot Runtime** làm cổng bảo mật để xác thực người dùng (ví dụ qua Keycloak) trước khi truy cập vào bộ nhớ 3, 12\. Runtime này đảm bảo rằng các API key và dữ liệu bộ nhớ nhạy cảm luôn nằm ở phía server và không bao giờ lộ ra phía client 3, 11\.  
* **Quản lý phiên (Session Management):** Giao thức AG-UI sử dụng các ID phiên được giao thức quản lý để duy trì ngữ cảnh hội thoại tách biệt cho từng người dùng đồng thời 13, 14\.  
* **Phân quyền dựa trên vai trò (RBAC):** Triển khai cơ chế lọc ngữ cảnh dựa trên vai trò (Role-based filtering), chỉ cung cấp cho Agent những thông tin bộ nhớ liên quan đến chức năng cụ thể của người dùng đó (ví dụ: nhân viên hỗ trợ chỉ thấy lịch sử hỗ trợ, không thấy dữ liệu tài chính) 15, 16\.

### 3\. Các chiến lược tối ưu hóa cửa sổ ngữ cảnh

Vì các mô hình ngôn ngữ có giới hạn về số lượng token, việc quản lý bộ nhớ cần các kỹ thuật thông minh 17, 18:

* **Tiêm ngữ cảnh có chọn lọc (Selective Context Injection):** Thay vì đưa toàn bộ lịch sử vào mỗi lần gọi AI, hệ thống chỉ phân tích truy vấn hiện tại và trích xuất những đoạn bộ nhớ có liên quan nhất để đưa vào cửa sổ ngữ cảnh 19\.  
* **Nén ngữ cảnh ngữ nghĩa:** Sử dụng **embeddings** để đại diện cho lịch sử hội thoại dưới dạng các vector đậm đặc, cho phép truy xuất thông tin liên quan từ kho lưu trữ bên ngoài một cách hiệu quả mà không làm quá tải bộ nhớ đệm 9, 20\.  
* **Tóm tắt phân cấp:** Hệ thống tự động tạo ra các bản tóm tắt ở các ranh giới hội thoại nhất định (ví dụ: sau mỗi 10 lượt chat hoặc sau mỗi phiên làm việc), giúp Agent có thể tham chiếu lại các sự kiện từ rất lâu trước đó mà không tốn nhiều token 8, 15\.

### 4\. Triển khai kỹ thuật (Technical Implementation)

Để xây dựng hệ thống này, bạn có thể kết hợp các công cụ sau:

* **LangGraph:** Sử dụng tính năng **Persistence** và các điểm kiểm tra (**checkpoints**) để lưu lại trạng thái của các luồng công việc (workflow) dài hạn, cho phép người dùng quay lại hoặc tiếp tục nhiệm vụ bất cứ lúc nào 21, 22\.  
* **Pydantic:** Định nghĩa các schema dữ liệu chặt chẽ cho bộ nhớ để đảm bảo tính nhất quán khi lưu trữ và truy xuất các sự thật đã được trích xuất 23, 24\.  
* **External Memory Augmentation:** Lưu trữ phần lớn bộ nhớ bên ngoài cửa sổ ngữ cảnh của mô hình và sử dụng cơ chế **Retrieval-Augmented Generation (RAG)** để nạp dữ liệu động khi cần thiết 25, 26\.

Việc áp dụng phương pháp bộ nhớ phân cấp giúp doanh nghiệp xây dựng những Agent AI không chỉ thông minh mà còn có **"khả năng thấu cảm" và ghi nhớ sâu sắc** về thói quen cũng như nhu cầu của từng nhân viên theo thời gian 27, 28\.  
