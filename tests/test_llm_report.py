import httpx
import pytest

from voc.analysis import analyze
from voc.llm import OpenAICompatibleProvider, add_enrichment
from voc.models import CreativeSuggestion, Enrichment
from voc.report import html_report, markdown_report, opportunities_csv


class FakeProvider:
    def __init__(self, bad=False):
        self.bad = bad

    def enrich(self, packet):
        theme = packet["themes"][0]
        return Enrichment(
            suggestions=[
                CreativeSuggestion(
                    theme=theme["theme"],
                    headline="Explore a simpler workflow",
                    rationale="A creative hypothesis based on the supplied quotes.",
                    evidence_ids=["invented" if self.bad else theme["evidence"][0]["record_id"]],
                )
            ]
        )


def test_enrichment_preserves_counts_and_validates_evidence(frame):
    original = analyze(frame)
    result = add_enrichment(original, FakeProvider())
    assert result["enrichment"]["status"] == "complete"
    assert result["summary"]["records"] == len(frame)
    assert add_enrichment(analyze(frame), FakeProvider(bad=True))["enrichment"]["status"] == "unavailable"


@pytest.mark.parametrize("mode", ["good", "malformed", "timeout", "unauthorized"])
def test_compatible_http_provider_with_mock_transport(frame, monkeypatch, mode):
    monkeypatch.setenv("VOC_LLM_API_KEY", "test-secret")
    monkeypatch.setenv("VOC_LLM_BASE_URL", "https://provider.invalid/v1")
    import json

    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-secret"
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        if mode == "timeout":
            raise httpx.ReadTimeout("test", request=request)
        if mode == "unauthorized":
            return httpx.Response(401, text="test-secret")
        packet = json.loads(payload["messages"][1]["content"])
        content = "not json" if mode == "malformed" else FakeProvider().enrich(packet).model_dump_json()
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = add_enrichment(analyze(frame), OpenAICompatibleProvider(client))
    assert result["enrichment"]["status"] == ("complete" if mode == "good" else "unavailable")
    assert "test-secret" not in str(result)


def test_exports_escape_input_and_have_empty_headers(frame):
    frame = frame.iloc[:1].copy()
    frame["text"] = '<script>alert("x")</script> The implementation is difficult.'
    frame["customer_type"] = '=HYPERLINK("https://example.com")'
    result = analyze(frame)
    result.update(id="run_test", dataset_id="ds_test", created_at="2026-10-01", filters={})
    assert "<script>" not in html_report(result)
    assert "\\<script\\>" in markdown_report(result)
    assert "'=HYPERLINK" in opportunities_csv(result)
    result["opportunities"] = []
    assert opportunities_csv(result).startswith("theme,concept,")
