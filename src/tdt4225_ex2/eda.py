from pathlib import Path

import polars as pl

pl.Config(set_tbl_cols=1000)


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

    df = remove_invalid_trips(df)  # Task 2.7
    df = df.unique()  # Remove duplicated lines (found during EDA)

    if verify:
        verify_data(df)

    return df


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


if __name__ == "__main__":
    eda()
