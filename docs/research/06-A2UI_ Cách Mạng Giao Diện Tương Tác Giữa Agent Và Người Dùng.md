Dựa trên các nguồn tài liệu, A2UI (Agent-to-User Interface) là một đặc tả (specification) giao diện người dùng sinh động (generative UI) được phát triển bởi Google. Nó cho phép các AI Agent tạo và hiển thị các giao diện người dùng tương tác, linh hoạt ngay tại thời điểm chạy (on the fly), thay vì dựa vào các giao diện tĩnh đã được lập trình sẵn từ trước.
Dưới đây là chi tiết về A2UI và cách bạn có thể tích hợp nó vào ngăn xếp công nghệ (stack) hiện tại của mình:
1. A2UI là gì?
• Cơ chế hoạt động: Thay vì chỉ phản hồi bằng văn bản đơn thuần, Agent có thể gửi các thành phần tương tác như biểu đồ, bảng dữ liệu đầy đủ, các biểu mẫu (forms) hoặc các nút bấm chức năng (ví dụ: "Approve" hoặc "Reject") phù hợp với nhiệm vụ hiện tại.
• Định dạng dữ liệu: A2UI sử dụng định dạng JSONL (JSON Lines) hoặc JSON-LD cấp cao, không phụ thuộc vào framework, cho phép nó được render (dựng hình) nguyên bản trên bất kỳ nền tảng nào như web, di động hay máy tính để bàn.
• Vị trí trong hệ sinh thái: A2UI được xây dựng dựa trên giao thức A2A (Agent-to-Agent) và hoạt động nhịp nhàng với AG-UI. Trong khi AG-UI cung cấp kết nối hai chiều hoàn chỉnh giữa backend và frontend, A2UI đóng vai trò là "ngôn ngữ" để mô tả các widget giao diện mà Agent muốn hiển thị.
2. Cách triển khai A2UI trong Stack của bạn
Với stack gồm CopilotKit, LangGraph (Python) và giao thức AG-UI, bạn có thể tích hợp A2UI theo các bước sau:
Phía Backend (Python / LangGraph)
• Định nghĩa Schema: Bạn cần thiết lập một JSON Schema hoàn chỉnh cho các tin nhắn A2UI trong backend để Agent hiểu cách cấu trúc dữ liệu.
• Sử dụng A2UI Composer: Để thiết kế các widget, bạn có thể sử dụng công cụ A2UI Composer để mô tả giao diện bằng ngôn ngữ tự nhiên và nhận về đặc tả JSON tương ứng.
• Cấu hình Prompt: Đưa các ví dụ về JSON A2UI (UI Examples) vào System Prompt của Agent LangGraph. Agent sẽ học cách phát đi ba loại thông điệp chính:
    1. surfaceUpdate: Định nghĩa các thành phần UI.
    2. dataModelUpdate: Cập nhật trạng thái dữ liệu cho UI đó.
    3. beginRendering: Tín hiệu bắt đầu dựng giao diện trên frontend.
• Xử lý ActivityMessage: Agent của bạn sẽ đóng gói các đặc tả này thành các đối tượng ActivityMessage để gửi về frontend thông qua giao thức AG-UI.
Phía Frontend (Next.js / CopilotKit)
• Tạo Message Renderer: Sử dụng hàm createA2UIMessageRenderer do CopilotKit cung cấp để tạo một trình dựng giao diện. Trình dựng này sẽ lắng nghe các tin nhắn A2UI từ backend và chuyển đổi chúng thành các component React trong thời gian thực.
• Tích hợp vào Provider: Bạn cần truyền trình dựng A2UIMessageRenderer này vào thành phần <CopilotKit> provider để toàn bộ ứng dụng có khả năng hiểu và hiển thị các widget A2UI.
• Giao tiếp qua AG-UI: Giao thức AG-UI sẽ đảm nhận việc vận chuyển các đặc tả A2UI và đồng bộ hóa trạng thái giữa Agent và các widget đang hiển thị trên màn hình người dùng.
3. Lợi ích khi sử dụng A2UI trong dự án phức tạp
• Tăng tính minh bạch: Thay vì các quy trình chạy ngầm khó hiểu, người dùng có thể thấy tiến độ và kết quả trung gian thông qua các thành phần UI sinh động.
• Cộng tác người-máy (Human-in-the-Loop): Agent có thể hiển thị một widget yêu cầu xác nhận hoặc chỉnh sửa thông tin thông qua cơ chế renderAndWaitForResponse, giúp quy trình làm việc doanh nghiệp trở nên an toàn và tin cậy hơn.
• Khả năng mở rộng: Bạn có thể xây dựng một thư viện widget A2UI phong phú và cho phép Agent tự quyết định sử dụng công cụ nào dựa trên ngữ cảnh mà không cần phải viết code UI mới cho mỗi tính năng.
Việc kết hợp A2UI để dựng giao diện linh hoạt và AG-UI làm đường truyền dữ liệu sẽ giúp ứng dụng của bạn vượt ra khỏi giới hạn của một chatbot truyền thống, trở thành một hệ điều hành Agentic thực thụ.