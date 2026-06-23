"""Unit tests for frontends/cost_tracker.py — token usage tracking."""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontends.cost_tracker import (
    TokenStats,
    scan_subagent_logs,
    get,
    reset,
    all_trackers,
    context_window_chars,
    current_input_chars,
    _trackers,
    _lock,
)


# ---------- TokenStats ----------

class TestTokenStats:
    def test_defaults(self):
        ts = TokenStats()
        assert ts.requests == 0
        assert ts.input == 0
        assert ts.output == 0
        assert ts.cache_create == 0
        assert ts.cache_read == 0
        assert ts.last_input == 0
        assert ts.last_output == 0
        assert ts.started_at > 0

    def test_total_input_side(self):
        ts = TokenStats(input=100, cache_create=50, cache_read=30)
        assert ts.total_input_side() == 180

    def test_total_tokens(self):
        ts = TokenStats(input=100, output=50, cache_create=20, cache_read=10)
        assert ts.total_tokens() == 180

    def test_cache_hit_rate_zero_input(self):
        ts = TokenStats()
        assert ts.cache_hit_rate() == 0.0

    def test_cache_hit_rate(self):
        ts = TokenStats(input=70, cache_create=0, cache_read=30)
        assert abs(ts.cache_hit_rate() - 30.0) < 0.01

    def test_elapsed_seconds(self):
        ts = TokenStats(started_at=time.time() - 10)
        elapsed = ts.elapsed_seconds()
        assert 9 < elapsed < 12


# ---------- get / reset / all_trackers ----------

class TestTrackerManagement:
    def setup_method(self):
        with _lock:
            _trackers.clear()

    def test_get_creates_new(self):
        ts = get("test_thread")
        assert isinstance(ts, TokenStats)
        assert ts.requests == 0

    def test_get_returns_same(self):
        ts1 = get("test_thread")
        ts2 = get("test_thread")
        assert ts1 is ts2

    def test_reset_removes(self):
        get("test_thread")
        reset("test_thread")
        with _lock:
            assert "test_thread" not in _trackers

    def test_reset_nonexistent(self):
        reset("nonexistent")  # should not raise

    def test_all_trackers(self):
        get("a")
        get("b")
        result = all_trackers()
        assert "a" in result
        assert "b" in result
        assert isinstance(result, dict)


# ---------- context_window_chars ----------

class TestContextWindowChars:
    def test_with_context_win(self):
        class Backend:
            context_win = 1000
        assert context_window_chars(Backend()) == 3000

    def test_missing_attr(self):
        class Backend:
            pass
        assert context_window_chars(Backend()) == 0

    def test_invalid_value(self):
        class Backend:
            context_win = "not_a_number"
        assert context_window_chars(Backend()) == 0


# ---------- current_input_chars ----------

class TestCurrentInputChars:
    def test_with_history(self):
        class Backend:
            history = [{"role": "user", "content": "hello"}]
        result = current_input_chars(Backend())
        assert result > 0

    def test_empty_history(self):
        class Backend:
            history = []
        assert current_input_chars(Backend()) == 0

    def test_no_history(self):
        class Backend:
            pass
        assert current_input_chars(Backend()) == 0


# ---------- scan_subagent_logs ----------

class TestScanSubagentLogs:
    def test_no_logs(self, tmp_path):
        result = scan_subagent_logs(root=str(tmp_path))
        assert result.requests == 0
        assert result.output == 0

    def test_output_log(self, tmp_path):
        task_dir = tmp_path / "temp" / "task1"
        task_dir.mkdir(parents=True)
        log = task_dir / "stdout.log"
        log.write_text(
            "[Output] tokens=150\n"
            "[Output] tokens=200\n",
            encoding="utf-8"
        )
        result = scan_subagent_logs(root=str(tmp_path))
        assert result.output == 350
        assert result.requests == 2

    def test_cache_new_format(self, tmp_path):
        task_dir = tmp_path / "temp" / "task2"
        task_dir.mkdir(parents=True)
        log = task_dir / "stdout.log"
        log.write_text(
            "[Cache] input=500 creation=100 read=200\n",
            encoding="utf-8"
        )
        result = scan_subagent_logs(root=str(tmp_path))
        assert result.input == 500
        assert result.cache_create == 100
        assert result.cache_read == 200

    def test_cache_old_format(self, tmp_path):
        task_dir = tmp_path / "temp" / "task3"
        task_dir.mkdir(parents=True)
        log = task_dir / "stdout.log"
        log.write_text(
            "[Cache] input=300 cached=100\n",
            encoding="utf-8"
        )
        result = scan_subagent_logs(root=str(tmp_path))
        assert result.input == 200  # max(0, 300-100)
        assert result.cache_read == 100

    def test_since_filters(self, tmp_path):
        task_dir = tmp_path / "temp" / "old_task"
        task_dir.mkdir(parents=True)
        log = task_dir / "stdout.log"
        log.write_text("[Output] tokens=100\n", encoding="utf-8")
        future = time.time() + 9999
        result = scan_subagent_logs(since=future, root=str(tmp_path))
        assert result.output == 0
