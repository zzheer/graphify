"""Secrets must never be shipped to an LLM backend (#2781).

``llm._read_files`` is the one place where raw file text is put into an
extraction prompt. Config/deployment formats (.yml/.yaml/.tfvars) and
credential-store files (.env*, *.pem/.key/.p12/.pfx, id_rsa*, *secrets*,
*credentials*) are kept out of it by default, with a one-line stderr note,
and ``GRAPHIFY_LLM_INCLUDE_SENSITIVE=1`` is the explicit override.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from graphify import llm


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("GRAPHIFY_LLM_INCLUDE_SENSITIVE", raising=False)
    monkeypatch.setattr(llm, "_llm_excluded_warned", set())


EXCLUDED_NAMES = [
    "docker-compose.yml",
    "ci.yaml",
    "prod.tfvars",
    "server.pem",
    "server.key",
    "bundle.p12",
    "bundle.pfx",
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
    ".env",
    ".env.local",
    "secrets.json",
    "my_secret.txt",
    "credentials.json",
    "aws_credentials",
    "SECRETS.md",
]

ALLOWED_NAMES = [
    "README.md", "design.txt", "paper.pdf", "notes.rst", "api.md",
    # keyword buried inside a word is a topic, not a credential store
    "secretary.md", "secretive-design.md", "credentialed_users.md",
]


@pytest.mark.parametrize("name", EXCLUDED_NAMES)
def test_excluded_names_have_a_reason(name):
    assert llm._llm_excluded_reason(Path(name)) is not None


@pytest.mark.parametrize("name", ALLOWED_NAMES)
def test_ordinary_documents_are_not_excluded(name):
    assert llm._llm_excluded_reason(Path(name)) is None


def test_read_files_drops_excluded_files_and_warns(tmp_path: Path, capsys):
    secret = tmp_path / "deploy.yml"
    secret.write_text("password: hunter2\n", encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("API_KEY=sk-live-123\n", encoding="utf-8")
    doc = tmp_path / "README.md"
    doc.write_text("# Hello\n", encoding="utf-8")

    prompt = llm._read_files([secret, env, doc], tmp_path)
    assert "hunter2" not in prompt
    assert "sk-live-123" not in prompt
    assert "# Hello" in prompt
    err = capsys.readouterr().err
    assert "not sending deploy.yml to the LLM backend" in err
    assert "not sending .env to the LLM backend" in err


def test_read_files_warns_once_per_file(tmp_path: Path, capsys):
    secret = tmp_path / "deploy.yml"
    secret.write_text("password: hunter2\n", encoding="utf-8")
    llm._read_files([secret], tmp_path)
    llm._read_files([secret], tmp_path)
    assert capsys.readouterr().err.count("not sending deploy.yml") == 1


def test_dispatched_source_text_skips_excluded(tmp_path: Path):
    secret = tmp_path / "prod.tfvars"
    secret.write_text("db_password = \"hunter2\"\n", encoding="utf-8")
    doc = tmp_path / "README.md"
    doc.write_text("# Hello\n", encoding="utf-8")
    seen = llm._dispatched_source_text([secret, doc], tmp_path)
    assert secret.resolve() not in seen
    assert doc.resolve() in seen


def test_include_sensitive_env_overrides(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GRAPHIFY_LLM_INCLUDE_SENSITIVE", "1")
    secret = tmp_path / "deploy.yml"
    secret.write_text("password: hunter2\n", encoding="utf-8")
    assert llm._llm_excluded_reason(secret) is None
    assert "hunter2" in llm._read_files([secret], tmp_path)


# Prose notes whose stem is a multi-word topic slug are documents *about* the
# subject; detect keeps them in the graph (#2106), so the prompt keeps them too.
PROSE_TOPIC_NAMES = [
    "managing-secrets-in-ci.md",
    "credential-rotation-runbook.md",
    "credentials_guide.md",
    "secret_manager.md",
]


@pytest.mark.parametrize("name", PROSE_TOPIC_NAMES)
def test_prose_topic_notes_are_not_excluded(name):
    assert llm._llm_excluded_reason(Path(name)) is None


def test_symlink_alias_is_judged_by_its_target(tmp_path: Path, capsys):
    target = tmp_path / "config" / "prod.yaml"
    target.parent.mkdir()
    target.write_text("password: hunter2\n", encoding="utf-8")
    alias = tmp_path / "docs" / "deployment.md"
    alias.parent.mkdir()
    try:
        alias.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported here")

    assert "hunter2" not in llm._read_files([alias], tmp_path)
    assert "not sending docs/deployment.md" in capsys.readouterr().err
    assert target.resolve() not in llm._dispatched_source_text([alias], tmp_path)


def test_image_refs_skip_credential_like_names(tmp_path: Path, capsys):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    secret = tmp_path / "aws_credentials_console_screenshot.png"
    secret.write_bytes(png)
    plain = tmp_path / "architecture_overview_diagram.png"
    plain.write_bytes(png)

    refs = llm._build_image_refs([secret, plain], tmp_path, read_bytes=False)
    assert [r.rel for r in refs] == ["architecture_overview_diagram.png"]
    assert "not sending aws_credentials_console_screenshot.png" in capsys.readouterr().err


def test_excluded_warned_set_is_bounded(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(llm, "_LLM_EXCLUDED_WARNED_MAX", 3)
    for i in range(10):
        assert llm._skip_llm_excluded(tmp_path / f"{i}.yml", f"{i}.yml")
    assert len(llm._llm_excluded_warned) <= 3
