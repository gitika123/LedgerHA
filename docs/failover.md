# Failover drill for LedgerHA (RDS Multi-AZ)

## Goal

Prove that committed order rows survive writer loss and that the application can reconnect to the promoted standby.

## Steps

1. Write a known order via `POST /orders` and note the `id`.
2. In AWS Console / CLI, reboot the RDS instance **with failover** (Multi-AZ must be enabled).
3. While failover runs, poll `GET /orders/{id}` and `/health`.
4. Record:
   - Approximate seconds until the writer endpoint accepts connections again
   - Whether the known order is still readable (should be — Multi-AZ is for durability/HA of the primary)
5. Recycle the app DB pool if needed (`pool_pre_ping=True` already reduces stale connections).
6. Run the timed probe and save the printed `reconnect_seconds`:

```bash
export DATABASE_URL='...'
export ORDER_ID='...'
python scripts/measure_reconnect.py
```

Only put that number on a resume after this script prints it for your account/region.

## Notes for interviews

- Multi-AZ standby is **not** a read replica you query; the app keeps using the writer endpoint.
- Contrast with Aurora reader endpoints if asked about read scale-out.
- Always destroy demo stacks (`terraform destroy`) — Multi-AZ is billed while running.
