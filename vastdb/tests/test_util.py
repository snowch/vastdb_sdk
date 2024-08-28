import pyarrow as pa
import pytest

from .. import errors, util


def test_slices():
    ROWS = 1 << 20
    t = pa.table({"x": range(ROWS), "y": [i / 1000 for i in range(ROWS)]})

    chunks = list(util.iter_serialized_slices(t))
    assert len(chunks) > 1
    sizes = [len(c) for c in chunks]

    assert max(sizes) < util.MAX_RECORD_BATCH_SLICE_SIZE
    assert t == pa.Table.from_batches(_parse(chunks))

    chunks = list(util.iter_serialized_slices(t, 1000))
    assert len(chunks) > 1
    sizes = [len(c) for c in chunks]

    assert max(sizes) < util.MAX_RECORD_BATCH_SLICE_SIZE
    assert t == pa.Table.from_batches(_parse(chunks))


def test_wide_row():
    cols = [pa.field(f"x{i}", pa.utf8()) for i in range(1000)]
    values = [['a' * 10000]] * len(cols)
    t = pa.table(values, schema=pa.schema(cols))
    assert len(t) == 1

    with pytest.raises(errors.TooWideRow):
        list(util.iter_serialized_slices(t))


def test_expand_ip_ranges():
    endpoints = ["http://172.19.101.1-3"]
    expected = ["http://172.19.101.1", "http://172.19.101.2", "http://172.19.101.3"]
    assert util.expand_ip_ranges(endpoints) == expected


def _parse(bufs):
    for buf in bufs:
        with pa.ipc.open_stream(buf) as reader:
            yield from reader


def test_prefix():
    assert util.prefix_to_range('a') == (b'a', b'b')
    assert util.prefix_to_range('abc') == (b'abc', b'abd')
    assert util.prefix_to_range('abc\x00') == (b'abc\x00', b'abc\x01')
    assert util.prefix_to_range('abc\x7f') == (b'abc\x7f', b'abc\x80')
    assert util.prefix_to_range('/a/b/c') == (b'/a/b/c', b'/a/b/d')
    assert util.prefix_to_range('/123α') == (b'/123\xce\xb1', b'/123\xce\xb2')
    assert util.prefix_to_range('/123αA') == (b'/123\xce\xb1A', b'/123\xce\xb1B')
    assert util.prefix_to_range('\U0010ffff') == (b'\xf4\x8f\xbf\xbf', b'\xf4\x8f\xbf\xc0')  # max unicode codepoint
    with pytest.raises(AssertionError):
        util.prefix_to_range('')
