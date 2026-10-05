import math

import polars as pl
import tqdm
from tabulate import tabulate

from tdt4225_ex2.db_connector import DbConnector
from tdt4225_ex2.eda import get_clean_data

TRIP_COLS = [
    "TRIP_ID",
    "CALL_TYPE",
    "ORIGIN_CALL",
    "ORIGIN_STAND",
    "TAXI_ID",
    "TIMESTAMP",
    "DAY_TYPE",
    "MISSING_DATA",
]
POLY_COLS = [
    "TRIP_ID",
    "COORDINATE_NUMBER",
    "LONGITUDE",
    "LATITUDE",
]

TRIP_SQL = f"INSERT INTO porto_trips ({', '.join(TRIP_COLS)}) VALUES ({', '.join('%s' for _ in TRIP_COLS)})"
POLY_SQL = f"INSERT INTO porto_trips_polyline ({', '.join(POLY_COLS)}) VALUES ({', '.join('%s' for _ in POLY_COLS)})"


class PortoHandler:
    """Coordinate database setup for the Porto dataset."""

    def __init__(self) -> None:
        self.db_connector = DbConnector()
        self.cursor = self.db_connector.cursor
        self.connection = self.db_connector.db_connection

    def create_tables(self) -> None:
        # Always start fresh during EDA
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips_polyline")
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips")
        self.connection.commit()

        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS porto_trips (
                TRIP_ID BIGINT PRIMARY KEY,
                CALL_TYPE CHAR NOT NULL,
                ORIGIN_CALL INT,
                ORIGIN_STAND INT,
                TAXI_ID INT NOT NULL,
                TIMESTAMP DATETIME NOT NULL,
                DAY_TYPE CHAR NOT NULL,
                MISSING_DATA BOOL NOT NULL
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

    def insert_data(self, df: pl.DataFrame):
        df = df.sort("TRIP_ID")
        batch_size = 7_500

        for offset in tqdm.trange(0, df.height, batch_size):
            batch = df.slice(offset, batch_size)

            self.cursor.executemany(TRIP_SQL, batch.select(TRIP_COLS).rows())

            poly_rows = (
                batch.select("TRIP_ID", "POLYLINE")
                .explode("POLYLINE", empty_as_null=False)
                .with_columns(
                    COORDINATE_NUMBER=pl.int_range(pl.len()).over("TRIP_ID"),
                    LONGITUDE=pl.col("POLYLINE").list.get(0),
                    LATITUDE=pl.col("POLYLINE").list.get(1),
                )
                .select(POLY_COLS)
                .rows()
            )
            for i in tqdm.trange(0, len(poly_rows), batch_size, leave=False):
                self.cursor.executemany(POLY_SQL, poly_rows[i : i + batch_size])

            self.connection.commit()

    def fill_db(self) -> None:
        try:
            self.create_tables()
            self.insert_data(get_clean_data())
        finally:
            self.db_connector.close_connection()

    def task2(self):
        def subtask1():
            queries = [
                ("taxis", "SELECT COUNT(DISTINCT TAXI_ID) FROM porto_trips"),
                ("trips", "SELECT COUNT(*) FROM porto_trips"),
                ("gps points", "SELECT COUNT(*) FROM porto_trips_polyline"),
            ]
            out = []
            for name, query in queries:
                self.cursor.execute(query)
                out.append((name, self.cursor.fetchone()[0]))

            print("1.")
            print(tabulate(out, headers=("Type", "Count")))

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
            print("3. top 20 taxi based on trips:")
            print(tabulate(self.cursor.fetchall(), headers=("Taxi ID", "Trip count")))

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
            print("4.a most common call type per taxi:")
            print(
                tabulate(
                    self.cursor.fetchall(),
                    headers=("Taxi ID", "Most used call type", "Used count"),
                )
            )

            # TODO: 4b

        def subtask6():
            query = """
            SELECT DISTINCT TRIP_ID
            FROM porto_trips_polyline
            WHERE LATITUDE BETWEEN %(latitude)s - %(d_latitude)s AND %(latitude)s + %(d_latitude)s
                AND LONGITUDE BETWEEN %(longitude)s - %(d_longitude)s AND %(longitude)s + %(d_longitude)s
                AND ST_Distance_Sphere(
                        POINT(LATITUDE, LONGITUDE),
                        POINT(%(latitude)s, %(longitude)s)
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
            )

        def subtask7():
            query = """
            SELECT COUNT(*)
            FROM (
                SELECT pt.TRIP_ID, COUNT(ptp.TRIP_ID) AS trip_gps_points
                FROM porto_trips AS pt
                LEFT JOIN porto_trips_polyline AS ptp ON pt.TRIP_ID = ptp.TRIP_ID
                GROUP BY pt.TRIP_ID
                HAVING trip_gps_points < 3
            ) AS invalid_trips"""
            self.cursor.execute(query)
            print("7. invalid trip count:", self.cursor.fetchone()[0])

        def subtask8():
            query = """
            SELECT pt.TRIP_ID
            FROM porto_trips AS pt
            INNER JOIN (
                SELECT TRIP_ID, MAX(COORDINATE_NUMBER) AS max_coord_num
                FROM porto_trips_polyline
                GROUP BY TRIP_ID
            ) AS tgp ON pt.TRIP_ID = tgp.TRIP_ID
            WHERE DATE(pt.TIMESTAMP + INTERVAL tgp.max_coord_num * 15 SECOND) > DATE(pt.TIMESTAMP)
            """
            self.cursor.execute(query)
            print("8. trips that started on one day and ended on another day:")
            print(tabulate(self.cursor.fetchall(), headers=("Trip ID",)))

        for subtask in (
            subtask1,
            subtask2,
            subtask3,
            subtask4,
            subtask6,
            subtask7,
            subtask8,
        ):
            subtask()
            print()


def main() -> None:
    PortoHandler().task2()


if __name__ == "__main__":
    main()
