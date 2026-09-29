import polars as pl

from tdt4225_ex2.db_connector import DbConnector


class PortoHandler:
    """Coordinate database setup for the Porto dataset."""

    def __init__(self) -> None:
        self.db_connector = DbConnector()
        self.cursor = self.db_connector.cursor
        self.connection = self.db_connector.db_connection

    def create_tables(self) -> None:
        self.cursor.execute("DROP TABLE IF EXISTS porto")  # Always start fresh during EDA
        self.connection.commit()

        # TODO: split into multiple tables?
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS porto (
                TRIP_ID BIGINT PRIMARY KEY,
                CALL_TYPE CHAR NOT NULL,
                ORIGIN_CALL INT,
                ORIGIN_STAND INT,
                TAXI_ID INT NOT NULL,
                TIMESTAMP DATETIME NOT NULL,
                DAY_TYPE CHAR NOT NULL,
                MISSING_DATA BOOL NOT NULL,
                POLYLINE TEXT
            )"""
        )
        self.connection.commit()

    def insert_data(self, df: pl.DataFrame):
        raise NotImplementedError

    def run(self) -> None:
        try:
            self.create_tables()
            self.insert_data(pl.DataFrame())
        finally:
            self.db_connector.close_connection()


def main() -> None:
    PortoHandler().run()


if __name__ == "__main__":
    main()
