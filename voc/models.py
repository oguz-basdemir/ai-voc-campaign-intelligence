from pydantic import BaseModel, ConfigDict, Field


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    filters: Filters = Field(default_factory=Filters)
    enrich: bool = False
    clusters: int = Field(default=6, ge=2, le=12)


class CreativeSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: str = Field(max_length=80)
    headline: str = Field(max_length=160)
    rationale: str = Field(max_length=800)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class Enrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestions: list[CreativeSuggestion] = Field(max_length=8)
