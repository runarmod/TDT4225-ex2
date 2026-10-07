import math
import sys

import polars as pl
import tqdm
from tabulate import tabulate

from tdt4225_ex2.const import POLY_COLS, POLY_SQL, TRIP_COLS, TRIP_SQL
from tdt4225_ex2.db_connector import DbConnector
from tdt4225_ex2.eda import prepare_data


class PortoHandler:
    """Coordinate database setup for the Porto dataset."""

    def __init__(self) -> None:
        self.db_connector = DbConnector()
        self.cursor = self.db_connector.cursor
        self.connection = self.db_connector.db_connection

    def drop_tables(self) -> None:
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips_polyline")
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips")
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
                DAY_TYPE CHAR NOT NULL,
                MISSING_DATA BOOL NOT NULL,
                DISTANCE_M DOUBLE NOT NULL,
                N_POINTS INT NOT NULL
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

    def insert_data(self, trips: pl.DataFrame, polyline: pl.DataFrame):
        batch_size = 50_000

        # The data is already deduplicated and every polyline row belongs to a
        # trip in the same dataframe, so the per-row checks are skipped for speed
        self.cursor.execute("SET unique_checks = 0")
        self.cursor.execute("SET foreign_key_checks = 0")
        try:
            # Trips first, since the polyline rows reference them
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

    def task2(self):
        def subtask1():
            query = "SELECT COUNT(DISTINCT TAXI_ID), COUNT(*), SUM(N_POINTS) FROM porto_trips"
            self.cursor.execute(query)
            print(
                "1.",
                tabulate(
                    self.cursor.fetchall(), headers=("Taxis", "Trips", "GPS points")
                ),
                sep="\n",
            )

        def subtask2():
            query = (
                "SELECT AVG(trip_count)"
                "FROM (SELECT TAXI_ID, COUNT(*) AS trip_count FROM porto_trips GROUP BY TAXI_ID) AS trip_count"
            )
            self.cursor.execute(query)
            print("2. average number of trips per taxi:", self.cursor.fetchone()[0])

        def subtask3():
            query = (
                "SELECT TAXI_ID, COUNT(*) AS trip_count "
                "FROM porto_trips "
                "GROUP BY TAXI_ID "
                "ORDER BY trip_count DESC "
                "LIMIT 20"
            )
            self.cursor.execute(query)
            print(
                "3. top 20 taxi based on trips:",
                tabulate(self.cursor.fetchall(), headers=("Taxi ID", "Trip count")),
                sep="\n",
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
            print(
                "4.a most common call type per taxi:",
                tabulate(
                    self.cursor.fetchall(),
                    headers=("Taxi ID", "Most used call type", "Used count"),
                ),
                sep="\n",
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
            print(
                "4.b average trip duration and distance, and share of trips "
                "starting in each time band, per call type:",
                tabulate(
                    self.cursor.fetchall(),
                    headers=(
                        "Call type",
                        "Avg duration [s]",
                        "Avg distance [m]",
                        "00-06 [%]",
                        "06-12 [%]",
                        "12-18 [%]",
                        "18-24 [%]",
                    ),
                ),
                sep="\n",
            )

        def subtask5():
            query = """
                SELECT TAXI_ID, SUM(N_POINTS) * 15 / 60 / 60 AS driven_hours, SUM(DISTANCE_M) / 1000
                FROM porto_trips
                GROUP BY TAXI_ID
                ORDER BY driven_hours DESC
            """
            self.cursor.execute(query)
            print(
                "5. most total hours and distance:",
                tabulate(
                    self.cursor.fetchall(),
                    headers=("Taxi ID", "Total hours [h]", "Total distance [km]"),
                ),
                sep="\n",
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
            print(
                "6. trips within 100 meters of Porto City Hall:",
                tabulate(self.cursor.fetchall(), headers=("Trip ID",)),
                sep="\n",
            )

        def subtask7():
            query = """
                SELECT COUNT(*)
                FROM porto_trips
                WHERE N_POINTS < 3
                """
            self.cursor.execute(query)
            print("7. invalid trip count:", self.cursor.fetchone()[0])

        def subtask8():
            query = """
            SELECT TRIP_ID
            FROM porto_trips
            WHERE DATE(TIMESTAMP + INTERVAL (N_POINTS - 1) * 15 SECOND) = DATE(TIMESTAMP) + INTERVAL 1 DAY
            """
            self.cursor.execute(query)
            print(
                "8. trips that started on one day and ended on another day:",
                tabulate(self.cursor.fetchall(), headers=("Trip ID",)),
                sep="\n",
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
            print(
                "9. circular trips (only for valid trips):",
                tabulate(self.cursor.fetchall(), headers=("Trip ID",)),
                sep="\n",
            )

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
            print(
                "10. top 20 taxis with the highest average idle time:",
                tabulate(
                    self.cursor.fetchall(),
                    headers=("Taxi ID", "Average idle time [h]", "Gaps"),
                ),
                sep="\n",
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
    try:
        handler.task2()
    finally:
        handler.db_connector.close_connection()


def fill_db() -> None:
    if "--force" not in sys.argv[1:]:
        answer = input(
            "This drops and rebuilds porto_trips and porto_trips_polyline. Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    PortoHandler().fill_db()


if __name__ == "__main__":
    task2()
