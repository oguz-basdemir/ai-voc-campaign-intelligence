import io
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from voc.config import MAX_BYTES
from voc.ingestion import DataValidationError, read_csv
from voc.models import AnalysisRequest
from voc.report import html_report, markdown_report, opportunities_csv
from voc.repository import get_analysis, get_dataset, list_analyses, list_datasets, save_dataset
from voc.service import run_analysis
from voc.synthetic import generate

app = FastAPI(
    title="AI Voice-of-Customer & Campaign Intelligence Agent",
    version="1.0.0",
    description="Synthetic data only. Evidence-backed marketing insights with optional LLM enrichment.",
)


@app.get("/health")
def health():
    return {"status": "ok", "synthetic_only": True}


@app.post("/api/demo")
def demo():
    buffer = io.StringIO()
    generate().to_csv(buffer, index=False)
    frame, stats = read_csv(buffer.getvalue().encode())
    return save_dataset(frame, "FlowPilot · synthetic feedback demo", stats)


@app.post("/api/datasets", status_code=201)
async def upload_dataset(file: Annotated[UploadFile, File()], synthetic: Annotated[bool, Form()]):
    if not synthetic:
        raise HTTPException(422, "This demo accepts synthetic feedback only. Confirm synthetic provenance.")
    try:
        content = await file.read(MAX_BYTES + 1)
        frame, stats = await run_in_threadpool(read_csv, content)
        return await run_in_threadpool(save_dataset, frame, file.filename or "Synthetic upload", stats)
    except DataValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@app.get("/api/datasets")
def datasets():
    return list_datasets()


@app.get("/api/datasets/{dataset_id}")
def dataset(dataset_id: str):
    try:
        return get_dataset(dataset_id)[0]
    except KeyError as exc:
        raise HTTPException(404, "Dataset not found") from exc


@app.post("/api/analyses", status_code=201)
def create_analysis(request: AnalysisRequest):
    try:
        return run_analysis(request)
    except KeyError as exc:
        raise HTTPException(404, "Dataset not found") from exc
    except DataValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/datasets/{dataset_id}/analyses")
def history(dataset_id: str):
    dataset(dataset_id)
    return list_analyses(dataset_id)


@app.get("/api/analyses/{analysis_id}")
def analysis(analysis_id: str):
    try:
        return get_analysis(analysis_id)
    except KeyError as exc:
        raise HTTPException(404, "Analysis not found") from exc


@app.get("/api/analyses/{analysis_id}/report")
def report(analysis_id: str, format: str = "md"):
    result = analysis(analysis_id)
    if format not in {"md", "html"}:
        raise HTTPException(422, "Report format must be md or html")
    return Response(
        markdown_report(result) if format == "md" else html_report(result),
        media_type="text/markdown" if format == "md" else "text/html",
        headers={"Content-Disposition": f'attachment; filename="voice-of-customer-report.{format}"'},
    )


@app.get("/api/analyses/{analysis_id}/opportunities.csv")
def export_opportunities(analysis_id: str):
    return Response(
        opportunities_csv(analysis(analysis_id)),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="campaign-opportunities.csv"'},
    )
