"""ClinGuide — Streamlit source-viewer UI."""

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="ClinGuide",
    page_icon="💊",
    layout="wide",
)

st.title("ClinGuide")
st.caption("Clinical Guidelines RAG Assistant — FDA Drug Label Search")

# --- Query Input ---
query = st.text_input(
    "Ask a clinical question",
    placeholder="e.g., What is the recommended starting dose of osimertinib for EGFR-mutated NSCLC?",
)

if query:
    with st.spinner("Searching drug labels..."):
        try:
            resp = httpx.post(
                f"{API_BASE}/query",
                json={"q": query},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            st.error("Cannot connect to ClinGuide API. Make sure the server is running on port 8000.")
            st.code("uvicorn clinguide.api.app:app --port 8000")
            st.stop()
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    # --- Abstention ---
    if data.get("abstained"):
        st.warning(f"**Abstained** — {data.get('abstain_reason', 'unknown reason')}")
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

                with st.expander(f"{marker} — {chunk_id}", expanded=(i == 0)):
                    if quoted:
                        st.markdown(f"> {quoted}")

                    # Fetch full chunk text
                    if chunk_id:
                        try:
                            chunk_resp = httpx.get(
                                f"{API_BASE}/chunks/{chunk_id}",
                                timeout=10.0,
                            )
                            if chunk_resp.status_code == 200:
                                chunk_data = chunk_resp.json()
                                if "error" not in chunk_data:
                                    meta = chunk_data.get("metadata", {})
                                    st.caption(
                                        f"**Drug:** {meta.get('drug_name', '?')} | "
                                        f"**Section:** {meta.get('section_name', '?')}"
                                    )

                                    full_text = chunk_data.get("text", "")
                                    # Highlight the quoted span
                                    if quoted and quoted in full_text:
                                        highlighted = full_text.replace(
                                            quoted,
                                            f"**:orange[{quoted}]**",
                                        )
                                        st.markdown(highlighted)
                                    else:
                                        st.text(full_text)
                        except Exception:
                            st.caption("Could not load full chunk text.")

# --- Footer ---
st.divider()
st.caption(
    "ClinGuide retrieves information from FDA drug labels via DailyMed. "
    "Not for clinical use — always verify against current prescribing information."
)
