from pathlib import Path

import numpy as np
import polars as pl
from haversine import Unit, haversine_vector

from tdt4225_ex2.const import DAY_TYPE_COLS, POLY_COLS, TRIP_COLS


def remove_invalid_trips(df: pl.DataFrame) -> pl.DataFrame:
    start_row_count = len(df)
    df = df.filter(pl.col("POLYLINE").list.len() >= 3)
    end_row_count = len(df)
    print(f"2.7: Number of invalid trips: {start_row_count - end_row_count}")
    return df


def verify_data(df: pl.DataFrame) -> None:
    # Verify CALL_TYPE follows rules
    assert df.select(pl.col("CALL_TYPE").str.contains(r"^[ABC]$").all()).item(), (
        "All day types should be A B or C"
    )

    # Verify ORIGIN_CALL follows rules
    a = pl.col("ORIGIN_CALL").is_not_null()
    b = pl.col("CALL_TYPE") == "A"
    assert df.select((~a | b).all()).item(), (
        "ORIGIN_CALL should only have value if CALL_TYPE is A"
    )

    # Verify ORIGIN_STAND follows rules
    a = pl.col("ORIGIN_STAND").is_not_null()
    b = pl.col("CALL_TYPE") == "B"
    assert df.select((~a | b).all()).item(), (
        "ORIGIN_STAND should only have value if CALL_TYPE is B"
    )


def get_data(verify: bool = False) -> pl.DataFrame:
    porto_csv = Path(__file__).resolve().parents[2] / "porto.csv"
    df = (
        pl.read_csv(porto_csv)
        .with_columns(
            pl.col(pl.String).replace(
                "", None
            ),  # Replace empty string with explicit null
            pl.from_epoch("TIMESTAMP", time_unit="s"),  # Unix time to timestamp
        )
        .with_columns(
            pl.col("ORIGIN_CALL", "ORIGIN_STAND").cast(pl.Int64),
            pl.col("POLYLINE").str.json_decode(pl.List(pl.List(pl.Float64))),
        )
    )

    if verify:
        verify_data(df)

    return df


def prepare_data() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    data = get_data()

    # df = remove_invalid_trips(df)  # Task 2.7 (Not allowed apparently!)

    data = data.unique()  # Remove duplicated lines (found during EDA)
    data = data.unique(
        subset=["TRIP_ID"], keep="first"
    )  # Remove lines with duplicated primary key (TODO: figure out some better way)

    # One row per GPS point, in the same order as in the polyline
    polyline = (
        data.select("TRIP_ID", "POLYLINE")
        .explode("POLYLINE", empty_as_null=False)
        .with_columns(
            COORDINATE_NUMBER=pl.int_range(pl.len()).over("TRIP_ID"),
            LONGITUDE=pl.col("POLYLINE").list.get(0),
            LATITUDE=pl.col("POLYLINE").list.get(1),
        )
        .select(POLY_COLS)
    )

    # Haversine between every row and the row above it. All trips are stacked in one
    # table, so for the first point of a trip the row above belongs to another trip.
    # That distance is not part of any trip and is set to 0 below.
    coordinates = polyline.select("LATITUDE", "LONGITUDE").to_numpy()
    segments = np.zeros(polyline.height)
    if polyline.height > 1:
        segments[1:] = haversine_vector(
            coordinates[:-1], coordinates[1:], unit=Unit.METERS
        )
    distances = (
        polyline.select(
            "TRIP_ID",
            SEGMENT_M=pl.when(pl.col("COORDINATE_NUMBER") > 0)
            .then(pl.Series(segments))
            .otherwise(
                0.0  # Ignore distance from last taxi trip to first position of next trip
            ),
        )
        .group_by("TRIP_ID")
        .agg(DISTANCE_M=pl.col("SEGMENT_M").sum())
    )

    trips = (
        data.with_columns(N_POINTS=pl.col("POLYLINE").list.len())
        .join(distances, on="TRIP_ID", how="left")
        .with_columns(pl.col("DISTANCE_M").fill_null(0.0))  # Trips without points
        .select(TRIP_COLS)
    )

    day_types = (
        data.select(pl.col("TIMESTAMP").dt.date().alias("DATE"), "DAY_TYPE")
        .unique()
        .sort(DAY_TYPE_COLS)
    )

    return trips, polyline, day_types
