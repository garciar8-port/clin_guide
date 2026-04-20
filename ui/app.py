"""ClinGuide — Streamlit source-viewer UI."""

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

# --- Demo data for mock mode ---
DEMO_RESPONSES = {
    "default": {
        "answer": (
            "The recommended starting dose of osimertinib (TAGRISSO) is **80 mg taken orally "
            "once daily**, with or without food, until disease progression or unacceptable "
            "toxicity [^1]. Osimertinib is indicated for adult patients with metastatic "
            "non-small cell lung cancer (NSCLC) whose tumors have EGFR exon 19 deletions "
            "or exon 21 L858R mutations [^2].\n\n"
            "Dose modifications may be required for adverse reactions. If QTc interval is "
            "greater than 500 msec, osimertinib should be withheld until QTc is less than "
            "481 msec, then resumed at 40 mg [^3]. For interstitial lung disease, "
            "osimertinib should be permanently discontinued [^3]."
        ),
        "citations": [
            {
                "marker": "[^1]",
                "chunk_id": "spl-osimertinib:34068-7:0",
                "quoted_span": (
                    "The recommended dosage of TAGRISSO is 80 mg taken orally once daily, "
                    "with or without food, until disease progression or unacceptable toxicity."
                ),
            },
            {
                "marker": "[^2]",
                "chunk_id": "spl-osimertinib:34067-9:0",
                "quoted_span": (
                    "TAGRISSO is indicated for the treatment of adult patients with metastatic "
                    "non-small cell lung cancer (NSCLC) whose tumors have epidermal growth "
                    "factor receptor (EGFR) exon 19 deletions or exon 21 L858R mutations."
                ),
            },
            {
                "marker": "[^3]",
                "chunk_id": "spl-osimertinib:34068-7:1",
                "quoted_span": (
                    "QTc interval greater than 500 msec: Withhold until QTc is less than "
                    "481 msec, then resume at 40 mg. "
                    "Interstitial lung disease: Permanently discontinue."
                ),
            },
        ],
        "confidence": 0.92,
        "disclaimer": (
            "This information is derived from FDA drug labeling retrieved on 2026-04-18. "
            "It is intended for informational purposes only and does not constitute medical "
            "advice. Always verify against the current prescribing information and consult "
            "a qualified healthcare professional before making clinical decisions."
        ),
        "abstained": False,
    },
    "abstain": {
        "answer": (
            "I don't have enough information in the available drug labels to answer this."
        ),
        "citations": [],
        "confidence": 0.0,
        "disclaimer": "Query classified as non_clinical. No answer generated.",
        "abstained": True,
        "abstain_reason": "non_clinical",
    },
}

DEMO_CHUNKS = {
    "spl-osimertinib:34068-7:0": {
        "text": (
            "The recommended dosage of TAGRISSO is 80 mg taken orally once daily, "
            "with or without food, until disease progression or unacceptable toxicity.\n\n"
            "For patients with difficulty swallowing solids, TAGRISSO tablets can be "
            "dispersed in approximately 60 mL (2 ounces) of non-carbonated water. "
            "No other liquids should be used. Stir until the tablet is dispersed into "
            "small pieces (the tablet will not completely dissolve) and swallow immediately. "
            "Rinse the container with 120 mL to 240 mL (4 to 8 ounces) of water and "
            "immediately drink."
        ),
        "metadata": {
            "drug_name": "TAGRISSO",
            "drug_generic": "osimertinib",
            "section_name": "Dosage and Administration",
            "loinc_code": "34068-7",
        },
    },
    "spl-osimertinib:34067-9:0": {
        "text": (
            "TAGRISSO is indicated for the treatment of adult patients with metastatic "
            "non-small cell lung cancer (NSCLC) whose tumors have epidermal growth factor "
            "receptor (EGFR) exon 19 deletions or exon 21 L858R mutations, as detected "
            "by an FDA-approved test.\n\n"
            "TAGRISSO is also indicated as adjuvant therapy after tumor resection in "
            "patients with non-small cell lung cancer (NSCLC) whose tumors have EGFR "
            "exon 19 deletions or exon 21 L858R mutations, as detected by an "
            "FDA-approved test."
        ),
        "metadata": {
            "drug_name": "TAGRISSO",
            "drug_generic": "osimertinib",
            "section_name": "Indications and Usage",
            "loinc_code": "34067-9",
        },
    },
    "spl-osimertinib:34068-7:1": {
        "text": (
            "Table 1. Recommended Dose Modifications for Adverse Reactions\n\n"
            "Adverse Reaction | Dose Modification\n"
            "--- | ---\n"
            "QTc interval greater than 500 msec on at least 2 separate ECGs | "
            "Withhold TAGRISSO until QTc interval is less than 481 msec or recovery "
            "to baseline if baseline QTc is greater than or equal to 481 msec, then "
            "resume at 40 mg dose\n"
            "Interstitial lung disease (ILD)/Pneumonitis | "
            "Permanently discontinue TAGRISSO\n"
            "Symptomatic congestive heart failure | "
            "Permanently discontinue TAGRISSO"
        ),
        "metadata": {
            "drug_name": "TAGRISSO",
            "drug_generic": "osimertinib",
            "section_name": "Dosage and Administration",
            "loinc_code": "34068-7",
        },
    },
}

NON_CLINICAL_KEYWORDS = [
    "recipe", "weather", "sports", "movie", "capital of", "president",
    "how to cook", "what time",
]


def is_non_clinical(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in NON_CLINICAL_KEYWORDS)


def get_demo_response(query: str) -> dict:
    if is_non_clinical(query):
        return DEMO_RESPONSES["abstain"]
    return DEMO_RESPONSES["default"]


# --- App ---

st.set_page_config(
    page_title="ClinGuide",
    page_icon="\U0001f48a",
    layout="wide",
)

st.title("ClinGuide")
st.caption("Clinical Guidelines RAG Assistant \u2014 FDA Drug Label Search")

# Mode toggle
demo_mode = st.sidebar.toggle("Demo Mode", value=True)
if demo_mode:
    st.sidebar.info(
        "Running in **demo mode** with sample responses. "
        "Connect to the live API by disabling this toggle."
    )

# --- Query Input ---
query = st.text_input(
    "Ask a clinical question",
    placeholder=(
        "e.g., What is the recommended starting dose of "
        "osimertinib for EGFR-mutated NSCLC?"
    ),
)

if query:
    with st.spinner("Searching drug labels..."):
        if demo_mode:
            data = get_demo_response(query)
        else:
            try:
                resp = httpx.post(
                    f"{API_BASE}/query",
                    json={"q": query},
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError:
                st.error(
                    "Cannot connect to ClinGuide API. "
                    "Make sure the server is running, or enable Demo Mode."
                )
                st.code("uvicorn clinguide.api.app:app --port 8000")
                st.stop()
            except Exception as e:
                st.error(f"API error: {e}")
                st.stop()

    # --- Abstention ---
    if data.get("abstained"):
        st.warning(
            f"**Abstained** \u2014 {data.get('abstain_reason', 'unknown reason')}"
        )
        st.info(data["answer"])
        st.stop()

    # --- Answer ---
    col_answer, col_sources = st.columns([3, 2])

    with col_answer:
        st.subheader("Answer")
        st.markdown(data["answer"])

        # Confidence indicator
        confidence = data.get("confidence", 0)
        if confidence >= 0.8:
            st.success(f"Confidence: {confidence:.0%}")
        elif confidence >= 0.5:
            st.warning(f"Confidence: {confidence:.0%}")
        else:
            st.error(f"Confidence: {confidence:.0%}")

        # Disclaimer
        with st.expander("Clinical Disclaimer"):
            st.caption(data.get("disclaimer", ""))

    # --- Source Viewer ---
    with col_sources:
        st.subheader("Sources")
        citations = data.get("citations", [])

        if not citations:
            st.info("No citations in this response.")
        else:
            for i, citation in enumerate(citations):
                marker = citation.get("marker", f"[^{i+1}]")
                chunk_id = citation.get("chunk_id", "")
                quoted = citation.get("quoted_span", "")

                with st.expander(
                    f"{marker} \u2014 {chunk_id}", expanded=(i == 0)
                ):
                    if quoted:
                        st.markdown(f"> {quoted}")

                    # Fetch full chunk text
                    if chunk_id:
                        chunk_data = None
                        if demo_mode:
                            chunk_data = DEMO_CHUNKS.get(chunk_id)
                        else:
                            try:
                                chunk_resp = httpx.get(
                                    f"{API_BASE}/chunks/{chunk_id}",
                                    timeout=10.0,
                                )
                                if chunk_resp.status_code == 200:
                                    chunk_data = chunk_resp.json()
                                    if "error" in chunk_data:
                                        chunk_data = None
                            except Exception:
                                pass

                        if chunk_data:
                            meta = chunk_data.get("metadata", {})
                            st.caption(
                                f"**Drug:** {meta.get('drug_name', '?')} | "
                                f"**Section:** "
                                f"{meta.get('section_name', '?')}"
                            )

                            full_text = chunk_data.get("text", "")
                            if quoted and quoted in full_text:
                                highlighted = full_text.replace(
                                    quoted,
                                    f"**:orange[{quoted}]**",
                                )
                                st.markdown(highlighted)
                            else:
                                st.text(full_text)
                        else:
                            st.caption(
                                "Full source text available when "
                                "connected to the API."
                            )

# --- Footer ---
st.divider()
st.caption(
    "ClinGuide retrieves information from FDA drug labels via DailyMed. "
    "Not for clinical use \u2014 always verify against current "
    "prescribing information."
)
