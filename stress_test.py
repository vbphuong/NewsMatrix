import time
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cấu hình API Backend URL
BASE_URL = "http://localhost:8000"
NUM_REQUESTS = 100  # Giảm xuống 50 requests để tránh nghẽn luồng đơn FastAPI
CONCURRENCY = 10   # Giảm độ song song để luồng đơn FastAPI xử lý kịp
TIMEOUT_SECONDS = 30  # Tăng thời gian chờ lên 30 giây để tránh timeout

def run_stress_test():
    print("=" * 60)
    print(" BẮT ĐẦU CHẠY THỬ NGHIỆM GỬI COMMENT ĐỒNG THỜI (ĐÃ TỐI ƯU CẤU HÌNH)")
    print("=" * 60)

    # Bước 1: Tạo tài khoản test tự động
    email = f"stress_user_{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    print(f"[*] Đang đăng ký tài khoản thử nghiệm: {email}...")
    try:
        register_resp = requests.post(f"{BASE_URL}/auth/", json={"email": email, "password": password})
        register_resp.raise_for_status()
        token_data = register_resp.json()
        token = token_data["access_token"]
        print("[+] Đăng ký tài khoản thành công.")
    except Exception as e:
        print(f"[-] Đăng ký thất bại. Kiểm tra xem backend đã chạy chưa: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Bước 2: Tìm một bài viết
    print("[*] Đang tìm bài viết để comment...")
    try:
        news_resp = requests.get(f"{BASE_URL}/news", headers=headers)
        news_resp.raise_for_status()
        news_list = news_resp.json().get("items", [])
        
        published_news = [n for n in news_list if n.get("status", "").lower() == "published"]
        if not published_news:
            print("[-] Không tìm thấy bài viết nào 'Published'.")
            return
        
        news_id = published_news[0]["news_id"]
        title = published_news[0]["title"]
        print(f"[+] Tìm thấy bài viết: ID {news_id} - '{title[:30]}...'")
    except Exception as e:
        print(f"[-] Không lấy được danh sách bài viết: {e}")
        return

    # Bước 3: Hàm gửi comment
    def send_single_comment(index):
        start_time = time.time()
        payload = {"content": f"Stress test comment #{index} - {uuid.uuid4().hex[:4]}"}
        try:
            resp = requests.post(
                f"{BASE_URL}/news/{news_id}/comments",
                json=payload,
                headers=headers,
                timeout=TIMEOUT_SECONDS
            )
            elapsed = time.time() - start_time
            if resp.status_code == 201:
                comment_data = resp.json()
                cid = comment_data.get("comment_id")
                return True, elapsed, cid, None
            else:
                return False, elapsed, None, f"HTTP {resp.status_code}: {resp.text}"
        except Exception as err:
            elapsed = time.time() - start_time
            return False, elapsed, None, str(err)

    # Bước 4: Thực hiện gửi đồng thời
    print(f"[*] Đang gửi {NUM_REQUESTS} comments (độ song song: {CONCURRENCY}, timeout: {TIMEOUT_SECONDS}s)...")
    start_total = time.time()
    
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(send_single_comment, i): i for i in range(1, NUM_REQUESTS + 1)}
        for future in as_completed(futures):
            results.append(future.result())
            
    total_duration = time.time() - start_total

    # Bước 5: Phân tích kết quả
    success_count = 0
    failure_count = 0
    total_latency = 0.0
    errors = {}
    
    negative_ids = 0
    positive_ids = 0

    for success, latency, cid, err in results:
        if success:
            success_count += 1
            total_latency += latency
            if cid is not None:
                if cid < 0:
                    negative_ids += 1
                else:
                    positive_ids += 1
        else:
            failure_count += 1
            errors[err] = errors.get(err, 0) + 1

    print("\n" + "=" * 60)
    print(" KẾT QUẢ THỬ NGHIỆM")
    print("=" * 60)
    print(f"- Tổng thời gian hoàn thành: {total_duration:.3f} giây")
    if success_count > 0:
        print(f"- Thời gian phản hồi trung bình mỗi request: {(total_latency / success_count) * 1000:.1f} mili-giây")
    print(f"- Số request Thành Công (201 Created): {success_count}/{NUM_REQUESTS}")
    print(f"- Số request Thất Bại: {failure_count}/{NUM_REQUESTS}")
    
    if success_count > 0:
        print(f"- Số ID âm (Xử lý qua RabbitMQ Async): {negative_ids}")
        print(f"- Số ID dương (Ghi trực tiếp vào DB Sync): {positive_ids}")

    if failure_count > 0:
        print("\nCác lỗi gặp phải:")
        for err_msg, count in errors.items():
            print(f"  + [{count} lần] {err_msg}")
    
    print("\n[GỢI Ý QUAN SÁT]:")
    if negative_ids > 0:
        print("  -> Hệ thống đang chạy qua RabbitMQ: phản hồi cực nhanh, ID trả về là số âm tạm thời.")
    else:
        print("  -> Hệ thống đang KHÔNG CÓ RabbitMQ (fallback ghi trực tiếp DB).")
    print("=" * 60)

if __name__ == "__main__":
    run_stress_test()
