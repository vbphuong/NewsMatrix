## External Configuration

Redis and RabbitMQ are not included in the project's source code directly. These are two external services that the backend connects to via environment variables.

### 1) Redis

You can run Redis using Docker, install it directly on your machine, or use a cloud service.

Run using Docker:

```bash
docker run --name newsmatrix-redis -p 6379:6379 -d redis:7-alpine
```

Recommendation for production:

```conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

The purpose of `allkeys-lru` is to keep hot keys in RAM longer and automatically evict least recently used keys first.

### 2) RabbitMQ

Run using Docker:

```bash
docker run --name newsmatrix-rabbitmq -p 5672:5672 -p 15672:15672 -d rabbitmq:3-management
```

The RabbitMQ Management UI will be available at:

```text
http://localhost:15672
```

Default credentials of the Docker image:

- Username: `guest`
- Password: `guest`

### 3) Backend `.env`

Add the following variables to `backend/.env`:

```env
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
RABBITMQ_QUEUE_NAME=news_interactions
CACHE_TTL_SECONDS=120
COMMENT_CACHE_TTL_SECONDS=300
```

### 4) How to Verify Connection

Once Redis and RabbitMQ are running, the backend will:

- Cache `like_count`, `comment_count`, and `followers_count`.
- Cache the lists of `liked_news_ids` and `followed_organization_ids`.
- Publish `like`, `comment`, and `follow` events to RabbitMQ if the queue is available.

If Redis or RabbitMQ is not running, the backend automatically falls back to synchronous processing so that the project runs locally without issues.

### 5) Important Notes

You do not need to create any `redis` or `rabbitmq` folders in the source code.

To cleanly separate environments, the correct approach is:

1. Use Docker or cloud services for Redis/RabbitMQ.
2. Keep them isolated from the backend and frontend.
3. Only configure the connection URLs in the `.env` file.

### 6) Minimum Checklist to Run the Application

1. PostgreSQL is running.
2. Redis is running.
3. RabbitMQ is running.
4. `backend/.env` points to the correct connection URLs.
5. Run the backend API.
6. Run the separate worker using `python -m api.worker`.
