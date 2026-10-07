TRIP_COLS = [
    "TRIP_ID",
    "CALL_TYPE",
    "ORIGIN_CALL",
    "ORIGIN_STAND",
    "TAXI_ID",
    "TIMESTAMP",
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
DAY_TYPE_COLS = [
    "DATE",
    "DAY_TYPE",
]

TRIP_SQL = f"INSERT INTO porto_trips ({', '.join(TRIP_COLS)}) VALUES ({', '.join('%s' for _ in TRIP_COLS)})"
POLY_SQL = f"INSERT INTO porto_trips_polyline ({', '.join(POLY_COLS)}) VALUES ({', '.join('%s' for _ in POLY_COLS)})"
DAY_TYPE_SQL = f"INSERT INTO porto_day_types ({', '.join(DAY_TYPE_COLS)}) VALUES ({', '.join('%s' for _ in DAY_TYPE_COLS)})"

# Further than 200 km/h for the 15 seconds between two GPS points is a GPS error
MAX_STEP_M = 200 / 3.6 * 15
