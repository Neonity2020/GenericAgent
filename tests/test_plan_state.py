"""Unit tests for frontends/plan_state.py — plan/todo state management."""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontends.plan_state import (
    extract,
    summary,
    is_complete,
    _strip_md,
    _has_done_glyph,
    current_step,
    default_session_plan_path,
    is_session_scoped_plan_path,
    is_plan_preset_prompt,
)


# ---------- _strip_md ----------

class TestStripMd:
    def test_bold(self):
        assert _strip_md("**hello**") == "hello"

    def test_italic(self):
        assert _strip_md("*world*") == "world"

    def test_underscore_bold(self):
        assert _strip_md("__bold__") == "bold"

    def test_backtick(self):
        assert _strip_md("`code`") == "code"

    def test_no_markdown(self):
        assert _strip_md("plain text") == "plain text"

    def test_mixed(self):
        assert _strip_md("**a** and *b* and `c`") == "a and b and c"


# ---------- _has_done_glyph ----------

class TestHasDoneGlyph:
    def test_x(self):
        assert _has_done_glyph("x")

    def test_X(self):
        assert _has_done_glyph("X")

    def test_checkmark(self):
        assert _has_done_glyph("✓")

    def test_empty(self):
        assert not _has_done_glyph("")

    def test_space(self):
        assert not _has_done_glyph(" ")


# ---------- extract ----------

class TestExtract:
    def test_empty(self):
        assert extract("") == []
        assert extract(None) == []

    def test_basic_open_items(self):
        text = "- [ ] Task A\n- [ ] Task B"
        items = extract(text)
        assert len(items) == 2
        assert all(st == "open" for _, st in items)

    def test_basic_done_items(self):
        text = "- [x] Task A\n- [X] Task B"
        items = extract(text)
        assert len(items) == 2
        assert all(st == "done" for _, st in items)

    def test_mixed_items(self):
        text = "- [ ] Open\n- [x] Done"
        items = extract(text)
        assert len(items) == 2
        statuses = {c: s for c, s in items}
        assert statuses["Open"] == "open"
        assert statuses["Done"] == "done"

    def test_numbered_items(self):
        text = "1. [ ] First\n2. [x] Second\n3. [ ] Third"
        items = extract(text)
        assert len(items) == 3

    def test_checkmark_unicode(self):
        text = "- [✓] Completed task"
        items = extract(text)
        assert len(items) == 1
        assert items[0][1] == "done"

    def test_escaped_newlines(self):
        text = "- [ ] A\\n- [x] B"
        items = extract(text)
        assert len(items) == 2

    def test_bold_stripped(self):
        text = "- [ ] **Important task**"
        items = extract(text)
        assert len(items) == 1
        assert items[0][0] == "Important task"

    def test_inline_done_content(self):
        text = "1. [✓ 已生成: summary] "
        items = extract(text)
        assert len(items) == 1
        assert items[0][1] == "done"

    def test_duplicate_done_wins(self):
        text = "- [ ] Task\n- [x] Task"
        items = extract(text)
        assert len(items) == 1
        assert items[0][1] == "done"


# ---------- summary ----------

class TestSummary:
    def test_all_done(self):
        items = [("a", "done"), ("b", "done")]
        assert summary(items) == (2, 2)

    def test_none_done(self):
        items = [("a", "open"), ("b", "open")]
        assert summary(items) == (0, 2)

    def test_mixed(self):
        items = [("a", "done"), ("b", "open"), ("c", "done")]
        assert summary(items) == (2, 3)

    def test_empty(self):
        assert summary([]) == (0, 0)


# ---------- is_complete ----------

class TestIsComplete:
    def test_all_done(self):
        assert is_complete([("a", "done"), ("b", "done")])

    def test_has_open(self):
        assert not is_complete([("a", "done"), ("b", "open")])

    def test_empty(self):
        assert is_complete([])


# ---------- current_step ----------

class TestCurrentStep:
    def test_empty(self):
        assert current_step([]) == ""

    def test_finds_pinned_step(self):
        messages = ["some text", "📌 当前步骤：Implement feature X"]
        result = current_step(messages)
        assert "Implement feature X" in result

    def test_summary_tag_preferred(self):
        messages = [
            "<summary>blah 当前步骤：From summary</summary>",
            "📌 当前步骤：From pin"
        ]
        result = current_step(messages)
        assert "From pin" in result or "From summary" in result

    def test_truncation(self):
        long_step = "A" * 200
        messages = [f"📌 当前步骤：{long_step}"]
        result = current_step(messages, max_len=60)
        assert len(result) <= 61  # 60 + ellipsis char


# ---------- default_session_plan_path ----------

class TestDefaultSessionPlanPath:
    def test_basic(self):
        result = default_session_plan_path("abc123")
        assert result == "temp/plan_abc123/plan.md"

    def test_slash_replaced(self):
        result = default_session_plan_path("a/b")
        assert "/" not in result.replace("temp/", "").replace("/plan.md", "").replace("plan_", "")

    def test_empty_session(self):
        result = default_session_plan_path("")
        assert "plan_sess" in result


# ---------- is_session_scoped_plan_path ----------

class TestIsSessionScopedPlanPath:
    def test_matching_path(self):
        assert is_session_scoped_plan_path("temp/plan_abc/plan.md", "abc")

    def test_non_matching_path(self):
        assert not is_session_scoped_plan_path("temp/plan_xyz/plan.md", "abc")

    def test_empty_path(self):
        assert not is_session_scoped_plan_path("", "abc")


# ---------- is_plan_preset_prompt ----------

class TestIsPlanPresetPrompt:
    def test_plan_sop(self):
        assert is_plan_preset_prompt("use plan_sop to do this")

    def test_plan_mode(self):
        assert is_plan_preset_prompt("enter plan mode")
        assert is_plan_preset_prompt("Plan 模式")

    def test_unrelated(self):
        assert not is_plan_preset_prompt("just a normal prompt")

    def test_none(self):
        assert not is_plan_preset_prompt(None)
