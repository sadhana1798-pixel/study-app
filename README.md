# StudyBuddy AI

A study app made of four connected parts:

1. **My Notes**: upload PDF/TXT/MD files or paste text. Notes are saved by subject.
2. **Chat with Notes**: ask questions and get answers taken only from *your* notes.
3. **Quiz**: makes questions from a note and remembers which subjects you get wrong.
4. **Study Planner**: makes a day-by-day timetable. Closer exams and weaker subjects get more hours.

The parts are connected: notes feed the chat and quiz, and quiz results feed the planner.

## How to run

```bash
# 1. (optional but recommended) make a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac / Linux

# 2. install
pip install -r requirements.txt

# 3. start
streamlit run app.py
```

The browser opens automatically. To try it quickly, upload the two files in `sample_notes/`.

### Optional: turn on AI mode
Without a key the app still works in **offline mode** (chat shows the best matching parts of your notes; quiz makes fill-in-the-blank questions). With a key, the chat writes proper answers and the quiz writes proper multiple-choice questions.

1. Copy `.env.example` to `.env`
2. Put your Claude API key in it: `ANTHROPIC_API_KEY=...`
3. Restart the app. The sidebar will show "AI mode: ON".

Never share your `.env` file or upload it to GitHub.

## How each part works (use this in your report and viva)

**Chat with Notes (RAG)**
1. Every note is cut into chunks of about 150 words (`notes.py`).
2. Each chunk is turned into numbers with **TF-IDF** (words that are rare and important get a higher score).
3. Your question is turned into numbers the same way. **Cosine similarity** finds the 4 closest chunks (`chatbot.py`).
4. Only those chunks are sent to the LLM with the instruction "answer using only these notes". This stops the AI from making things up.

**Quiz** (`quiz.py`)
- AI mode: the LLM returns questions as JSON. The code checks every item and ignores broken ones.
- Offline mode: pick a sentence, hide its longest keyword, use similar-length keywords from the note as wrong options.
- Every answer is saved (subject, topic, right or wrong) in the SQLite database.

**Study Planner** (`planner.py`)
- Each day, free hours are split between subjects whose exam has not happened yet.
- `weakness = 1 - quiz accuracy` (0.5 if you have not taken a quiz)
- `urgency = 1 / sqrt(days left)`
- `priority = (0.2 + weakness) * urgency`
- Hours are given in 30-minute blocks, using the largest-remainder method so the total is always exact.
- You set free hours separately for each weekday, so the timetable follows your real schedule.

## Project structure

```
app.py          Streamlit screens (the 4 pages)
database.py     SQLite: notes, quiz results, exams
notes.py        read PDF/TXT/MD, cut text into chunks
chatbot.py      TF-IDF retrieval + answer generation
quiz.py         AI and offline quiz makers
planner.py      priority formula and timetable
llm.py          small Claude API wrapper (optional)
tests/          python tests/test_core.py
sample_notes/   two notes to try the app
```

## Run the tests

```bash
python tests/test_core.py
```

## Ideas to extend it (good for "Future work")

- Replace TF-IDF with **sentence embeddings** (`sentence-transformers`) and a vector database such as **ChromaDB**. Retrieval then understands meaning, not just matching words. Only `NoteRetriever` in `chatbot.py` needs to change.
- Train a small **ML model** that predicts how many hours you need per topic from your quiz history, and use it in the planner instead of the fixed formula.
- Spaced repetition: show wrong questions again after 1, 3 and 7 days.
- Add your college class timetable so study time is only planned in free slots.
- Read scanned PDFs with OCR.

## Known limits (be honest about these in your report)

- Scanned (image) PDFs have no text to read, so they are skipped.
- TF-IDF matches words, not meaning, so a question worded very differently from the notes may find nothing.
- Offline quiz questions are simple fill-in-the-blank.
- Data is stored in a local `study.db` file, so it is one user per computer.
