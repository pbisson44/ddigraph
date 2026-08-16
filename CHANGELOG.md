# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## 0.5.0 — unreleased

Makes the RDF story real. The package advertised five graph backends and
shipped one, and the RDF surface that did exist was spread across four
mutually inconsistent namespaces and three predicate conventions, so
nothing it produced could be joined to anyone else's data. This release
settles the vocabulary, gives every DDI flavor one graph shape, and
removes the CLI verbs deprecated in 0.4.0rc1.

This entry grows as the release lands; it is not yet dated or published.

### Added

- **Backend-neutral graph view** (`ddigraph.graph.view`). `iter_graph()`
  streams any DDI file as `GraphChunk` values built from the existing
  `Node` and `Relationship` dataclasses, so exporters, previewers and
  validators target one shape instead of three. Previously only
  DDI-Codebook had such a projection, which is why every `demo/load_*.py`
  script works on DDI-L alone.
- **DDI-CDI reaches the graph tier for the first time.** It was
  parse-only: `api.aload` raises `NotImplementedError` for it, no adapter
  writes it, and the CLI has no `cdi` format choice, so a parsed CDI file
  had nowhere to go. It now projects to the same nodes and relationships
  as the other two flavors.
- **A defined RDF vocabulary** (`ddigraph.rdf.vocabulary`). One project
  namespace, versioned independently of the package, aligned to the DDI
  Alliance's own published RDF work: DISCO for
  Study/Variable/Question/Universe/DataFile, SKOS for code lists and
  categories, XKOS for classification levels. Neither vocabulary was
  referenced anywhere in this repo before. Every node carries two
  `rdf:type` triples -- the standard class for interoperability and the
  project class for identity -- because the standard alignment is
  many-to-one and could not otherwise be reversed.
- **`ddigraph export`**, the first command that writes a file rather than
  loading a database. Emits Turtle, N-Triples, JSON-LD, RDF/XML, JSON or
  CSV, needs no Neo4j connection, and works for all three DDI flavors:

  ```bash
  ddigraph export survey.xml --format turtle -o out.ttl
  ```

  RDF formats need the `[rdf]` extra; JSON and CSV work on a base
  install. Also available as `ddigraph.export()` from Python, alongside
  `ddigraph.iter_graph()` for building your own consumer.
- **RDF as an input format** (`ddigraph.rdf.read_graph`). Turtle,
  N-Triples, JSON-LD and RDF/XML parse back into the same `GraphChunk`
  stream the XML parsers produce, so everything built on the graph view
  consumes them unchanged. The round trip is lossless at triple level:
  exporting a fixture, reading it back and re-exporting reproduces the
  original graph exactly, for all four fixtures and all four
  serialisations.

  Two things make that possible, and neither is an accident. Every node
  already carried a project-namespace `rdf:type` beside its standard
  class. Relationships needed the same treatment: three published
  predicates are reached by more than one relationship type
  (`disco:question`, `skos:inScheme`, `dcterms:isPartOf` -- nine of 369
  types), and `skos:inScheme` also reverses the graph's edge direction,
  so those now carry a project-namespace companion triple. The other
  published predicates are one-to-one and get none, keeping the extra
  triples to the cases that need them.

  The reader skips subjects with no project type rather than guessing, so
  pointing it at unrelated RDF yields nothing instead of nonsense, and a
  mixed graph still yields the part it understands.
- **`ddigraph load` accepts RDF**, closing the loop:

  ```bash
  ddigraph export survey.xml --format turtle -o out.ttl
  ddigraph load out.ttl
  ```

  This needed a Neo4j writer over `GraphChunk`
  (`ddigraph.graph.writer.GraphChunkWriter`). `Neo4jGraphAdapter` takes a
  `DDIIngestGraph`, which only the codebook parser produces, so RDF and
  DDI-CDI had no way into a database. The new writer groups a chunk by
  label and identity shape and issues one `UNWIND` per group, so it needs
  no knowledge of the schema -- and it gives **DDI-CDI its first write
  path**. Labels and relationship types are validated before being
  interpolated into Cypher, because Neo4j cannot parameterise them and an
  RDF input's labels come from a file someone else wrote.
- **Code lists and categories are emitted as SKOS.** A `CodeList` becomes
  a `skos:ConceptScheme` and a `Category` a `skos:Concept`, with
  `skos:prefLabel`, `skos:notation` and `skos:definition`. Membership is
  emitted from the member's side as `skos:inScheme`, inverting the graph
  edge, because `skos:member` belongs to `skos:Collection` rather than
  `skos:ConceptScheme`. `external_references` becomes `skos:exactMatch`,
  which is the hook for joining a code list to EuroVoc, DBpedia or any
  other published vocabulary.
- **`ddigraph shapes`**, writing SHACL derived from `DDISchema` -- the same
  table that generates the Neo4j constraints, so the shapes cannot drift
  from the data:

  ```bash
  ddigraph shapes -o shapes.ttl --flavor lifecycle
  ```

  Every exported fixture is validated against them with `pyshacl` in the
  test suite, which holds the vocabulary and the writer to the contract
  consumers are asked to validate against. `--flavor` is recommended for
  real data: 21 labels appear in more than one DDI flavor with different
  identity fields, and constraints the flavors disagree on are dropped
  rather than guessed at.
- **`ddigraph preview`**, answering "what is actually in this file?"
  without a database and without an optional extra:

  ```bash
  ddigraph preview survey.xml --format html -o preview.html
  ```

  Until now the only way to see what a load had produced was to open
  Neo4j Browser and start writing Cypher; `ddigraph load` reports
  `nodes=1247, relationships=3891` and nothing about what any of them
  are. Preview reports the *shape* -- counts per node type and per
  `type -[EDGE]-> type` -- because the demo corpus runs to 65 MB and a
  box per node is unreadable. `--limit N` adds example identities when
  the counts alone do not tell you whether the right thing was parsed.

  Three renderers: `text` for the terminal, `mermaid` to paste into the
  docs or a GitHub comment, and `html` as one self-contained page with an
  inline SVG chart -- no CDN, no external stylesheet, no JavaScript, so
  it works offline and survives being emailed.
- **`ddigraph validate`**, checking a file against the official DDI XSD:

  ```bash
  ddigraph validate survey.xml || exit 1
  ```

  The package has shipped the official schemas all along -- 154 XSD files
  across Codebook 2.6, Lifecycle 3.1/3.2/3.3 and CDI 1.0 -- and only the
  build-time codegen ever read them. Nothing let a user ask the question a
  data archivist asks first. It picks the schema from the flavor and, for
  DDI-L, from the version the document declares in its own namespace, and
  exits non-zero on a violation. `load` and `export` take `--validate` to
  run the same check as a pre-flight. No new dependency: `lxml` was already
  required and covers XSD 1.0, which is what the DDI schemas are.

  **It is opt-in, and the reason matters.** Every XML fixture in this
  repository fails validation -- they are synthetic, and the Codebook one
  is a bare `<codeBook>` with no namespace at all -- as does a good deal of
  published DDI. Those files parse and load correctly. Validating by
  default would refuse work that currently succeeds.

  It also required working around a defect in the DDI Alliance's own
  Codebook 2.6 schema, which is not itself valid XSD: in 55 places an
  `xs:attribute` holds its `xs:annotation` after its `xs:simpleType`, while
  the specification requires `(annotation?, simpleType?)`. Every conforming
  parser rejects it, so without intervention Codebook could not be
  validated at all. The file's checksum matches `schemas/manifest.json`, so
  this is upstream rather than a vendoring accident. ddigraph reorders the
  annotations in the in-memory tree and leaves the file byte-identical, and
  a test asserts the repair changes no element and no name.
- **`--include-cdi`** on `ddigraph bootstrap`, for pre-provisioning the
  DDI-CDI schema when CDI data is written by something other than
  ddigraph.
- **The vocabulary namespace resolves.** `vocabulary.py` described the
  namespace IRI as dereferenceable, and it was not: nothing was served at
  it, so every IRI in every exported file pointed at a 404. There is now a
  reference page at `https://pbisson44.github.io/ddigraph/ns/1.0/` and a
  `vocabulary.ttl` beside it, defining 249 classes, 369 object properties
  and 85 datatype properties.

  It is generated from `DDISchema` -- the same table behind the Neo4j
  constraints and the SHACL shapes -- so it cannot describe terms the
  exporter does not emit, and a test fails if the committed copy drifts.
  A hand-maintained mapping table that no code implemented is what this
  release started out fixing; a hand-maintained vocabulary document would
  have been the same bug one level up.

  Terms with a published equivalent are declared against it rather than
  redefined (`rdfs:subClassOf disco:Question`, not `owl:equivalentClass`,
  because the alignment is many-to-one). The three predicates whose graph
  direction is opposite to the published one are declared `owl:inverseOf`
  rather than `rdfs:subPropertyOf`, since calling them subproperties would
  tell a reasoner the scheme is in the concept. The document asserts
  nothing about DISCO, SKOS or XKOS terms themselves.
- **`shacl` extra** (`pip install "ddigraph[shacl]"`), pulling `rdflib`
  and `pyshacl`.
- **`tests/fixtures/cdi_sample.xml`**, a small materialised DDI-CDI file.
  The demo corpus lives in Git LFS and is not materialised in CI, so the
  suite needed its own.

### Changed

- **`xmlschema` is no longer a runtime dependency.** It appears nowhere
  under `src/`; its only use is `scripts/generate_schema_definitions.py`,
  the XSD codegen, which is not shipped in the wheel. Every base install
  was pulling it, and `elementpath` behind it, for nothing. It now lives
  in `[dev]`.
- **`ddigraph bootstrap` no longer creates DDI-CDI constraints by
  default.** A codebook bootstrap issued 154 queries, 77 of them for a
  format with no shipped writer; it now issues 77. Use `--include-cdi` to
  restore the old behaviour.
- **The `__version__` fallback for uninstalled checkouts reads
  `0.0.0.dev0`.** It had been pinned at `"0.4.0"` through three patch
  releases, because nothing makes a hard-coded literal follow
  `pyproject.toml`. A version that cannot be trusted now looks like it.

### Documentation

- **Documented examples are executed by the test suite.** A fenced block
  opts in with a `<!-- runnable -->` marker and is then run for real, in
  both languages. Nothing checked this before, which is why three
  documented examples could not run: `backends/networkx.md` called
  `nx.info(G)`, removed in NetworkX 3.x while the extra requires `>=3.6.1`,
  and `backends/rdf.md` documented a `DDIFragmentParser()` / `.parse(path)`
  API that has never existed.
- **`backends/rdf.md` rewritten** in both languages. It described four
  different namespaces across two examples, a predicate mapping table no
  code implemented, and an API that does not exist. It now documents the
  shipped commands, the real vocabulary, and the SKOS output.
- **Python examples that cannot be executed must still parse.** Plenty of
  them legitimately cannot run in CI -- they need a database, a Gremlin
  server, or an API key -- so they are now syntax-checked instead. That
  caught `backends/gremlin.md` in both languages: a nested `for` with no
  indented body, which raised `IndentationError` before reaching the API it
  was demonstrating, using `fragment.element_type` and `.fragment_id`,
  which no object in the package has. Rewritten against `iter_graph`, with
  the two-phase collect-then-wire ordering the DDI-L parser requires.
- **Documented `ddigraph` imports are verified.** Every
  `from ddigraph... import X` in the docs must resolve, which covers the
  examples that need a database and so cannot be executed. It found
  `CDILoader`, which has never existed, and a `ddigraph.settings` module
  that is called `ddigraph.config`.
- **The parser API that never existed is gone from the docs.** Twenty-five
  occurrences of `DDIFragmentParser()` followed by `.parse(path)` were
  spread across seven pages in both languages; the real class takes the
  path in `__init__` and exposes `parse_batches()`. Those examples now use
  `iter_graph`, and a test rejects the old idiom.
- **An eight-lesson course**, `learn/`, in both languages. It teaches the
  concepts and the package together: why survey metadata is a graph, how to
  inspect a file before loading it, the node/edge/identity model, the RDF
  vocabulary and why every node carries two types, XSD against SHACL,
  building a pipeline to a store ddigraph has never heard of, and two
  lessons on putting the graph in front of a language model -- grounding it
  so it stops inventing your survey, then giving it a tool so it can query
  the graph itself. Each lesson carries an exercise with a hidden solution,
  and every code block in all eighteen pages is executed by the test suite
  except the two that need an API key, which are marked as such.
- **New case study**, `advanced/rdf-case-study.md`, walking a code list
  from DDI to validated linked data. Every step in it runs in CI.
- **"Included with ddigraph" corrected** for rdflib, gremlinpython and
  networkx across three pages and two languages. All three have been
  optional extras since 0.4.0rc1.
- `reference/cli.md` covers `export`, `shapes`, `preview`, `--include-cdi`
  and RDF input; `getting-started/installation.md` covers the `shacl`
  extra and no longer lists `xmlschema` as a runtime dependency.

### Removed

- **`demo/load_rdf.py` and `demo/export_files.py`**, both superseded by
  `ddigraph export`. `load_rdf.py` in particular had become an
  anti-example: it minted its own namespace, emitted Neo4j relationship
  names as predicates, and flattened DDI URNs, which is precisely what
  this release set out to stop.
- **`ddigraph ensure-schema` and `ddigraph ensure-fragment-schema`**
  (breaking). Both were deprecated in 0.4.0rc1 and have named 0.5.0 as
  their removal release ever since. `bootstrap` replaces both: it
  includes the DDI-L fragment schema by default, and takes
  `--no-include-fragments` for the codebook-only case. The library
  function `ensure_fragment_schema` is unaffected -- only the CLI
  subcommands were deprecated.
- **`src/ddigraph/schema/definitions.py`**, 102 KB of unreachable code.
  Both it and the `schema/definitions/` package were tracked, and Python
  resolves a package before a same-named module, so the file had not been
  imported since the package landed -- while still shipping in every
  wheel and sdist.

### Testing

- **Mutation testing** (`make mutation`), scoped to the RDF vocabulary and
  the graph tier via `[tool.mutmut]`. Not a CI gate. It found a real
  crash -- `to_lower_camel("_")` raised `ValueError`, because the
  emptiness guard sat after the unpack that raises -- and showed that the
  Cypher generator's tests asserted substrings loosely enough that
  swapping a match variable to `None`, or dropping the row payload
  entirely, went unnoticed. Both are now pinned exactly.

### Fixed

- **`to_lower_camel` raised `ValueError` on a separator-only name.** The
  guard on an empty result ran after `head, *tail = parts`, which is what
  raises when there is nothing to unpack.
- **`NEO4J_*` silently overrode `DDIGRAPH_NEO4J_*`.** `AliasChoices` is
  first-match-wins and every connection field listed the bare industry
  name first, so the prefix the docstring called "preferred" always lost.
  A stale `NEO4J_URI` in a shell or `.env` redirected writes to the wrong
  database while `resolve_credentials_source()` reported `DDIGRAPH_*` as
  the source. Bare `NEO4J_*` names still apply when no `DDIGRAPH_*` value
  is set, so Aura credential files keep working.
- **`include_cdi` was unreachable.** `bootstrap_queries` forwarded its
  flag positionally into `generate_all_schema_queries(include_fragments,
  include_cdi)`, leaving `include_cdi` at its `True` default regardless of
  the caller.
- **`DDIIngestGraph.nodes()` raised `AttributeError` on any codebook file
  containing a processing event.** `_NODE_MAPPINGS` gave `ProcessingEvent`
  an identity field of `event_id` against a record whose attribute is
  `processing_event_id`. It survived because the Neo4j adapter writes
  through `as_dict()` and never touches that projection.
- **DDI-CDI relationship endpoints named labels no node could have.**
  Endpoint labels came straight from the association tag, but the parser
  collapses many concrete tags into shared collections -- `Step` lands in
  `activities` and surfaces as `CDIActivity` -- so 102 of 134 endpoint
  labels were unreachable and a consumer joining on `(label, identity)`
  would fabricate a node beside the real one.
- **Bootstrap permission errors pointed at `NEO4DDI_NEO4J_DATABASE`**,
  removed in 0.4.0 and ignored since.
- **Composite-identity nodes collapsed onto one RDF subject.** The writer
  minted subject IRIs from the first identity value alone, so all fourteen
  `DDIGenericIdentifiable` nodes in a codebook fixture -- keyed on
  `(dataset_id, element_tag, identifiable_id)` and sharing a `dataset_id`
  -- landed on one IRI with their properties merged. Every identity value
  now participates.
- **`ruff check .` failed on `main`.** `demo/audit_graph_standalone.py`
  carried a non-raw docstring containing backslashes (`D301`), failing the
  blocking lint gate; its `audit/` twin already had the `r` prefix.

### Deferred to 0.6.0

- **Gremlin, NetworkX and pandas remain demo scripts, not adapters.**
  `src/ddigraph/` ships two write paths -- `Neo4jGraphAdapter` and the new
  `GraphChunkWriter` -- and nothing else. This release stopped the README
  and the backend pages from claiming otherwise, and `iter_graph` now
  makes writing one of these a short piece of work rather than a parser
  rewrite, but a shipped, tested adapter for each is its own iteration.
- **Content negotiation on the vocabulary namespace.** GitHub Pages serves
  the reference page at the namespace IRI, which is what makes it
  dereferenceable for a human. It cannot answer `Accept: text/turtle` with
  `vocabulary.ttl`, and individual term IRIs
  (`.../ns/1.0/Study`) do not resolve on their own -- only the namespace
  document does. Both need hosting that this project does not currently
  have. The Turtle is published and linked; it just has to be fetched by
  its own URL.
- **SHACL validation behind a CLI verb.** `ddigraph validate` checks a
  document against its XSD; nothing checks an *export* against the shapes.
  `ddigraph shapes` writes the SHACL and the test suite runs `pyshacl`
  against it, so that second check is two commands and a `pyshacl` install
  rather than one verb. Folding it in is small, but it wants a considered
  exit-code and report format rather than printing whatever `pyshacl`
  returns.
- **SKOS coverage beyond code lists.** Categories, code lists and concept
  schemes are mapped. `xkos:ClassificationLevel` is used for
  `CategoryGroup` alone; the wider XKOS surface -- classification
  correspondences, levels across a whole scheme -- is untouched.
- **DDI-CDI is readable and writable but not curated.** It reaches the
  graph tier and RDF for the first time in this release, and every one of
  its ~209 entity types resolves to a project-namespace term. None of them
  are hand-aligned to published classes the way the DDI-C and DDI-L
  concepts are.

## 0.4.3 — 2026-08-12

- ruff format and check

## 0.4.2 — 2026-06-13

Operational hardening for multi-file graphs and the packaged
distribution, plus a graph-audit tool and broader loader test
coverage.

### Added

- **Survey-root entry-point labelling**
  (``AsyncFragmentGraphWriter.mark_entry_points``): every ``Instrument``
  and ``StudyUnit`` is now labelled ``:EntryPoint``, not just the file's
  declared ``TopLevelReference``. A single FragmentInstance declares one
  top level, but a file -- or an accumulated multi-file graph -- can hold
  many survey roots; all of them are now discoverable as traversal entry
  points regardless of how many files were loaded.
- **``audit/audit_other_nodes.py``** -- a standalone audit script that
  explains the generic "Other" nodes in a loaded graph and flags any
  genuine problems.
- **Expanded loader tests**: fragment entry-point marking,
  ``_resolve_reference`` fallback paths, a loader integration test, and
  coverage for declared-top-level vs. survey-root labelling.

### Changed

- **``audit/`` excluded from the published sdist** so the packaged
  distribution stays lean; audit tooling now lives under ``audit/``.
- mkdocs-material "grid cards" rendering fix on the docs home page.

### Fixed

- Silenced the ``DeprecationWarning``s that ddigraph's own deprecation
  shims emitted during the test run.
- markdownlint ``MD007`` (unordered-list indentation) addressed via
  inline directives.

## 0.4.1 — 2026-06-06

Correctness release. Makes DDI-L fragment identity version-aware and
smooths Neo4j Aura configuration, alongside CI/publish hardening.

### Added

- **``NEO4J_USERNAME`` recognised** as a config alias (added to the
  ``neo4j_user`` ``AliasChoices``) so Neo4j Aura ``.env`` files -- which
  ship ``NEO4J_USERNAME`` -- work without edits.
- **Automated PyPI publishing** wired into the release workflow.

### Changed

- **Version-aware DDI-L fragment identity (URN-based node key).**
  ``Fragment.node_key`` / ``FragmentReference.node_key`` now key nodes on
  the full DDI URN (``urn:ddi:<agency>:<id>:<version>``) instead of the
  bare id, so two versions of the same DDI id become distinct nodes.
  ``Fragment.to_dict()`` writes the version-aware key as ``fragment_id``
  and keeps the bare DDI id as ``ddi_id``; a fragment and the references
  pointing at it derive the same key. Falls back to the bare id when no
  version is present.
- Workflow permission hardening from code-scanning alerts (explicit
  ``permissions:`` blocks on the GitHub Actions workflows).
- Bumped ``codecov/codecov-action`` from 6 to 7.

### Fixed

- Demo script fixes (``demo/load_ddi.py``, ``demo/load_sdmx_lfs.py``).

## 0.4.0 — 2026-05-16

Final milestone of the 0.4.0 simplification work. The bespoke
DDI-Codebook record builders collapse onto a declarative,
mypy-checked composition registry, and the redundant generic-dispatch
table folds into a single fallback. The XSD files remain the source of
truth for items, their fields, and their relationships.

### Added

- **Declarative composition registry**
  (``src/ddigraph/ingest/_composition_specs.py``): one typed
  ``CompositionSpec`` per regular flat codebook handler. A single
  walker (``BatchBuilder._run_composition``) consumes the registry,
  replacing ~30 near-identical hand-written ``ingest_*`` bodies. The
  registry is typed Python data, not a string mini-language -- it is
  mypy-checked and needs no parser (see
  ``docs/en/project/dsl-design.md`` for why a string DSL was
  rejected).
- **Selector primitives** (``src/ddigraph/ingest/_compose.py``): the
  small set of pure extraction functions (``text``, ``text_any``,
  ``metadata``, ``textual``, ``refs_by_suffix``, ``child_texts``, ...)
  the registry composes, with unit tests pinning each to the loader
  helper it mirrors.
- **Byte-equality snapshot gate**
  (``tests/test_codebook_loader_snapshot.py``): every per-handler
  migration is verified to produce a byte-identical record set against
  a committed baseline.

### Changed

- **Generic codebook dispatch collapsed**: the 77-line block in
  ``_build_handlers`` that registered one identical lambda per
  ``_GENERIC_IDENTIFIABLE_TAGS`` member is gone. The iterparse loop now
  falls back to ``ingest_generic_identifiable`` directly, leaving the
  frozenset as the single source of truth for generic dispatch. The
  audit script and dispatch-coverage tests import that frozenset
  instead of scraping it from source.
- **``ingest/loader.py`` reduced** from 4,289 to ~3,500 lines with no
  behaviour change; the remaining bespoke handlers are genuinely
  recursive (spawn child records) or irregular (custom id derivation,
  metadata-dict mutation) and stay as clean Python.

## 0.4.0rc1

Third milestone of the 0.4.0 simplification work. Adds the tooling,
naming, packaging, and CI gates that make the package PyPI-ready,
along with the contributor on-ramp and an advisory readability tool
for the docs tree.

### Added

- **CRUD-simple Python API** (carried from 0.4.0b1) is now backed by
  a comprehensive guard suite: 34 ``tests/test_extras_lazy_imports.py``
  cases enforce that no module under ``src/ddigraph/`` top-level
  imports any optional extra; 54 ``tests/test_public_api.py`` cases
  enforce the public/private naming convention (every public module
  declares ``__all__``; no name in any ``__all__`` starts with a
  single underscore; private modules are not referenced from docs
  or demos).
- **Packaging audit gates** in ``publish.yml``'s dry-run job:
  ``twine check``, ``pyroma -d`` (now scores 10/10), and
  ``check-manifest`` (clean against the hatch sdist target).
- **OIDC Trusted Publishing** wired into the PyPI publish job;
  drops ``secrets.PYPI_TOKEN`` and adds the standard
  ``environment: pypi`` + ``id-token: write`` configuration.
- **Markdownlint gate** (``DavidAnson/markdownlint-cli2-action@v23``)
  on every PR. The repo passes the comprehensive ruleset at 0
  violations after auto-fixes plus targeted annotations of bare
  ``` fences with the ``text`` language.
- **``scripts/check_readability.py``** advisory Flesch-Kincaid
  grade-level audit over ``docs/en/``. Uses ``textstat`` (optional
  ``docs`` extra) and strips YAML front matter, fenced code, HTML
  tags, and mkdocs admonition markers before scoring.
- **``CONTRIBUTING.md``** at the repo root with the dev-loop
  checklist; deep guide lives at ``docs/en/project/contributing.md``.

### Changed

- **Tooling retargeted to Python 3.14**:
  ``[tool.ruff] target-version = "py314"``,
  ``[tool.mypy] python_version = "3.14"``. ``requires-python``
  drops the ``!=3.14.1`` exclusion.
- **``pydocstyle`` retired** in favour of ruff's ``D`` rule family
  (Google convention). The separate ``ruff check --select D`` CI
  step is gone; ``ruff check .`` now exercises the whole file tree.
- **ruff ``N`` (pep8-naming) enabled** with documented per-rule
  ignores (``N802``/``N806``/``N811``) for stdlib mirror names,
  uppercase namespace locals in demos, and constant-alias imports
  in tests.
- **Optional extras split**: rdflib, gremlinpython, networkx,
  pandas + openpyxl, and sdmx1 are now ``[project.optional-dependencies]``
  groups (``[rdf]``, ``[gremlin]``, ``[networkx]``, ``[pandas]``,
  ``[sdmx]``) plus an ``[all]`` aggregator. Base install drops to
  six packages (lxml, neo4j, orjson, pydantic, pydantic-settings,
  xmlschema).
- **`NEO4DDI_*` env-var aliases removed**, with a one-shot
  ``DeprecationWarning`` in ``Settings.model_post_init`` listing
  every offending variable still in the environment. Use
  ``DDIGRAPH_*`` going forward.
- **CLI four-verb shape**: added ``ddigraph bootstrap`` and
  ``ddigraph version``. ``ensure-schema`` and
  ``ensure-fragment-schema`` are retained as deprecated wrappers
  pointing users at ``bootstrap``; scheduled for removal in 0.5.0.

### Deprecated

- ``NEO4DDI_*`` environment variables (removed from the validation
  alias chain; still detected at startup for the warning).
- ``ddigraph ensure-schema`` and ``ddigraph ensure-fragment-schema``
  CLI subcommands (still functional through 0.4.x; removal in 0.5.0).

### Fixed

- Worked around a ruff 0.15.12 ``target-version = "py314"``
  formatter bug that strips parens from ``except (A, B):`` clauses
  and emits invalid Python 3 syntax. Three call sites (demos and
  the readability script) now hoist the exception tuple to a
  named module-level variable; ``except _TUPLE:`` is not a
  multi-exception clause syntactically so ruff format leaves it alone.
- mypy now excludes ``demo/`` from strict checking. Demo scripts
  depend on optional extras that the base install does not pull
  in; they are user-facing examples, not part of the typed
  package surface.

### Deferred to 0.4.0 final / 0.5.0

- **Declarative composition DSL** for the bespoke codebook
  handlers. ``ingest/loader.py`` currently sits at ~4,300 lines
  after the ``_claim_id`` consolidation; the target is ~900 lines
  once the selector DSL absorbs the remaining hand-coded
  ``ingest_*`` methods. Designing and validating that DSL is its
  own iteration.
- **Grade-10 documentation readability** rewrite across
  every ``docs/en/`` page and French parity for the eight missing
  ``docs/fr/`` pages (``user-guide/``, ``advanced/``,
  ``backends/``, ``project/``). The tooling
  (``scripts/check_readability.py``) is in; the translation +
  rewrite work is a multi-week pass.
- **Demo data to Git LFS**. The 88 MB of XML in
  ``demo/`` still ships in the repo via plain git; LFS migration
  is its own ops change.
- **``--tune key=value`` CLI flag collapse**.
  The 25+ tuning flags on ``ddigraph load`` still work; the
  collapsed form is a behaviour change for power users that
  deserves a dedicated commit.

---

## 0.4.0b1

Second milestone of the 0.4.0 simplification work. Adds the user-facing
CRUD API as the primary usage goal and starts factoring shared
loader helpers.

### Added

- **`ddigraph.load(path, *, target=...)`** -- one-line sync ingestion
  that auto-detects DDI flavor and dispatches to the right loader.
- **`ddigraph.aload(...)`** -- the async equivalent.
- **`ddigraph.detect(path)`** -- typed ``Literal["codebook","lifecycle","cdi","unknown"]``
  flavor detector.
- **`ddigraph.bootstrap(*, target=..., include_fragments=True)`** /
  **`ddigraph.abootstrap(...)`** -- create indexes and constraints
  for the configured Neo4j target.
- **`LoadResult` dataclass** with ``nodes_written``,
  ``relationships_written``, ``duration_s``, ``flavor``, ``target``,
  ``dataset_id``, ``dry_run``, and the raw ``totals`` mapping.
- **`ddigraph bootstrap`** CLI subcommand (canonical alias for
  ``ensure-schema --include-fragments``; the legacy command remains
  as a deprecated wrapper until 0.5.0).
- **`ddigraph version`** CLI subcommand that prints
  ``ddigraph.__version__``.
- **``BatchBuilder._claim_id(dedup_set, identifier)``** helper that
  consolidates the dedup-by-id pattern previously inlined in 39
  codebook ``ingest_*`` handlers.

### Changed

- The package's top-level docstring now anchors examples on the new
  CRUD API.
- ``__all__`` reordered to put the CRUD entry points first, with the
  power-user surface (loaders, batches, schema container) listed
  below as still-supported public exports.

### Deprecated

- ``ddigraph ensure-schema`` and ``ddigraph ensure-fragment-schema``
  emit a ``DeprecationWarning`` and forward to ``ddigraph bootstrap``.
  Removal scheduled for 0.5.0.

### Deferred

- The full handler collapse for the DDI-Codebook loader
  (``_capture`` driven by ``NodeDefinition.properties``) requires the
  selector DSL described in the composition design doc. The
  ``_claim_id`` helper added in this milestone is its smallest piece.
- ``--tune key=value`` / ``--config FILE`` CLI flag collapse. The
  existing 25+ tuning flags on ``load`` keep working in 0.4.0b1; the
  collapse is a backward-incompatible change for power users that
  lands in 0.4.0rc1.

---

## 0.4.0a1

First alpha cut of the 0.4.0 simplification work. Behaviour is mostly
the same as 0.3.0 -- existing imports and CLI commands keep working --
but the schema/loader internals have been reorganised so the XSDs in
``schemas/`` are now the single source of truth for node and
relationship metadata.

### Added

- **XSD-driven schema generator** (`scripts/generate_schema_definitions.py`)
  parses every bundled DDI XSD and emits Python tables under
  `src/ddigraph/schema/_generated/{codebook,lifecycle,cdi}.py`:
  - DDI-CDI 1.0: 209 entities + 240 association tags.
  - DDI-L 3.x: 189 concrete identifiables + 282 `*Reference` element types.
  - DDI-Codebook 2.6: 73 in-scope elements + 10 layout exclusions.
  CI runs the generator with `--check` so any drift between the
  committed artefacts and the XSDs blocks PRs.
- **XSD structural relationship coverage audit**
  (`scripts/xsd_coverage.py --structural`) reports per-flavor coverage
  between XSD-declared relationships and the runtime relationship
  tables. Threshold is enforced at 100 % in CI.
- **`src/ddigraph/schema/_overrides/schema_overrides.toml`** is the
  human-edited bridge between XSD-derived metadata and runtime
  `NodeDefinition` / relationship-type tables. The TOML carries 32
  curated CDI node definitions and 64 curated DDI-L relationship-type
  names; everything else falls back to deterministic defaults derived
  from the XSDs.
- **CDI public surface** at the top-level package: `CDIBatch`,
  `CDIBatchStream`, `is_cdi_format`, `parse_cdi_batches` are now
  importable as `from ddigraph import ...`.
- Pinned the 3.14 entry of the CI matrix to `3.14.4` exactly.

### Changed

- **`src/ddigraph/schema/definitions.py`** (3,218 lines) replaced with
  a `definitions/` package: `_dataclasses.py` + `codebook.py` +
  `lifecycle.py` + `cdi.py` + `__init__.py`. Every public name the old
  monolith exposed (`DDISchema`, `NodeDefinition`,
  `RelationshipDefinition`, `CODEBOOK_NODES`, `FRAGMENT_NODES`,
  `FRAGMENT_RELATIONSHIP_TYPES`, `CDI_NODES`) remains importable from
  `ddigraph.schema.definitions`.
- **CDI loader collapse.** `src/ddigraph/ingest/cdi_loader.py` shrinks
  1,617 -> 850 lines:
  - `_CDI_RELATIONSHIP_MAP` (128-line literal) becomes a one-line call
    to `cdi_relationships()` in the override loader. Every one of the
    240 XSD-declared CDI associations now produces a runtime
    relationship (was 26). 10 explicit `[ddi_cdi.relationship_overrides]`
    entries preserve historical rel_type names like `HAS_CONCEPT`.
  - `_CDI_TAG_MAP` (700-line literal) becomes a 52-entry
    `_CDI_BESPOKE_MAP` plus an XSD-driven auto-derivation for the
    remaining 158 generic-default entries.
  - 26 near-identical `CDI*Record` subclasses are deleted. Their
    optional fields (`agent_type`, `value`, `version`, `code`,
    `structure_type`, `component_type`, `dataset_type`, `domain_type`,
    `entity_type`) are promoted onto `CDIRecord`. `CDIGenericRecord`
    is kept as a backward-compatible alias.
- **DDI-L lifecycle relationship coverage.** `FRAGMENT_RELATIONSHIP_TYPES`
  now derives from `FRAGMENT_GENERATED_REFERENCES`: every one of the
  282 `*Reference` element types declared in `schemas/ddi/v3_3/*.xsd`
  has a runtime entry. The 64 curated rel_type names with semantic
  prefixes (`USES_CONCEPT`, `IN_CATEGORY_GROUP`, etc.) are preserved
  via `[ddi_l.relationship_overrides]`.
- Removed the non-existent `ddigraph audit` references from the EN/FR
  documentation indexes.

### Fixed

- Added `xmlschema>=3.4` as a runtime dependency (used by the
  CDI-flavor generator path).
- Added explicit `__all__` to `paths.py` and `schema/neo4j_adapter.py`.

### Deferred to later 0.4.0 milestones

- `cdi_loader.py` still has 33 hand-named `CDIBatch` collections; the
  downstream adapter dispatch on those is preserved unchanged. A
  follow-up commit can fold them into a dict-keyed structure once the
  Cypher adapter is ready.
- `fragment_loader.py:_extract_properties` still has type-specific
  branches (CodeList `code_count`, QuestionItem `question_text`, etc.).
  Replacing them needs a declarative-selector DSL in the override
  file; the DSL design lands once there.
- Public CRUD API (`ddigraph.load` / `aload` / `detect` / `bootstrap`),
  CLI slim, docstring + readability passes, FR docs parity, PyPI
  Trusted Publishing, and the demo data move to Git LFS land in the
  0.4.0b1 and 0.4.0rc1 milestones.

---

## Pre-0.4.0 groundwork

Retitled from "Unreleased": this section sits below 0.4.0a1 and describes
the XSD-coverage work that shipped with it, so the old heading claimed
these changes were still pending years after they landed.

### Added

- **Real XSD-driven coverage for every DDI flavor.** The bundled parsers now
  recognize every concrete identifiable element declared in
  `schemas/ddi/v3_3`, `schemas/ddi-c/codebook.xsd`, and
  `schemas/ddi-cdi/xml-schema/ddi-cdi.xsd`:
  - DDI-L 3.x: 189/189 concrete Maintainable/Versionable/Identifiable elements
  - DDI-C 2.x: 73/73 codebook elements carrying the `GLOBALS` attribute group
  - DDI-CDI 1.0: 210/210 concrete top-level entity elements
- `scripts/xsd_coverage.py` -- real XSD-parsing audit with machine-readable
  JSON output (`--json`) and configurable threshold (`--threshold`); used by
  CI and the `TestRealXSDCoverage` pytest class.
- `GenericIdentifiableRecord` and `BatchBuilder.ingest_generic_identifiable()`
  in `ddigraph.ingest.loader` -- uniform capture for concrete codebook
  elements without a bespoke record class.
- `CDIGenericRecord` and the `generic_entities` collection on `CDIBatch` --
  round-trip storage for the DDI-CDI entity classes beyond the ~35
  hand-tuned record types.
- 106 DDI-L identifiable `NodeDefinition` entries (and matching `NAME_TAGS`)
  covering every remaining concrete element in DDI-L 3.3.

### Changed

- `DDIBatchStream.__iter__` tracks whether each matched element was dispatched
  to a generic or bespoke handler and skips in-place `elem.clear()` for
  generic captures so parent handlers can still reach nested children.
- `CDIBatchStream.__iter__` only processes elements that are the XML root or
  direct children of the root, preventing nested reusable types (e.g.
  `Identifier`, `ObjectName`) from being cleared before their parent entity
  finishes parsing.
- `BatchBuilder._count_records()` (the chunk-flush trigger) no longer counts
  `generic_identifiables`, keeping existing chunk-size semantics intact even
  as broader XSD coverage introduces many auxiliary records per document.

---

## v0.1.0

### Added

**DDI Format Support**

- **DDI Codebook** (DDI-C 2.5 and 2.6) support with streaming XML parsing for files of any size
- **DDI Lifecycle** (DDI-L 3.2/3.3) FragmentInstance support with batched writes and full async I/O
- **DDI-CDI 1.0** support with a streaming parser for 25 core entity types and 12 relationship types
- **Format auto-detection** -- `detect_ddi_format()` inspects the root element and namespace to pick
  the right parser automatically
- DDI-C 2.6 entity types: NCube, NCubeGroup, DocumentDescription, SampleFrame, QualityStatement,
  StudyAuthorization, StudyDevelopment, ExPostEvaluation

**Multi-Backend Architecture**

- **`GraphWriteAdapter` protocol** (`ddigraph.schema.adapter`) for pluggable backend implementations
  (sync and async)
- **Neo4j** -- Bolt driver, schema bootstrap, UNWIND batching, retry with exponential backoff
- **RDF/SPARQL** -- via rdflib and SPARQLWrapper
- **Gremlin** -- via gremlinpython (JanusGraph, Neptune, Cosmos DB)
- **NetworkX** -- in-memory graph for local analysis and prototyping
- **pandas** -- tabular analysis and CSV/Excel export
- Demo scripts for all backends (`demo/load_rdf.py`, `demo/load_gremlin.py`,
  `demo/load_networkx.py`, `demo/load_pandas.py`)

**CLI**

- `load` with format auto-detection, `--dry-run`, `--replace`, and configurable batching
- `ensure-schema` / `ensure-fragment-schema` for database constraint and index setup
- `detect` to identify DDI format without loading
- `audit` for graph content verification
- Credential source auditing at startup

**Core Engine**

- Streaming `iterparse`-based XML parsing -- memory stays constant regardless of file size
- Async write pipeline with `asyncio.Queue` back-pressure and configurable writer concurrency
- UNWIND-based batched writes reducing Neo4j transactions by 10--100x
- Retry with exponential backoff and jitter for transient write failures
- Unified schema definitions in `ddigraph.schema.definitions` (single source of truth)
- Shared parsing utilities in `ddigraph.utils.parsing`
- Shared retry logic in `ddigraph.utils.retry.retry_transient`
- Configuration via environment variables with `.env` file support (pydantic-settings v2)
- Structured logging with configurable log levels
- Python 3.12--3.14 support

**Documentation and Project**

- Bilingual docs (English / French) with mkdocs-material and mkdocs-static-i18n
- Demo scripts for all backends
- SECURITY.md, CODE_OF_CONDUCT.md, `.pre-commit-config.yaml`
- GitHub issue/PR templates and Dependabot configuration
- `pytest-cov` with 70 % branch-coverage gate
- PyPI publication -- installable via `pip install ddigraph`
- MIT License

---

[Full docs changelog](https://pbisson44.github.io/ddigraph/project/changelog/)
