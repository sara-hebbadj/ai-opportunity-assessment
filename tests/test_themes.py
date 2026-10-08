"""Voice of staff: the data files, the coding prompt and the parsing of model answers."""

from __future__ import annotations

from opportunity_assessment import themes
from opportunity_assessment.llm import FakeLLM, Tracer


def test_120_snippets_with_unique_ids():
    snippets = themes.load_snippets()
    assert len(snippets) == 120
    assert len({s["snippet_id"] for s in snippets}) == 120
    assert sum(s["source"] == "survey" for s in snippets) == 40


def test_codebook_has_eight_themes():
    assert [t["theme_id"] for t in themes.load_codebook()] == themes.THEME_IDS


def test_author_labels_cover_every_snippet_and_use_valid_themes():
    labels = themes.load_author_labels()
    assert set(labels) == {s["snippet_id"] for s in themes.load_snippets()}
    assert {r["author_theme"] for r in labels.values()} <= set(themes.THEME_IDS)


def test_prompt_never_contains_the_answer_key():
    snippet = themes.load_snippets()[0]
    text = " ".join(m["content"] for m in themes.build_messages(snippet, themes.load_codebook()))
    assert snippet["text"] in text
    assert "author_theme" not in text and "clarity" not in text


def test_code_snippet_parses_json(scripted):
    llm = scripted('```json\n{"theme": "t3", "reason": "rework"}\n```')
    row = themes.code_snippet(llm, themes.load_snippets()[0], themes.load_codebook())
    assert row["theme"] == "T3" and row["error"] == ""


def test_bad_answers_are_recorded_not_raised(scripted):
    llm = scripted("no json here", '{"theme": "T9"}')
    snippet, codebook = themes.load_snippets()[0], themes.load_codebook()
    assert themes.code_snippet(llm, snippet, codebook)["error"] == "ValueError"
    assert themes.code_snippet(llm, snippet, codebook)["error"].startswith("bad theme")


def test_fake_llm_runs_offline(tmp_path):
    row = themes.code_snippet(FakeLLM(Tracer(path=tmp_path / "t.jsonl")), themes.load_snippets()[0],
                              themes.load_codebook())
    assert row["theme"] == "T1"


def test_compare_coders_skips_uncoded_snippets():
    result = themes.compare_coders({"S1": "T1", "S2": "T2", "S3": ""}, {"S1": "T1", "S2": "T1", "S3": "T3"})
    assert result["n"] == 2
    assert result["agreement"] == 0.5


def test_sara_sheet_starts_empty():
    assert themes.load_sara_codes() == {}
