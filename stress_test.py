import time
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure API Backend URL
BASE_URL = "http://localhost:8000"
NUM_REQUESTS = 1000  # Number of requests to run
CONCURRENCY = 20   # Thread pool limit for concurrent execution
TIMEOUT_SECONDS = 30  # Request timeout threshold in seconds

def run_stress_test():
    print("=" * 60)
    print(" STARTING CONCURRENT COMMENT STRESS TEST (OPTIMIZED CONFIGURATION)")
    print("=" * 60)

    # Step 1: Create a test user account
    email = f"stress_user_{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    print(f"[*] Registering test account: {email}...")
    try:
        register_resp = requests.post(f"{BASE_URL}/auth/", json={"email": email, "password": password})
        register_resp.raise_for_status()
        token_data = register_resp.json()
        token = token_data["access_token"]
        print("[+] Test account registered successfully.")
    except Exception as e:
        print(f"[-] Registration failed. Check if the backend is running: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Fetch an article to comment on
    print("[*] Finding a published article to comment on...")
    try:
        news_resp = requests.get(f"{BASE_URL}/news", headers=headers)
        news_resp.raise_for_status()
        news_list = news_resp.json().get("items", [])
        
        published_news = [n for n in news_list if n.get("status", "").lower() == "published"]
        if not published_news:
            print("[-] No 'Published' articles found.")
            return
        
        news_id = published_news[0]["news_id"]
        title = published_news[0]["title"]
        print(f"[+] Found article: ID {news_id} - '{title[:30]}...'")
    except Exception as e:
        print(f"[-] Failed to fetch articles list: {e}")
        return

    # Step 3: Function to send a single comment request
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

    # Step 4: Perform concurrent requests
    print(f"[*] Sending {NUM_REQUESTS} comments (concurrency: {CONCURRENCY}, timeout: {TIMEOUT_SECONDS}s)...")
    start_total = time.time()
    
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(send_single_comment, i): i for i in range(1, NUM_REQUESTS + 1)}
        for future in as_completed(futures):
            results.append(future.result())
            
    total_duration = time.time() - start_total

    # Step 5: Analyze stress test results
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
    print(" STRESS TEST RESULTS")
    print("=" * 60)
    print(f"- Total duration: {total_duration:.3f} seconds")
    if success_count > 0:
        print(f"- Average response latency per request: {(total_latency / success_count) * 1000:.1f} milliseconds")
    print(f"- Successful requests (201 Created): {success_count}/{NUM_REQUESTS}")
    print(f"- Failed requests: {failure_count}/{NUM_REQUESTS}")
    
    if success_count > 0:
        print(f"- Negative IDs (Processed via RabbitMQ Async): {negative_ids}")
        print(f"- Positive IDs (Written directly to DB Sync): {positive_ids}")

    if failure_count > 0:
        print("\nEncountered errors:")
        for err_msg, count in errors.items():
            print(f"  + [{count} times] {err_msg}")
    
    print("\n[OBSERVATION HINT]:")
    if negative_ids > 0:
        print("  -> The system is routing requests via RabbitMQ: lightning fast response, returned temporary negative IDs.")
    else:
        print("  -> RabbitMQ is not active (falling back to direct DB sync write).")
    print("=" * 60)

if __name__ == "__main__":
    run_stress_test()
