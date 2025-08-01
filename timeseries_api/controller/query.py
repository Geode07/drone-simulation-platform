# query.py
from datetime import timedelta
from fastapi import HTTPException

def parse_interval(interval_str: str) -> timedelta:
    unit_multipliers = {
        "second": 1,
        "seconds": 1,
        "minute": 60,
        "minutes": 60
    }

    try:
        num, unit = interval_str.strip().split()
        return timedelta(seconds=int(num) * unit_multipliers[unit.lower()])
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid interval format: {interval_str}")

async def get_resampled_trace(conn, drone_id: str, interval_td: timedelta):
    rows = await conn.fetch("""
        SELECT time_bucket($1, ts) AS bucket,
               AVG(ST_Y(location::geometry)) AS lat,
               AVG(ST_X(location::geometry)) AS lon,
               AVG(altitude_meters) AS alt,
               AVG(agl_meters) AS agl,
               AVG(heading_deg) AS heading
        FROM gps_trace
        WHERE drone_id = $2
        GROUP BY bucket
        ORDER BY bucket
    """, interval_td, drone_id)

    return [
        {
            "bucket": row["bucket"].isoformat(),
            "lat": row["lat"],
            "lon": row["lon"],
            "alt": row["alt"],
            "agl": row["agl"],
            "heading": row["heading"]
        }
        for row in rows
    ]

async def get_first_point(conn, drone_id: str):
    row = await conn.fetchrow("""
        SELECT ts, ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lon
        FROM gps_trace
        WHERE drone_id = $1
        ORDER BY ts ASC
        LIMIT 1
    """, drone_id)

    if not row:
        return None

    return {
        "timestamp": row["ts"].isoformat(),
        "lat": row["lat"],
        "lon": row["lon"]
    }

async def get_all_trace(conn, drone_id: str):
    rows = await conn.fetch("""
        SELECT ts, ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lon,
               altitude_meters AS alt, agl_meters AS agl, heading_deg AS heading
        FROM gps_trace
        WHERE drone_id = $1
        ORDER BY ts ASC
    """, drone_id)

    return [
        {
            "timestamp": row["ts"].isoformat(),
            "lat": row["lat"],
            "lon": row["lon"],
            "alt": row["alt"],
            "agl": row["agl"],
            "heading": row["heading"]
        }
        for row in rows
    ]

async def get_latest_position(conn, drone_id: str) -> dict:
    row = await conn.fetchrow("""
        SELECT
            ts,
            ST_Y(location::geography) AS lat,
            ST_X(location::geography) AS lon,
            altitude_meters AS alt,
            agl_meters AS agl,
            heading_deg AS heading
        FROM gps_trace
        WHERE drone_id = $1
        ORDER BY ts DESC
        LIMIT 1
    """, drone_id)

    return {
        "timestamp": row["ts"].isoformat(),
        "lat": row["lat"],
        "lon": row["lon"],
        "alt": row["alt"],
        "agl": row["agl"],
        "heading": row["heading"]
    } if row else {}

