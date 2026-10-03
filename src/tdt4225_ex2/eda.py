import random
from pathlib import Path
from typing import Literal, TypedDict

import polars as pl
import pydeck as pdk

pl.Config(set_tbl_cols=1000)


class TripPath(TypedDict):
    path: list[list[float]]
    trip_id: int
    color: int


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


def get_clean_data(verify: bool = False):
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

    # df = remove_invalid_trips(df)  # Task 2.7 (Not allowed apparently!)

    df = df.unique()  # Remove duplicated lines (found during EDA)
    df = df.unique(
        subset=["TRIP_ID"], keep="first"
    )  # Remove lines with duplicated primary key (TODO: figure out some better way)

    if verify:
        verify_data(df)

    return df


def get_color(seed: int) -> tuple[int, int, int, Literal[128]]:
    random.seed(seed)
    return tuple(random.randrange(60, 256) for _ in range(3)) + (128,)


def visualize_trip_paths(data: list[TripPath]) -> None:
    layer = pdk.Layer(
        "PathLayer",
        data,
        get_path="path",
        get_color="color",
        # get_color=[255, 128, 0, 128],
        width_min_pixels=1,
        pickable=True,
    )
    view = pdk.ViewState(latitude=41.17, longitude=-8.65, zoom=11)
    pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        map_style="dark",
        tooltip={"text": "Trip {trip_id}"},
    ).to_html("routes.html")


def eda():
    df = get_clean_data(verify=True)
    dupe_counts = (
        df.group_by("TRIP_ID").agg(pl.len().alias("count")).filter(pl.col("count") > 1)
    )
    print(dupe_counts)

    dupe_ids = dupe_counts["TRIP_ID"].implode()

    all_dupes = df.filter(pl.col("TRIP_ID").is_in(dupe_ids)).sort(
        ["TRIP_ID", "TIMESTAMP"]
    )
    print(all_dupes)

    data: list[TripPath] = [
        TripPath(
            path=row["POLYLINE"],
            trip_id=row["TRIP_ID"],
            color=get_color(row["TAXI_ID"]),
        )
        for row in df.sample(100000).iter_rows(named=True)
    ]
    visualize_trip_paths(data)


if __name__ == "__main__":
    eda()
