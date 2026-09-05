#!/usr/bin/env python3
"""Validate the rendered CV PDF, its synchronized publications, and profile links."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from ruamel.yaml import YAML


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CV_PATH = REPOSITORY_ROOT / "_data" / "cv.yml"
PDF_PATH = (
    REPOSITORY_ROOT
    / "assets"
    / "rendercv"
    / "rendercv_output"
    / "Haruto_Suzuki_CV.pdf"
)


def expected_profile_urls(cv: dict[str, object]) -> set[str]:
    """Build the canonical URLs for the social networks used in this CV."""
    url_prefixes = {
        "GitHub": "https://github.com/",
        "LinkedIn": "https://linkedin.com/in/",
    }
    urls: set[str] = set()
    for profile in cv.get("social_networks", []):
        network = profile["network"]
        if network in url_prefixes:
            urls.add(f"{url_prefixes[network]}{profile['username']}")
    return urls


def main() -> None:
    if not PDF_PATH.is_file():
        raise FileNotFoundError(f"CV PDF was not generated: {PDF_PATH}")

    yaml = YAML(typ="safe")
    cv = yaml.load(CV_PATH.read_text(encoding="utf-8"))["cv"]
    document = pymupdf.open(PDF_PATH)
    if document.page_count < 1:
        raise ValueError("The generated PDF contains no pages.")

    pdf_text = "\n".join(page.get_text() for page in document)
    pdf_urls = {
        link["uri"].rstrip("/")
        for page in document
        for link in page.get_links()
        if link.get("uri")
    }

    expected_text = [cv["name"]]
    expected_text.extend(title.upper() for title in cv["sections"])
    expected_text.extend(
        publication["title"] for publication in cv["sections"].get("Preprints", [])
    )
    expected_text.extend(
        publication["title"] for publication in cv["sections"].get("Publications", [])
    )
    expected_text.extend(
        entry["company"]
        for entries in cv["sections"].values()
        for entry in entries
        if isinstance(entry, dict) and entry.get("company")
    )
    missing_text = [text for text in expected_text if text not in pdf_text]
    if missing_text:
        raise ValueError(f"Missing expected PDF text: {', '.join(missing_text)}")

    expected_urls = {url.rstrip("/") for url in expected_profile_urls(cv)}
    expected_urls.update(
        publication["url"].rstrip("/")
        for publication in cv["sections"].get("Preprints", [])
        if publication.get("url")
    )
    expected_urls.update(
        publication["url"].rstrip("/")
        for publication in cv["sections"].get("Publications", [])
        if publication.get("url")
    )
    missing_urls = sorted(expected_urls - pdf_urls)
    if missing_urls:
        raise ValueError(f"Missing expected PDF links: {', '.join(missing_urls)}")

    print(
        f"CV check passed: {document.page_count} pages, "
        f"{len(expected_urls)} required links verified."
    )


if __name__ == "__main__":
    main()
