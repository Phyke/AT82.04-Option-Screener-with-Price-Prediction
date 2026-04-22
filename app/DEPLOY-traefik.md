# Deploy to Hostinger VPS with Traefik + Let's Encrypt

Single hostname, one TLS cert, everything served under
`https://<your-hostname>`:

- `https://<host>/` -> SvelteKit frontend
- `https://<host>/api/*` -> FastAPI backend (Traefik strips `/api`)

Traefik runs as its own always-on compose. The app stack joins Traefik's
Docker network and Traefik auto-discovers it via labels.

## 0. Hostinger prerequisites

1. Make sure ports `80` and `443` are open in the Hostinger firewall
   (they usually are by default on VPS plans).
2. Confirm the provided hostname (the `${DOMAIN}` you set in `.env`)
   resolves to your VPS public IP:

   ```bash
   dig +short "$DOMAIN"
   # -> should print the same IP as `curl ifconfig.me` on the VPS
   ```

3. Docker + Docker Compose v2 installed.

## 1. Create the shared Traefik network (once)

Both composes reference an external network called `proxy`. Create it:

```bash
docker network create proxy
```

## 2. Start Traefik (always-on)

From the `app/` directory:

```bash
cd ~/options-screener/app      # wherever you cloned the repo
cp .env.traefik.example .env   # edit DOMAIN and ACME_EMAIL

docker compose -f docker-compose.traefik.yml --env-file .env up -d
docker compose -f docker-compose.traefik.yml logs -f traefik
```

You should see Traefik start listening on `:80` and `:443`. Ctrl-C out of
the logs once it looks healthy.

Traefik now:

- auto-discovers any container with `traefik.enable=true` on the `proxy` network,
- auto-redirects HTTP to HTTPS,
- issues Let's Encrypt certs via the HTTP-01 challenge and stores them in
  a persistent Docker volume (`traefik_letsencrypt`). Certs survive
  container recreation.

## 3. Upload the trained model

The `.pkl` isn't in git. From your local machine:

```bash
scp backend/models/price_model.pkl \
    user@"$DOMAIN":~/options-screener/app/backend/models/
```

## 4. Build and start the app stack

Back on the VPS, in `app/`:

```bash
docker compose -f docker-compose.prod.traefik.yml --env-file .env build
docker compose -f docker-compose.prod.traefik.yml --env-file .env up -d
```

Wait ~30s for Let's Encrypt to issue the cert, then open
`https://<your-DOMAIN>` in a browser.

Verify the API too:

```bash
curl -sI "https://${DOMAIN}/api/health"
# -> HTTP/2 200
```

## Updating

```bash
git pull
docker compose -f docker-compose.prod.traefik.yml --env-file .env build
docker compose -f docker-compose.prod.traefik.yml --env-file .env up -d
```

The API URL (`https://<DOMAIN>/api`) is baked into the frontend at build
time, so changing `DOMAIN` requires a rebuild.

## Logs

```bash
# Traefik
docker compose -f docker-compose.traefik.yml logs -f

# App
docker compose -f docker-compose.prod.traefik.yml logs -f backend
docker compose -f docker-compose.prod.traefik.yml logs -f frontend
docker compose -f docker-compose.prod.traefik.yml logs -f redis
```

## Tearing down the app (Traefik keeps running)

```bash
docker compose -f docker-compose.prod.traefik.yml --env-file .env down
```

## Stopping Traefik too

```bash
docker compose -f docker-compose.traefik.yml --env-file .env down
# Cert volume (traefik_letsencrypt) is kept. Add -v to wipe it.
```

## Troubleshooting

**Cert not issuing / stuck on self-signed**
Check Traefik logs: `docker compose -f docker-compose.traefik.yml logs traefik`.
Common causes:
- Port `80` blocked from the public internet (HTTP-01 needs it).
- DNS for `${DOMAIN}` not pointing at the VPS yet (propagation).
- CAA record on the parent domain restricting Let's Encrypt. Check with
  `dig CAA <parent-domain>` - if a restrictive policy exists, you'll
  need a different hostname.

**404 on `/api/*`**
Traefik routes are label-based. Confirm the app came up on the `proxy`
network:
```bash
docker compose -f docker-compose.prod.traefik.yml ps
docker inspect app-backend-1 --format '{{json .NetworkSettings.Networks}}' | jq
```

**CORS errors**
Since frontend + API share an origin, you shouldn't see CORS errors. If
you do, it means the frontend was built with the wrong `VITE_API_URL` -
rebuild after fixing `DOMAIN` in `.env`.

## File layout

```
app/
├── docker-compose.traefik.yml         # Traefik itself (always on)
├── docker-compose.prod.traefik.yml    # App stack (this guide)
├── .env.traefik.example
├── .env                                # your copy (gitignored)
├── backend/
└── frontend/
```
