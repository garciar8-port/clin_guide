"""Tests for multi-turn conversation support."""

from clinguide.api.conversation import Session, SessionStore


class TestSession:
    def test_add_messages(self):
        s = Session(session_id="test-1")
        s.add_user_message("What is the dose of osimertinib?")
        s.add_assistant_message("80 mg once daily.")
        assert len(s.messages) == 2
        assert s.messages[0].role == "user"
        assert s.messages[1].role == "assistant"

    def test_context_window(self):
        s = Session(session_id="test-1")
        s.add_user_message("Q1")
        s.add_assistant_message("A1")
        s.add_user_message("Q2")
        s.add_assistant_message("A2")

        window = s.get_context_window(max_turns=2)
        assert len(window) == 4
        assert window[0]["role"] == "user"
        assert window[0]["content"] == "Q1"

    def test_contextual_query_no_history(self):
        s = Session(session_id="test-1")
        result = s.format_contextual_query("What is the dose?")
        assert result == "What is the dose?"

    def test_contextual_query_with_history(self):
        s = Session(session_id="test-1")
        s.add_user_message("What is the dose of osimertinib?")
        s.add_assistant_message("80 mg once daily.")
        result = s.format_contextual_query("What about pediatric dosing?")
        assert "osimertinib" in result
        assert "pediatric" in result


class TestSessionStore:
    def test_get_or_create(self):
        store = SessionStore()
        s1 = store.get_or_create("session-1")
        s2 = store.get_or_create("session-1")
        assert s1 is s2
        assert store.size == 1

    def test_different_sessions(self):
        store = SessionStore()
        store.get_or_create("s1")
        store.get_or_create("s2")
        assert store.size == 2

    def test_eviction(self):
        store = SessionStore(max_sessions=2)
        store.get_or_create("s1")
        store.get_or_create("s2")
        store.get_or_create("s3")
        assert store.size == 2
        assert store.get("s1") is None  # oldest evicted

    def test_delete(self):
        store = SessionStore()
        store.get_or_create("s1")
        store.delete("s1")
        assert store.size == 0
