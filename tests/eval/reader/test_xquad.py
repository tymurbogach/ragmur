"""Descarga fijada, partición y casos XQuAD-es sin modelos."""

from pathlib import Path
from typing import Any

import pytest
from eval.reader.xquad import (
    PARTITION_SEED,
    check_article_count,
    document_key,
    iter_paragraphs,
    list_cases,
    load_dataset,
    sample_cases,
    split_articles,
)


def tiny_dataset() -> dict[str, Any]:
    """Dos artículos mínimos en formato SQuAD v1.1."""
    return {
        "data": [
            {
                "title": "Tesla",
                "paragraphs": [
                    {
                        "context": "Nikola Tesla was an inventor.",
                        "qas": [
                            {
                                "id": "qa-1",
                                "question": "Who was Nikola Tesla?",
                                "answers": [{"text": "an inventor"}, {"text": "an inventor"}],
                            }
                        ],
                    },
                    {
                        "context": "He worked on alternating current.",
                        "qas": [
                            {
                                "id": "qa-2",
                                "question": "What did he work on?",
                                "answers": [{"text": "alternating current"}],
                            }
                        ],
                    },
                ],
            },
            {
                "title": "Curie",
                "paragraphs": [
                    {
                        "context": "Marie Curie won two Nobel prizes.",
                        "qas": [
                            {
                                "id": "qa-3",
                                "question": "How many Nobel prizes?",
                                "answers": [{"text": "two"}],
                            }
                        ],
                    }
                ],
            },
        ]
    }


def test_bad_file_is_refused(tmp_path: Path) -> None:
    corrupted = tmp_path / "xquad.es.json"
    corrupted.write_text('{"data": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset(corrupted)


def test_parsing_counts_and_distinct_answers() -> None:
    data = tiny_dataset()
    paragraphs = iter_paragraphs(data)
    assert [key for key, _ in paragraphs] == [
        "xquad-es:Tesla:0",
        "xquad-es:Tesla:1",
        "xquad-es:Curie:0",
    ]
    cases = list_cases(data, "dev", dev_size=2)
    assert [case.case_id for case in cases] == ["qa-1", "qa-2", "qa-3"]
    assert cases[0].answers == ("an inventor",)
    assert cases[0].document_key == document_key("Tesla", 0) == "xquad-es:Tesla:0"


def test_partition_is_deterministic_and_order_independent() -> None:
    titles = ["Tesla", "Curie", "Newton", "Galileo"]
    first = split_articles(titles, PARTITION_SEED, 3)
    assert first == split_articles(list(reversed(titles)), PARTITION_SEED, 3)
    assert sorted(title for title, split in first.items() if split == "dev")
    assert sum(1 for split in first.values() if split == "dev") == 3
    assert sum(1 for split in first.values() if split == "reserve") == 1


def test_reserve_is_sealed() -> None:
    data = tiny_dataset()
    with pytest.raises(ValueError, match="sealed"):
        list_cases(data, "reserve")
    opened = list_cases(data, "reserve", allow_reserve=True, dev_size=1)
    assert opened and all(case.split == "reserve" for case in opened)


def test_article_count_guard() -> None:
    with pytest.raises(ValueError, match="48 articles"):
        check_article_count(["Tesla", "Curie"])
    check_article_count([f"Article {index}" for index in range(48)])


def test_sampling_is_deterministic() -> None:
    cases = list_cases(tiny_dataset(), "dev", dev_size=2)
    first = sample_cases(cases, 2, PARTITION_SEED)
    assert [case.case_id for case in first] == [
        case.case_id for case in sample_cases(cases, 2, PARTITION_SEED)
    ]
    with pytest.raises(ValueError, match="sample size"):
        sample_cases(cases, 10, PARTITION_SEED)


def test_hash_mismatch_names_file_to_delete(tmp_path: Path) -> None:
    from eval.reader.xquad import verify_dataset_file

    bad = tmp_path / "xquad.es.json"
    bad.write_text('{"data": []}', encoding="utf-8")
    with pytest.raises(ValueError, match=r"delete.*xquad\.es\.json"):
        verify_dataset_file(bad)


def test_download_uses_tmp_file_and_renames(tmp_path: Path) -> None:
    import hashlib
    from unittest.mock import Mock, patch

    from eval.reader import xquad as xquad_module

    payload = b'{"data": []}'
    digest = hashlib.sha256(payload).hexdigest()
    target = tmp_path / "xquad.es.json"
    with (
        patch.object(xquad_module, "DATASET_SHA256", digest),
        patch.object(xquad_module, "urllib") as urllib_mock,
    ):
        response = Mock()
        response.read.return_value = payload
        urllib_mock.request.urlopen.return_value.__enter__.return_value = response
        out = xquad_module.download_dataset(target)
    assert out == target
    assert target.read_bytes() == payload
    assert not target.with_name(target.name + ".tmp").exists()


def test_collection_suffix_default_and_rejection() -> None:
    from eval.reader.index import DEFAULT_COLLECTION_SUFFIX
    from eval.reader.prepare import build_arguments

    assert build_arguments([]).collection_suffix == DEFAULT_COLLECTION_SUFFIX
    assert build_arguments([]).allow_dirty is False
