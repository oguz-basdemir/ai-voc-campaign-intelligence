import hashlib
import io
import re

import pandas as pd

from voc.config import MAX_BYTES, MAX_ROWS, MAX_TEXT_LENGTH
from voc.models import Filters

REQUIRED = ["source", "customer_id", "date", "customer_type", "text", "market", "product"]
SOURCES = {"review", "survey", "support_ticket", "sales_note", "interview"}


class DataValidationError(ValueError):
    pass


def read_csv(content: bytes) -> tuple[pd.DataFrame, dict]:
    """Strict CSV validation; stable IDs and duplicate removal preserve honest denominators."""
    if len(content) > MAX_BYTES:
        raise DataValidationError("CSV exceeds the 5 MB limit.")
    try:
        frame = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataValidationError("Upload a nonempty, UTF-8 CSV with a header.") from exc
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing columns: {', '.join(missing)}.")
    if frame.empty or len(frame) > MAX_ROWS:
        raise DataValidationError("CSV must contain between 1 and 10,000 feedback records.")
    frame = frame[REQUIRED].copy()
    for col in REQUIRED:
        frame[col] = frame[col].str.strip()
        if frame[col].eq("").any():
            raise DataValidationError(f"Column '{col}' contains blank values.")
    unknown = sorted(set(frame.source) - SOURCES)
    if unknown:
        raise DataValidationError(f"Unknown sources: {', '.join(unknown)}. Use {', '.join(sorted(SOURCES))}.")
    if frame.text.str.len().gt(MAX_TEXT_LENGTH).any():
        raise DataValidationError("Feedback text may contain at most 5,000 characters per record.")
    if any(frame[c].str.len().gt(120).any() for c in REQUIRED if c != "text"):
        raise DataValidationError("Metadata fields may contain at most 120 characters.")
    if not frame.date.map(lambda x: bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", x))).all():
        raise DataValidationError("Dates must use YYYY-MM-DD.")
    try:
        pd.to_datetime(frame.date, format="%Y-%m-%d", errors="raise")
    except ValueError as exc:
        raise DataValidationError("Dates contain an invalid calendar date.") from exc
    before = len(frame)
    frame = frame.drop_duplicates().reset_index(drop=True)
    frame.insert(
        0,
        "record_id",
        frame.apply(lambda row: "voc_" + hashlib.sha256(row.to_json().encode()).hexdigest()[:16], axis=1),
    )
    return frame, {
        "input_rows": before,
        "accepted_rows": len(frame),
        "duplicates_removed": before - len(frame),
    }


def apply_filters(frame: pd.DataFrame, filters: Filters) -> pd.DataFrame:
    result = frame.copy()
    for column, values in [
        ("source", filters.sources),
        ("product", filters.products),
        ("customer_type", filters.segments),
        ("market", filters.markets),
    ]:
        if values:
            result = result[result[column].isin(values)]
    for date in (filters.date_from, filters.date_to):
        if date:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    raise ValueError
                pd.to_datetime(date, format="%Y-%m-%d", errors="raise")
            except ValueError as exc:
                raise DataValidationError("Filter dates must be valid YYYY-MM-DD dates.") from exc
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        raise DataValidationError("Start date must be on or before end date.")
    if filters.date_from:
        result = result[result.date >= filters.date_from]
    if filters.date_to:
        result = result[result.date <= filters.date_to]
    return result.reset_index(drop=True)
