# csl-mvp

## Setup

This project uses Python 3.11 and a local virtual environment inside the repository.

### Clone repository

```bash
git clone https://github.com/xinyili0603/Big_Co_Team_9.git
cd csl-mvp
```

### Create virtual environment (Python 3.11)

```bash
python3.11 -m venv .venv
```

### Activate virtual environment

Mac/Linux:

```bash
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Install SciSpacy model

```bash
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
```

## Run Pipeline

### Step 1: Ingest PubMed data

```bash
python src/ingestion.py --keywords hemophilia plasma hematology --max_docs 50 --output data/raw_documents.json
```

### Step 2: Validate data

```bash
python src/validate_raw_documents.py --input data/raw_documents.json --output data/raw_documents_summary.json
```

### Step 3: Extract entities

```bash
python src/ner.py --input data/raw_documents.json --output data/entities.json
```

### Step 4: Clean entities

```bash
python src/clean_entities.py --input data/entities.json --output data/entities_cleaned.json
```

### Step 5: Extract relations

```bash
python src/relation_extraction.py --documents data/raw_documents.json --entities data/entities_cleaned.json --output data/triples_model_primary.json
```

## Example Outputs

### Example: Raw PubMed Document

```json
{
  "id": "41953841",
  "type": "pubmed",
  "title": "Screening chemical libraries for the development of oral treatments for bleeding disorders.",
  "abstract": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively. Treatment has long relied on invasive IV infusions... These studies conclude that the procoagulant activity of the chemical compounds in FVIII-deficient plasma is due to the activation of FXII.",
  "claims": null,
  "assignee": null,
  "inventors": [
    "Renaud Zelli",
    "Landry Seyve"
  ],
  "publication_date": "2026-05-01"
}
```

### Example: Extracted Entities

```json
[
  {
    "entity_id": "10dee9df-0378-4421-854c-84f38c53ad33",
    "document_id": "41953841",
    "type": "disease",
    "name": "Hemophilia",
    "normalized_name": "hemophilia",
    "sentence": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively."
  },
  {
    "entity_id": "c1ce6802-e45b-4f5b-8d0c-83411b0d4f4f",
    "document_id": "41953841",
    "type": "protein",
    "name": "factor VIII",
    "normalized_name": "factor viii",
    "sentence": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively."
  },
  {
    "entity_id": "5706a3f9-e9ca-45d2-a0af-b22414cc89fd",
    "document_id": "41953841",
    "type": "compound",
    "name": "adapalene",
    "normalized_name": "adapalene",
    "sentence": "We screened 3 chemical collections totaling > 2300 chemical compounds; we identified adapalene, a commercialized antiacneic compound (Differin), which is strongly hydrophobic."
  }
]
```

### Example: Cleaned Entities

The cleaning step removes `unknown` entities and keeps typed spans for downstream relation extraction.

```json
[
  {
    "entity_id": "10dee9df-0378-4421-854c-84f38c53ad33",
    "document_id": "41953841",
    "type": "disease",
    "name": "Hemophilia",
    "normalized_name": "hemophilia",
    "sentence": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively."
  },
  {
    "entity_id": "c1ce6802-e45b-4f5b-8d0c-83411b0d4f4f",
    "document_id": "41953841",
    "type": "protein",
    "name": "factor VIII",
    "normalized_name": "factor viii",
    "sentence": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively."
  }
]
```

### Example: Extracted Relationships

```json
[
  {
    "subject_id": "doc:41953841",
    "predicate": "MENTIONS",
    "object_id": "10dee9df-0378-4421-854c-84f38c53ad33",
    "source_sentence": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively.",
    "document_id": "41953841"
  },
  {
    "subject_id": "doc:41953841",
    "predicate": "MENTIONS",
    "object_id": "c1ce6802-e45b-4f5b-8d0c-83411b0d4f4f",
    "source_sentence": "Hemophilia is a rare bleeding disorder due to factor VIII (FVIII) or FIX deficiency involved in hemophilia A (HA) or HB, respectively.",
    "document_id": "41953841"
  },
  {
    "subject_id": "doc:41953841",
    "predicate": "AUTHORED_BY",
    "object_id": "f74dd11f-5103-41c4-ab00-e20744f2c22a",
    "source_sentence": "",
    "document_id": "41953841"
  }
]
```

### Pipeline Summary (Command Line Output)

```text
$ python src/ingestion.py --keywords hemophilia plasma hematology --max_docs 50 --output data/raw_documents.json
Found 50 PMIDs
Skipped 3 documents with no abstract
Saved 47 documents to data/raw_documents.json

$ python src/validate_raw_documents.py --input data/raw_documents.json --output data/raw_documents_summary.json
Validation summary
Total documents: 47
Unique PMIDs: 47
Missing titles: 0
Missing abstracts: 0
Missing publication dates: 0
Short abstracts (<200 chars): 0
Average abstract length (chars): 1718.32
Average abstract length (words): 241.53
Suspicious document IDs: []

$ python src/ner.py --input data/raw_documents.json --output data/entities.json
Loaded 47 documents
Total entities extracted: 4346
compound: 34
disease: 105
gene: 10
organization: 1
protein: 97
researcher: 385
unknown: 3714
Saved entities to data/entities.json

$ python src/clean_entities.py --input data/entities.json --output data/entities_cleaned.json
Original entity count: 4346
Cleaned entity count: 632
Removed unknown count: 3714
Removed duplicate count: 0
Removed blacklist count: 0
Removed malformed count: 0
Final counts by entity type:
- compound: 34
- disease: 105
- gene: 10
- organization: 1
- protein: 97
- researcher: 385
Saved cleaned entities to data/entities_cleaned.json

$ python src/relation_extraction.py --documents data/raw_documents.json --entities data/entities_cleaned.json --output data/triples_model_primary.json
Total triples: 638
MENTIONS: 247
AUTHORED_BY: 385
TREATS: 3
ASSOCIATED_WITH: 3
ACTIVATES: 0
Candidate semantic relations considered: 11
Semantic relations accepted: 6
Saved triples to data/triples_model_primary.json
```

## Notes

- Always activate the virtual environment before running scripts.
- Do NOT commit `.venv/`, `.env`, or `data/*.json`.
- Use Python 3.11 (required for SciSpacy compatibility).
- If installation fails, ensure pip is updated:

```bash
python -m pip install --upgrade pip
```
