"""Comprueba que las particiones NLI sean disjuntas y estén etiquetadas."""

from pathlib import Path

import yaml  # type: ignore[import-untyped]


def test_nli_cases_have_disjoint_premises_and_all_labels() -> None:
    cases = yaml.safe_load(Path("eval/nli_cases.yaml").read_text(encoding="utf-8"))
    dev = {case["premise"] for case in cases if case["split"] == "dev"}
    test = {case["premise"] for case in cases if case["split"] == "test"}
    assert dev and test and dev.isdisjoint(test)
    for split in ("dev", "test"):
        assert {
            claim["label"] for case in cases if case["split"] == split for claim in case["claims"]
        } == {"supported", "unsupported", "contradicted"}
