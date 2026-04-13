"""Clean extracted entities for downstream relation extraction."""

import argparse
import json
from collections import Counter
from pathlib import Path


BLACKLIST = {
    "study",
    "studies",
    "patient",
    "patients",
    "data",
    "level",
    "levels",
    "groups",
    "hours",
    "management",
    "outcomes",
    "safety",
    "literature",
    "classification",
    "progress",
    "benefits",
    "tested",
}
FUNCTION_WORD_ENDINGS = {
    "and",
    "or",
    "of",
    "for",
    "with",
    "to",
    "in",
    "on",
    "by",
    "from",
    "into",
    "at",
    "as",
}
BOUNDARY_ARTIFACTS = {".", "?", "!", ";", ":"}
MAX_NAME_LENGTH = 80


def load_entities(input_path: str) -> list[dict]:
    """Load entity records from JSON."""
    with open(input_path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def save_entities(entities: list[dict], output_path: str) -> None:
    """Write cleaned entity records to JSON."""
    output_file_path = Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    with output_file_path.open("w", encoding="utf-8") as output_file:
        json.dump(entities, output_file, indent=2, ensure_ascii=False)


def has_sentence_boundary_artifact(name: str) -> bool:
    """Return True for likely sentence-boundary or punctuation artifacts."""
    stripped = name.strip()
    if not stripped:
        return True
    if "\n" in stripped:
        return True
    if any(marker in stripped for marker in (" .", " ?", " !")):
        return True
    if stripped[0] in BOUNDARY_ARTIFACTS or stripped[-1] in BOUNDARY_ARTIFACTS:
        return True
    return False


def ends_with_function_word(name: str) -> bool:
    """Return True when a span ends with an obvious function word."""
    tokens = name.strip().lower().split()
    return bool(tokens) and tokens[-1] in FUNCTION_WORD_ENDINGS


def is_blacklisted(entity: dict) -> bool:
    """Return True when an entity is a generic low-value term."""
    normalized_name = str(entity.get("normalized_name", "")).strip().lower()
    return normalized_name in BLACKLIST


def is_malformed(entity: dict) -> bool:
    """Return True when an entity span is likely a bad extraction."""
    name = str(entity.get("name", "")).strip()
    entity_type = str(entity.get("type", "")).strip().lower()

    if has_sentence_boundary_artifact(name):
        return True
    if ends_with_function_word(name):
        return True
    if entity_type != "researcher" and len(name) > MAX_NAME_LENGTH:
        return True
    return False


def dedupe_key(entity: dict) -> tuple[str, str, str, str]:
    """Build the deduplication key."""
    return (
        str(entity.get("document_id", "")).strip(),
        str(entity.get("normalized_name", "")).strip(),
        str(entity.get("type", "")).strip(),
        str(entity.get("sentence", "")).strip(),
    )


def clean_entities(entities: list[dict]) -> tuple[list[dict], dict]:
    """Apply filtering and deduplication to entity records."""
    cleaned_entities: list[dict] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    removed_unknown_count = 0
    removed_duplicate_count = 0
    removed_blacklist_count = 0
    removed_malformed_count = 0

    for entity in entities:
        entity_type = str(entity.get("type", "")).strip().lower()

        if entity_type == "unknown":
            removed_unknown_count += 1
            continue

        if is_blacklisted(entity):
            removed_blacklist_count += 1
            continue

        if is_malformed(entity):
            removed_malformed_count += 1
            continue

        key = dedupe_key(entity)
        if key in seen_keys:
            removed_duplicate_count += 1
            continue

        seen_keys.add(key)
        cleaned_entities.append(
            {
                "entity_id": entity["entity_id"],
                "document_id": entity["document_id"],
                "type": entity["type"],
                "name": entity["name"],
                "normalized_name": entity["normalized_name"],
                "sentence": entity["sentence"],
            }
        )

    summary = {
        "original_entity_count": len(entities),
        "cleaned_entity_count": len(cleaned_entities),
        "removed_unknown_count": removed_unknown_count,
        "removed_duplicate_count": removed_duplicate_count,
        "removed_blacklist_count": removed_blacklist_count,
        "removed_malformed_count": removed_malformed_count,
        "final_counts_by_type": dict(sorted(Counter(entity["type"] for entity in cleaned_entities).items())),
    }
    return cleaned_entities, summary


def main() -> None:
    """Run entity cleanup from the command line."""
    parser = argparse.ArgumentParser(description="Clean extracted entities for downstream use.")
    parser.add_argument("--input", required=True, help="Path to input entities JSON.")
    parser.add_argument("--output", required=True, help="Path to cleaned entities JSON.")
    args = parser.parse_args()

    entities = load_entities(args.input)
    cleaned_entities, summary = clean_entities(entities)
    save_entities(cleaned_entities, args.output)

    print(f"Original entity count: {summary['original_entity_count']}")
    print(f"Cleaned entity count: {summary['cleaned_entity_count']}")
    print(f"Removed unknown count: {summary['removed_unknown_count']}")
    print(f"Removed duplicate count: {summary['removed_duplicate_count']}")
    print(f"Removed blacklist count: {summary['removed_blacklist_count']}")
    print(f"Removed malformed count: {summary['removed_malformed_count']}")
    print("Final counts by entity type:")
    for entity_type, count in summary["final_counts_by_type"].items():
        print(f"- {entity_type}: {count}")
    print(f"Saved cleaned entities to {args.output}")


if __name__ == "__main__":
    main()
