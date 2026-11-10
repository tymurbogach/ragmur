"""Carga y valida el manifiesto y el conjunto de evaluación."""

import hashlib
from pathlib import Path
from typing import Annotated, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class StrictModel(BaseModel):
    """Rechaza campos que no pertenecen al contrato de evaluación."""

    model_config = ConfigDict(extra="forbid")


class PageLocator(StrictModel):
    type: Literal["page"]
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> "PageLocator":
        if self.end < self.start:
            raise ValueError("Invalid page range")
        return self


class OffsetLocator(StrictModel):
    type: Literal["offset"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "OffsetLocator":
        if self.end <= self.start:
            raise ValueError("Invalid offset range")
        return self


class SectionLocator(StrictModel):
    type: Literal["section"]
    path: list[str] = Field(min_length=1)
    ordinal: int = Field(ge=1)
    value: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: list[str]) -> list[str]:
        if any(not part.strip() for part in value):
            raise ValueError("Section path must not be blank")
        return value

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Section value must not be blank")
        return value


Locator = Annotated[PageLocator | OffsetLocator | SectionLocator, Field(discriminator="type")]


class DocumentSpec(StrictModel):
    key: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    tenant: str = Field(min_length=1)
    owner_id: str | None = None

    @field_validator("key", "path", "source", "license", "tenant")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Document fields must not be blank")
        return value

    @field_validator("owner_id")
    @classmethod
    def owner_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Owner ID must not be blank")
        return value


class CorpusManifest(StrictModel):
    documents: list[DocumentSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_keys(self) -> "CorpusManifest":
        keys = [document.key for document in self.documents]
        if len(set(keys)) != len(keys):
            raise ValueError("Document keys must be unique")
        identities = [(item.tenant, item.owner_id, item.sha256) for item in self.documents]
        if len(set(identities)) != len(identities):
            raise ValueError("Documents must be unique within their authorized space")
        return self


class Scope(StrictModel):
    tenant: str = Field(min_length=1)
    owner_id: str | None = None

    @field_validator("tenant", "owner_id")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Scope values must not be blank")
        return value


class EvidenceSpec(StrictModel):
    evidence_id: str = Field(min_length=1)
    document: str = Field(min_length=1)
    locator: Locator
    quote: str = Field(min_length=1)

    @field_validator("evidence_id", "document", "quote")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evidence fields must not be blank")
        return value


class QuerySpec(StrictModel):
    id: str = Field(min_length=1)
    split: Literal["dev", "test"]
    scope: Scope
    query: str = Field(min_length=1)
    expected: list[EvidenceSpec]
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_query(self) -> "QuerySpec":
        if not self.id.strip() or not self.query.strip() or not self.note.strip():
            raise ValueError("Query fields must not be blank")
        ids = [evidence.evidence_id for evidence in self.expected]
        if len(set(ids)) != len(ids):
            raise ValueError("Evidence IDs must be unique within a query")
        return self


def _load_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot read evaluation file: {path.name}") from exc


def load_manifest(path: Path) -> CorpusManifest:
    """Comprueba el manifiesto, la ubicación y la huella de cada documento."""
    manifest = CorpusManifest.model_validate(_load_yaml(path))
    root = path.parent.resolve()
    for document in manifest.documents:
        file_path = (root / document.path).resolve()
        if not file_path.is_relative_to(root) or not file_path.is_file():
            raise ValueError(f"Invalid corpus path for {document.key}")
        digest = hashlib.sha256()
        with file_path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != document.sha256:
            raise ValueError(f"Corpus hash mismatch for {document.key}")
    return manifest


def load_queries(path: Path, manifest: CorpusManifest) -> list[QuerySpec]:
    """Comprueba las consultas, particiones y referencias al corpus."""
    queries = TypeAdapter(list[QuerySpec]).validate_python(_load_yaml(path))
    ids = [query.id for query in queries]
    if len(set(ids)) != len(ids):
        raise ValueError("Query IDs must be unique")
    documents = {document.key: document for document in manifest.documents}
    tenants = {document.tenant for document in manifest.documents}
    keys = set(documents)
    if any(evidence.document not in keys for query in queries for evidence in query.expected):
        raise ValueError("A query references an unknown document")
    for query in queries:
        if query.scope.tenant not in tenants:
            raise ValueError("A query scope references an unknown tenant")
    for query in queries:
        for evidence in query.expected:
            document = documents[evidence.document]
            if document.tenant != query.scope.tenant or (
                query.scope.owner_id is not None and document.owner_id != query.scope.owner_id
            ):
                raise ValueError("An evidence reference is outside the query scope")
    return queries


def validate_dataset(queries: list[QuerySpec]) -> None:
    """Exige el tamaño y las particiones mínimos del conjunto del roadmap."""
    if not 25 <= len(queries) <= 30:
        raise ValueError("The golden set must contain 25 to 30 queries")
    for split in ("dev", "test"):
        partition = [query for query in queries if query.split == split]
        if not any(query.expected for query in partition) or not any(
            not query.expected for query in partition
        ):
            raise ValueError(f"The {split} split requires positive and negative queries")
