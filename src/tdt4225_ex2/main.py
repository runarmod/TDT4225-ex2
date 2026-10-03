import itertools

import polars as pl
import tqdm

from tdt4225_ex2.db_connector import DbConnector
from tdt4225_ex2.eda import get_clean_data


class PortoHandler:
    """Coordinate database setup for the Porto dataset."""

    def __init__(self) -> None:
        self.db_connector = DbConnector()
        self.cursor = self.db_connector.cursor
        self.connection = self.db_connector.db_connection

    def create_tables(self) -> None:
        # Always start fresh during EDA
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips")
        self.cursor.execute("DROP TABLE IF EXISTS porto_trips_polyline")
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
        batch_size = 10_000
        for batch in tqdm.tqdm(
            itertools.batched(df.iter_rows(named=True), batch_size),
            total=len(df) // batch_size + 1,
        ):
            cols = [
                "TRIP_ID",
                "CALL_TYPE",
                "ORIGIN_CALL",
                "ORIGIN_STAND",
                "TAXI_ID",
                "TIMESTAMP",
                "DAY_TYPE",
                "MISSING_DATA",
            ]
            self.cursor.executemany(
                f"INSERT INTO porto_trips ({', '.join(cols)}) VALUES ({', '.join('%s' for _ in cols)})",
                [[row[k] for k in cols] for row in batch],
            )

            cols = [
                "TRIP_ID",
                "COORDINATE_NUMBER",
                "LONGITUDE",
                "LATITUDE",
            ]
            insert_rows = [
                (row["TRIP_ID"], i, *coord)
                for row in batch
                for i, coord in enumerate(row["POLYLINE"])
            ]
            self.cursor.executemany(
                f"INSERT INTO porto_trips_polyline ({', '.join(cols)}) VALUES ({', '.join('%s' for _ in cols)})",
                insert_rows,
            )

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
