"""Unit tests for agent_loop.py — core agent loop primitives."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_loop import (
    StepOutcome,
    BaseHandler,
    json_default,
    exhaust,
    get_pretty_json,
    _clean_content,
    _compact_tool_args,
    try_call_generator,
)


# ---------- StepOutcome ----------

class TestStepOutcome:
    def test_defaults(self):
        o = StepOutcome(data="hello")
        assert o.data == "hello"
        assert o.next_prompt is None
        assert o.should_exit is False

    def test_custom_fields(self):
        o = StepOutcome(data={"k": 1}, next_prompt="next", should_exit=True)
        assert o.data == {"k": 1}
        assert o.next_prompt == "next"
        assert o.should_exit is True

    def test_none_data(self):
        o = StepOutcome(data=None)
        assert o.data is None


# ---------- json_default ----------

class TestJsonDefault:
    def test_set_becomes_list(self):
        result = json_default({1, 2, 3})
        assert isinstance(result, list)
        assert sorted(result) == [1, 2, 3]

    def test_non_serializable_becomes_str(self):
        class Foo:
            def __str__(self):
                return "foo_repr"
        assert json_default(Foo()) == "foo_repr"

    def test_works_with_json_dumps(self):
        data = {"items": {1, 2}, "obj": object()}
        result = json.dumps(data, default=json_default)
        assert isinstance(result, str)


# ---------- exhaust ----------

class TestExhaust:
    def test_returns_generator_return_value(self):
        def gen():
            yield "a"
            yield "b"
            return "final"
        assert exhaust(gen()) == "final"

    def test_empty_generator(self):
        def gen():
            return "done"
            yield  # make it a generator
        assert exhaust(gen()) == "done"

    def test_no_return_value(self):
        def gen():
            yield 1
            yield 2
        assert exhaust(gen()) is None


# ---------- get_pretty_json ----------

class TestGetPrettyJson:
    def test_basic_dict(self):
        result = get_pretty_json({"a": 1, "b": "hello"})
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": "hello"}

    def test_script_key_gets_semicolons_expanded(self):
        data = {"script": "a(); b(); c()"}
        result = get_pretty_json(data)
        assert ";\n  " in result

    def test_newlines_unescaped(self):
        data = {"text": "line1\nline2"}
        result = get_pretty_json(data)
        assert "\\n" not in result
        assert "line1\nline2" in result


# ---------- _clean_content ----------

class TestCleanContent:
    def test_empty(self):
        assert _clean_content("") == ""
        assert _clean_content(None) == ""

    def test_strips_file_content_tags(self):
        text = "before<file_content>lots of stuff</file_content>after"
        result = _clean_content(text)
        assert "<file_content>" not in result

    def test_strips_tool_tags(self):
        text = "hello<tool_use>inner</tool_use>world"
        result = _clean_content(text)
        assert "<tool_use>" not in result

    def test_collapses_excessive_newlines(self):
        text = "a\n\n\n\n\nb"
        result = _clean_content(text)
        assert "\n\n\n" not in result

    def test_shrinks_large_code_blocks(self):
        lines = "\n".join(f"line {i}" for i in range(20))
        text = f"```python\n{lines}\n```"
        result = _clean_content(text)
        assert "... (" in result
        assert "lines)" in result

    def test_preserves_small_code_blocks(self):
        lines = "\n".join(f"line {i}" for i in range(5))
        text = f"```python\n{lines}\n```"
        result = _clean_content(text)
        assert "line 0" in result
        assert "line 4" in result


# ---------- _compact_tool_args ----------

class TestCompactToolArgs:
    def test_basic(self):
        result = _compact_tool_args("some_tool", {"key": "value"})
        assert "value" in result

    def test_strips_index(self):
        result = _compact_tool_args("some_tool", {"key": "val", "_index": 3})
        assert "_index" not in result

    def test_path_basename(self):
        result = _compact_tool_args("file_read", {"path": "/a/b/c/file.py"})
        assert "file.py" in result
        assert "/a/b/c/" not in result

    def test_update_working_checkpoint_truncates(self):
        long_info = "x" * 100
        result = _compact_tool_args("update_working_checkpoint", {"key_info": long_info})
        assert len(result) <= 63  # 60 + "..."

    def test_ask_user_with_candidates(self):
        result = _compact_tool_args("ask_user", {
            "question": "Pick one",
            "candidates": ["A", "B"]
        })
        assert "Pick one" in result
        assert "A" in result
        assert "B" in result

    def test_long_args_truncated(self):
        result = _compact_tool_args("code_run", {"code": "x" * 200})
        assert len(result) <= 123  # 120 + "..."


# ---------- try_call_generator ----------

class TestTryCallGenerator:
    def test_regular_function(self):
        def f():
            return 42
        gen = try_call_generator(f)
        assert exhaust(gen) == 42

    def test_generator_function(self):
        def g():
            yield "step1"
            yield "step2"
            return "done"
        gen = try_call_generator(g)
        collected = []
        try:
            while True:
                collected.append(next(gen))
        except StopIteration as e:
            assert e.value == "done"
        assert collected == ["step1", "step2"]


# ---------- BaseHandler ----------

class TestBaseHandler:
    def test_dispatch_unknown_tool(self):
        handler = BaseHandler()
        gen = handler.dispatch("nonexistent_tool", {}, None)
        messages = []
        try:
            while True:
                messages.append(next(gen))
        except StopIteration as e:
            outcome = e.value
        assert any("未知工具" in m for m in messages)
        assert outcome.should_exit is False

    def test_dispatch_bad_json(self):
        handler = BaseHandler()
        gen = handler.dispatch("bad_json", {"msg": "parse error"}, None)
        try:
            while True:
                next(gen)
        except StopIteration as e:
            outcome = e.value
        assert outcome.next_prompt == "parse error"
        assert outcome.should_exit is False

    def test_turn_end_callback_returns_prompt(self):
        handler = BaseHandler()
        result = handler.turn_end_callback(None, [], [], 1, "prompt", {})
        assert result == "prompt"
