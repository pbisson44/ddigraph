"""Generated DDI-Codebook 2.6 schema metadata.

Auto-generated from ``schemas/ddi-c/codebook.xsd`` by
``scripts/generate_schema_definitions.py``. Do not edit by hand.

Re-run::

    python scripts/generate_schema_definitions.py

to regenerate after changing the bundled XSDs.
"""

from typing import NamedTuple


class CodebookElement(NamedTuple):
    """A DDI-Codebook element whose type carries the GLOBALS attributeGroup.

    ``tag`` is the lowercase element name as it appears in the
    XML payload (the codebook loader dispatches by lowercase).
    ``complex_type`` is the XSD complexType name. ``is_layout``
    is True for CALS table / presentation markup that the runtime
    skips for graph ingestion.
    """

    tag: str
    complex_type: str
    is_layout: bool


CODEBOOK_GENERATED_ELEMENTS: tuple[CodebookElement, ...] = (
    CodebookElement(tag="anlyinfo", complex_type="anlyInfoType", is_layout=False),
    CodebookElement(tag="boundpoly", complex_type="boundPolyType", is_layout=False),
    CodebookElement(tag="catgry", complex_type="catgryType", is_layout=False),
    CodebookElement(tag="catgrygrp", complex_type="catgryGrpType", is_layout=False),
    CodebookElement(tag="catlevel", complex_type="catLevelType", is_layout=False),
    CodebookElement(tag="citation", complex_type="citationType", is_layout=False),
    CodebookElement(tag="codebook", complex_type="codeBookType", is_layout=True),
    CodebookElement(
        tag="codinginstructions", complex_type="codingInstructionsType", is_layout=False
    ),
    CodebookElement(tag="cohort", complex_type="cohortType", is_layout=False),
    CodebookElement(tag="colspec", complex_type="colspecType", is_layout=True),
    CodebookElement(
        tag="controlledvocabused", complex_type="controlledVocabUsedType", is_layout=False
    ),
    CodebookElement(tag="cubecoord", complex_type="CubeCoordType", is_layout=False),
    CodebookElement(tag="dataaccs", complex_type="dataAccsType", is_layout=False),
    CodebookElement(tag="datacoll", complex_type="dataCollType", is_layout=False),
    CodebookElement(tag="datadscr", complex_type="dataDscrType", is_layout=False),
    CodebookElement(tag="dataitem", complex_type="dataItemType", is_layout=True),
    CodebookElement(tag="derivation", complex_type="derivationType", is_layout=False),
    CodebookElement(
        tag="developmentactivity", complex_type="developmentActivityType", is_layout=False
    ),
    CodebookElement(tag="dimensns", complex_type="dimensnsType", is_layout=False),
    CodebookElement(tag="diststmt", complex_type="distStmtType", is_layout=False),
    CodebookElement(tag="dmns", complex_type="dmnsType", is_layout=False),
    CodebookElement(tag="docdscr", complex_type="docDscrType", is_layout=False),
    CodebookElement(tag="docsrc", complex_type="docSrcType", is_layout=False),
    CodebookElement(tag="expostevaluation", complex_type="exPostEvaluationType", is_layout=False),
    CodebookElement(tag="extlink", complex_type="ExtLinkType", is_layout=False),
    CodebookElement(tag="filecitation", complex_type="citationType", is_layout=False),
    CodebookElement(tag="filecommand", complex_type="fileCommandType", is_layout=False),
    CodebookElement(tag="filederivation", complex_type="fileDerivationType", is_layout=False),
    CodebookElement(tag="filedscr", complex_type="fileDscrType", is_layout=False),
    CodebookElement(tag="filestrc", complex_type="fileStrcType", is_layout=False),
    CodebookElement(tag="filetxt", complex_type="fileTxtType", is_layout=False),
    CodebookElement(tag="frameunit", complex_type="frameUnitType", is_layout=False),
    CodebookElement(tag="geobndbox", complex_type="geoBndBoxType", is_layout=False),
    CodebookElement(tag="geomap", complex_type="geoMapType", is_layout=False),
    CodebookElement(tag="invalrng", complex_type="invalrngType", is_layout=False),
    CodebookElement(tag="item", complex_type="itemType", is_layout=True),
    CodebookElement(tag="link", complex_type="LinkType", is_layout=False),
    CodebookElement(tag="location", complex_type="locationType", is_layout=False),
    CodebookElement(tag="locmap", complex_type="locMapType", is_layout=False),
    CodebookElement(tag="measure", complex_type="measureType", is_layout=False),
    CodebookElement(tag="metadataaccs", complex_type="metadataAccsType", is_layout=False),
    CodebookElement(tag="method", complex_type="methodType", is_layout=False),
    CodebookElement(tag="mrow", complex_type="mrowType", is_layout=True),
    CodebookElement(tag="ncube", complex_type="nCubeType", is_layout=False),
    CodebookElement(tag="ncubegrp", complex_type="nCubeGrpType", is_layout=False),
    CodebookElement(tag="othermat", complex_type="otherMatType", is_layout=False),
    CodebookElement(tag="othrstdymat", complex_type="othrStdyMatType", is_layout=False),
    CodebookElement(tag="physloc", complex_type="physLocType", is_layout=False),
    CodebookElement(tag="point", complex_type="pointType", is_layout=False),
    CodebookElement(tag="polygon", complex_type="polygonType", is_layout=False),
    CodebookElement(tag="prodstmt", complex_type="prodStmtType", is_layout=False),
    CodebookElement(tag="qualitystatement", complex_type="qualityStatementType", is_layout=False),
    CodebookElement(tag="range", complex_type="rangeType", is_layout=False),
    CodebookElement(tag="recdimnsn", complex_type="recDimnsnType", is_layout=False),
    CodebookElement(tag="recgrp", complex_type="recGrpType", is_layout=False),
    CodebookElement(tag="resource", complex_type="resourceType", is_layout=False),
    CodebookElement(tag="row", complex_type="rowType", is_layout=True),
    CodebookElement(tag="rspstmt", complex_type="rspStmtType", is_layout=False),
    CodebookElement(tag="sampleframe", complex_type="sampleFrameType", is_layout=False),
    CodebookElement(tag="serstmt", complex_type="serStmtType", is_layout=False),
    CodebookElement(tag="setavail", complex_type="setAvailType", is_layout=False),
    CodebookElement(tag="sourcecitation", complex_type="citationType", is_layout=False),
    CodebookElement(tag="sources", complex_type="sourcesType", is_layout=False),
    CodebookElement(tag="standard", complex_type="standardType", is_layout=False),
    CodebookElement(
        tag="standardscompliance", complex_type="standardsComplianceType", is_layout=False
    ),
    CodebookElement(tag="stdydscr", complex_type="stdyDscrType", is_layout=False),
    CodebookElement(tag="stdyinfo", complex_type="stdyInfoType", is_layout=False),
    CodebookElement(
        tag="studyauthorization", complex_type="studyAuthorizationType", is_layout=False
    ),
    CodebookElement(tag="studydevelopment", complex_type="studyDevelopmentType", is_layout=False),
    CodebookElement(tag="subject", complex_type="subjectType", is_layout=False),
    CodebookElement(tag="sumdscr", complex_type="sumDscrType", is_layout=False),
    CodebookElement(tag="table", complex_type="tableType", is_layout=True),
    CodebookElement(tag="targetsamplesize", complex_type="targetSampleSizeType", is_layout=False),
    CodebookElement(tag="tbody", complex_type="tbodyType", is_layout=True),
    CodebookElement(tag="tgroup", complex_type="tgroupType", is_layout=True),
    CodebookElement(tag="thead", complex_type="theadType", is_layout=True),
    CodebookElement(tag="titlstmt", complex_type="titlStmtType", is_layout=False),
    CodebookElement(tag="usestmt", complex_type="useStmtType", is_layout=False),
    CodebookElement(tag="valrng", complex_type="valrngType", is_layout=False),
    CodebookElement(tag="var", complex_type="varType", is_layout=False),
    CodebookElement(tag="vargrp", complex_type="varGrpType", is_layout=False),
    CodebookElement(tag="varrange", complex_type="varRangeType", is_layout=False),
    CodebookElement(tag="verstmt", complex_type="verStmtType", is_layout=False),
)


__all__ = ["CODEBOOK_GENERATED_ELEMENTS", "CodebookElement"]
