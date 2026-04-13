"""Build conservative first-pass relation triples from cleaned entities."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


TREATMENT_TRIGGERS = (
    "treat",
    "treats",
    "treated",
    "treatment",
    "therapy",
    "therapeutic",
    "prophylaxis",
    "prophylactic",
    "preventive",
    "prevent",
    "prevention",
    "indicated for",
    "used in",
    "used for",
    "benefit in",
    "improve",
    "improves",
    "improved",
    "effective in",
    "efficacy in",
)
ASSOCIATION_TRIGGERS = (
    "associated with",
    "linked to",
    "related to",
    "involved in",
    "implicated in",
    "due to",
    "deficiency",
    "deficiency of",
    "elevated in",
    "reduced in",
    "marker of",
    "characteristic of",
)
COMPOUND_PROTEIN_ASSOCIATION_TRIGGERS = (
    "activate",
    "activation",
    "inhibit",
    "inhibition",
    "target",
    "binds",
    "modulate",
    "affects",
    "dependent on",
    "due to",
)
ACTIVATION_TRIGGERS = (
    "activates",
    "activation",
    "activation of",
    "induces",
    "triggers",
    "stimulates",
)
MAX_TREATMENT_SENTENCE_LENGTH = 420
MAX_COMPOUND_PROTEIN_SENTENCE_LENGTH = 280


def load_json(input_path: str) -> list[dict]:
    """Load a JSON list from disk."""
    with open(input_path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def save_json(records: list[dict], output_path: str) -> None:
    """Write a JSON list to disk."""
    output_file_path = Path(output_path)
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    with output_file_path.open("w", encoding="utf-8") as output_file:
        json.dump(records, output_file, indent=2, ensure_ascii=False)


def build_mentions_triples(entities: list[dict], valid_document_ids: set[str]) -> list[dict]:
    """Create DOCUMENT -> MENTIONS -> entity triples."""
    triples: list[dict] = []

    for entity in entities:
        document_id = str(entity.get("document_id", "")).strip()
        if not document_id or document_id not in valid_document_ids:
            continue
        if entity["type"] == "researcher":
            continue

        triples.append(
            {
                "subject_id": f"doc:{document_id}",
                "predicate": "MENTIONS",
                "object_id": entity["entity_id"],
                "source_sentence": entity["sentence"],
                "document_id": document_id,
            }
        )

    return triples


def group_entities_by_sentence(entities: list[dict], valid_document_ids: set[str]) -> dict[tuple[str, str], list[dict]]:
    """Group cleaned entities by document and exact sentence."""
    entities_by_sentence: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for entity in entities:
        document_id = str(entity.get("document_id", "")).strip()
        sentence = str(entity.get("sentence", "")).strip()
        if not document_id or document_id not in valid_document_ids or not sentence:
            continue
        entities_by_sentence[(document_id, sentence)].append(entity)

    return entities_by_sentence


def build_authored_by_triples(entities: list[dict], valid_document_ids: set[str]) -> list[dict]:
    """Create DOCUMENT -> AUTHORED_BY -> researcher triples."""
    triples: list[dict] = []

    for entity in entities:
        document_id = str(entity.get("document_id", "")).strip()
        if not document_id or document_id not in valid_document_ids:
            continue
        if entity["type"] != "researcher":
            continue

        triples.append(
            {
                "subject_id": f"doc:{document_id}",
                "predicate": "AUTHORED_BY",
                "object_id": entity["entity_id"],
                "source_sentence": "",
                "document_id": document_id,
            }
        )

    return triples


def sentence_has_treatment_trigger(sentence: str) -> bool:
    """Return True when a sentence contains a conservative treatment cue."""
    normalized_sentence = sentence.lower()
    return any(trigger in normalized_sentence for trigger in TREATMENT_TRIGGERS)


def sentence_has_association_trigger(sentence: str) -> bool:
    """Return True when a sentence contains a conservative association cue."""
    normalized_sentence = sentence.lower()
    return any(trigger in normalized_sentence for trigger in ASSOCIATION_TRIGGERS)


def sentence_has_activation_trigger(sentence: str) -> bool:
    """Return True when a sentence contains a conservative activation cue."""
    normalized_sentence = sentence.lower()
    return any(trigger in normalized_sentence for trigger in ACTIVATION_TRIGGERS)


def sentence_has_compound_protein_trigger(sentence: str) -> bool:
    """Return True when a sentence contains a compound-protein association cue."""
    normalized_sentence = sentence.lower()
    return any(trigger in normalized_sentence for trigger in COMPOUND_PROTEIN_ASSOCIATION_TRIGGERS)


def is_ambiguous_sentence(
    entities: list[dict],
    allowed_types: set[str],
    max_per_type: int = 2,
    max_total: int = 4,
) -> bool:
    """Treat crowded sentences as ambiguous for conservative extraction."""
    counts = Counter(entity["type"] for entity in entities if entity["type"] in allowed_types)
    return any(count > max_per_type for count in counts.values()) or sum(counts.values()) > max_total


def find_trigger_position(sentence: str, triggers: tuple[str, ...]) -> int:
    """Return the earliest trigger position, or -1 if none is present."""
    normalized_sentence = sentence.lower()
    positions = [normalized_sentence.find(trigger) for trigger in triggers if trigger in normalized_sentence]
    return min(positions) if positions else -1


def build_treats_triples(entities: list[dict], valid_document_ids: set[str]) -> tuple[list[dict], int]:
    """Create COMPOUND -> TREATS -> DISEASE triples from same-sentence co-occurrence."""
    entities_by_sentence = group_entities_by_sentence(entities, valid_document_ids)
    triples: list[dict] = []
    candidate_count = 0

    for (document_id, sentence), sentence_entities in entities_by_sentence.items():
        if not sentence_has_treatment_trigger(sentence):
            continue
        if len(sentence) > MAX_TREATMENT_SENTENCE_LENGTH:
            continue

        compounds = [entity for entity in sentence_entities if entity["type"] == "compound"]
        diseases = [entity for entity in sentence_entities if entity["type"] == "disease"]
        if not compounds or not diseases:
            continue
        if is_ambiguous_sentence(sentence_entities, {"compound", "disease"}, max_per_type=2, max_total=4):
            continue

        candidate_count += len(compounds) * len(diseases)
        for compound in compounds:
            for disease in diseases:
                triples.append(
                    {
                        "subject_id": compound["entity_id"],
                        "predicate": "TREATS",
                        "object_id": disease["entity_id"],
                        "source_sentence": sentence,
                        "document_id": document_id,
                    }
                )

    return triples, candidate_count


def build_associated_with_triples(entities: list[dict], valid_document_ids: set[str]) -> tuple[list[dict], int]:
    """Create PROTEIN -> ASSOCIATED_WITH -> DISEASE triples from same-sentence cues."""
    entities_by_sentence = group_entities_by_sentence(entities, valid_document_ids)
    triples: list[dict] = []
    candidate_count = 0

    for (document_id, sentence), sentence_entities in entities_by_sentence.items():
        normalized_sentence = sentence.lower()

        if sentence_has_association_trigger(sentence):
            proteins = [entity for entity in sentence_entities if entity["type"] == "protein"]
            diseases = [entity for entity in sentence_entities if entity["type"] == "disease"]
            if proteins and diseases and not is_ambiguous_sentence(sentence_entities, {"protein", "disease"}, max_per_type=2, max_total=4):
                candidate_count += len(proteins) * len(diseases)
                for protein in proteins:
                    protein_name = protein["name"].lower()
                    protein_pos = normalized_sentence.find(protein_name)
                    if protein_pos == -1:
                        continue

                    for disease in diseases:
                        disease_name = disease["name"].lower()
                        disease_pos = normalized_sentence.find(disease_name)
                        if disease_pos == -1 or protein["entity_id"] == disease["entity_id"]:
                            continue

                        is_supported_pair = False
                        for phrase in ("associated with", "linked to", "related to", "involved in", "implicated in", "elevated in", "reduced in", "marker of", "characteristic of"):
                            phrase_pos = normalized_sentence.find(phrase)
                            if phrase_pos != -1 and protein_pos < phrase_pos and disease_pos > phrase_pos:
                                is_supported_pair = True
                                break

                        if not is_supported_pair and "due to" in normalized_sentence:
                            due_to_pos = normalized_sentence.find("due to")
                            if disease_pos < due_to_pos and protein_pos > due_to_pos:
                                is_supported_pair = True

                        if not is_supported_pair and "deficiency of" in normalized_sentence:
                            deficiency_of_pos = normalized_sentence.find("deficiency of")
                            if protein_pos > deficiency_of_pos and disease_pos < deficiency_of_pos:
                                is_supported_pair = True

                        if not is_supported_pair and "deficiency" in normalized_sentence and disease_name.endswith("deficiency") and protein_name in disease_name:
                            is_supported_pair = True

                        if not is_supported_pair:
                            continue

                        triples.append(
                            {
                                "subject_id": protein["entity_id"],
                                "predicate": "ASSOCIATED_WITH",
                                "object_id": disease["entity_id"],
                                "source_sentence": sentence,
                                "document_id": document_id,
                            }
                        )

        if sentence_has_compound_protein_trigger(sentence) and len(sentence) <= MAX_COMPOUND_PROTEIN_SENTENCE_LENGTH:
            compounds = [entity for entity in sentence_entities if entity["type"] == "compound"]
            proteins = [entity for entity in sentence_entities if entity["type"] == "protein"]
            if compounds and proteins and not is_ambiguous_sentence(sentence_entities, {"compound", "protein"}, max_per_type=2, max_total=4):
                candidate_count += len(compounds) * len(proteins)
                for compound in compounds:
                    for protein in proteins:
                        triples.append(
                            {
                                "subject_id": compound["entity_id"],
                                "predicate": "ASSOCIATED_WITH",
                                "object_id": protein["entity_id"],
                                "source_sentence": sentence,
                                "document_id": document_id,
                            }
                        )

    return triples, candidate_count


def build_activates_triples(entities: list[dict], valid_document_ids: set[str]) -> tuple[list[dict], int]:
    """Create PROTEIN -> ACTIVATES -> PROTEIN triples from same-sentence cues."""
    entities_by_sentence = group_entities_by_sentence(entities, valid_document_ids)
    triples: list[dict] = []
    candidate_count = 0

    for (document_id, sentence), sentence_entities in entities_by_sentence.items():
        if not sentence_has_activation_trigger(sentence):
            continue

        proteins = [entity for entity in sentence_entities if entity["type"] == "protein"]
        if len(proteins) < 2 or len(proteins) > 3:
            continue

        normalized_sentence = sentence.lower()
        trigger_pos = find_trigger_position(sentence, ACTIVATION_TRIGGERS)
        if trigger_pos == -1:
            continue

        candidate_count += len(proteins) * (len(proteins) - 1)
        before = [
            entity
            for entity in proteins
            if normalized_sentence.find(entity["name"].lower()) != -1
            and normalized_sentence.find(entity["name"].lower()) < trigger_pos
        ]
        after = [
            entity
            for entity in proteins
            if normalized_sentence.find(entity["name"].lower()) != -1
            and normalized_sentence.find(entity["name"].lower()) > trigger_pos
        ]

        subject = None
        object_ = None
        if before and after:
            subject = max(before, key=lambda entity: normalized_sentence.find(entity["name"].lower()))
            object_ = min(after, key=lambda entity: normalized_sentence.find(entity["name"].lower()))

        if not subject or not object_:
            continue

        triples.append(
            {
                "subject_id": subject["entity_id"],
                "predicate": "ACTIVATES",
                "object_id": object_["entity_id"],
                "source_sentence": sentence,
                "document_id": document_id,
            }
        )

    return triples, candidate_count


def deduplicate_triples(triples: list[dict]) -> list[dict]:
    """Deduplicate triples by their full identifying fields."""
    deduplicated: list[dict] = []
    seen_keys: set[tuple[str, str, str, str, str]] = set()

    for triple in triples:
        key = (
            triple["subject_id"],
            triple["predicate"],
            triple["object_id"],
            triple["source_sentence"],
            triple["document_id"],
        )
        if key in seen_keys:
            continue

        seen_keys.add(key)
        deduplicated.append(triple)

    return deduplicated


def build_triples(documents: list[dict], entities: list[dict]) -> tuple[list[dict], int]:
    """Build conservative first-pass triples."""
    valid_document_ids = {str(document.get("id", "")).strip() for document in documents if str(document.get("id", "")).strip()}

    treats_triples, treats_candidates = build_treats_triples(entities, valid_document_ids)
    associated_triples, associated_candidates = build_associated_with_triples(entities, valid_document_ids)
    activates_triples, activates_candidates = build_activates_triples(entities, valid_document_ids)

    triples = []
    triples.extend(build_mentions_triples(entities, valid_document_ids))
    triples.extend(build_authored_by_triples(entities, valid_document_ids))
    triples.extend(treats_triples)
    triples.extend(associated_triples)
    triples.extend(activates_triples)
    semantic_candidate_count = treats_candidates + associated_candidates + activates_candidates
    return deduplicate_triples(triples), semantic_candidate_count


def main() -> None:
    """Run relation extraction from the command line."""
    parser = argparse.ArgumentParser(description="Build conservative first-pass relation triples.")
    parser.add_argument("--documents", required=True, help="Path to raw documents JSON.")
    parser.add_argument("--entities", required=True, help="Path to cleaned entities JSON.")
    parser.add_argument("--output", required=True, help="Path to triples JSON output.")
    args = parser.parse_args()

    documents = load_json(args.documents)
    entities = load_json(args.entities)
    triples, semantic_candidate_count = build_triples(documents, entities)
    save_json(triples, args.output)

    predicate_counts = Counter(triple["predicate"] for triple in triples)
    semantic_predicates = {"TREATS", "ASSOCIATED_WITH", "ACTIVATES"}
    accepted_semantic_count = sum(1 for triple in triples if triple["predicate"] in semantic_predicates)
    print(f"Total triples: {len(triples)}")
    for predicate in ("MENTIONS", "AUTHORED_BY", "TREATS", "ASSOCIATED_WITH", "ACTIVATES"):
        print(f"{predicate}: {predicate_counts.get(predicate, 0)}")
    print(f"Candidate semantic relations considered: {semantic_candidate_count}")
    print(f"Semantic relations accepted: {accepted_semantic_count}")
    print(f"Saved triples to {args.output}")


if __name__ == "__main__":
    main()
