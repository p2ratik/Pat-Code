"""
test_config.py — Config model & loader tests
No credentials, no API calls, no file system side-effects.
"""

import sys
import pytest
from pathlib import Path
from pydantic import ValidationError

from config.config import (
    ApprovalPolicy,
    Config,
    MCPServerConfig,
    ModelConfig,
    ShellEnvironmentPolicy,
    SubagentDefinition,
)


# ---------------------------------------------------------------------------
# ModelConfig
# ---------------------------------------------------------------------------

class TestModelConfig:
    def test_defaults(self):
        m = ModelConfig()
        assert m.name == "gpt-oss-120b"
        assert m.temperature == 0.0
        assert m.context_window == 256_000

    def test_custom_values(self):
        m = ModelConfig(name="gpt-4o", temperature=0.7, context_window=128_000)
        assert m.name == "gpt-4o"
        assert m.temperature == 0.7

    def test_temperature_lower_bound(self):
        with pytest.raises(ValidationError):
            ModelConfig(temperature=-0.1)

    def test_temperature_upper_bound(self):
        with pytest.raises(ValidationError):
            ModelConfig(temperature=2.1)

    def test_temperature_boundary_ok(self):
        ModelConfig(temperature=0.0)
        ModelConfig(temperature=2.0)


# ---------------------------------------------------------------------------
# ShellEnvironmentPolicy
# ---------------------------------------------------------------------------

class TestShellEnvironmentPolicy:
    def test_defaults(self):
        s = ShellEnvironmentPolicy()
        assert s.ignore_default_excludes is False
        assert "*KEY*" in s.exclude_patterns

    def test_custom_patterns(self):
        s = ShellEnvironmentPolicy(exclude_patterns=["*PASS*"])
        assert "*PASS*" in s.exclude_patterns
        assert "*KEY*" not in s.exclude_patterns


# ---------------------------------------------------------------------------
# MCPServerConfig
# ---------------------------------------------------------------------------

class TestMCPServerConfig:
    def test_stdio_transport(self):
        cfg = MCPServerConfig(command="npx", args=["-y", "some-server"])
        assert cfg.command == "npx"
        assert cfg.url is None

    def test_http_transport(self):
        cfg = MCPServerConfig(url="http://localhost:8080")
        assert cfg.url == "http://localhost:8080"
        assert cfg.command is None

    def test_no_transport_raises(self):
        with pytest.raises(ValidationError):
            MCPServerConfig()

    def test_both_transports_raises(self):
        with pytest.raises(ValidationError):
            MCPServerConfig(command="npx", url="http://localhost:8080")


# ---------------------------------------------------------------------------
# ApprovalPolicy
# ---------------------------------------------------------------------------

class TestApprovalPolicy:
    def test_all_values_present(self):
        values = {p.value for p in ApprovalPolicy}
        assert "on-request" in values
        assert "auto" in values
        assert "never" in values
        assert "yolo" in values
        assert "auto-edit" in values
        assert "on-failure" in values

    def test_from_string(self):
        assert ApprovalPolicy("auto") == ApprovalPolicy.AUTO


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_defaults(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        assert cfg.max_turns == 100
        assert cfg.approval == ApprovalPolicy.ON_REQUEST
        assert cfg.mcp_servers == {}
        assert cfg.allowed_tools is None

    def test_model_name_property(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        assert cfg.model_name == cfg.model.name

    def test_model_name_setter(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        cfg.model_name = "gpt-4o"
        assert cfg.model_name == "gpt-4o"
        assert cfg.model.name == "gpt-4o"

    def test_temperature_property(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        assert cfg.temperature == cfg.model.temperature

    def test_temperature_setter(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        cfg.temperature = 0.9
        assert cfg.model.temperature == 0.9

    def test_validate_missing_api_key(self, tmp_path, monkeypatch):
        """validate() must return an error when no API key is present."""
        monkeypatch.delenv("API_KEY", raising=False)
        # Ensure keyring returns nothing
        monkeypatch.setattr(
            "config.config.get_credential", lambda key: None
        )
        cfg = Config(cwd=tmp_path)
        errors = cfg.validate()
        assert any("API key" in e for e in errors)

    def test_validate_missing_cwd(self, tmp_path, monkeypatch):
        """validate() must return an error when cwd doesn't exist."""
        monkeypatch.setattr("config.config.get_credential", lambda key: "fake-key")
        nonexistent = tmp_path / "does_not_exist"
        cfg = Config(cwd=nonexistent)
        errors = cfg.validate()
        assert any("Working directory" in e for e in errors)

    def test_validate_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.config.get_credential", lambda key: "fake-key")
        cfg = Config(cwd=tmp_path)
        errors = cfg.validate()
        assert errors == []

    def test_to_dict_is_serialisable(self, tmp_path):
        import json
        cfg = Config(cwd=tmp_path)
        d = cfg.to_dict()
        # must be JSON-serialisable (no Path objects etc.)
        json.dumps(d)

    def test_mcp_server_config_embedded(self, tmp_path):
        cfg = Config(
            cwd=tmp_path,
            mcp_servers={"my-server": MCPServerConfig(command="node", args=["server.js"])},
        )
        assert "my-server" in cfg.mcp_servers


# ---------------------------------------------------------------------------
# SubagentDefinition (dataclass)
# ---------------------------------------------------------------------------

class TestSubagentDefinition:
    def test_defaults(self):
        sd = SubagentDefinition(name="test", description="desc", goal_prompt="do stuff")
        assert sd.allowed_tools is None
        assert sd.max_turns == 20
        assert sd.timeout_seconds == 600
