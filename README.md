[![version](https://img.shields.io/pypi/v/vastdb.svg)](https://pypi.org/project/vastdb)

# VAST DB Python SDK

🚧 Please note that this package in a pre-release stage. Until version 1.x is officially released, the API should be considered unstable.

## Introduction

`vastdb` is a Python-based SDK designed for interacting with [VAST Database](https://vastdata.com/database) & [VAST Catalog](https://vastdata.com/blog/vast-catalog-treat-your-file-system-like-a-database), enabling schema and table management, efficient ingest, query and modification of columnar data. For more details, see [our whitepaper](https://vastdata.com/whitepaper/#TheVASTDataBase).

[![vastdb](docs/vastdb.png)](https://vastdata.com/database)

## Getting started

### Requirements

- Linux client with Python 3.9+ and a network access to the VAST cluster
- [Virtual IP pool configured with DNS service](https://support.vastdata.com/s/topic/0TOV40000000FThOAM/configuring-network-access-v50)
- [S3 access & secret keys on VAST cluster](https://support.vastdata.com/s/article/UUID-4d2e7e23-b2fb-7900-d98f-96c31a499626)
- [Tabular identity policy with the proper permissions](https://support.vastdata.com/s/article/UUID-14322b60-d6a2-89ac-3df0-3dfbb6974182)


### Installation

```bash
pip install vastdb
```

Also, see [our release notes](CHANGELOG.md).

### Quickstart

Creating schemas and tables + basic inserts and selects:

```python
import pyarrow as pa
import vastdb

session = vastdb.connect(
    endpoint='http://vip-pool.v123-xy.VastENG.lab',
    access=AWS_ACCESS_KEY_ID,
    secret=AWS_SECRET_ACCESS_KEY)

with session.transaction() as tx:
    bucket = tx.bucket("bucket-name")

    schema = bucket.create_schema("schema-name")
    print(bucket.schemas())

    columns = pa.schema([
        ('c1', pa.int16()),
        ('c2', pa.float32()),
        ('c3', pa.utf8()),
    ])
    table = schema.create_table("table-name", columns)
    print(schema.tables())
    print(table.columns())

    arrow_table = pa.table(schema=columns, data=[
        [111, 222, 333],
        [0.5, 1.5, 2.5],
        ['a', 'bb', 'ccc'],
    ])
    table.insert(arrow_table)

    result = pa.Table.from_batches(table.select())  # SELECT * FROM t
    assert result == arrow_table

    # the transaction is automatically committed when exiting the context
```

## Filters and projections

Our SDK supports predicate and projection pushdown:

```python
    # SELECT c1 FROM t WHERE (c2 > 2) AND (c3 IS NULL)
    table.select(columns=['c1'],
                 predicate=(table['c2'] > 2) & table['c3'].isnull())

    # SELECT c2, c3 FROM t WHERE (c2 BETWEEN 0 AND 1) OR (c2 > 10)
    table.select(columns=['c2', 'c3'],
                 predicate=table['c2'].between(0, 1) | (table['c2'] > 10))

    # SELECT * FROM t WHERE c3 LIKE '%substring%'
    table.select(predicate=table['c3'].contains('substring'))
```

## Import a single Parquet file via S3 protocol

It is possible to efficiently create a table from a Parquet file (without copying it via the client):

```python
    with tempfile.NamedTemporaryFile() as f:
        pa.parquet.write_table(arrow_table, f.name)
        s3.put_object(Bucket='bucket-name', Key='staging/file.parquet', Body=f)

    schema = tx.bucket('bucket-name').schema('schema-name')
    table = util.create_table_from_files(
        schema=schema, table_name='imported-table',
        parquet_files=['/bucket-name/staging/file.parquet'])
```

## Import multiple Parquet files concurrently via S3 protocol

We can import multiple files concurrently into a table (by utilizing multiple CNodes' cores):

```python
    schema = tx.bucket('bucket-name').schema('schema-name')
    table = util.create_table_from_files(
        schema=schema, table_name='large-imported-table',
        parquet_files=[f'/bucket-name/staging/file{i}.parquet' for i in range(10)])
```

## Post-processing

### Export

`Table.select()` returns a stream of [PyArrow record batches](https://arrow.apache.org/docs/python/data.html#record-batches), which can be directly exported into a Parquet file:

```python
batches = table.select()
with contextlib.closing(pa.parquet.ParquetWriter('/path/to/file.parquet', batches.schema)) as writer:
    for batch in table_batches:
        writer.write_batch(batch)
```

### DuckDB

We can use [DuckDB](https://duckdb.org/docs/guides/python/sql_on_arrow.html) to post-process the resulting stream of [PyArrow record batches](https://arrow.apache.org/docs/python/data.html#record-batches):

```python
import duckdb
conn = duckdb.connect()

batches = table.select(columns=['c1'], predicate=(table['c2'] > 2))
print(conn.execute("SELECT sum(c1) FROM batches").arrow())
```

## Semi-sorted projections

We can create, list and delete [available semi-sorted projections](https://support.vastdata.com/s/article/UUID-e4ca42ab-d15b-6b72-bd6b-f3c77b455de4):

```python
p = table.create_projection('proj', sorted=['c3'], unsorted=['c1'])
print(table.projections())
print(p.get_stats())
p.drop()
```

## Snapshots

It is possible to use [snapshots](https://vastdata.com/blog/bringing-snapshots-to-vasts-element-store) for accessing the Database:

```python
snaps = bucket.list_snapshots()
batches = snaps[0].schema('schema-name').table('table-name').select()
```

## VAST Catalog

[VAST Catalog](https://vastdata.com/blog/vast-catalog-treat-your-file-system-like-a-database) can be queried as a regular table:

```python
table = pa.Table.from_batches(tx.catalog.select(['element_type']))
df = table.to_pandas()

total_elements = len(df)
print(f"Total elements in the catalog: {total_elements}")

file_count = (df['element_type'] == 'FILE').sum()
print(f"Number of files/objects: {file_count}")

distinct_elements = df['element_type'].unique()
print("Distinct element types on the system:")
print(distinct_elements)
```

See the following blog posts for more examples:

- https://vastdata.com/blog/the-vast-catalog-in-action-part-1
- https://vastdata.com/blog/the-vast-catalog-in-action-part-2
