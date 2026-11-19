import pyarrow.parquet as pq, sys, json
base = "data/stinkbid/runs/outcomes/P1__U_Q1/"
for t in ("bids", "fills", "outcomes", "bench", "audit", "bid_status"):
    f = pq.ParquetFile(base + t + ".parquet")
    print(t, f.metadata.num_rows, "rows")
    print("  ", [x.name for x in f.schema_arrow])
print(open(base + "meta.json").read())
print(open(base + "done.json").read())
