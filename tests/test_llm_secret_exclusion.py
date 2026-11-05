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

ALLOWED_NAMES = ["README.md", "design.txt", "paper.pdf", "notes.rst", "api.md"]


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
