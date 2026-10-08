import math
import sys

import polars as pl
import tqdm
from tabulate import tabulate

from tdt4225_ex2.const import (
    DAY_TYPE_COLS,
    DAY_TYPE_SQL,
    POLY_COLS,
    POLY_SQL,
    TRIP_COLS,
    TRIP_SQL,
)
from tdt4225_ex2.data_cleaning import prepare_data
from tdt4225_ex2.db_connector import DbConnector


class PortoHandler:
    """Coordinate database setup for the Porto dataset."""

    def __init__(self) -> None:
        self.db_connector = DbConnector()
        self.cursor = self.db_connector.cursor
        self.connection = self.db_connector.db_connection
        self.limit = False

    def drop_tables(self) -> None:
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips_polyline")
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips")
        self.cursor.execute("DROP TABLE IF EXISTS porto_day_types")
        self.connection.commit()

    def create_tables(self) -> None:
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS porto_trips (
                TRIP_ID BIGINT PRIMARY KEY,
                CALL_TYPE CHAR NOT NULL,
                ORIGIN_CALL INT,
                ORIGIN_STAND INT,
                TAXI_ID INT NOT NULL,
                TIMESTAMP DATETIME NOT NULL,
                DISTANCE_M DOUBLE NOT NULL,
                N_POINTS INT NOT NULL
            )"""
        )
        # The day type is the same for all trips on a date, so it is stored once
        # per date and looked up with DATE(porto_trips.TIMESTAMP)
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS porto_day_types (
                DATE DATE PRIMARY KEY,
                DAY_TYPE CHAR NOT NULL
            )"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS porto_trips_polyline (
                TRIP_ID BIGINT NOT NULL,
                COORDINATE_NUMBER INT NOT NULL,
                LONGITUDE DOUBLE NOT NULL,
                LATITUDE DOUBLE NOT NULL,
                PRIMARY KEY (TRIP_ID, COORDINATE_NUMBER),
                CONSTRAINT FOREIGN KEY (TRIP_ID) REFERENCES porto_trips(TRIP_ID)
                    ON DELETE CASCADE ON UPDATE CASCADE
            )"""
        )
        self.connection.commit()

    def create_indexes(self) -> None:
        # Created after the inserts, as building it once is cheaper than
        # maintaining it for every inserted row
        self.cursor.execute(
            "CREATE INDEX idx_lat_lon ON porto_trips_polyline (LATITUDE, LONGITUDE)"
        )
        self.connection.commit()

    def insert_data(
        self, trips: pl.DataFrame, polyline: pl.DataFrame, day_types: pl.DataFrame
    ):
        batch_size = 50_000

        # The data is already deduplicated and every polyline row belongs to a
        # trip in the same dataframe, so the per-row checks are skipped for speed
        self.cursor.execute("SET unique_checks = 0")
        self.cursor.execute("SET foreign_key_checks = 0")
        try:
            # Day types first, so a date with several day types fails on the
            # primary key before the large tables are filled
            self.cursor.executemany(
                DAY_TYPE_SQL, day_types.select(DAY_TYPE_COLS).rows()
            )
            self.connection.commit()

            # Trips before the polyline rows, since the polyline rows reference them
            trips = trips.sort("TRIP_ID")
            for offset in tqdm.trange(0, trips.height, batch_size, desc="porto_trips"):
                batch = trips.slice(offset, batch_size)
                self.cursor.executemany(TRIP_SQL, batch.select(TRIP_COLS).rows())
                self.connection.commit()

            polyline = polyline.sort("TRIP_ID", "COORDINATE_NUMBER")
            for offset in tqdm.trange(
                0, polyline.height, batch_size, desc="porto_trips_polyline"
            ):
                batch = polyline.slice(offset, batch_size)
                self.cursor.executemany(POLY_SQL, batch.select(POLY_COLS).rows())
                self.connection.commit()
        finally:
            self.cursor.execute("SET unique_checks = 1")
            self.cursor.execute("SET foreign_key_checks = 1")

    def fill_db(self) -> None:
        try:
            self.drop_tables()
            self.create_tables()
            self.insert_data(*prepare_data())
            self.create_indexes()
        finally:
            self.db_connector.close_connection()

    def show_output(self, title: str, headers: tuple[str, ...], intfmt=""):
        ROW_LIMIT = 20
        TAIL_ROWS = 3

        rows = self.cursor.fetchall()
        total = len(rows)
        truncated = self.limit and total > ROW_LIMIT
        if truncated:
            head = ROW_LIMIT - TAIL_ROWS
            # A row of None is printed as missingval and marks the cut
            rows = [*rows[:head], (None,) * len(headers), *rows[-TAIL_ROWS:]]
        print(title)
        print(
            tabulate(
                rows,
                headers=headers,
                tablefmt="rounded_outline",
                floatfmt=",.2f",
                intfmt=intfmt,
                missingval="...",
                numalign="right",
            )
        )
        if truncated:
            print(f"Showing first {head} and last {TAIL_ROWS} of {total:,} rows")
        elif total > ROW_LIMIT:
            print(f"{total:,} rows")

    def task2(self):
        def subtask1():
            query = "SELECT COUNT(DISTINCT TAXI_ID), COUNT(*), CAST(SUM(N_POINTS) AS SIGNED) FROM porto_trips"
            self.cursor.execute(query)
            self.show_output(
                "1. Number of taxis, trips and GPS points:",
                ("Taxis", "Trips", "GPS points"),
                intfmt=",",
            )

        def subtask2():
            query = """
                SELECT AVG(trip_count)
                FROM (
                    SELECT TAXI_ID, COUNT(*) AS trip_count
                    FROM porto_trips
                    GROUP BY TAXI_ID
                ) AS taxi_trip_counts
            """

            self.cursor.execute(query)
            self.show_output(
                "2. Average number of trips per taxi:",
                ("Average number of trips per taxi",),
            )

        def subtask3():
            query = (
                "SELECT TAXI_ID, COUNT(*) AS trip_count "
                "FROM porto_trips "
                "GROUP BY TAXI_ID "
                "ORDER BY trip_count DESC "
                "LIMIT 20"
            )
            self.cursor.execute(query)
            self.show_output(
                "3. Top 20 taxis by number of trips:", ("Taxi ID", "Trip count")
            )

        def subtask4():
            query = """
                SELECT TAXI_ID, CALL_TYPE, trip_count
                FROM (
                    SELECT TAXI_ID, CALL_TYPE, COUNT(*) AS trip_count, ROW_NUMBER()
                    OVER (PARTITION BY TAXI_ID ORDER BY COUNT(*) DESC, CALL_TYPE) AS rn
                    FROM porto_trips GROUP BY TAXI_ID, CALL_TYPE
                ) ranked
                WHERE rn = 1"""
            self.cursor.execute(query)
            self.show_output(
                "4.a Most used call type per taxi:",
                ("Taxi ID", "Call type", "Trip count"),
            )
            print()

            query = """
                SELECT
                    CALL_TYPE,
                    AVG(N_POINTS) * 15,
                    AVG(DISTANCE_M),
                    AVG(HOUR(TIMESTAMP) < 6) * 100,
                    AVG(HOUR(TIMESTAMP) BETWEEN 6 AND 11) * 100,
                    AVG(HOUR(TIMESTAMP) BETWEEN 12 AND 17) * 100,
                    AVG(HOUR(TIMESTAMP) >= 18) * 100
                FROM porto_trips
                GROUP BY CALL_TYPE
                ORDER BY CALL_TYPE
                """
            self.cursor.execute(query)
            self.show_output(
                "4.b Average trip duration and distance, and share of trips "
                "starting in each time band, per call type:",
                (
                    "Call type",
                    "Avg duration [s]",
                    "Avg distance [m]",
                    "00-06 [%]",
                    "06-12 [%]",
                    "12-18 [%]",
                    "18-24 [%]",
                ),
            )

        def subtask5():
            query = """
                SELECT TAXI_ID, SUM(N_POINTS) * 15 / 60 / 60 AS driven_hours, SUM(DISTANCE_M) / 1000
                FROM porto_trips
                GROUP BY TAXI_ID
                ORDER BY driven_hours DESC
            """
            self.cursor.execute(query)
            self.show_output(
                "5. Taxis by total hours and distance driven:",
                ("Taxi ID", "Total hours [h]", "Total distance [km]"),
            )

        def subtask6():
            query = """
            SELECT DISTINCT TRIP_ID
            FROM porto_trips_polyline
            WHERE LATITUDE BETWEEN %(latitude)s - %(d_latitude)s AND %(latitude)s + %(d_latitude)s
                AND LONGITUDE BETWEEN %(longitude)s - %(d_longitude)s AND %(longitude)s + %(d_longitude)s
                AND ST_Distance_Sphere(
                        POINT(LONGITUDE, LATITUDE),
                        POINT(%(longitude)s, %(latitude)s)
                    ) <= %(distance)s"""

            earth_radius = 6378137  # meters
            meters_per_degree = earth_radius * math.pi / 180

            distance = 100  # meters

            latitude = 41.15794
            longitude = -8.62911

            d_latitude = distance / meters_per_degree
            d_longitude = distance / (
                meters_per_degree * math.cos(math.radians(latitude))
            )
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "d_latitude": d_latitude,
                "d_longitude": d_longitude,
                "distance": distance,
            }
            self.cursor.execute(query, params)
            self.show_output(
                "6. Trips within 100 meters of Porto City Hall:", ("Trip ID",)
            )

        def subtask7():
            query = """
                SELECT COUNT(*)
                FROM porto_trips
                WHERE N_POINTS < 3
                """
            self.cursor.execute(query)
            self.show_output(
                "7. Invalid trips (fewer than 3 GPS points):", ("Invalid trips",)
            )

        def subtask8():
            query = """
            SELECT TRIP_ID
            FROM porto_trips
            WHERE DATE(TIMESTAMP + INTERVAL (N_POINTS - 1) * 15 SECOND) = DATE(TIMESTAMP) + INTERVAL 1 DAY
            """
            self.cursor.execute(query)
            self.show_output(
                "8. Trips that started on one day and ended on the next:", ("Trip ID",)
            )

        def subtask9():
            query = """
                SELECT pt.TRIP_ID
                FROM porto_trips as pt
                    INNER JOIN porto_trips_polyline as s
                        ON pt.TRIP_ID = s.TRIP_ID AND s.COORDINATE_NUMBER = 0
                    INNER JOIN porto_trips_polyline as e
                        ON pt.TRIP_ID = e.TRIP_ID AND e.COORDINATE_NUMBER = pt.N_POINTS - 1
                WHERE pt.N_POINTS > 2
                    AND ST_Distance_Sphere(
                        POINT(s.LONGITUDE, s.LATITUDE),
                        POINT(e.LONGITUDE, e.LATITUDE)
                    ) <= 50
                """
            self.cursor.execute(query)
            self.show_output("9. Circular trips (valid trips only):", ("Trip ID",))

        def subtask10():
            # Naive solution:
            # For each taxi, find all its trips. Find the time between each of its trips,
            # and find the average time between.
            #
            # Optimization:
            # For each taxi, find the start time of the first trip, end time of last trip,
            # and total driving time. Average idle time is:
            # (last trip end - first trip start - total driving time) / (total trips - 1)
            # This way we do not have to touch the huge porto_trips_polyline table :)

            query = """
                SELECT
                    TAXI_ID,
                    (
                        TIMESTAMPDIFF(
                            SECOND,
                            MIN(TIMESTAMP),
                            MAX(TIMESTAMP + INTERVAL N_POINTS * 15 SECOND)
                        ) - SUM(N_POINTS * 15)
                    ) / (COUNT(*) - 1) / 60 / 60 AS avg_idle_hours,
                    COUNT(*) - 1 AS gap_count
                FROM porto_trips
                GROUP BY TAXI_ID
                HAVING COUNT(*) > 1
                ORDER BY avg_idle_hours DESC
                LIMIT 20
                """
            self.cursor.execute(query)
            self.show_output(
                "10. Top 20 taxis by average idle time between trips:",
                ("Taxi ID", "Average idle time [h]", "Gaps"),
            )

        for subtask in (
            subtask1,
            subtask2,
            subtask3,
            subtask4,
            subtask5,
            subtask6,
            subtask7,
            subtask8,
            subtask9,
            subtask10,
        ):
            subtask()
            print()


def task2() -> None:
    handler = PortoHandler()
    handler.limit = "--limit" in sys.argv[1:]
    try:
        handler.task2()
    finally:
        handler.db_connector.close_connection()


def fill_db() -> None:
    if "--force" not in sys.argv[1:]:
        answer = input(
            "This drops and rebuilds porto_trips, porto_trips_polyline and porto_day_types. Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    PortoHandler().fill_db()


if __name__ == "__main__":
    task2()
