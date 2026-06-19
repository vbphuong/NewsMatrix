# Các Tính Năng Của Hệ Thống NewsMatrix

Tài liệu này tổng hợp toàn bộ các tính năng hiện có của trang web NewsMatrix (đã lược bỏ các phần liên quan đến hàng đợi (queue), bộ nhớ đệm (cache) và RAG theo yêu cầu).

---

## 1. Phân Quyền & Quản Lý Truy Cập (Role-Based Access Control - RBAC)
Hệ thống được thiết kế với cơ chế phân quyền chặt chẽ trên cả Frontend (Vue Router guard) và Backend (FastAPI dependencies). Có 3 vai trò chính:
* **Admin (Quản trị viên):** Có toàn quyền quản lý người dùng, tổ chức, danh mục bài viết và tải lên tài liệu.
* **Journalist (Nhà báo):** Có quyền quản lý bài viết thuộc phạm vi tổ chức của mình (Tạo, sửa, xóa, chuyển đổi nháp/xuất bản).
* **User (Người dùng phổ thông):** Đọc tin tức công khai, tương tác (thích/theo dõi) và bình luận.

---

## 2. Các Tính Năng Phân Hệ Khách (Public Client Features)

### 2.1. Trang Chủ (Homepage)
* Giao diện phong cách Bento sang trọng hiển thị tổng quan các lối vào chính (Tin tức, Tổ chức, Đăng nhập).
* Khu vực trưng bày hình ảnh động cho phép ẩn/hiện và xem ảnh lớn.

### 2.2. Trang Tin Tức (News Feed)
* **Xem danh sách tin tức:** Hiển thị danh sách các bài báo đã được xuất bản (không hiển thị các bài viết nháp - Draft). Mỗi bài viết gồm ảnh đại diện, tiêu đề, nội dung tóm tắt, danh sách tác giả, danh mục và các chỉ số tương tác (lượt thích, bình luận, số người theo dõi tổ chức).
* **Lọc & Tìm kiếm:**
  * Tìm kiếm từ khóa theo tiêu đề, nội dung, danh mục hoặc ngày tháng.
  * Bộ lọc nhanh theo danh mục bài viết.
  * Bộ lọc theo ngày xuất bản cụ thể.
* **Lựa chọn nguồn dữ liệu (Multi-source Toggle):** Cho phép xem tin tức từ 3 nguồn khác nhau:
  1. *System data:* Dữ liệu thực tế được lấy từ cơ sở dữ liệu backend.
  2. *Mock data:* Dữ liệu giả lập lưu trong file JSON nội bộ (`news.json`).
  3. *External data:* Gọi API tin tức bên ngoài (GNews API) với cơ chế tự động làm mới mỗi 60 giây và cho phép tùy chỉnh URL API.
* **Phân trang (Pagination):** Cho phép thay đổi kích thước trang (5 hoặc 10 bài viết trên một trang) và chuyển trang linh hoạt.
* **Tương tác trực tiếp:** Thích/Bỏ thích bài viết và Theo dõi/Hủy theo dõi tổ chức viết bài trực tiếp trên card tin tức (chỉ dành cho người dùng đã đăng nhập).

### 2.3. Trang Chi Tiết Tin Tức (News Detail Page)
* Hiển thị đầy đủ thông tin chi tiết của bài báo (Tiêu đề, tác giả, ngày xuất bản, nội dung chi tiết, thẻ danh mục).
* **Quản lý tương tác:** Nút Thích/Bỏ thích bài viết và Theo dõi/Hủy theo dõi tổ chức. Chỉ khả dụng đối với tin tức có trạng thái "Published".
* **Hệ thống Bình luận (Comments):**
  * Xem danh sách các bình luận dưới bài báo kèm email người gửi và thời gian gửi.
  * Form gửi bình luận mới (yêu cầu đăng nhập và bài viết đã xuất bản).

### 2.4. Trang Giới Thiệu (About Page)
* Cung cấp thông tin sứ mệnh, giá trị cốt lõi và lộ trình phát triển của hệ thống.
* **Trải nghiệm tương tác (Try it out):** Khu vực tương tác nhập Họ & Tên và chọn hình ảnh hiển thị động bằng Two-way Data Binding.

---

## 3. Các Tính Năng Quản Lý Của Nhà Báo (Journalist Workspace)
Khu vực làm việc chuyên dụng dành riêng cho nhà báo thuộc các tổ chức tòa soạn (Admin cũng có quyền truy cập):
* **Xem tin tức nội bộ:** Danh sách các bài viết thuộc tổ chức mà nhà báo đang trực thuộc (bao gồm cả bài nháp và bài đã xuất bản).
* **Tạo bài viết mới:** Nhập tiêu đề, nội dung, chọn trạng thái (Draft / Published), chọn nhiều danh mục bài viết (Categories) đi kèm.
* **Chỉnh sửa bài viết:** Cập nhật thông tin chi tiết bài báo cũ.
* **Xóa bài viết:** Gỡ bỏ hoàn toàn bài báo khỏi hệ thống của tổ chức (có hộp thoại xác nhận).

---

## 4. Các Tính Năng Quản Trị Hệ Thống (Admin Portal)

### 4.1. Quản Lý Tổ Chức (Organization Management)
* **Xem danh sách tổ chức:** Danh sách các tòa soạn kèm các cấu hình giới hạn đăng bài hàng ngày (`daily_post_limit`), giới hạn lượt chỉnh sửa (`current_edit_limit`) và số người theo dõi.
* **Thêm mới tổ chức:** Khởi tạo không gian tổ chức mới với tên, mô tả, giới hạn bài đăng hàng ngày và giới hạn chỉnh sửa.
* **Chỉnh sửa tổ chức:** Cập nhật thông tin và các giới hạn vận hành của tòa soạn.
* **Xóa tổ chức:** Gỡ bỏ tổ chức (chỉ hiển thị nút xóa cho Admin).
* **Quản lý Nhân sự của Tổ chức (Organization Detail Page):**
  * Xem danh sách các nhà báo đang thuộc biên chế tổ chức (phân trang 5 người/trang).
  * Chỉ định (Add) thêm nhà báo từ danh sách nhà báo tự do chưa được gán tổ chức.
  * Trục xuất (Remove) nhà báo ra khỏi tổ chức.

### 4.2. Quản Lý Danh Mục (Category Management)
* Xem danh sách các thể loại/danh mục tin tức sắp xếp theo thứ tự bảng chữ cái.
* Tạo danh mục mới (yêu cầu tên không trùng lặp và không để trống).
* Chỉnh sửa tên danh mục.
* Xóa danh mục bài viết.

### 4.3. Quản Lý Người Dùng (People Governance)
* Giao diện Bento Box hiện đại thống kê nhanh các chỉ số (Tổng số người dùng, tổng số vai trò, số nhóm vai trò đang hoạt động).
* Danh sách thư mục người dùng chi tiết hiển thị avatar, email, vai trò (role pill) và ngày cập nhật gần nhất.
* **Tạo người dùng mới:** Nhập Email, mật khẩu và gán quyền trực tiếp (User, Journalist, Admin).
* **Cập nhật người dùng:** Thay đổi email, phân vai trò mới, hoặc đổi mật khẩu (nếu để trống sẽ giữ nguyên mật khẩu cũ).
* **Xóa tài khoản người dùng.**

### 4.4. Đọc & Nhập Tài Liệu (Document Ingestion)
* **Tải lên tài liệu PDF:** Admin tải lên các tài liệu PDF chuyên ngành phục vụ lưu trữ.
* **Xử lý tài liệu:** Tự động đẩy file PDF vào Supabase Storage (bucket `raw_data`), thực hiện chia nhỏ nội dung tài liệu (chunking) và đếm số trang/số chunk được tạo ra.
* **Xem lịch sử tài liệu:** Hiển thị danh sách tài liệu đã tải lên bao gồm tên file, số trang, số chunk, định dạng file, đường dẫn lưu trữ và thời gian khởi tạo.

---

## 5. Xác Thực Người Dùng & Bảo Mật (Authentication & Security)
* **Đăng ký tài khoản (Sign Up):** Tạo tài khoản người dùng mới qua email và mật khẩu (gán mặc định vai trò "User").
* **Đăng nhập tiêu chuẩn (Sign In):** Xác thực thông tin qua email & mật khẩu, trả về JWT Token từ backend để lưu trữ phiên làm việc.
* **Đăng nhập mạng xã hội (Social Login):** Đăng nhập nhanh qua Google hoặc GitHub (chỉ cần nhập email và chọn nhà cung cấp dịch vụ, hệ thống tự động đăng ký tài khoản mới nếu email chưa tồn tại trong hệ thống).
* **Đăng xuất (Logout):** Xóa session lưu trữ JWT cục bộ và điều hướng về trang đăng nhập.
