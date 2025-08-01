#ingest.py
from psycopg2.extras import execute_batch
from .models import DroneBatch

def ingest_drone_batch(cur, conn, batch: DroneBatch):
    rows = [
        (
            batch.drone_id,
            point.ts,
            f"SRID=4326;POINT({point.lon} {point.lat})",
            point.alt,
            point.agl,
            point.heading
        )
        for point in batch.data
    ]

    execute_batch(cur, """
        INSERT INTO gps_trace (drone_id, ts, location, altitude_meters, agl_meters, heading_deg)
        VALUES (%s, %s, ST_GeogFromText(%s), %s, %s, %s)
    """, rows)

    conn.commit()
    return len(rows)
