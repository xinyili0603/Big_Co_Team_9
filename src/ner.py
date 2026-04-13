"""Extract first-pass entities from PubMed abstracts with SciSpacy."""

import argparse
import json
import uuid
from collections import Counter
from pathlib import Path


MODEL_NAME = "en_core_sci_sm"
LABEL_TO_TYPE = {
    "disease": "disease",
    "diseases": "disease",
    "chemical": "compound",
    "simple_chemical": "compound",
    "drug": "compound",
    "gene": "gene",
    "dna": "gene",
    "rna": "gene",
    "gene_or_gene_product": "gene",
    "protein": "protein",
    "org": "organization",
    "organization": "organization",
}
KNOWN_PROTEINS = {"fviii", "fix", "fxii", "vwf"}
KNOWN_GENES = {"f8", "f9", "f12"}
KNOWN_DISEASES = {
    "hemophilia",
    "hemophilia a",
    "hemophilia b",
    "haemophilia a",
    "haemophilia b",
    "von willebrand disease",
}
KNOWN_COMPOUNDS = {
    "adapalene",
    "differin",
    "emicizumab",
    "efmoroctocog alfa",
    "rurioctocog alfa pegol",
    "heparin",
    "epsilon-aminocaproic acid",
}
ORG_SUFFIXES = (
    "inc",
    "ltd",
    "llc",
    "corp",
    "corporation",
    "company",
    "university",
    "hospital",
    "institute",
)


def load_documents(input_path: str) -> list[dict]:
    """Load raw PubMed documents from JSON."""
    with open(input_path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def normalize_text(text: str) -> str:
    """Lowercase and trim whitespace."""
    return " ".join(text.strip().lower().split())


def preprocess_abstract(text: str) -> str:
    """Clean abstract whitespace before NLP processing."""
    return " ".join((text or "").split()).strip()


def load_nlp():
    """Load the SciSpacy pipeline."""
    try:
        import scispacy  # noqa: F401
        import spacy
    except ImportError as exc:
        raise SystemExit(
            "SciSpacy is not installed. Install it first, then download the en_core_sci_sm model."
        ) from exc

    try:
        nlp = spacy.load(MODEL_NAME)
    except OSError as exc:
        raise SystemExit(
            "SciSpacy model 'en_core_sci_sm' is not installed. Download the model and retry."
        ) from exc

    if "parser" not in nlp.pipe_names and "senter" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")

    return nlp


def map_entity_type(label: str, name: str) -> str:
    """Map SciSpacy labels into the project entity schema."""
    mapped = LABEL_TO_TYPE.get(label.lower())
    if mapped:
        return mapped

    normalized = normalize_text(name)
    if normalized in KNOWN_DISEASES:
        return "disease"
    if any(token in normalized for token in ("disease", "disorder", "syndrome", "deficiency")):
        return "disease"
    if normalized in KNOWN_COMPOUNDS:
        return "compound"
    if normalized.startswith("factor ") or normalized in KNOWN_PROTEINS or " protein" in normalized:
        return "protein"
    if normalized.startswith("gene ") or normalized.endswith(" gene") or normalized in KNOWN_GENES:
        return "gene"
    if normalized.endswith(("mab", "nib")) or " alfa" in normalized or " pegol" in normalized:
        return "compound"
    if any(normalized.endswith(suffix) for suffix in ORG_SUFFIXES):
        return "organization"
    return "unknown"


def build_entity(document_id: str, entity_type: str, name: str, sentence: str) -> dict:
    """Build one entity record in the required output schema."""
    return {
        "entity_id": str(uuid.uuid4()),
        "document_id": document_id,
        "type": entity_type,
        "name": name,
        "normalized_name": normalize_text(name),
        "sentence": sentence,
    }


def extract_text_entities(document_id: str, abstract: str, nlp) -> list[dict]:
    """Extract sentence-level entities from an abstract with SciSpacy."""
    doc = nlp(abstract)
    entities: list[dict] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for sentence in doc.sents:
        sentence_text = sentence.text.strip()
        if not sentence_text:
            continue

        for ent in sentence.ents:
            name = ent.text.strip()
            if not name:
                continue

            entity_type = map_entity_type(ent.label_, name)
            key = (entity_type, normalize_text(name), sentence_text)
            if key in seen_keys:
                continue

            seen_keys.add(key)
            entities.append(build_entity(document_id, entity_type, name, sentence_text))

    return entities


def extract_researcher_entities(document: dict) -> list[dict]:
    """Create researcher entities from document metadata."""
    document_id = str(document.get("id", "")).strip()
    researchers = document.get("inventors") or []
    entities: list[dict] = []
    seen_names: set[str] = set()

    for researcher in researchers:
        name = str(researcher).strip()
        normalized = normalize_text(name)
        if not normalized or normalized in seen_names:
            continue

        seen_names.add(normalized)
        entities.append(build_entity(document_id, "researcher", name, ""))

    return entities


def extract_entities(documents: list[dict], nlp) -> list[dict]:
    """Extract text entities from abstracts plus researcher metadata entities."""
    all_entities: list[dict] = []

    for document in documents:
        document_id = str(document.get("id", "")).strip()
        abstract = preprocess_abstract(document.get("abstract", ""))

        if abstract:
            all_entities.extend(extract_text_entities(document_id, abstract, nlp))

        all_entities.extend(extract_researcher_entities(document))

    return all_entities


def save_entities(entities: list[dict], output_path: str) -> None:
    """Write entities to a JSON file."""
    output_file_path = Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    with output_file_path.open("w", encoding="utf-8") as output_file:
        json.dump(entities, output_file, indent=2, ensure_ascii=False)


def main() -> None:
    """Run SciSpacy-based entity extraction."""
    parser = argparse.ArgumentParser(description="Extract first-pass entities from PubMed abstracts.")
    parser.add_argument("--input", required=True, help="Path to raw PubMed documents JSON.")
    parser.add_argument("--output", required=True, help="Path to entity JSON output.")
    args = parser.parse_args()

    documents = load_documents(args.input)
    nlp = load_nlp()
    entities = extract_entities(documents, nlp)
    save_entities(entities, args.output)

    counts = Counter(entity["type"] for entity in entities)
    print(f"Loaded {len(documents)} documents")
    print(f"Total entities extracted: {len(entities)}")
    for entity_type in sorted(counts):
        print(f"{entity_type}: {counts[entity_type]}")
    print(f"Saved entities to {args.output}")


if __name__ == "__main__":
    main()
