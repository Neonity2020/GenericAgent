"""Unit tests for plugins/hooks.py — plugin registration system."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.hooks import register, trigger, unregister, clear, has, _registry


class TestHooksRegister:
    def setup_method(self):
        clear()

    def test_register_and_has(self):
        @register("test_event")
        def handler(ctx):
            pass
        assert has("test_event")

    def test_no_registered(self):
        assert not has("nonexistent")

    def test_multiple_handlers(self):
        @register("evt")
        def h1(ctx):
            pass
        @register("evt")
        def h2(ctx):
            pass
        assert len(_registry["evt"]) == 2


class TestHooksTrigger:
    def setup_method(self):
        clear()

    def test_trigger_calls_handlers(self):
        calls = []

        @register("test")
        def handler(ctx):
            calls.append(ctx.get("val"))

        trigger("test", {"val": 42})
        assert calls == [42]

    def test_trigger_returns_context(self):
        @register("test")
        def handler(ctx):
            return {**ctx, "added": True}

        result = trigger("test", {"x": 1})
        assert result["added"] is True
        assert result["x"] == 1

    def test_trigger_nonexistent_event(self):
        result = trigger("nope", {"a": 1})
        assert result == {"a": 1}

    def test_handler_exception_is_caught(self, capsys):
        @register("err")
        def handler(ctx):
            raise RuntimeError("boom")

        result = trigger("err", {"x": 1})
        assert result == {"x": 1}
        captured = capsys.readouterr()
        assert "boom" in captured.err


class TestHooksUnregister:
    def setup_method(self):
        clear()

    def test_unregister_removes_handler(self):
        @register("evt")
        def handler(ctx):
            pass
        unregister("evt", handler)
        assert not has("evt")

    def test_unregister_nonexistent_event(self):
        def handler(ctx):
            pass
        unregister("nonexistent", handler)  # should not raise

    def test_unregister_preserves_others(self):
        @register("evt")
        def h1(ctx):
            pass
        @register("evt")
        def h2(ctx):
            pass
        unregister("evt", h1)
        assert has("evt")
        assert len(_registry["evt"]) == 1


class TestHooksClear:
    def setup_method(self):
        clear()

    def test_clear_specific_event(self):
        @register("a")
        def h1(ctx):
            pass
        @register("b")
        def h2(ctx):
            pass
        clear("a")
        assert not has("a")
        assert has("b")

    def test_clear_all(self):
        @register("a")
        def h1(ctx):
            pass
        @register("b")
        def h2(ctx):
            pass
        clear()
        assert not has("a")
        assert not has("b")
