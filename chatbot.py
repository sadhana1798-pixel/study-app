"""Chat with your notes (RAG = Retrieval Augmented Generation).

Step 1 (retrieval): find the pieces of your notes most similar to the question.
Step 2 (generation): give only those pieces to the LLM and ask it to answer.
Without an API key, step 2 is skipped and the best pieces are shown directly.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import llm
import notes as notes_lib

SYSTEM_PROMPT = (
    "You are a friendly study assistant. Answer the student's question using ONLY "
    "the notes provided. If the notes do not contain the answer, say so clearly. "
    "Keep the answer short and simple."
)


class NoteRetriever:
    """Turns notes into chunks and finds the chunks closest to a question (TF-IDF)."""

    def __init__(self, note_rows, chunk_words=150, overlap=30):
        self.chunks = []
        for n in note_rows:
            for piece in notes_lib.chunk_text(n["content"], chunk_words, overlap):
                self.chunks.append(
                    {"text": piece, "title": n["title"], "subject": n["subject"], "note_id": n["id"]}
                )
        self.vectorizer = None
        self.matrix = None
        if self.chunks:
            try:
                self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
                self.matrix = self.vectorizer.fit_transform([c["text"] for c in self.chunks])
            except ValueError:  # notes had no usable words
                self.chunks = []

    def search(self, query, k=4, min_score=0.05):
        if not self.chunks:
            return []
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix).ravel()
        best = scores.argsort()[::-1][:k]
        return [dict(self.chunks[i], score=float(scores[i])) for i in best if scores[i] >= min_score]


def _offline_answer(hits):
    parts = ["Here are the most relevant parts of your notes:\n"]
    for h in hits[:3]:
        text = h["text"] if len(h["text"]) <= 400 else h["text"][:400] + "…"
        parts.append(f"**{h['title']}**: {text}\n")
    return "\n".join(parts)


def answer_question(question, retriever, k=4):
    """Returns {"answer": str, "sources": [chunks], "mode": "ai" | "offline" | "none"}."""
    hits = retriever.search(question, k=k)
    if not hits:
        return {
            "answer": "I couldn't find anything about that in your notes. Try different words, or add more notes.",
            "sources": [],
            "mode": "none",
        }

    prefix = ""
    if llm.llm_available():
        context = "\n\n".join(f"[{i}] ({h['title']}) {h['text']}" for i, h in enumerate(hits, 1))
        try:
            answer = llm.ask_llm(f"Notes:\n{context}\n\nQuestion: {question}", system=SYSTEM_PROMPT)
            return {"answer": answer, "sources": hits, "mode": "ai"}
        except Exception as err:  # no internet, bad key, ...
            prefix = f"(The AI could not answer: {err}. Showing your notes instead.)\n\n"

    return {"answer": prefix + _offline_answer(hits), "sources": hits, "mode": "offline"}
