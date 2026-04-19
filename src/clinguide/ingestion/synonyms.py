"""Brand→generic→class synonym dictionary for query expansion."""

import json
from pathlib import Path

SYNONYMS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "synonyms.json"

# Seed dictionary — expanded at ingestion time from DailyMed metadata
_SEED: dict[str, dict] = {
    "tagrisso": {"generic": "osimertinib", "class": ["EGFR TKI", "antineoplastic"]},
    "osimertinib": {"generic": "osimertinib", "class": ["EGFR TKI", "antineoplastic"]},
    "keytruda": {"generic": "pembrolizumab", "class": ["PD-1 inhibitor", "antineoplastic"]},
    "pembrolizumab": {"generic": "pembrolizumab", "class": ["PD-1 inhibitor", "antineoplastic"]},
    "opdivo": {"generic": "nivolumab", "class": ["PD-1 inhibitor", "antineoplastic"]},
    "nivolumab": {"generic": "nivolumab", "class": ["PD-1 inhibitor", "antineoplastic"]},
    "herceptin": {"generic": "trastuzumab", "class": ["HER2 inhibitor", "antineoplastic"]},
    "trastuzumab": {"generic": "trastuzumab", "class": ["HER2 inhibitor", "antineoplastic"]},
    "ibrance": {"generic": "palbociclib", "class": ["CDK4/6 inhibitor", "antineoplastic"]},
    "palbociclib": {"generic": "palbociclib", "class": ["CDK4/6 inhibitor", "antineoplastic"]},
    "metformin": {"generic": "metformin", "class": ["biguanide", "antidiabetic"]},
    "glucophage": {"generic": "metformin", "class": ["biguanide", "antidiabetic"]},
    "lisinopril": {"generic": "lisinopril", "class": ["ACE inhibitor", "antihypertensive"]},
    "prinivil": {"generic": "lisinopril", "class": ["ACE inhibitor", "antihypertensive"]},
    "zestril": {"generic": "lisinopril", "class": ["ACE inhibitor", "antihypertensive"]},
    "atorvastatin": {"generic": "atorvastatin", "class": ["statin", "antilipemic"]},
    "lipitor": {"generic": "atorvastatin", "class": ["statin", "antilipemic"]},
    "warfarin": {"generic": "warfarin", "class": ["anticoagulant"]},
    "coumadin": {"generic": "warfarin", "class": ["anticoagulant"]},
}


class SynonymDictionary:
    """Lookup brand/generic drug name synonyms for query expansion."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if SYNONYMS_PATH.exists():
            with open(SYNONYMS_PATH) as f:
                self._data = json.load(f)
        else:
            self._data = dict(_SEED)

    def save(self) -> None:
        SYNONYMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SYNONYMS_PATH, "w") as f:
            json.dump(self._data, f, indent=2)

    def add(self, brand: str, generic: str, drug_class: list[str] | None = None) -> None:
        """Add a brand/generic pair to the dictionary."""
        entry = {"generic": generic.lower(), "class": drug_class or []}
        self._data[brand.lower()] = entry
        self._data[generic.lower()] = entry

    def expand(self, term: str) -> list[str]:
        """Return a list of synonyms for a drug name (brand, generic, class terms)."""
        key = term.lower().strip()
        entry = self._data.get(key)
        if not entry:
            return [term]

        terms = {term, key, entry["generic"]}
        # Find all brand names for this generic
        for name, e in self._data.items():
            if e["generic"] == entry["generic"]:
                terms.add(name)
        return list(terms)

    def get_generic(self, term: str) -> str | None:
        """Get the generic name for a drug term, or None if unknown."""
        entry = self._data.get(term.lower().strip())
        return entry["generic"] if entry else None
