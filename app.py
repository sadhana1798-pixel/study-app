"""StudyBuddy AI - notes + chat with notes + quiz + smart study planner.

Run with:  streamlit run app.py
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import chatbot
import database as db
import llm
import notes as notes_lib
import planner
import quiz as quiz_lib

st.set_page_config(page_title="StudyBuddy AI", page_icon="📚", layout="wide")
db.init_db()

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEFAULT_HOURS = [3, 3, 3, 3, 3, 5, 5]


def flash(message):
    """Show a message after the page reloads."""
    st.session_state["flash"] = message
    st.rerun()


def show_flash():
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


# ---------------------------------------------------------------- notes page
def notes_page():
    st.header("📝 My Notes")
    show_flash()

    with st.expander("➕ Add a note", expanded=not db.list_notes()):
        existing = db.list_subjects()
        c1, c2 = st.columns(2)
        picked = c1.selectbox("Subject", existing if existing else ["(no subjects yet)"])
        typed = c2.text_input("...or type a new subject")
        subject = typed.strip() or (picked if existing else "")

        title = st.text_input("Title for pasted text (e.g. Unit 2 - Neural Networks)")
        uploaded = st.file_uploader("Upload PDF / TXT / MD files", type=["pdf", "txt", "md"], accept_multiple_files=True)
        pasted = st.text_area("...or paste your notes here", height=150)

        if st.button("Save", type="primary"):
            if not subject:
                st.error("Please choose or type a subject.")
            else:
                saved = 0
                for f in uploaded or []:
                    try:
                        text = notes_lib.extract_text(f.name, f.getvalue())
                    except Exception as err:
                        st.error(f"Could not read {f.name}: {err}")
                        continue
                    if not text:
                        st.warning(f"{f.name} has no readable text (is it a scanned PDF?).")
                        continue
                    db.add_note(subject, f.name.rsplit(".", 1)[0], text)
                    saved += 1
                if pasted.strip():
                    db.add_note(subject, title.strip() or "Untitled note", notes_lib.clean_text(pasted))
                    saved += 1
                if saved:
                    flash(f"Saved {saved} note(s) under '{subject}'.")
                else:
                    st.warning("Nothing to save - upload a file or paste some text.")

    all_notes = db.list_notes()
    if not all_notes:
        st.info("No notes yet. Add your first note above.")
        return

    search = st.text_input("🔎 Search inside notes").strip().lower()
    for subject in db.list_subjects():
        subject_notes = [
            n for n in all_notes
            if n["subject"] == subject and (not search or search in (n["title"] + n["content"]).lower())
        ]
        if not subject_notes:
            continue
        st.subheader(subject)
        for n in subject_notes:
            with st.expander(f"{n['title']}  ·  {len(n['content'].split())} words"):
                st.write(n["content"][:3000] + ("…" if len(n["content"]) > 3000 else ""))
                if st.button("🗑 Delete this note", key=f"del_{n['id']}"):
                    db.delete_note(n["id"])
                    flash("Note deleted.")


# ----------------------------------------------------------------- chat page
def chat_page():
    st.header("💬 Chat with your notes")
    all_notes = db.list_notes()
    if not all_notes:
        st.info("Add some notes first, then come back and ask questions.")
        return

    choice = st.selectbox("Search in", ["All subjects"] + db.list_subjects())
    pool = all_notes if choice == "All subjects" else [n for n in all_notes if n["subject"] == choice]
    retriever = chatbot.NoteRetriever(pool)

    history = st.session_state.setdefault("chat_history", [])
    if history and st.button("Clear chat"):
        st.session_state["chat_history"] = []
        st.rerun()

    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    question = st.chat_input("Ask something from your notes...")
    if question:
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        result = chatbot.answer_question(question, retriever)
        sources = ", ".join(sorted({f"{s['title']} ({s['subject']})" for s in result["sources"]}))
        reply = result["answer"] + (f"\n\n*Sources: {sources}*" if sources else "")
        history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)


# ----------------------------------------------------------------- quiz page
def quiz_page():
    st.header("🧠 Quiz yourself")
    all_notes = db.list_notes()
    if not all_notes:
        st.info("Add some notes first.")
        return

    options = {f"{n['subject']} - {n['title']}": n for n in all_notes}
    label = st.selectbox("Pick a note", list(options))
    n_questions = st.slider("Number of questions", 3, 10, 5)

    if st.button("Generate quiz", type="primary"):
        note = options[label]
        with st.spinner("Making questions..."):
            questions, mode = quiz_lib.build_quiz(note["content"], n_questions, topic=note["title"])
        if not questions:
            st.error("This note is too short to make questions from. Try a longer note.")
        else:
            st.session_state["quiz_counter"] = st.session_state.get("quiz_counter", 0) + 1
            st.session_state["quiz"] = {
                "id": st.session_state["quiz_counter"],
                "questions": questions,
                "mode": mode,
                "subject": note["subject"],
                "topic": note["title"],
                "results": None,
            }

    quiz = st.session_state.get("quiz")
    if not quiz:
        return

    st.caption("Questions written by AI" if quiz["mode"] == "ai" else "Offline mode: fill-in-the-blank questions")
    with st.form("quiz_form"):
        for i, q in enumerate(quiz["questions"]):
            st.radio(
                f"Q{i + 1}. {q['question']}",
                options=list(range(len(q["options"]))),
                format_func=lambda j, q=q: q["options"][j],
                index=None,
                key=f"q_{quiz['id']}_{i}",
            )
        submitted = st.form_submit_button("Submit answers")

    if submitted and quiz["results"] is None:
        results = []
        for i, q in enumerate(quiz["questions"]):
            chosen = st.session_state.get(f"q_{quiz['id']}_{i}")
            results.append((q["question"], chosen == q["answer"]))
        quiz["results"] = results
        db.add_quiz_results(quiz["subject"], quiz["topic"], results)

    if quiz["results"] is not None:
        score = sum(ok for _, ok in quiz["results"])
        st.subheader(f"Score: {score} / {len(quiz['results'])}")
        for i, (q, (_, ok)) in enumerate(zip(quiz["questions"], quiz["results"])):
            icon = "✅" if ok else "❌"
            st.write(f"{icon} **Q{i + 1}.** Correct answer: **{q['options'][q['answer']]}**")
        st.caption("Your results are saved - the Study Planner uses them to find your weak subjects.")


# -------------------------------------------------------------- planner page
def planner_page():
    st.header("📅 Smart Study Planner")
    show_flash()

    subjects = db.list_subjects()
    st.subheader("1. Your exams")
    c1, c2, c3 = st.columns([2, 2, 1])
    subject = c1.selectbox("Subject", subjects) if subjects else c1.text_input("Subject")
    exam_date = c2.date_input(
        "Exam date", value=date.today() + timedelta(days=14), min_value=date.today() + timedelta(days=1)
    )
    if c3.button("Add / update"):
        if subject and subject.strip():
            db.set_exam(subject.strip(), exam_date)
            flash(f"Exam saved for {subject}.")
        else:
            st.error("Enter a subject first.")

    exams = db.list_exams()
    for e in exams:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{e['subject']}** - {e['exam_date'].strftime('%a %d %b %Y')} ({(e['exam_date'] - date.today()).days} days left)")
        if c2.button("Remove", key=f"rm_{e['subject']}"):
            db.delete_exam(e["subject"])
            flash("Exam removed.")

    st.subheader("2. Your free study hours")
    cols = st.columns(7)
    hours = [
        cols[i].number_input(WEEKDAYS[i], min_value=0.0, max_value=16.0, value=float(DEFAULT_HOURS[i]), step=0.5)
        for i in range(7)
    ]

    st.subheader("3. Your plan")
    if not exams:
        st.info("Add at least one exam to build a plan.")
        return

    weakness = planner.weakness_from_accuracy(db.subject_accuracy(), [e["subject"] for e in exams])
    if st.button("Make my timetable", type="primary"):
        rows = planner.build_plan(exams, hours, weakness)
        if not rows:
            st.warning("No study time to plan - check your exam dates and free hours.")
            return

        st.write("**Why this order?** Closer exams and weaker subjects (from your quiz results) get more time.")
        st.dataframe(pd.DataFrame(planner.priority_table(exams, weakness)), use_container_width=True, hide_index=True)

        table = pd.DataFrame(planner.plan_by_day(rows))[["day", "plan", "total_hours"]]
        table.columns = ["Day", "What to study", "Hours"]
        st.dataframe(table, use_container_width=True, hide_index=True)

        st.write("**Total hours per subject**")
        st.bar_chart(pd.Series(planner.hours_by_subject(rows)))
        st.download_button("Download timetable (CSV)", table.to_csv(index=False), "timetable.csv", "text/csv")


# --------------------------------------------------------------------- main
st.sidebar.title("📚 StudyBuddy AI")
page = st.sidebar.radio("Go to", ["My Notes", "Chat with Notes", "Quiz", "Study Planner"])
if llm.llm_available():
    st.sidebar.success("AI mode: ON")
else:
    st.sidebar.info("AI mode: OFF (offline). Add ANTHROPIC_API_KEY to .env for smarter answers and quizzes.")

{"My Notes": notes_page, "Chat with Notes": chat_page, "Quiz": quiz_page, "Study Planner": planner_page}[page]()
