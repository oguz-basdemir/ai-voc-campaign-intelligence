import io

import pytest
from fastapi.testclient import TestClient

from voc.api import app
from voc.ingestion import read_csv
from voc.synthetic import generate


@pytest.fixture
def frame():
    buffer = io.StringIO()
    generate(96).to_csv(buffer, index=False)
    return read_csv(buffer.getvalue().encode())[0]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VOC_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("VOC_LLM_API_KEY", raising=False)
    with TestClient(app) as client:
        yield client
