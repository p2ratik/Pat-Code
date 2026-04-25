"""
test_utils.py — Tests for utility modules (text, errors, paths).
Pure unit tests — no I/O, no credentials, no network.
"""

import pytest
from pathlib import Path

from utils.text import count_tokens, estimate_tokens, truncate_text
from utils.errors import AgentError, ConfigError
from utils.paths import display_path_rel_to_cwd


# ---------------------------------------------------------------------------
# count_tokens / estimate_tokens
# ---------------------------------------------------------------------------

class TestCountTokens:
    """
    count_tokens(text, model) — text first, model second.
    This also validates the bug fix we applied.
    """

    def test_correct_arg_order(self):
        """Calling with (text, model) must not crash and return a positive int."""
        result = count_tokens("hello world", "cl100k_base")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_text_returns_one(self):
        result = count_tokens("", "cl100k_base")
        assert result >= 1

    def test_longer_text_more_tokens(self):
        short = count_tokens("hi", "cl100k_base")
        long = count_tokens("hi " * 100, "cl100k_base")
        assert long > short

    def test_unknown_model_falls_back(self):
        """Unknown model should fall back to cl100k_base silently."""
        result = count_tokens("some text", "totally-fake-model-xyz")
        assert isinstance(result, int)
        assert result > 0

    def test_none_text_uses_estimate(self):
        """If text is None-ish, estimate_tokens handles it."""
        result = estimate_tokens("")
        assert result >= 1

    def test_estimate_tokens_proportional(self):
        short = estimate_tokens("ab")
        long = estimate_tokens("ab" * 100)
        assert long >= short


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------

class TestTruncateText:
    def test_short_text_unchanged(self):
        text = "hello world"
        result = truncate_text(text, model="cl100k_base", max_tokens=1000)
        assert result == text

    def test_long_text_truncated(self):
        text = "word " * 2000
        result = truncate_text(text, model="cl100k_base", max_tokens=50)
        assert len(result) < len(text)
        assert "[truncated]" in result

    def test_truncated_result_fits_budget(self):
        text = "word " * 2000
        max_tokens = 100
        result = truncate_text(text, model="cl100k_base", max_tokens=max_tokens)
        actual_tokens = count_tokens(result, "cl100k_base")
        # Allow a small margin for the suffix
        assert actual_tokens <= max_tokens + 5


# ---------------------------------------------------------------------------
# AgentError / ConfigError
# ---------------------------------------------------------------------------

class TestAgentError:
    def test_basic_message(self):
        e = AgentError("something went wrong")
        assert "something went wrong" in str(e)

    def test_with_details(self):
        e = AgentError("bad", details={"code": 42})
        assert "code=42" in str(e)

    def test_with_cause(self):
        cause = ValueError("root cause")
        e = AgentError("outer", cause=cause)
        assert "root cause" in str(e)

    def test_to_dict(self):
        e = AgentError("msg", details={"k": "v"})
        d = e.to_dict()
        assert d["type"] == "AgentError"
        assert d["message"] == "msg"
        assert d["details"] == {"k": "v"}
        assert d["cause"] is None

    def test_is_exception(self):
        with pytest.raises(AgentError):
            raise AgentError("boom")


class TestConfigError:
    def test_is_agent_error(self):
        e = ConfigError("bad config")
        assert isinstance(e, AgentError)

    def test_config_key_stored(self):
        e = ConfigError("missing key", config_key="api_key")
        assert e.config_key == "api_key"
        assert "api_key" in str(e)

    def test_config_file_stored(self):
        e = ConfigError("bad file", config_file="/etc/config.toml")
        assert e.config_file == "/etc/config.toml"
        assert "/etc/config.toml" in str(e)

    def test_to_dict_has_type(self):
        e = ConfigError("x")
        assert e.to_dict()["type"] == "ConfigError"


# ---------------------------------------------------------------------------
# display_path_rel_to_cwd
# ---------------------------------------------------------------------------

class TestDisplayPathRelToCwd:
    def test_absolute_path_within_cwd(self, tmp_path):
        file_path = str(tmp_path / "subdir" / "file.py")
        result = display_path_rel_to_cwd(file_path, cwd=tmp_path)
        assert "subdir" in result
        # Should be relative, not the full absolute path
        assert str(tmp_path) not in result or result.startswith("subdir")

    def test_cwd_none_returns_something(self, tmp_path):
        result = display_path_rel_to_cwd(str(tmp_path / "foo.py"), cwd=None)
        assert isinstance(result, str)
        assert len(result) > 0
