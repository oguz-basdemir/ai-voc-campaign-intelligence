from voc.analysis import analyze
from voc.ingestion import apply_filters
from voc.llm import add_enrichment
from voc.models import AnalysisRequest
from voc.repository import get_dataset, save_analysis


def run_analysis(request: AnalysisRequest) -> dict:
    metadata, frame = get_dataset(request.dataset_id)
    scope = apply_filters(frame, request.filters)
    result = analyze(scope, request.clusters)
    result["filters"] = request.filters.model_dump()
    result["dataset_name"] = metadata["name"]
    result["enrichment"] = {"status": "disabled", "suggestions": []}
    if request.enrich and not scope.empty:
        add_enrichment(result)
    return save_analysis(request.dataset_id, result)
