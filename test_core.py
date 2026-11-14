"""Simple tests. Run from the project folder with:  python tests/test_core.py
(pytest also works if you have it installed)."""
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import chatbot  # noqa: E402
import database  # noqa: E402
import notes  # noqa: E402
import planner  # noqa: E402
import quiz  # noqa: E402

ML_TEXT = (ROOT / "sample_notes" / "machine_learning_basics.txt").read_text()
PY_TEXT = (ROOT / "sample_notes" / "python_basics.txt").read_text()


def use_temp_db():
    database.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"


def test_chunk_text_covers_everything():
    words = [f"w{i}" for i in range(500)]
    chunks = notes.chunk_text(" ".join(words), chunk_words=100, overlap=20)
    joined = " ".join(chunks).split()
    assert set(joined) == set(words)
    assert all(len(c.split()) <= 100 for c in chunks)
    assert notes.chunk_text("") == []
    assert len(notes.chunk_text("only a few words")) == 1


def test_extract_text_txt_and_bad_type():
    assert notes.extract_text("a.txt", b"hello   world\r\n\r\n\r\n\r\nbye") == "hello world\n\nbye"
    try:
        notes.extract_text("a.exe", b"x")
        assert False, "should reject .exe"
    except ValueError:
        pass


def test_database_roundtrip():
    use_temp_db()
    nid = database.add_note("ML", "Basics", ML_TEXT)
    database.add_note("Python", "Intro", PY_TEXT)
    assert database.list_subjects() == ["ML", "Python"]
    assert database.get_note(nid)["title"] == "Basics"
    assert len(database.list_notes("ML")) == 1

    database.add_quiz_results("ML", "Basics", [("q1", True), ("q2", False), ("q3", False), ("q4", False)])
    database.add_quiz_results("Python", "Intro", [("q1", True), ("q2", True)])
    acc = database.subject_accuracy()
    assert acc["ML"] == 0.25 and acc["Python"] == 1.0
    assert database.topic_accuracy("ML")[0][0] == "Basics"

    database.set_exam("ML", date(2026, 12, 1))
    database.set_exam("ML", date(2026, 12, 5))  # update, not duplicate
    assert database.list_exams() == [{"subject": "ML", "exam_date": date(2026, 12, 5)}]
    database.delete_exam("ML")
    assert database.list_exams() == []

    database.delete_note(nid)
    assert database.list_subjects() == ["Python"]


def test_retriever_finds_the_right_note():
    rows = [
        {"id": 1, "subject": "ML", "title": "ML basics", "content": ML_TEXT},
        {"id": 2, "subject": "Python", "title": "Python basics", "content": PY_TEXT},
    ]
    r = chatbot.NoteRetriever(rows)
    hits = r.search("what is overfitting and how to reduce it")
    assert hits and hits[0]["title"] == "ML basics"
    hits = r.search("how do I handle exceptions with try and except")
    assert hits and hits[0]["title"] == "Python basics"
    assert r.search("recipe for chocolate cake") == []
    assert chatbot.NoteRetriever([]).search("anything") == []


def test_chatbot_offline_answer(monkeypatch_llm_off=True):
    rows = [{"id": 1, "subject": "ML", "title": "ML basics", "content": ML_TEXT}]
    r = chatbot.NoteRetriever(rows)
    chatbot.llm.llm_available = lambda: False
    result = chatbot.answer_question("what is gradient descent", r)
    assert result["mode"] == "offline" and "learning rate" in result["answer"].lower()
    result = chatbot.answer_question("zebra migration routes", r)
    assert result["mode"] == "none"


def test_offline_quiz_is_valid():
    qs = quiz.generate_quiz_offline(ML_TEXT, n=5, seed=1)
    assert len(qs) == 5
    for q in qs:
        assert "_____" in q["question"]
        assert len(q["options"]) == 4 and len(set(q["options"])) == 4
        assert 0 <= q["answer"] < 4
        # the correct word must really come from the note
        assert q["options"][q["answer"]] in ML_TEXT.lower()
    assert quiz.generate_quiz_offline("too short", n=3) == []


def test_build_quiz_falls_back_offline():
    quiz.llm.llm_available = lambda: False
    qs, mode = quiz.build_quiz(PY_TEXT, n=4, topic="Python basics")
    assert mode == "offline" and len(qs) == 4 and qs[0]["topic"] == "Python basics"


def test_parse_quiz_json_ignores_bad_items():
    raw = 'Sure! ```json\n[{"question":"Q?","options":["a","b","c","d"],"answer":2},' \
          '{"question":"bad","options":["a"],"answer":0}, 5]\n```'
    out = quiz.parse_quiz_json(raw)
    assert out == [{"question": "Q?", "options": ["a", "b", "c", "d"], "answer": 2}]
    assert quiz.parse_quiz_json("no json here") == []
    assert quiz.parse_quiz_json("[not valid json]") == []


START = date(2026, 11, 16)  # a Monday
FLAT_4H = [4] * 7


def test_planner_hours_add_up_and_stop_at_exam():
    exams = [
        {"subject": "A", "exam_date": date(2026, 11, 19)},
        {"subject": "B", "exam_date": date(2026, 11, 26)},
    ]
    rows = planner.build_plan(exams, FLAT_4H, {"A": 0.5, "B": 0.5}, start=START)
    per_day = {}
    for r in rows:
        per_day[r["date"]] = per_day.get(r["date"], 0) + r["hours"]
    assert all(h == 4 for h in per_day.values())
    assert max(r["date"] for r in rows if r["subject"] == "A") < date(2026, 11, 19)
    assert max(r["date"] for r in rows) < date(2026, 11, 26)


def test_planner_closer_exam_gets_more_time():
    exams = [
        {"subject": "A", "exam_date": date(2026, 11, 20)},
        {"subject": "B", "exam_date": date(2026, 12, 10)},
    ]
    rows = planner.build_plan(exams, FLAT_4H, {"A": 0.5, "B": 0.5}, start=START)
    first_day = {r["subject"]: r["hours"] for r in rows if r["date"] == START}
    assert first_day["A"] > first_day["B"]


def test_planner_weaker_subject_gets_more_time():
    exams = [
        {"subject": "A", "exam_date": date(2026, 12, 1)},
        {"subject": "B", "exam_date": date(2026, 12, 1)},
    ]
    rows = planner.build_plan(exams, FLAT_4H, {"A": 0.9, "B": 0.1}, start=START)
    totals = planner.hours_by_subject(rows)
    assert totals["A"] > totals["B"]


def test_planner_weekday_hours_and_edge_cases():
    exams = [{"subject": "A", "exam_date": date(2026, 11, 24)}]
    hours = [1, 2, 3, 4, 5, 6, 0]  # Mon..Sun
    rows = planner.build_plan(exams, hours, {"A": 0.5}, start=START)
    by_date = {r["date"]: r["hours"] for r in rows}
    assert by_date[date(2026, 11, 16)] == 1       # Monday
    assert by_date[date(2026, 11, 21)] == 6       # Saturday
    assert date(2026, 11, 22) not in by_date      # Sunday has 0 free hours
    assert planner.build_plan([], FLAT_4H, {}, start=START) == []
    assert planner.build_plan([{"subject": "A", "exam_date": START}], FLAT_4H, {}, start=START) == []


def test_weakness_and_tables():
    w = planner.weakness_from_accuracy({"A": 0.8}, ["A", "B"])
    assert abs(w["A"] - 0.2) < 1e-9 and w["B"] == planner.DEFAULT_WEAKNESS
    exams = [{"subject": "A", "exam_date": date(2026, 11, 20)}]
    rows = planner.build_plan(exams, FLAT_4H, {"A": 0.5}, start=START)
    table = planner.plan_by_day(rows)
    assert table[0]["plan"] == "A 4h" and table[0]["total_hours"] == 4
    assert planner.priority_table(exams, {"A": 0.5}, today=START)[0]["days_left"] == 4


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {type(err).__name__}: {err}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
