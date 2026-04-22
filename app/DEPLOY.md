# Deploy to a VPS over plain HTTP

Full stack: FastAPI backend + SvelteKit frontend + Redis, exposed on two
host ports. No reverse proxy.

## Prerequisites

- A VPS with Docker + Docker Compose v2.
- Inbound TCP open on whatever ports you choose (default `80` for the UI
  and `8000` for the API).

## One-time setup on the VPS

```bash
git clone <your-repo> options-screener
cd options-screener/app

cp .env.example .env
# edit .env and set PUBLIC_HOST to your VPS IP or hostname
```

The trained model (`backend/models/price_model.pkl`) and demo snapshot
(`backend/data/demo_snapshot.pkl`) are tracked in git, so `git clone`
brings everything you need.

## Build and start

From the `app/` directory on the VPS:

```bash
docker compose -f docker-compose.prod.yml --env-file .env build
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

Then open `http://<PUBLIC_HOST>` in your browser. The UI talks to the API
at `http://<PUBLIC_HOST>:8000`.

Verify:

```bash
docker compose -f docker-compose.prod.yml ps
curl -I http://<PUBLIC_HOST>:8000/health
```

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env build
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

Note: the API URL is baked into the frontend at build time, so changing
`PUBLIC_HOST` or `BACKEND_PORT` requires a rebuild.

## Logs

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f redis
```

## Ports

| Service  | Container port | Host port                   |
| -------- | -------------- | --------------------------- |
| frontend | 3000           | `${FRONTEND_PORT}` (def 80) |
| backend  | 8000           | `${BACKEND_PORT}` (def 8000)|
| redis    | 6379           | not exposed                 |

## Building elsewhere and pushing images

Optional - build locally, push to a registry, pull on the VPS:

```bash
# locally
docker compose -f docker-compose.prod.yml --env-file .env build
docker tag options-screener-backend:latest registry.example.com/you/options-backend:latest
docker tag options-screener-frontend:latest registry.example.com/you/options-frontend:latest
docker push registry.example.com/you/options-backend:latest
docker push registry.example.com/you/options-frontend:latest
```

Then set `BACKEND_IMAGE` / `FRONTEND_IMAGE` in the VPS `.env` to the
registry tags and:

```bash
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

## Data persistence

- `redis_data` named volume - option-chain + daily-history cache survives restarts.
- `./backend/models` bind-mounted read-only - upload the `.pkl` once.
