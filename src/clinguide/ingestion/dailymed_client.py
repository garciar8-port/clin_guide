"""Async client for the DailyMed SPL REST API."""

from pathlib import Path

import httpx

BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
DEFAULT_PAGE_SIZE = 100


class DailyMedClient:
    """Fetches FDA drug labels (SPL XML) from the DailyMed API."""

    def __init__(self, storage_dir: Path = Path("data/raw")) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    async def search_labels(
        self,
        drug_name: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """Search for SPL labels, optionally filtered by drug name.

        Returns the raw JSON response with `data` and `metadata` keys.
        """
        params: dict[str, str | int] = {"page": page, "pagesize": page_size}
        if drug_name:
            params["drug_name"] = drug_name

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{BASE_URL}/spls.json", params=params)
            resp.raise_for_status()
            return resp.json()

    async def fetch_spl_xml(self, set_id: str) -> bytes:
        """Fetch raw SPL XML for a given setId."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(f"{BASE_URL}/spls/{set_id}.xml")
            resp.raise_for_status()
            return resp.content

    async def fetch_and_store(self, set_id: str) -> Path:
        """Fetch SPL XML and persist to local storage. Returns the file path."""
        xml_bytes = await self.fetch_spl_xml(set_id)
        path = self._storage_dir / f"{set_id}.xml"
        path.write_bytes(xml_bytes)
        return path

    async def list_all_set_ids(
        self,
        drug_name: str | None = None,
        max_pages: int | None = None,
    ) -> list[dict]:
        """Paginate through all labels, returning a list of {setid, title, published_date}.

        If max_pages is set, stops after that many pages.
        """
        entries: list[dict] = []
        page = 1

        while True:
            result = await self.search_labels(drug_name=drug_name, page=page)
            entries.extend(result.get("data", []))

            metadata = result.get("metadata", {})
            total_pages = metadata.get("total_pages", 1)

            if page >= total_pages:
                break
            if max_pages and page >= max_pages:
                break
            page += 1

        return entries

    def load_cached_xml(self, set_id: str) -> bytes | None:
        """Load SPL XML from local cache if it exists."""
        path = self._storage_dir / f"{set_id}.xml"
        if path.exists():
            return path.read_bytes()
        return None
