"""Explicit backend selection + disable switch for ambient-key auto-detection (#4361).

`detect_backend()` picks a cloud provider purely from whichever API key is set
in the environment, and community labeling additionally falls back to `claude -p`
when the CLI is on PATH. Keys in a developer environment are often there for
other tools, so a bare `graphify extract .` could send uncached documents to a
provider the user did not intend.

These tests pin the additions that put the user back in control:

- `GRAPHIFY_BACKEND=<name>` selects a backend explicitly, overriding ambient keys;
- `GRAPHIFY_BACKEND=none` disables every LLM backend, including the `claude -p`
  fallback, so the AST pass keeps working;
- auto-detection reports the exact environment variable that selected it.
"""
from __future__ import annotations

import pytest

from graphify import llm

DISABLE_SENTINELS = ["none", "off", "disable", "disabled"]


def test_detect_backend_with_source_names_the_ambient_variable(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    backend, source = llm.detect_backend_with_source()
    assert backend == "gemini"
    assert source == "auto-detected from GEMINI_API_KEY"
    assert llm.detect_backend() == "gemini"


def test_graphify_backend_selects_explicitly(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    monkeypatch.setenv("GRAPHIFY_BACKEND", "openai")
    backend, source = llm.detect_backend_with_source()
    assert backend == "openai", "GRAPHIFY_BACKEND must win over an ambient key"
    assert source == "GRAPHIFY_BACKEND=openai"


@pytest.mark.parametrize("sentinel", DISABLE_SENTINELS)
def test_graphify_backend_none_disables(monkeypatch, sentinel):
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    monkeypatch.setenv("GRAPHIFY_BACKEND", sentinel)
    assert llm.detect_backend() is None
    assert llm.backend_disabled_by_env() is True
    _, source = llm.detect_backend_with_source()
    assert source == f"GRAPHIFY_BACKEND={sentinel}"


def test_backend_not_disabled_when_unset(monkeypatch):
    assert llm.backend_disabled_by_env() is False


def test_extract_files_direct_refuses_cleanly_when_disabled(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_BACKEND", "none")
    with pytest.raises(ValueError, match="GRAPHIFY_BACKEND=none"):
        llm.extract_files_direct([], backend=None)


def test_generate_community_labels_skips_claude_cli_when_disabled(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_BACKEND", "none")
    monkeypatch.setattr(llm, "_claude_cli_available", lambda: True)

    calls = {"n": 0}

    def _spy(*args, **kwargs):  # pragma: no cover - must not run
        calls["n"] += 1
        return {}

    monkeypatch.setattr(llm, "label_communities", _spy)

    labels, source = llm.generate_community_labels(
        None, {0: ["a"], 1: ["b"]}, quiet=True
    )
    assert source == "placeholder"
    assert labels == {0: "Community 0", 1: "Community 1"}
    assert calls["n"] == 0, "no backend may be contacted when GRAPHIFY_BACKEND=none"


# --- GRAPHIFY_NO_LLM hard kill switch (#2781) ------------------------------

@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_graphify_no_llm_forces_no_backend(monkeypatch, value):
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    monkeypatch.setenv("GRAPHIFY_BACKEND", "openai")  # explicit choice loses too
    monkeypatch.setenv("GRAPHIFY_NO_LLM", value)
    backend, source = llm.detect_backend_with_source()
    assert backend is None
    assert source == f"GRAPHIFY_NO_LLM={value}"
    assert llm.detect_backend() is None
    assert llm.backend_disabled_by_env() is True


@pytest.mark.parametrize("value", ["", "0", "false", "off"])
def test_graphify_no_llm_falsy_values_do_not_disable(monkeypatch, value):
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    monkeypatch.setenv("GRAPHIFY_NO_LLM", value)
    assert llm.detect_backend() == "gemini"
    assert llm.backend_disabled_by_env() is False


def test_extract_files_direct_refuses_even_explicit_backend_when_no_llm(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_NO_LLM", "1")
    with pytest.raises(ValueError, match="GRAPHIFY_NO_LLM=1"):
        llm.extract_files_direct([], backend="gemini")


def test_generate_community_labels_skips_llm_when_no_llm(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_NO_LLM", "1")
    monkeypatch.setattr(llm, "_claude_cli_available", lambda: True)
    calls = {"n": 0}

    def _spy(*args, **kwargs):  # pragma: no cover - must not run
        calls["n"] += 1
        return {}

    monkeypatch.setattr(llm, "label_communities", _spy)
    # An explicit backend= must not bypass the kill switch either.
    labels, source = llm.generate_community_labels(
        None, {0: ["a"], 1: ["b"]}, backend="gemini", quiet=True
    )
    assert source == "placeholder"
    assert labels == {0: "Community 0", 1: "Community 1"}
    assert calls["n"] == 0



def test_call_llm_refuses_even_explicit_backend_when_no_llm(monkeypatch):
    # dedup's tiebreaker and community labeling both funnel through _call_llm.
    monkeypatch.setenv("GRAPHIFY_NO_LLM", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    with pytest.raises(ValueError, match="GRAPHIFY_NO_LLM=1"):
        llm._call_llm("yes or no?", backend="gemini")


def test_label_communities_refuses_even_explicit_backend_when_no_llm(monkeypatch):
    monkeypatch.setenv("GRAPHIFY_NO_LLM", "1")
    with pytest.raises(ValueError, match="GRAPHIFY_NO_LLM=1"):
        llm.label_communities(None, {0: ["a"]}, backend="gemini")


def test_pr_triage_refuses_when_no_llm(monkeypatch):
    from graphify import prs

    monkeypatch.setenv("GRAPHIFY_NO_LLM", "1")
    monkeypatch.setenv("GRAPHIFY_TRIAGE_BACKEND", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient")
    with pytest.raises(ValueError, match="GRAPHIFY_NO_LLM=1"):
        prs._resolve_triage_backend()


def test_extract_files_direct_skips_the_call_when_every_unit_is_excluded(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "ambient")
    secret = tmp_path / "deploy.yml"
    secret.write_text("password: hunter2\n", encoding="utf-8")

    def _boom(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("backend was called with an empty prompt")

    monkeypatch.setattr(llm, "_call_gemini", _boom)
    result = llm.extract_files_direct([secret], backend="gemini", root=tmp_path)
    assert result["nodes"] == [] and result["edges"] == []
    assert result["input_tokens"] == 0
