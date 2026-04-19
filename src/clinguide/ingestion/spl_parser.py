"""Parse FDA SPL XML into structured LabelDocument objects."""

from lxml import etree

from clinguide.core.models import LabelDocument, LabelSection, TableExtract, SECTION_CODES

NS = {"hl7": "urn:hl7-org:v3"}


def parse_spl(raw_xml: bytes) -> LabelDocument:
    """Parse raw SPL XML into a LabelDocument with typed sections and tables."""
    root = etree.fromstring(raw_xml)

    set_id = _xpath_first(root, "//hl7:setId/@root", "")
    version_id = _xpath_first(root, "//hl7:versionNumber/@value", "")

    # Drug names
    drug_name = _xpath_first(root, ".//hl7:manufacturedProduct/hl7:name/text()", "")
    drug_generic = _xpath_first(
        root, ".//hl7:genericMedicine/hl7:name/text()", ""
    )

    # Extract sections matching our LOINC codes
    sections: list[LabelSection] = []
    for section_el in root.xpath("//hl7:section[hl7:code]", namespaces=NS):
        code = _xpath_first(section_el, "hl7:code/@code", "")
        if code not in SECTION_CODES:
            continue

        text = _extract_text(section_el)
        tables = _extract_tables(section_el)

        if not text.strip() and not tables:
            continue

        sections.append(
            LabelSection(
                loinc_code=code,
                section_name=SECTION_CODES[code],
                text=text,
                tables=tables,
            )
        )

    return LabelDocument(
        set_id=set_id,
        version_id=version_id,
        drug_name=drug_name,
        drug_generic=drug_generic,
        sections=sections,
    )


def _xpath_first(el: etree._Element, xpath: str, default: str) -> str:
    """Return the first XPath match or a default."""
    results = el.xpath(xpath, namespaces=NS)
    return str(results[0]) if results else default


def _extract_text(section_el: etree._Element) -> str:
    """Extract all paragraph text from a section's <text> element, including subsections."""
    parts: list[str] = []

    # Get text from the section's direct <text> child
    for text_el in section_el.xpath("hl7:text", namespaces=NS):
        _collect_text_content(text_el, parts)

    # Also gather text from nested subsections (component/section)
    for subsection in section_el.xpath("hl7:component/hl7:section", namespaces=NS):
        sub_code = _xpath_first(subsection, "hl7:code/@code", "")
        # Only recurse into subsections that share the parent's LOINC code
        # or have no code (unnamed subsections)
        if sub_code and sub_code in SECTION_CODES:
            continue  # This is a top-level section, handled separately
        sub_title = _xpath_first(subsection, "hl7:title/text()", "")
        if sub_title:
            parts.append(f"\n{sub_title}")
        for text_el in subsection.xpath("hl7:text", namespaces=NS):
            _collect_text_content(text_el, parts)

    return "\n".join(parts).strip()


def _collect_text_content(el: etree._Element, parts: list[str]) -> None:
    """Recursively collect text from paragraphs, list items, and other text nodes."""
    for child in el:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ""

        if tag == "table":
            # Tables are handled separately
            continue
        elif tag == "paragraph":
            text = _element_full_text(child).strip()
            if text:
                parts.append(text)
        elif tag == "list":
            for item in child.xpath("hl7:item", namespaces=NS):
                text = _element_full_text(item).strip()
                if text:
                    parts.append(f"  - {text}")
        elif tag in ("caption", "title"):
            text = _element_full_text(child).strip()
            if text:
                parts.append(text)
        else:
            # Recurse into other containers
            _collect_text_content(child, parts)


def _element_full_text(el: etree._Element) -> str:
    """Get all text content from an element, including text in child elements like <sup>, <sub>, <content>."""
    return "".join(el.itertext())


def _extract_tables(section_el: etree._Element) -> list[TableExtract]:
    """Extract all tables from a section as structured TableExtract objects."""
    tables: list[TableExtract] = []

    for table_el in section_el.xpath(".//hl7:table", namespaces=NS):
        caption_text = _xpath_first(table_el, "hl7:caption/text()", "")
        caption = caption_text if caption_text else None

        headers: list[str] = []
        for th in table_el.xpath(".//hl7:thead/hl7:tr/hl7:th", namespaces=NS):
            headers.append(_element_full_text(th).strip())

        rows: list[list[str]] = []
        for tr in table_el.xpath(".//hl7:tbody/hl7:tr", namespaces=NS):
            cells: list[str] = []
            for td in tr.xpath("hl7:td", namespaces=NS):
                cells.append(_element_full_text(td).strip())
            if cells:
                rows.append(cells)

        if headers or rows:
            tables.append(TableExtract(caption=caption, headers=headers, rows=rows))

    return tables
