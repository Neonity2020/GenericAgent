"""Unit tests for ga.py — utility functions and helpers."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ga import smart_format, file_patch, file_read, expand_file_refs, ask_user, format_error, consume_file


# ---------- smart_format ----------

class TestSmartFormat:
    def test_short_string_unchanged(self):
        assert smart_format("hello", max_str_len=100) == "hello"

    def test_long_string_truncated(self):
        data = "a" * 300
        result = smart_format(data, max_str_len=100, omit_str=" ... ")
        assert " ... " in result
        assert len(result) < len(data)

    def test_exact_boundary(self):
        data = "x" * 100
        result = smart_format(data, max_str_len=100, omit_str=" ... ")
        assert result == data  # should not be truncated (len < max + omit*2)

    def test_non_string_converted(self):
        result = smart_format(12345, max_str_len=100)
        assert result == "12345"

    def test_preserves_start_and_end(self):
        data = "START" + "x" * 500 + "END"
        result = smart_format(data, max_str_len=100, omit_str=" ... ")
        assert result.startswith("START")
        assert result.endswith("END")


# ---------- file_patch ----------

class TestFilePatch:
    def test_successful_patch(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        result = file_patch(str(f), "hello", "goodbye")
        assert result["status"] == "success"
        assert f.read_text(encoding="utf-8") == "goodbye world"

    def test_empty_old_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        result = file_patch(str(f), "", "x")
        assert result["status"] == "error"

    def test_old_content_not_found(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        result = file_patch(str(f), "nonexistent", "x")
        assert result["status"] == "error"

    def test_multiple_matches(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("aaa bbb aaa", encoding="utf-8")
        result = file_patch(str(f), "aaa", "ccc")
        assert result["status"] == "error"

    def test_file_not_exists(self, tmp_path):
        result = file_patch(str(tmp_path / "nope.txt"), "a", "b")
        assert result["status"] == "error"


# ---------- file_read ----------

class TestFileRead:
    def test_basic_read(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        result = file_read(str(f))
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_start_offset(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        result = file_read(str(f), start=2)
        assert "line1" not in result
        assert "line2" in result

    def test_keyword_search(self, tmp_path):
        f = tmp_path / "test.txt"
        lines = [f"line {i}" for i in range(100)]
        f.write_text("\n".join(lines), encoding="utf-8")
        result = file_read(str(f), keyword="line 50")
        assert "line 50" in result

    def test_file_not_found(self, tmp_path):
        result = file_read(str(tmp_path / "nope.txt"))
        assert "Error" in result

    def test_no_line_numbers(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello\nworld\n", encoding="utf-8")
        result = file_read(str(f), show_linenos=False)
        assert "1|" not in result
        assert "hello" in result


# ---------- expand_file_refs ----------

class TestExpandFileRefs:
    def test_no_refs(self):
        assert expand_file_refs("plain text") == "plain text"

    def test_valid_ref(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("aaa\nbbb\nccc\nddd\n", encoding="utf-8")
        text = f"before {{{{file:{f}:2:3}}}} after"
        result = expand_file_refs(text)
        assert "bbb" in result
        assert "ccc" in result
        assert "before" in result
        assert "after" in result

    def test_file_not_found_raises(self):
        with pytest.raises(ValueError, match="引用文件不存在"):
            expand_file_refs("{{file:/nonexistent/file.txt:1:1}}")

    def test_line_out_of_range(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("one\ntwo\n", encoding="utf-8")
        with pytest.raises(ValueError, match="行号越界"):
            expand_file_refs(f"{{{{file:{f}:1:100}}}}")


# ---------- ask_user ----------

class TestAskUser:
    def test_basic(self):
        result = ask_user("What?")
        assert result["status"] == "INTERRUPT"
        assert result["intent"] == "HUMAN_INTERVENTION"
        assert result["data"]["question"] == "What?"
        assert result["data"]["candidates"] == []

    def test_with_candidates(self):
        result = ask_user("Pick one", candidates=["A", "B"])
        assert result["data"]["candidates"] == ["A", "B"]


# ---------- format_error ----------

class TestFormatError:
    def test_captures_exception_info(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = format_error(e)
        assert "ValueError" in result
        assert "test error" in result


# ---------- consume_file ----------

class TestConsumeFile:
    def test_consumes_and_deletes(self, tmp_path):
        f = tmp_path / "msg.txt"
        f.write_text("hello", encoding="utf-8")
        result = consume_file(str(tmp_path), "msg.txt")
        assert result == "hello"
        assert not f.exists()

    def test_file_not_exists_returns_none(self, tmp_path):
        result = consume_file(str(tmp_path), "nope.txt")
        assert result is None

    def test_none_dir(self):
        result = consume_file(None, "file.txt")
        assert result is None
