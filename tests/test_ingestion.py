import pytest

from voc.ingestion import DataValidationError, apply_filters, read_csv
from voc.models import Filters
from voc.synthetic import generate


def encode(frame):
    return frame.to_csv(index=False).encode()


def test_synthetic_generation_is_reproducible():
    assert generate(50).equals(generate(50))
    assert set(generate().source) == {"review", "survey", "support_ticket", "sales_note", "interview"}
    assert generate().customer_id.str.startswith("SYN-").all()


def test_roundtrip_stable_ids_and_deduplication():
    import pandas as pd

    original = generate(4)
    duplicated = pd.concat([original, original.iloc[:1]], ignore_index=True)
    frame, stats = read_csv(encode(duplicated))
    assert stats == {"input_rows": 5, "accepted_rows": 4, "duplicates_removed": 1}
    assert frame.record_id.tolist() == read_csv(encode(original))[0].record_id.tolist()


@pytest.mark.parametrize("content", [b"", b"text\nhello", b"\xff\xfe", b"source,customer_id\nreview,a"])
def test_bad_csv(content):
    with pytest.raises(DataValidationError):
        read_csv(content)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "email"),
        ("date", "2026-02-30"),
        ("date", "01/02/2026"),
        ("text", " "),
        ("text", "x" * 5001),
        ("customer_id", "x" * 121),
    ],
)
def test_field_validation(field, value):
    data = generate(1)
    data.loc[0, field] = value
    with pytest.raises(DataValidationError):
        read_csv(encode(data))


def test_size_limits(monkeypatch):
    from voc import ingestion

    monkeypatch.setattr(ingestion, "MAX_ROWS", 2)
    with pytest.raises(DataValidationError, match="10,000"):
        read_csv(encode(generate(3)))
    monkeypatch.setattr(ingestion, "MAX_BYTES", 4)
    with pytest.raises(DataValidationError, match="5 MB"):
        read_csv(b"too large")


def test_filters_are_intersection_and_inclusive(frame):
    row = frame.iloc[0]
    result = apply_filters(
        frame,
        Filters(
            products=[row["product"]], markets=[row["market"]], date_from=row["date"], date_to=row["date"]
        ),
    )
    assert not result.empty
    assert set(result["product"]) == {row["product"]}
    assert set(result.date) == {row["date"]}
    assert apply_filters(frame, Filters(markets=["Unknown"])).empty


@pytest.mark.parametrize(
    "filters", [Filters(date_from="yesterday"), Filters(date_from="2026-07-01", date_to="2026-06-01")]
)
def test_filter_validation(frame, filters):
    with pytest.raises(DataValidationError):
        apply_filters(frame, filters)
