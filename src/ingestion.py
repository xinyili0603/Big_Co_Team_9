import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import requests


EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_TIMEOUT = 30
DEFAULT_HEADERS = {"User-Agent": "csl-behring-mvp/0.1"}
MONTH_LOOKUP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _request_xml(endpoint: str, params: dict[str, Any]) -> ET.Element:
    url = f"{EUTILS_BASE_URL}/{endpoint}"
    response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return ET.fromstring(response.content)


def _search_pubmed_ids(query: str, max_docs: int) -> list[str]:
    root = _request_xml(
        "esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmax": max_docs,
            "retmode": "xml",
        },
    )
    return [node.text.strip() for node in root.findall("./IdList/Id") if node.text]


def _normalize_month(value: str | None) -> int:
    if not value:
        return 1

    cleaned = value.strip()
    if cleaned.isdigit():
        month = int(cleaned)
        return month if 1 <= month <= 12 else 1

    return MONTH_LOOKUP.get(cleaned[:4].lower().rstrip("."), 1)


def _parse_publication_date(article: ET.Element) -> str:
    pub_date = article.find(".//PubDate")
    if pub_date is None:
        return ""

    year_text = pub_date.findtext("Year")
    medline_date = pub_date.findtext("MedlineDate")
    if not year_text and medline_date:
        year_text = medline_date.strip()[:4]

    if not year_text or not year_text.isdigit():
        return ""

    month = _normalize_month(pub_date.findtext("Month"))
    day_text = pub_date.findtext("Day")
    day = int(day_text) if day_text and day_text.isdigit() else 1

    try:
        return datetime(int(year_text), month, day).strftime("%Y-%m-%d")
    except ValueError:
        return f"{int(year_text):04d}-{month:02d}-01"


def _extract_abstract(article: ET.Element) -> str:
    abstract_nodes = article.findall(".//Abstract/AbstractText")
    parts: list[str] = []

    for node in abstract_nodes:
        text = " ".join(part.strip() for part in node.itertext() if part and part.strip())
        if text:
            parts.append(text)

    return "\n".join(parts).strip()


def _extract_authors(article: ET.Element) -> list[str]:
    authors: list[str] = []

    for author in article.findall(".//AuthorList/Author"):
        collective_name = author.findtext("CollectiveName")
        if collective_name:
            authors.append(collective_name.strip())
            continue

        last_name = (author.findtext("LastName") or "").strip()
        fore_name = (author.findtext("ForeName") or "").strip()
        if last_name or fore_name:
            full_name = " ".join(part for part in [fore_name, last_name] if part)
            authors.append(full_name)

    return authors


def _extract_title(article: ET.Element) -> str:
    title_node = article.find("./ArticleTitle")
    if title_node is None:
        return ""

    return " ".join(part.strip() for part in title_node.itertext() if part and part.strip())


def _fetch_pubmed_metadata(pmids: list[str]) -> tuple[list[dict[str, Any]], int]:
    if not pmids:
        return [], 0

    root = _request_xml(
        "efetch.fcgi",
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
    )

    documents: list[dict[str, Any]] = []
    seen_pmids: set[str] = set()
    skipped_no_abstract = 0

    for pubmed_article in root.findall("./PubmedArticle"):
        pmid = pubmed_article.findtext("./MedlineCitation/PMID")
        if not pmid:
            continue

        pmid = pmid.strip()
        if pmid in seen_pmids:
            continue

        article = pubmed_article.find("./MedlineCitation/Article")
        if article is None:
            continue

        abstract = _extract_abstract(article)
        if not abstract:
            skipped_no_abstract += 1
            continue

        documents.append(
            {
                "id": pmid,
                "type": "pubmed",
                "title": _extract_title(article),
                "abstract": abstract,
                "claims": None,
                "assignee": None,
                "inventors": _extract_authors(article),
                "publication_date": _parse_publication_date(article),
            }
        )
        seen_pmids.add(pmid)

    return documents, skipped_no_abstract


def fetch_pubmed_documents(keywords: list[str], max_docs: int) -> list[dict]:
    query = " AND ".join(keyword.strip() for keyword in keywords if keyword.strip())
    if not query:
        return []

    try:
        pmids = _search_pubmed_ids(query, max_docs)
        print(f"Found {len(pmids)} PMIDs")
        documents, skipped_no_abstract = _fetch_pubmed_metadata(pmids)
        print(f"Skipped {skipped_no_abstract} documents with no abstract")
        return documents
    except (requests.RequestException, ET.ParseError) as exc:
        print(f"PubMed fetch failed: {exc}", file=sys.stderr)
        return []


def save_documents(documents: list[dict], output_path: str) -> None:
    output_file_path = Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    with output_file_path.open("w", encoding="utf-8") as output_file:
        json.dump(documents, output_file, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch PubMed documents as structured JSON.")
    parser.add_argument("--keywords", nargs="+", required=True, help="Search keywords for PubMed.")
    parser.add_argument("--max_docs", type=int, required=True, help="Maximum number of documents to fetch.")
    parser.add_argument("--output", required=True, help="Path to the output JSON file.")
    args = parser.parse_args()

    if args.max_docs <= 0:
        parser.error("--max_docs must be greater than 0")

    documents = fetch_pubmed_documents(args.keywords, args.max_docs)
    save_documents(documents, args.output)
    print(f"Saved {len(documents)} documents to {args.output}")


if __name__ == "__main__":
    main()
