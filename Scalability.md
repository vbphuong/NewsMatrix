## Scalability Direction

The main objective is to prevent the database from getting choked or bottlenecked when traffic spikes for likes, comments, and follows occur.

### 1) RabbitMQ for Write-Heavy Actions

Write-heavy user interactions such as `like`, `unlike`, `comment`, `follow`, and `unfollow` are offloaded to RabbitMQ to:

- Shave traffic peaks by decoupling incoming requests from database writes.
- Reduce write overhead on the primary relational database.
- Allow worker instances to consume events asynchronously and scale independently.

In the current code:

- The API tries to publish events to the `news_interactions` queue.
- If RabbitMQ is not available, the backend falls back to synchronous execution to ensure the local project still runs.
- The standalone worker can be started by running `python -m api.worker`.

### 2) Redis for Hot Cache and Projections

Redis is used to cache read-heavy metrics and lists:

- `like_count`
- `comment_count`
- `followers_count`
- `liked_news_ids` list for each user
- `followed_organization_ids` list for each user
- Comment feed cache per news article

When a user loads or refreshes a page, the backend prioritizes reading these values from Redis. If a cache miss occurs, it falls back to querying the SQL database and primes the cache back into Redis.

### 3) LRU eviction + Pareto 80/20 Rule

In a news application, a small portion of popular articles (hot items) receives the majority of traffic. Therefore, it is unnecessary to keep all historical articles in cache memory simultaneously.

- Redis should be configured with `maxmemory-policy allkeys-lru`.
- When the allocated memory limit is reached, Redis automatically evicts the least recently used (LRU) keys.
- Popular keys remain alive, while cold keys are pruned.

Operational concept:

1. Popular articles and active metrics are cached in Redis.
2. As memory limits are hit, Redis evicts the cold keys.
3. Older, low-traffic articles drop out of the cache first.

### 4) Environment Variables

Add the following configuration parameters to your backend `.env`:

```env
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
RABBITMQ_QUEUE_NAME=news_interactions
CACHE_TTL_SECONDS=120
COMMENT_CACHE_TTL_SECONDS=300
```

For production environments, ensure you set a memory limit and LRU eviction policy in the Redis configuration (`redis.conf`):

```conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

### 5) How to Run Locally

To enable the full asynchronous pipeline and caching, run the services in the following order:

1. Create and activate your Python environment:

	```bash
	cd backend
	source ../.venv/bin/activate
	pip install -r requirements.txt
	```

2. Verify that PostgreSQL is running and `SQL_ALCHEMY_DATABASE_URL` in `backend/.env` points to your database instance.

3. Start Redis.

	If using Docker:

	```bash
	docker run --name newsmatrix-redis -p 6379:6379 -d redis:7-alpine
	```

4. Start RabbitMQ.

	If using Docker:

	```bash
	docker run --name newsmatrix-rabbitmq -p 5672:5672 -p 15672:15672 -d rabbitmq:3-management
	```

	Open the Management Dashboard at `http://localhost:15672` (using credentials `guest` / `guest`).

5. Configure environment variables in `backend/.env`:

	```env
	REDIS_URL=redis://localhost:6379/0
	RABBITMQ_URL=amqp://guest:guest@localhost:5672/%2F
	RABBITMQ_QUEUE_NAME=news_interactions
	CACHE_TTL_SECONDS=120
	COMMENT_CACHE_TTL_SECONDS=300
	```

6. Run the Backend API:

	```bash
	cd backend
	python -m api.main
	```

	If running with Uvicorn reload features:

	```bash
	uvicorn api.main:app --reload --port 8000
	```

7. Run the background worker to consume interactions asynchronously:

	```bash
	cd backend
	python -m api.worker
	```

8. Launch the Frontend Dev Server:

	```bash
	cd frontend
	npm install
	npm run dev
	```

If Redis or RabbitMQ are not active, the backend relies on the synchronous fallback. This means database operations happen in real-time, although you will miss out on throttling benefits and cache performance.