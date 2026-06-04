## External Configuration

Redis và RabbitMQ không nằm trong source code của project. Đây là 2 service bên ngoài mà backend sẽ kết nối tới qua biến môi trường.

### 1) Redis

Bạn có thể chạy Redis bằng Docker, cài trực tiếp trên máy, hoặc dùng dịch vụ cloud.

Chạy bằng Docker:

```bash
docker run --name newsmatrix-redis -p 6379:6379 redis:7-alpine
```

Khuyến nghị cho production:

```conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

Mục đích của `allkeys-lru` là giữ các key hot trong RAM lâu hơn và tự đẩy key ít dùng ra trước.

### 2) RabbitMQ

Chạy bằng Docker:

```bash
docker run --name newsmatrix-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

RabbitMQ Management UI sẽ ở:

```text
http://localhost:15672
```

Tài khoản mặc định của Docker image:

- Username: `guest`
- Password: `guest`

### 3) Backend `.env`

Thêm các biến sau vào `backend/.env`:

```env
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
RABBITMQ_QUEUE_NAME=news_interactions
CACHE_TTL_SECONDS=120
COMMENT_CACHE_TTL_SECONDS=300
```

### 4) Cách kiểm tra kết nối

Sau khi bật Redis và RabbitMQ, backend sẽ:

- cache `like_count`, `comment_count`, `followers_count`
- cache danh sách `liked_news_ids` và `followed_organization_ids`
- đẩy `like`, `comment`, `follow` sang RabbitMQ nếu queue có sẵn

Nếu Redis hoặc RabbitMQ chưa chạy, backend vẫn có fallback sync để project không bị lỗi.

### 5) Lưu ý quan trọng

Bạn không cần tạo thêm folder `redis` hay `rabbitmq` trong source code.

Nếu muốn tách môi trường rõ ràng hơn, cách đúng là:

1. Dùng Docker hoặc dịch vụ cloud cho Redis/RabbitMQ.
2. Giữ chúng tách biệt khỏi backend và frontend.
3. Chỉ cấu hình URL trong `.env`.

### 6) Trạng thái tối thiểu để chạy

1. PostgreSQL đang chạy.
2. Redis đang chạy.
3. RabbitMQ đang chạy.
4. `backend/.env` đã trỏ đúng URL.
5. Chạy backend API.
6. Chạy worker riêng bằng `python -m api.worker`.
