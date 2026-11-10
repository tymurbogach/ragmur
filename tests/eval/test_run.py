"""Interfaz del evaluador sin inferencia real."""

from eval.run import build_arguments, document_uuid


def test_document_uuid_is_stable() -> None:
    assert document_uuid("en-normans") == document_uuid("en-normans")
    assert document_uuid("en-normans") != document_uuid("es-tesla-1")


def test_build_arguments_defaults() -> None:
    args = build_arguments([])
    assert args.candidates == 30 and args.top_k == 10 and args.split == "all"
