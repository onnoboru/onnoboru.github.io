#!/usr/bin/env python3
"""Sync BibTeX publications into RenderCV data and generate the CV PDF."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode, splitname
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CV_PATH = REPOSITORY_ROOT / "_data" / "cv.yml"
BIBLIOGRAPHY_PATH = REPOSITORY_ROOT / "_bibliography" / "papers.bib"
DESIGN_PATH = REPOSITORY_ROOT / "assets" / "rendercv" / "design.yaml"
SETTINGS_PATH = REPOSITORY_ROOT / "assets" / "rendercv" / "settings.yaml"
LOCALE_PATH = REPOSITORY_ROOT / "assets" / "rendercv" / "locale.yaml"
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "assets" / "rendercv" / "rendercv_output"


def remove_front_matter(source: str) -> str:
    """Remove the optional Jekyll front matter from a BibTeX file."""
    lines = source.splitlines()
    if not lines or lines[0].strip() != "---":
        return source

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])

    raise ValueError(f"Unclosed YAML front matter in {BIBLIOGRAPHY_PATH}")


def display_name(bibtex_name: str) -> str:
    """Convert either BibTeX author-name order into a natural display name."""
    if bibtex_name.startswith("{") and bibtex_name.endswith("}"):
        return bibtex_name[1:-1]

    components = splitname(bibtex_name, strict_mode=False)
    name_parts = [
        *components["first"],
        *components["von"],
        *components["last"],
        *components["jr"],
    ]
    return " ".join(name_parts)


def load_bibliography() -> list[dict[str, str]]:
    """Parse the repository bibliography into BibTeX entries."""
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    bibliography_source = remove_front_matter(
        BIBLIOGRAPHY_PATH.read_text(encoding="utf-8")
    )
    database = bibtexparser.loads(bibliography_source, parser=parser)
    return database.entries


def publication_from_entry(entry: dict[str, str]) -> dict[str, object]:
    """Convert one BibTeX entry into a RenderCV publication entry."""
    missing_fields = [field for field in ("title", "author", "year") if not entry.get(field)]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise ValueError(f"BibTeX entry {entry.get('ID', '<unknown>')} is missing: {fields}")

    authors = [
        display_name(author.strip())
        for author in re.split(r"\s+and\s+", entry["author"], flags=re.IGNORECASE)
    ]
    year = entry["year"]
    publication_date: int | str = int(year) if year.isdigit() else year
    publication: dict[str, object] = {
        "title": DoubleQuotedScalarString(entry["title"]),
        "authors": authors,
        "date": publication_date,
    }

    venue = entry.get("journal") or entry.get("booktitle") or entry.get("publisher")
    if venue:
        publication["journal"] = venue

    if entry.get("doi"):
        publication["url"] = f"https://doi.org/{entry['doi']}"
    elif entry.get("url"):
        publication["url"] = entry["url"]

    archive = entry.get("archiveprefix", "")
    identifier = entry.get("eprint") or entry.get("arxiv")
    primary_class = entry.get("primaryclass")
    if archive.casefold() == "arxiv" and identifier:
        suffix = f" [{primary_class}]" if primary_class else ""
        publication["journal"] = f"arXiv:{identifier}{suffix}"
        publication.setdefault("url", f"https://arxiv.org/abs/{identifier}")

    return publication


def parse_preprints(entries: list[dict[str, str]]) -> list[dict[str, object]]:
    """Convert BibTeX entries marked as preprints to RenderCV publications."""

    entries = [
        entry
        for entry in entries
        if entry.get("additional_info", "").strip().casefold() == "preprint"
    ]
    entries.sort(
        key=lambda entry: (entry.get("year", ""), entry.get("title", "")),
        reverse=True,
    )

    preprints = [publication_from_entry(entry) for entry in entries]

    if not preprints:
        raise ValueError(
            f"No entries marked with additional_info = {{Preprint}} in {BIBLIOGRAPHY_PATH}"
        )

    return preprints


PUBLICATION_ENTRY_TYPES = {
    "article",
    "book",
    "inbook",
    "incollection",
    "inproceedings",
    "mastersthesis",
    "phdthesis",
    "techreport",
}


def parse_publications(entries: list[dict[str, str]]) -> list[dict[str, object]]:
    """Convert non-preprint academic BibTeX entries to RenderCV publications."""
    publication_entries = [
        entry
        for entry in entries
        if entry.get("ENTRYTYPE", "").casefold() in PUBLICATION_ENTRY_TYPES
        and entry.get("additional_info", "").strip().casefold() != "preprint"
    ]
    publication_entries.sort(
        key=lambda entry: (entry.get("year", ""), entry.get("title", "")),
        reverse=True,
    )
    return [publication_from_entry(entry) for entry in publication_entries]


def sync_cv_sections() -> bool:
    """Update generated publication sections while preserving YAML formatting."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)

    original = CV_PATH.read_text(encoding="utf-8")
    cv_data = yaml.load(original)
    sections = cv_data["cv"]["sections"]
    bibliography_entries = load_bibliography()
    preprints = parse_preprints(bibliography_entries)
    publications = parse_publications(bibliography_entries)

    if "Preprints" in sections:
        sections["Preprints"] = preprints
    else:
        research_index = list(sections).index("Research Experience")
        sections.insert(research_index + 1, "Preprints", preprints)

    if publications:
        sections["Publications"] = publications
    elif "Publications" in sections:
        del sections["Publications"]

    output = StringIO()
    yaml.dump(cv_data, output)
    updated = output.getvalue()
    if updated == original:
        return False

    CV_PATH.write_text(updated, encoding="utf-8")
    return True


def find_rendercv() -> str:
    """Find RenderCV in the active Python environment or on PATH."""
    environment_executable = Path(sys.executable).with_name("rendercv")
    if environment_executable.is_file():
        return str(environment_executable)

    executable = shutil.which("rendercv")
    if executable:
        return executable

    raise RuntimeError(
        "RenderCV is not available in the active environment. "
        "Run this through Pixi: pixi run render-cv"
    )


def render_pdf() -> None:
    """Render the synchronized CV using the repository's design files."""
    command = [
        find_rendercv(),
        "render",
        str(CV_PATH.relative_to(REPOSITORY_ROOT)),
        "--settings",
        str(SETTINGS_PATH.relative_to(REPOSITORY_ROOT)),
        "--design",
        str(DESIGN_PATH.relative_to(REPOSITORY_ROOT)),
        "--locale-catalog",
        str(LOCALE_PATH.relative_to(REPOSITORY_ROOT)),
    ]
    subprocess.run(command, check=True, cwd=REPOSITORY_ROOT)
    for typst_file in OUTPUT_DIRECTORY.glob("*.typ"):
        typst_file.unlink()


def main() -> None:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument(
        "--sync-only",
        action="store_true",
        help="Update _data/cv.yml from BibTeX without generating a PDF.",
    )
    arguments = argument_parser.parse_args()

    changed = sync_cv_sections()
    message = (
        "Synchronized BibTeX publications and preprints."
        if changed
        else "BibTeX publications and preprints are already synchronized."
    )
    print(message, flush=True)
    if not arguments.sync_only:
        render_pdf()


if __name__ == "__main__":
    main()
