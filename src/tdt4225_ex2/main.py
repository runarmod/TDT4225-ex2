import polars as pl
import tqdm

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

    def run(self) -> None:
        try:
            self.create_tables()
            self.insert_data(get_clean_data())
        finally:
            self.db_connector.close_connection()


def main() -> None:
    PortoHandler().run()


if __name__ == "__main__":
    main()
