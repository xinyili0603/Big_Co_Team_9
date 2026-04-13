"""Validate ingested raw PubMed documents and summarize data quality."""

import argparse
import json
from pathlib import Path


def load_documents(input_path: str) -> list[dict]:
    """Load raw document records from a JSON file."""
    with open(input_path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def is_missing(value: object) -> bool:
    """Return True when a field is missing or empty after trimming."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    return not value.strip()


def format_sample_record(document: dict) -> str:
    """Format one record for readable console output."""
    abstract = (document.get("abstract") or "").strip()
    preview = abstract[:160].replace("\n", " ")
    if len(abstract) > 160:
        preview += "..."

    return (
        f"- id: {document.get('id', '')}\n"
        f"  title: {(document.get('title') or '').strip()}\n"
        f"  publication_date: {(document.get('publication_date') or '').strip()}\n"
        f"  abstract_chars: {len(abstract)}\n"
        f"  abstract_preview: {preview}"
    )


def summarize_documents(documents: list[dict]) -> dict:
    """Compute validation metrics for raw documents."""
    total_documents = len(documents)
    unique_ids = len({str(doc.get("id", "")).strip() for doc in documents if str(doc.get("id", "")).strip()})
    missing_titles = 0
    missing_abstracts = 0
    missing_publication_dates = 0
    short_abstracts = 0
    suspicious_document_ids: list[str] = []
    total_abstract_chars = 0
    total_abstract_words = 0

    for document in documents:
        doc_id = str(document.get("id", "")).strip()
        title = document.get("title")
        abstract = document.get("abstract")
        publication_date = document.get("publication_date")

        title_missing = is_missing(title)
        abstract_missing = is_missing(abstract)
        publication_date_missing = is_missing(publication_date)
        abstract_text = "" if abstract_missing else str(abstract).strip()
        abstract_is_short = bool(abstract_text) and len(abstract_text) < 200

        if title_missing:
            missing_titles += 1
        if abstract_missing:
            missing_abstracts += 1
        if publication_date_missing:
            missing_publication_dates += 1
        if abstract_is_short:
            short_abstracts += 1

        if abstract_text:
            total_abstract_chars += len(abstract_text)
            total_abstract_words += len(abstract_text.split())

        if title_missing or abstract_missing or abstract_is_short or publication_date_missing:
            suspicious_document_ids.append(doc_id)

    avg_abstract_chars = round(total_abstract_chars / total_documents, 2) if total_documents else 0.0
    avg_abstract_words = round(total_abstract_words / total_documents, 2) if total_documents else 0.0

    return {
        "total_documents": total_documents,
        "unique_ids": unique_ids,
        "missing_titles": missing_titles,
        "missing_abstracts": missing_abstracts,
        "missing_publication_dates": missing_publication_dates,
        "short_abstracts": short_abstracts,
        "avg_abstract_chars": avg_abstract_chars,
        "avg_abstract_words": avg_abstract_words,
        "suspicious_document_ids": suspicious_document_ids,
    }


def save_summary(summary: dict, output_path: str) -> None:
    """Write the validation summary JSON."""
    output_file_path = Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    with output_file_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, indent=2, ensure_ascii=False)


def main() -> None:
    """Run validation from the command line."""
    parser = argparse.ArgumentParser(description="Validate raw PubMed JSON documents.")
    parser.add_argument("--input", required=True, help="Path to the raw documents JSON file.")
    parser.add_argument("--output", required=True, help="Path to the summary JSON output file.")
    args = parser.parse_args()

    documents = load_documents(args.input)
    summary = summarize_documents(documents)
    save_summary(summary, args.output)

    print("Validation summary")
    print(f"Total documents: {summary['total_documents']}")
    print(f"Unique PMIDs: {summary['unique_ids']}")
    print(f"Missing titles: {summary['missing_titles']}")
    print(f"Missing abstracts: {summary['missing_abstracts']}")
    print(f"Missing publication dates: {summary['missing_publication_dates']}")
    print(f"Short abstracts (<200 chars): {summary['short_abstracts']}")
    print(f"Average abstract length (chars): {summary['avg_abstract_chars']}")
    print(f"Average abstract length (words): {summary['avg_abstract_words']}")
    print(f"Suspicious document IDs: {summary['suspicious_document_ids']}")
    print("")
    print("Sample records")
    for index, document in enumerate(documents[:3], start=1):
        print(f"Record {index}")
        print(format_sample_record(document))
    print("")
    print(f"Summary written to {args.output}")


if __name__ == "__main__":
    main()
