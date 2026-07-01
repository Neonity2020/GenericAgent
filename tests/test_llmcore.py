"""Unit tests for llmcore.py — LLM utility functions."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llmcore import auto_make_url, compress_history_tags, _sanitize_leading_user_msg, _try_parse_tool_args


# ---------- auto_make_url ----------

class TestAutoMakeUrl:
    def test_base_with_dollar_sign(self):
        assert auto_make_url("https://api.example.com$", "chat/completions") == "https://api.example.com"

    def test_base_already_ends_with_path(self):
        result = auto_make_url("https://api.example.com/v1/chat/completions", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"

    def test_base_with_v1(self):
        result = auto_make_url("https://api.example.com/v1", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"

    def test_base_without_version(self):
        result = auto_make_url("https://api.example.com", "chat/completions")
        assert result == "https://api.example.com/v1/chat/completions"

    def test_trailing_slashes(self):
        result = auto_make_url("https://api.example.com/", "/chat/completions/")
        assert result == "https://api.example.com/v1/chat/completions"


# ---------- compress_history_tags ----------

class TestCompressHistoryTags:
    def setup_method(self):
        compress_history_tags._cd = -1

    def test_empty_messages(self):
        result = compress_history_tags([], force=True)
        assert result == []

    def test_compresses_old_thinking_tags(self):
        long_text = "x" * 2000
        messages = [
            {"role": "assistant", "content": f"<thinking>{long_text}</thinking>"},
        ] + [{"role": "user", "content": f"msg {i}"} for i in range(15)]
        compress_history_tags(messages, keep_recent=10, max_len=100, force=True)
        assert len(messages[0]["content"]) < 2000

    def test_skips_recent_messages(self):
        long_text = "x" * 2000
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
        messages.append({"role": "assistant", "content": f"<thinking>{long_text}</thinking>"})
        compress_history_tags(messages, keep_recent=10, max_len=100, force=True)
        assert long_text in messages[-1]["content"]

    def test_interval_skips(self):
        compress_history_tags._cd = 0
        messages = [{"role": "user", "content": "hi"}]
        result = compress_history_tags(messages, interval=5)
        assert result == messages

    def test_compresses_list_content(self):
        long_text = "y" * 2000
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": f"<thinking>{long_text}</thinking>"}
            ]},
        ] + [{"role": "user", "content": f"msg {i}"} for i in range(15)]
        compress_history_tags(messages, keep_recent=10, max_len=100, force=True)
        assert len(messages[0]["content"][0]["text"]) < 2000


# ---------- _sanitize_leading_user_msg ----------

class TestSanitizeLeadingUserMsg:
    def test_string_content_unchanged(self):
        msg = {"role": "user", "content": "hello"}
        result = _sanitize_leading_user_msg(msg)
        assert result["content"] == "hello"

    def test_tool_result_blocks_flattened(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": "tool output"},
                {"type": "text", "text": "user text"}
            ]
        }
        result = _sanitize_leading_user_msg(msg)
        assert result["content"] == [{"type": "text", "text": "tool output\nuser text"}]

    def test_nested_tool_result_content(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": [
                    {"type": "text", "text": "nested text"}
                ]}
            ]
        }
        result = _sanitize_leading_user_msg(msg)
        assert "nested text" in result["content"][0]["text"]

    def test_does_not_mutate_original(self):
        msg = {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        original_content = msg["content"]
        _sanitize_leading_user_msg(msg)
        assert msg["content"] is original_content


# ---------- _try_parse_tool_args ----------

class TestTryParseToolArgs:
    def test_empty_string(self):
        assert _try_parse_tool_args("") == [{}]

    def test_none(self):
        assert _try_parse_tool_args(None) == [{}]

    def test_valid_json(self):
        result = _try_parse_tool_args('{"key": "value"}')
        assert result == [{"key": "value"}]

    def test_concatenated_json(self):
        result = _try_parse_tool_args('{"a":1}{"b":2}')
        assert result == [{"a": 1}, {"b": 2}]

    def test_invalid_json(self):
        result = _try_parse_tool_args("not json at all")
        assert len(result) == 1
        assert "_raw" in result[0]

    def test_partial_invalid(self):
        result = _try_parse_tool_args('{"a":1}{bad}')
        assert len(result) == 1
        assert "_raw" in result[0]
