"""
test_client_response.py — Tests for client/response.py data models.
Pure unit tests — no network, no credentials.
"""

import json
import pytest

from client.response import (
    StreamEvent,
    StreamEventType,
    TextDelta,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    ToolResultMessage,
    parse_tool_call_arguments,
)


# ---------------------------------------------------------------------------
# TextDelta
# ---------------------------------------------------------------------------

class TestTextDelta:
    def test_str(self):
        td = TextDelta("hello")
        assert str(td) == "hello"

    def test_content_stored(self):
        td = TextDelta("world")
        assert td.content == "world"


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------

class TestTokenUsage:
    def test_defaults(self):
        u = TokenUsage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0
        assert u.cached_tokens == 0

    def test_addition(self):
        a = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cached_tokens=2)
        b = TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30, cached_tokens=0)
        c = a + b
        assert c.prompt_tokens == 30
        assert c.completion_tokens == 15
        assert c.total_tokens == 45
        assert c.cached_tokens == 2

    def test_addition_identity(self):
        a = TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8)
        zero = TokenUsage()
        assert (a + zero).prompt_tokens == 5


# ---------------------------------------------------------------------------
# ToolCall / ToolCallDelta
# ---------------------------------------------------------------------------

class TestToolCall:
    def test_fields(self):
        tc = ToolCall(call_id="abc123", name="shell", arguments={"command": "ls"})
        assert tc.call_id == "abc123"
        assert tc.name == "shell"

    def test_name_defaults_none(self):
        tc = ToolCall(call_id="x")
        assert tc.name is None

    def test_arguments_defaults_empty_str(self):
        tc = ToolCall(call_id="x")
        assert tc.arguments == ""


class TestToolCallDelta:
    def test_fields(self):
        d = ToolCallDelta(call_id="id1", name="read_file", arguments_delta='{"path":')
        assert d.name == "read_file"
        assert d.arguments_delta == '{"path":'

    def test_arguments_delta_defaults_empty(self):
        d = ToolCallDelta(call_id="id1")
        assert d.arguments_delta == ""


# ---------------------------------------------------------------------------
# StreamEvent
# ---------------------------------------------------------------------------

class TestStreamEvent:
    def test_text_delta_event(self):
        e = StreamEvent(
            type=StreamEventType.TEXT_DELTA,
            text_delta=TextDelta("hello"),
        )
        assert e.type == StreamEventType.TEXT_DELTA
        assert e.text_delta.content == "hello"

    def test_error_event(self):
        e = StreamEvent(type=StreamEventType.ERROR, error="oops")
        assert e.error == "oops"
        assert e.text_delta is None

    def test_tool_call_complete_event(self):
        tc = ToolCall(call_id="cid", name="shell", arguments={"command": "ls"})
        e = StreamEvent(type=StreamEventType.TOOL_CALL_COMPLETE, tool_call=tc)
        assert e.tool_call.name == "shell"

    def test_message_complete_with_usage(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        e = StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            finish_reason="stop",
            usage=usage,
        )
        assert e.finish_reason == "stop"
        assert e.usage.total_tokens == 15

    @pytest.mark.parametrize("event_type", list(StreamEventType))
    def test_all_event_types_constructable(self, event_type):
        e = StreamEvent(type=event_type)
        assert e.type == event_type


# ---------------------------------------------------------------------------
# ToolResultMessage
# ---------------------------------------------------------------------------

class TestToolResultMessage:
    def test_to_openai_message(self):
        msg = ToolResultMessage(tool_call_id="call_1", content="result text")
        openai_msg = msg.to_openai_message()
        assert openai_msg["role"] == "tool"
        assert openai_msg["tool_call_id"] == "call_1"
        assert openai_msg["content"] == "result text"

    def test_is_error_defaults_false(self):
        msg = ToolResultMessage(tool_call_id="x", content="ok")
        assert msg.is_error is False


# ---------------------------------------------------------------------------
# parse_tool_call_arguments
# ---------------------------------------------------------------------------

class TestParseToolCallArguments:
    def test_valid_json(self):
        result = parse_tool_call_arguments('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_empty_string(self):
        result = parse_tool_call_arguments("")
        assert result == {}

    def test_invalid_json_returns_raw(self):
        raw = "not valid json {"
        result = parse_tool_call_arguments(raw)
        assert "raw_arguments" in result
        assert result["raw_arguments"] == raw

    def test_nested_json(self):
        payload = json.dumps({"nested": {"a": 1}, "list": [1, 2, 3]})
        result = parse_tool_call_arguments(payload)
        assert result["nested"]["a"] == 1
        assert result["list"] == [1, 2, 3]
