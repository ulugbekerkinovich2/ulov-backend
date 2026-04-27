# Monitoring

Self-hosted **Prometheus + Grafana + Alertmanager** stack for the ULOV+
backend. Backend runs under PM2 on the host (port 8499); the stack reaches
it through `host.docker.internal` (mapped via `extra_hosts`).

## Layout

```
docker-compose.monitoring.yml      # 3-service compose
monitoring/
├── prometheus.yml                 # scrape config
├── alertmanager.yml               # Telegram fan-out + inhibit rules
├── rules/
│   └── api-alerts.yml             # ApiDown, HighErrorRate, P95, Memory, NoTraffic
└── grafana/
    ├── provisioning/
    │   ├── datasources/prometheus.yml
    │   └── dashboards/dashboard.yml
    └── dashboards/
        └── ulov-api.json          # 10-panel default dashboard
nginx/
├── grafana.misterdev.uz.conf      # public Grafana vhost
└── ulov-api.misterdev.uz.conf     # API vhost with /metrics allowlist
```

## First-time deploy (prod)

```bash
cd /var/www/workers/ulov/backend
git pull

# 1. Secrets (.env)
echo "GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 24)" >> .env
# Optional Telegram alerts
echo "TELEGRAM_BOT_TOKEN=…" >> .env
echo "TELEGRAM_CHAT_ID=…"  >> .env
echo "GRAFANA_ROOT_URL=https://grafana.misterdev.uz" >> .env

# 2. Boot the stack
docker compose -f docker-compose.monitoring.yml up -d
docker compose -f docker-compose.monitoring.yml ps   # all 3 healthy

# 3. Public vhost for Grafana
sudo cp nginx/grafana.misterdev.uz.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/grafana.misterdev.uz \
          /etc/nginx/sites-enabled/
sudo certbot --nginx -d grafana.misterdev.uz
sudo nginx -t && sudo systemctl reload nginx

# 4. Lock down /metrics
sudo cp nginx/ulov-api.misterdev.uz.conf /etc/nginx/sites-available/
sudo nginx -t && sudo systemctl reload nginx
```

## Verifying

```bash
# Backend metrics reachable on the loopback
curl -s http://127.0.0.1:8499/metrics | head -10

# Prometheus scrape targets
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job:.labels.job, health:.health}'

# Sample query
curl -s 'http://localhost:9090/api/v1/query?query=up{job="ulov-api"}' | jq

# Grafana
open https://grafana.misterdev.uz   # login: admin / $GRAFANA_ADMIN_PASSWORD
```

## Reload after edits

```bash
# Edit prometheus.yml or rules/*.yml then:
curl -X POST http://localhost:9090/-/reload
# Or restart the container:
docker compose -f docker-compose.monitoring.yml restart prometheus
```

## Retention

Prometheus retains 15 days / 5 GB by default (whichever first). Adjust the
`--storage.tsdb.retention.*` flags in `docker-compose.monitoring.yml`.

## Adding new alerts

Drop a new YAML file under `monitoring/rules/`; Prometheus picks it up via
`rule_files: /etc/prometheus/rules/*.yml`. After saving:

```bash
docker exec ulov-prometheus promtool check rules /etc/prometheus/rules/*.yml
curl -X POST http://localhost:9090/-/reload
```

## Custom business metrics (future)

Add `app/core/metrics.py`:

```python
from prometheus_client import Counter, Histogram

service_transitions_total = Counter(
    "service_transitions_total",
    "Service state transitions",
    ["from_status", "to_status"],
)
otp_send_total = Counter(
    "otp_send_total",
    "OTP send attempts",
    ["outcome"],
)
```

Then bump the counter where the event happens (e.g. in
`app/modules/services/service.py` after a successful transition). The
instrumentator already exposes `/metrics`; Prometheus picks them up
automatically on the next scrape.
