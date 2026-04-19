from datetime import date

from pydantic import BaseModel


# --- Ingestion models ---


class TableExtract(BaseModel):
    caption: str | None = None
    headers: list[str]
    rows: list[list[str]]


class LabelSection(BaseModel):
    loinc_code: str
    section_name: str
    text: str
    tables: list[TableExtract] = []


class LabelDocument(BaseModel):
    set_id: str
    version_id: str
    drug_name: str = ""
    drug_generic: str = ""
    drug_class: list[str] = []
    approval_date: date | None = None
    last_updated: date | None = None
    sections: list[LabelSection] = []


class Chunk(BaseModel):
    chunk_id: str  # stable: f"{set_id}:{loinc_code}:{chunk_idx}"
    set_id: str
    version_id: str
    drug_name: str
    drug_generic: str
    drug_class: list[str]
    loinc_code: str
    section_name: str
    text: str
    tables: list[TableExtract] = []
    approval_date: date | None = None
    last_updated: date | None = None


# --- LOINC section mapping ---

SECTION_CODES: dict[str, str] = {
    "34067-9": "Indications and Usage",
    "34068-7": "Dosage and Administration",
    "34070-3": "Contraindications",
    "34071-1": "Warnings and Precautions",
    "34073-7": "Adverse Reactions",
    "34074-5": "Drug Interactions",
    "42228-7": "Use in Specific Populations",
}


# --- Query/response models ---


class QueryRequest(BaseModel):
    q: str
    filters: dict[str, str] | None = None


class Citation(BaseModel):
    marker: str  # e.g. "[^1]"
    chunk_id: str
    quoted_span: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float
    disclaimer: str
    abstained: bool = False
    abstain_reason: str | None = None
