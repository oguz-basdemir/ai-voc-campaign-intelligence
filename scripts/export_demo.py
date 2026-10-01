"""Generate committed portfolio outputs directly from the same service used by the API."""

from voc.config import ROOT
from voc.ingestion import read_csv
from voc.models import AnalysisRequest
from voc.report import html_report, markdown_report, opportunities_csv
from voc.repository import save_dataset
from voc.service import run_analysis


def main():
    frame, stats = read_csv((ROOT / "data" / "synthetic_feedback.csv").read_bytes())
    metadata = save_dataset(frame, "FlowPilot · synthetic feedback demo", stats)
    result = run_analysis(AnalysisRequest(dataset_id=metadata["id"]))
    output = ROOT / "docs" / "examples"
    output.mkdir(parents=True, exist_ok=True)
    for filename, text in [
        ("voice-of-customer-report.md", markdown_report(result)),
        ("voice-of-customer-report.html", html_report(result)),
        ("campaign-opportunities.csv", opportunities_csv(result)),
    ]:
        (output / filename).write_text(text, encoding="utf-8")
    print(
        {
            "records": result["summary"]["records"],
            "themes": len(result["themes"]),
            "language_phrases": len(result["language_library"]),
            "top_campaign": result["opportunities"][0]["concept"],
            "output": str(output),
        }
    )


if __name__ == "__main__":
    main()
