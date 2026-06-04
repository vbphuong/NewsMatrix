## Scalability Direction

Mục tiêu là tránh để database bị choke khi lượng like, comment, follow tăng đột biến.

### 1) RabbitMQ cho write-heavy actions

Các thao tác `like`, `unlike`, `comment`, `follow`, `unfollow` được đẩy qua RabbitMQ để:

- Cắt peak traffic thành từng event nhỏ.
- Giảm áp lực ghi trực tiếp vào database.
- Cho phép worker xử lý bất đồng bộ và có thể scale độc lập.

Trong code hiện tại:

- API sẽ cố publish event vào queue `news_interactions`.
- Nếu RabbitMQ chưa có, backend sẽ fallback về xử lý sync để project vẫn chạy local.
- Worker riêng có thể chạy bằng `python -m api.worker`.

### 2) Redis cho hot cache và projection

Redis dùng để cache các phần hay bị đọc lại:

- `like_count`
- `comment_count`
- `followers_count`
- danh sách `liked_news_ids`
- danh sách `followed_organization_ids`
- cache comments của từng bài viết

Khi user refresh lại trang, backend ưu tiên đọc từ Redis trước. Nếu cache miss thì mới quay về database và prime lại cache.

### 3) LRU + Pareto 80/20

Với website tin tức, phần lớn traffic sẽ dồn vào một nhóm nhỏ bài hot. Vì vậy không cần cache tất cả mọi thứ cùng lúc.

- Redis nên được cấu hình `maxmemory-policy allkeys-lru`.
- Khi RAM đầy, Redis tự đẩy ra các key ít được dùng gần đây nhất.
- Key hot sẽ sống lâu hơn, key lạnh bị thay thế trước.

Ý tưởng vận hành:

1. Bài hot được đẩy vào Redis.
2. Khi RAM đầy, Redis evict key ít dùng nhất.
3. Bài cũ, ít traffic sẽ rơi khỏi cache trước.

### 4) Environment variables

Thêm các biến sau vào backend environment:

```env
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
RABBITMQ_QUEUE_NAME=news_interactions
CACHE_TTL_SECONDS=120
COMMENT_CACHE_TTL_SECONDS=300
```

Nếu dùng Redis thật cho production, nên set memory cap và LRU ở tầng server, ví dụ:

```conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

### 5) Cách chạy local

Nếu muốn bật đầy đủ async + cache, chạy theo thứ tự này:

1. Tạo và kích hoạt Python environment như hiện tại.

	```bash
	cd backend
	source ../.venv/bin/activate
	pip install -r requirements.txt
	```

2. Đảm bảo PostgreSQL đang chạy và `SQL_ALCHEMY_DATABASE_URL` trong `backend/.env` trỏ đúng database.

3. Start Redis.

	Nếu dùng Docker:

	```bash
	docker run --name newsmatrix-redis -p 6379:6379 redis:7-alpine
	```

4. Start RabbitMQ.

	Nếu dùng Docker:

	```bash
	docker run --name newsmatrix-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
	```

	Sau đó mở RabbitMQ Management UI tại `http://localhost:15672` với `guest / guest`.

5. Thêm biến môi trường vào `backend/.env`.

	```env
	REDIS_URL=redis://localhost:6379/0
	RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
	RABBITMQ_QUEUE_NAME=news_interactions
	CACHE_TTL_SECONDS=120
	COMMENT_CACHE_TTL_SECONDS=300
	```

6. Chạy backend API.

	```bash
	cd backend
	python -m api.main
	```

	Nếu project của bạn đang chạy bằng Uvicorn thay vì module trực tiếp, dùng lệnh tương đương hiện tại của bạn, ví dụ:

	```bash
	uvicorn api.main:app --reload --port 8000
	```

7. Chạy worker để xử lý event bất đồng bộ.

	```bash
	cd backend
	python -m api.worker
	```

8. Mở frontend như bình thường ở thư mục `frontend`.

	```bash
	cd frontend
	npm install
	npm run dev
	```

Nếu Redis hoặc RabbitMQ chưa bật, backend vẫn chạy theo fallback sync. Nghĩa là request vẫn ghi DB trực tiếp, chỉ là chưa có lợi ích về throttling và cache.