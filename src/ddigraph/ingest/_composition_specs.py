"""Declarative composition registry for the flat codebook handlers.

Plan step K. Each ``CompositionSpec`` here replaces one near-identical
``ingest_*`` method in ``ddigraph.ingest.loader``: resolve an id,
dedup it, pull a few fields out of child elements, build a record,
append it. The walker that consumes these specs is
``BatchBuilder._run_composition`` in ``loader.py``.

This registry is *typed Python data*, not a string mini-language: it
is mypy-checked, needs no parser, and composes the ``_compose``
primitives directly. See ``docs/en/project/dsl-design.md`` for why a
string DSL was rejected.

This module deliberately does **not** import ``loader`` (that would be
circular); ``CompositionSpec.record`` is the record class *name*,
resolved by the walker against the loader module's own globals.
``_compose`` is safe to import even though it imports ``loader`` at
module top -- nothing here or there touches loader attributes at
import time, only inside function bodies.

Private module; does not widen the public surface.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ddigraph.ingest import _compose as c

if TYPE_CHECKING:
    from lxml import etree

_UNSET: object = object()


@dataclass(frozen=True, slots=True)
class Field:
    """One record keyword built from the current element.

    Exactly one of ``select`` / ``alias`` / ``const`` is set:

    * ``select`` -- a pure ``(elem) -> value`` callable (composed from
      ``_compose`` primitives).
    * ``alias`` -- reuse the value already computed for another field
      in the same spec (fields evaluate in declaration order).
    * ``const`` -- a literal value.
    """

    name: str
    select: Callable[[etree._Element], object] | None = None
    alias: str | None = None
    const: object = _UNSET

    @property
    def has_const(self) -> bool:
        """True when a literal ``const`` value was supplied."""
        return self.const is not _UNSET


@dataclass(frozen=True, slots=True)
class CompositionSpec:
    """Recipe for one flat codebook handler.

    Attributes:
        collection: ``DDIBatch`` list attribute (also the
            ``_append_and_count`` name).
        record: record dataclass *name* in the ``loader`` module.
        id_field: record kwarg that receives the resolved id.
        id_slug: when ``None`` the element is skipped if it has no
            id (matches ``if not file_id ... return``); otherwise the
            synthesised fallback is ``<dataset>:<slug>_<counter>``.
        counter: ``self.<counter>`` int attribute for the fallback
            (only consulted when ``id_slug`` is set).
        dedup: ``self.<dedup>`` set attribute for de-duplication.
        fields: explicit record kwargs, evaluated in order.
        splat_metadata: append ``**_common_metadata(elem)``.
        splat_textual: append ``**_textual_metadata(elem)``.
        textual_label_fallback: when ``splat_textual`` and the
            textual ``label`` is ``None``, fill it from this Field.
    """

    collection: str
    record: str
    id_field: str
    dedup: str
    id_slug: str | None = None
    counter: str = ""
    # ``"always"`` -- bump the counter every call, then resolve the id
    # with the synthesised default (the ``_get_identifier(elem,
    # default=...) or ...`` idiom). ``"lazy"`` -- resolve the bare id
    # first and only bump+synthesise when it is missing (the ``id =
    # _get_identifier(elem); if not id: counter += 1; id = ...``
    # idiom). Ignored when ``id_slug`` is None.
    id_mode: str = "always"
    fields: tuple[Field, ...] = ()
    # Keys copied verbatim from ``_textual_metadata(elem)`` into the
    # record kwargs of the same name (the ``description=textual[...],
    # name=textual[...], label=textual[...]`` idiom -- a *partial*
    # textual splat that, unlike ``splat_textual``, omits rationale /
    # language for records that do not accept them).
    textual_fields: tuple[str, ...] = ()
    splat_metadata: bool = False
    splat_textual: bool = False
    textual_label_fallback: Field | None = field(default=None)
    # Keys to pop from the ``_common_metadata`` dict before splatting,
    # for handlers that compute one of those keys explicitly instead
    # (e.g. ``ingest_software`` sets ``version`` from the element).
    metadata_drop: tuple[str, ...] = ()


# Common selector fragments reused across specs.
def _label_or_text(e: etree._Element) -> str | None:
    """``labl`` child, else the element's own text (the loader idiom)."""
    return c.text(e, "labl") or c.text_or_none(e)


# The flat-handler registry. Keyed by the migrated ``ingest_*`` method
# name so the migration is one method at a time and the dispatch table
# in loader.py stays untouched until step 4.
SPECS: dict[str, CompositionSpec] = {
    "ingest_file": CompositionSpec(
        collection="data_files",
        record="DataFileRecord",
        id_field="file_id",
        dedup="seen_files",
        id_slug=None,  # skip files with no id (matches current behaviour)
        fields=(
            Field("name", select=lambda e: c.text(e, ".//fileName")),
            Field("uri", select=lambda e: c.text(e, ".//fileURI") or c.attr(e, "URI")),
            Field("label", alias="name"),
        ),
        splat_metadata=True,
    ),
    "ingest_organization": CompositionSpec(
        collection="organizations",
        record="OrganizationRecord",
        id_field="organization_id",
        dedup="seen_organizations",
        id_slug="org",
        counter="organization_index",
        fields=(
            Field(
                "name",
                select=lambda e: (
                    c.text(e, "producerName") or c.text(e, "orgName") or c.text_or_none(e)
                ),
            ),
            Field("abbreviation", select=lambda e: c.text(e, "abbr")),
            Field("label", alias="name"),
        ),
        splat_metadata=True,
    ),
    "ingest_series": CompositionSpec(
        collection="series_list",
        record="SeriesRecord",
        id_field="series_id",
        dedup="seen_series",
        id_slug="series",
        counter="series_index",
        fields=(
            Field(
                "external_references",
                select=lambda e: c.refs_by_suffix(e, "Reference"),
            ),
        ),
        splat_textual=True,
        textual_label_fallback=Field("label", select=_label_or_text),
        splat_metadata=True,
    ),
    "ingest_group": CompositionSpec(
        collection="groups",
        record="GroupRecord",
        id_field="group_id",
        dedup="seen_groups",
        id_slug="group",
        counter="group_index",
        fields=(Field("label", select=_label_or_text),),
        splat_metadata=True,
    ),
    "ingest_data_collection_event": CompositionSpec(
        collection="data_collection_events",
        record="DataCollectionEventRecord",
        id_field="event_id",
        dedup="seen_collection_events",
        id_slug="event",
        counter="collection_event_index",
        fields=(Field("label", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_logical_record": CompositionSpec(
        collection="logical_records",
        record="LogicalRecord",
        id_field="logical_record_id",
        dedup="seen_logical_records",
        id_slug="logical",
        counter="logical_record_index",
        fields=(Field("label", select=_label_or_text),),
        splat_metadata=True,
    ),
    "ingest_other_material": CompositionSpec(
        collection="other_materials",
        record="OtherMaterialRecord",
        id_field="material_id",
        dedup="seen_materials",
        id_slug="material",
        counter="other_material_index",
        fields=(
            Field("label", select=_label_or_text),
            Field("uri", select=lambda e: c.text(e, "URI") or c.attr(e, "URI")),
        ),
        splat_metadata=True,
    ),
    "ingest_methodology": CompositionSpec(
        collection="methodology_notes",
        record="MethodologyNoteRecord",
        id_field="note_id",
        dedup="seen_method_notes",
        id_slug="method_note",
        counter="method_note_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_processing_event": CompositionSpec(
        collection="processing_events",
        record="ProcessingEventRecord",
        id_field="processing_event_id",
        dedup="seen_processing_events",
        id_slug="processing",
        counter="processing_event_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_software": CompositionSpec(
        collection="software",
        record="SoftwareRecord",
        id_field="software_id",
        dedup="seen_software",
        id_slug="software",
        counter="software_index",
        fields=(
            Field("name", select=lambda e: c.text(e, "name") or c.text_or_none(e)),
            Field("version", select=lambda e: c.attr(e, "version") or c.text(e, "version")),
        ),
        splat_metadata=True,
        metadata_drop=("version",),
    ),
    "ingest_access_condition": CompositionSpec(
        collection="access_conditions",
        record="AccessConditionRecord",
        id_field="access_condition_id",
        dedup="seen_access_conditions",
        id_slug="access",
        counter="access_condition_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_physical_structure": CompositionSpec(
        collection="physical_structures",
        record="PhysicalStructureRecord",
        id_field="physical_structure_id",
        dedup="seen_physical_structures",
        id_slug="physical",
        counter="physical_structure_index",
        fields=(Field("label", select=_label_or_text),),
        splat_metadata=True,
    ),
    "ingest_sampling_procedure": CompositionSpec(
        collection="sampling_procedures",
        record="SamplingProcedureRecord",
        id_field="sampling_id",
        dedup="seen_sampling",
        id_slug="sampling",
        counter="sampling_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_weight": CompositionSpec(
        collection="weights",
        record="WeightRecord",
        id_field="weight_id",
        dedup="seen_weights",
        id_slug="weight",
        counter="weight_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_representation": CompositionSpec(
        collection="representations",
        record="RepresentationRecord",
        id_field="representation_id",
        dedup="seen_representations",
        id_slug="representation",
        counter="representation_index",
        fields=(Field("label", select=_label_or_text),),
        splat_metadata=True,
    ),
    "ingest_funding": CompositionSpec(
        collection="funding",
        record="FundingRecord",
        id_field="funding_id",
        dedup="seen_funding",
        id_slug="funding",
        counter="funding_index",
        fields=(
            Field(
                "agency",
                select=lambda e: (
                    c.attr(e, "agency") or c.text_any(e, "fundAg", "fundingAgency", "sponsor")
                ),
            ),
            Field(
                "grant_number",
                select=lambda e: (
                    c.attr(e, "grantNo")
                    or c.text_any(e, "grantNo", "grantNumber", "contractNumber")
                ),
            ),
        ),
        splat_metadata=True,
        metadata_drop=("agency",),
    ),
    "ingest_ncube": CompositionSpec(
        collection="ncubes",
        record="NCubeRecord",
        id_field="ncube_id",
        dedup="seen_ncubes",
        id_slug="ncube",
        counter="ncube_index",
        id_mode="lazy",
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_ncube_group": CompositionSpec(
        collection="ncube_groups",
        record="NCubeGroupRecord",
        id_field="ncube_group_id",
        dedup="seen_ncube_groups",
        id_slug="ncube_grp",
        counter="ncube_group_index",
        id_mode="lazy",
        fields=(
            Field(
                "ncube_ids",
                select=lambda e: c.child_texts(e, ".//nCubeRef", ".//ncubeRef"),
            ),
        ),
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_sample_frame": CompositionSpec(
        collection="sample_frames",
        record="SampleFrameRecord",
        id_field="sample_frame_id",
        dedup="seen_sample_frames",
        id_slug="sample_frame",
        counter="sample_frame_index",
        id_mode="lazy",
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_quality_statement": CompositionSpec(
        collection="quality_statements",
        record="QualityStatementRecord",
        id_field="quality_id",
        dedup="seen_quality_statements",
        id_slug="quality",
        counter="quality_statement_index",
        id_mode="lazy",
        fields=(
            Field(
                "standard",
                select=lambda e: c.text(e, ".//standard") or c.text(e, ".//qualityStandard"),
            ),
        ),
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_study_authorization": CompositionSpec(
        collection="study_authorizations",
        record="StudyAuthorizationRecord",
        id_field="authorization_id",
        dedup="seen_study_authorizations",
        id_slug="auth",
        counter="study_authorization_index",
        id_mode="lazy",
        fields=(
            Field(
                "authorization_statement",
                select=lambda e: c.text(e, ".//authorizationStatement") or c.text(e, ".//authStmt"),
            ),
        ),
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_study_development": CompositionSpec(
        collection="study_developments",
        record="StudyDevelopmentRecord",
        id_field="development_id",
        dedup="seen_study_developments",
        id_slug="dev",
        counter="study_development_index",
        id_mode="lazy",
        fields=(
            Field(
                "activity_type",
                select=lambda e: (
                    c.text(e, ".//developmentActivity") or c.text(e, ".//activityType")
                ),
            ),
        ),
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_ex_post_evaluation": CompositionSpec(
        collection="ex_post_evaluations",
        record="ExPostEvaluationRecord",
        id_field="evaluation_id",
        dedup="seen_ex_post_evaluations",
        id_slug="eval",
        counter="ex_post_evaluation_index",
        id_mode="lazy",
        fields=(Field("completion_date", select=lambda e: c.text(e, ".//completionDate")),),
        textual_fields=("description", "name", "label"),
        splat_metadata=True,
    ),
    "ingest_code_list": CompositionSpec(
        collection="code_lists",
        record="CodeListRecord",
        id_field="code_list_id",
        dedup="seen_code_lists",
        id_slug="code_list",
        counter="code_list_index",
        fields=(
            # textual label, falling back to ``labl`` / element text.
            Field(
                "label",
                select=lambda e: c.textual(e)["label"] or _label_or_text(e),
            ),
            Field(
                "external_references",
                select=lambda e: c.refs_by_suffix(e, "Reference"),
            ),
        ),
        textual_fields=("name", "description", "language"),
        splat_metadata=True,
    ),
    "ingest_citation": CompositionSpec(
        collection="citations",
        record="CitationRecord",
        id_field="citation_id",
        dedup="seen_citations",
        id_slug="citation",
        counter="citation_index",
        fields=(
            Field(
                "title",
                select=lambda e: c.text_any(e, "titl", "title", "titlStmt/titl", "titleStmt/titl"),
            ),
            Field(
                "bibliographic",
                select=lambda e: c.text_any(e, "biblCit", "bibliographicCitation"),
            ),
            Field(
                "authors",
                select=lambda e: c.text_any(e, "AuthEnty", "author", "responsibleParty"),
            ),
        ),
        splat_metadata=True,
    ),
    "ingest_represented_variable": CompositionSpec(
        collection="represented_variables",
        record="RepresentedVariableRecord",
        id_field="represented_variable_id",
        dedup="seen_represented_variables",
        id_slug="represented_variable",
        counter="represented_variable_index",
        fields=(
            Field(
                "label",
                select=lambda e: c.text_any(e, "labl", "label") or c.text_or_none(e),
            ),
            Field(
                "concept",
                select=lambda e: c.attr(e, "concept") or c.text_any(e, "concept", "conceptRef"),
            ),
        ),
        splat_metadata=True,
    ),
    # Parametrized handlers: the dispatch passes a per-tag ``*_type``
    # literal that the element cannot carry on its own; the migrated
    # one-liner forwards it through ``_run_composition(..., extra=...)``.
    "ingest_coverage": CompositionSpec(
        collection="coverage",
        record="CoverageRecord",
        id_field="coverage_id",
        dedup="seen_coverage",
        id_slug="coverage",
        counter="coverage_index",
        fields=(
            Field(
                "description",
                select=lambda e: (
                    c.text_any(e, "keyword", "topcClas", "geogCover", "nation", "temporal")
                    or c.text_or_none(e)
                ),
            ),
            Field(
                "start_date",
                select=lambda e: (
                    c.attr(e, "start") or c.text_any(e, "start", "startDate", "eventStart")
                ),
            ),
            Field(
                "end_date",
                select=lambda e: c.attr(e, "end") or c.text_any(e, "end", "endDate", "eventEnd"),
            ),
        ),
        splat_metadata=True,
    ),
    "ingest_control_construct": CompositionSpec(
        collection="control_constructs",
        record="ControlConstructRecord",
        id_field="construct_id",
        dedup="seen_constructs",
        id_slug="construct",
        counter="construct_index",
        fields=(
            Field(
                "label",
                select=lambda e: c.text_any(e, "labl", "label") or c.text_or_none(e),
            ),
        ),
        splat_metadata=True,
    ),
    "ingest_comparison": CompositionSpec(
        collection="comparisons",
        record="ComparisonRecord",
        id_field="comparison_id",
        dedup="seen_comparisons",
        id_slug="comparison",
        counter="comparison_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
    "ingest_contributor_role": CompositionSpec(
        collection="contributor_roles",
        record="ContributorRoleRecord",
        id_field="contributor_id",
        dedup="seen_contributors",
        id_slug="contributor",
        counter="contributor_index",
        fields=(
            Field(
                "name",
                select=lambda e: (
                    c.text_any(e, "AuthEnty", "name", "contributorName") or c.text_or_none(e)
                ),
            ),
            Field(
                "role",
                select=lambda e: c.attr(e, "role") or c.text_any(e, "role", "roleName"),
            ),
        ),
        splat_metadata=True,
    ),
    "ingest_access_policy": CompositionSpec(
        collection="access_policies",
        record="AccessPolicyRecord",
        id_field="access_policy_id",
        dedup="seen_access_policies",
        id_slug="policy",
        counter="access_policy_index",
        fields=(Field("description", select=c.text_or_none),),
        splat_metadata=True,
    ),
}


__all__ = ["SPECS", "CompositionSpec", "Field"]
