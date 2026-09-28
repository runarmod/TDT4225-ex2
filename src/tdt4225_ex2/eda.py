from pathlib import Path

import polars as pl

pl.Config(set_tbl_cols=1000)

porto_csv = Path(__file__).resolve().parents[2] / "porto.csv"
df = (
    pl.read_csv(porto_csv)
    .with_columns(
        pl.col(pl.String).replace("", None),  # Replace empty string with explicit null
        pl.from_epoch("TIMESTAMP", time_unit="s"),  # Unix time to timestamp
    )
    .with_columns(
        pl.col("ORIGIN_CALL", "ORIGIN_STAND").cast(pl.Int64),
    )
)

print(df.describe())

print(df.sample(10))

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
