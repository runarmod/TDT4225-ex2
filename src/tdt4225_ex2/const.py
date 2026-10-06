TRIP_COLS = [
    "TRIP_ID",
    "CALL_TYPE",
    "ORIGIN_CALL",
    "ORIGIN_STAND",
    "TAXI_ID",
    "TIMESTAMP",
    "DAY_TYPE",
    "MISSING_DATA",
    "DISTANCE_M",
    "N_POINTS",
]
POLY_COLS = [
    "TRIP_ID",
    "COORDINATE_NUMBER",
    "LONGITUDE",
    "LATITUDE",
]

TRIP_SQL = f"INSERT INTO porto_trips ({', '.join(TRIP_COLS)}) VALUES ({', '.join('%s' for _ in TRIP_COLS)})"
POLY_SQL = f"INSERT INTO porto_trips_polyline ({', '.join(POLY_COLS)}) VALUES ({', '.join('%s' for _ in POLY_COLS)})"
