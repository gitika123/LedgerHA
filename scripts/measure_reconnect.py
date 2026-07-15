#!/usr/bin/env python3
"""
Timed reconnect probe for LedgerHA Multi-AZ failover drills.

Usage (during / right after RDS reboot-with-failover):
  export DATABASE_URL='postgresql+psycopg://user:pass@HOST:5432/ledgerha'
  export ORDER_ID='<uuid of a committed order>'
  python scripts/measure_reconnect.py

Records wall-clock seconds until PK read succeeds again. Paste that number
into the resume ONLY after you measure it yourself.
"""

from __future__ import annotations

import os
import sys
import time

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("Install app deps first: pip install -r app/requirements.txt", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    order_id = os.environ.get("ORDER_ID")
    if not url or not order_id:
        print("Set DATABASE_URL and ORDER_ID", file=sys.stderr)
        sys.exit(2)

    engine = create_engine(url, pool_pre_ping=True)
    timeout_s = float(os.environ.get("FAILOVER_TIMEOUT_S", "180"))
    interval_s = float(os.environ.get("POLL_INTERVAL_S", "1.0"))

    start = time.monotonic()
    deadline = start + timeout_s
    attempts = 0
    last_err = None

    while time.monotonic() < deadline:
        attempts += 1
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT id, status FROM orders WHERE id = :id"),
                    {"id": order_id},
                ).fetchone()
            if row:
                elapsed = time.monotonic() - start
                print(f"OK id={row[0]} status={row[1]}")
                print(f"reconnect_seconds={elapsed:.1f}")
                print(f"attempts={attempts}")
                return
            last_err = "row missing"
        except Exception as exc:  # noqa: BLE001 - drill script should keep polling
            last_err = str(exc)
        time.sleep(interval_s)

    print(f"FAIL after {timeout_s}s attempts={attempts} last_err={last_err}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
