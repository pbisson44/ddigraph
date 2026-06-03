# DDI Schemas

This directory contains official DDI Alliance schemas for three DDI families.

## Schema Families

| Family | Directory | Source | Version |
| ------ | --------- | ------ | ------- |
| **DDI-Lifecycle** | `ddi/` | [ddialliance/ddi-l_3](https://github.com/ddialliance/ddi-l_3) | 3.3 |
| **DDI-Codebook** | `ddi-c/` | [ddialliance/ddi-c_2](https://github.com/ddialliance/ddi-c_2) | 2.6 |
| **DDI-CDI** | `ddi-cdi/` | [ddi-cdi/ddi-cdi](https://github.com/ddi-cdi/ddi-cdi) | 1.0 |

### DDI-Lifecycle (DDI-L)

DDI-Lifecycle 3.3 XML Schemas covering versions 3.1, 3.2, and 3.3. Used by the
FragmentInstance loader for questionnaire flow, control constructs, and
instrument metadata.

### DDI-Codebook (DDI-C)

DDI-Codebook 2.6 XML Schema (`codebook.xsd`) plus supporting Dublin Core and
XHTML module schemas. Used by the Codebook loader for study-level metadata,
variables, questions, and code schemes.

### DDI-CDI

DDI Cross-Domain Integration 1.0 XML Schema and OWL/Turtle ontology. Provides
a domain-independent model for research data documentation spanning multiple
DDI lineages.

## Updating Schemas

The helper script `scripts/update_schemas.py` refreshes this directory from the
official repositories.

```bash
# Update all schema families
python scripts/update_schemas.py

# Update a single family
python scripts/update_schemas.py --family ddi-l
python scripts/update_schemas.py --family ddi-c
python scripts/update_schemas.py --family ddi-cdi

# Force re-download (ignore cache)
python scripts/update_schemas.py --force-download

# Validate schemas against the manifest (used in CI)
python scripts/update_schemas.py --check
```

The file-level checksums in `manifest.json` pin the expected contents per family
and are validated by `--check`.

## Licensing

See the included `license.txt` for DDI-L schema usage terms. DDI-C and DDI-CDI
schemas are published under Creative Commons Attribution 4.0 International
(CC-BY-4.0) by the DDI Alliance.
