from voc.repository import get_analysis
from voc.synthetic import generate


def test_full_workflow_persistence_exports_and_scoping(client):
    demo = client.post("/api/demo").json()
    assert demo["rows"] == 640
    assert client.post("/api/demo").json()["id"] == demo["id"]
    payload = {
        "dataset_id": demo["id"],
        "filters": {"segments": ["Operations manager"], "markets": ["Nordics"]},
    }
    response = client.post("/api/analyses", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert 0 < result["summary"]["records"] < 640
    assert all(
        r["customer_type"] == "Operations manager" and r["market"] == "Nordics" for r in result["records"]
    )
    assert get_analysis(result["id"]) == result
    assert client.get(f"/api/analyses/{result['id']}").json() == result
    assert client.get(f"/api/datasets/{demo['id']}/analyses").json()[0]["id"] == result["id"]
    report = client.get(f"/api/analyses/{result['id']}/report")
    assert "All demo customer data is synthetic" in report.text
    assert "Nordics" in report.text
    assert result["id"] in report.text
    assert "attachment" in report.headers["content-disposition"]
    assert client.get(f"/api/analyses/{result['id']}/report?format=html").text.startswith("<!doctype")
    assert client.get(f"/api/analyses/{result['id']}/opportunities.csv").text.startswith("theme,concept")
    assert client.get(f"/api/analyses/{result['id']}/report?format=pdf").status_code == 422


def test_upload_requires_synthetic_attestation_and_valid_csv(client):
    files = {"file": ("demo.csv", generate(10).to_csv(index=False), "text/csv")}
    assert client.post("/api/datasets", files=files, data={"synthetic": "false"}).status_code == 422
    response = client.post("/api/datasets", files=files, data={"synthetic": "true"})
    assert response.status_code == 201
    assert response.json()["rows"] == 10
    assert client.get("/api/datasets").json()[0]["id"] == response.json()["id"]
    assert (
        client.post(
            "/api/datasets", files={"file": ("bad.csv", "oops")}, data={"synthetic": "true"}
        ).status_code
        == 422
    )


def test_not_found_and_invalid_requests(client):
    assert client.get("/api/datasets/missing").status_code == 404
    assert client.get("/api/analyses/missing").status_code == 404
    assert client.post("/api/analyses", json={"dataset_id": "missing"}).status_code == 404
    assert client.post("/api/analyses", json={"dataset_id": "x", "clusters": 20}).status_code == 422
    assert client.get("/health").json()["synthetic_only"]


def test_empty_scope_and_missing_provider_fall_back(client):
    dataset = client.post("/api/demo").json()
    empty = client.post(
        "/api/analyses", json={"dataset_id": dataset["id"], "filters": {"markets": ["Atlantis"]}}
    ).json()
    assert empty["summary"]["records"] == 0
    enriched = client.post("/api/analyses", json={"dataset_id": dataset["id"], "enrich": True}).json()
    assert enriched["enrichment"]["status"] == "unavailable"
    assert enriched["opportunities"]


def test_invalid_filter_dates(client):
    dataset = client.post("/api/demo").json()
    response = client.post(
        "/api/analyses", json={"dataset_id": dataset["id"], "filters": {"date_from": "not-a-date"}}
    )
    assert response.status_code == 422
