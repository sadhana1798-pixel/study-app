"""Quiz generator.

With an API key the LLM writes proper multiple-choice questions.
Without one, a simple offline method makes fill-in-the-blank questions:
pick a sentence, hide its longest keyword, and use other keywords from the
notes as wrong options.
"""
import json
import random
import re

import llm

STOPWORDS = set(
    """about above after again against because before being below between could during each
    every first from further having into itself just might more most other over same should
    since some such than that their theirs them then there these they this those through
    under until very what when where which while whom whose will with within would your yours
    also many much often usually called using used uses use like make makes made""".split()
)


# ---------- offline questions ----------
def _candidate_words(text):
    words = re.findall(r"[A-Za-z][A-Za-z\-]{4,}", text)
    return [w for w in words if w.lower() not in STOPWORDS]


def generate_quiz_offline(text, n=5, seed=None):
    rng = random.Random(seed)
    vocab = sorted({w.lower() for w in _candidate_words(text)})
    if len(vocab) < 4:
        return []

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if 8 <= len(s.split()) <= 35]
    rng.shuffle(sentences)

    questions = []
    for sentence in sentences:
        candidates = _candidate_words(sentence)
        if not candidates:
            continue
        answer = max(candidates, key=len)
        blanked = re.sub(re.escape(answer), "_____", sentence, flags=re.IGNORECASE)

        pool = [w for w in vocab if w != answer.lower()]
        rng.shuffle(pool)
        pool.sort(key=lambda w: abs(len(w) - len(answer)))  # similar-looking words are better wrong options
        wrong = rng.sample(pool[:8], 3) if len(pool) >= 3 else []
        if len(wrong) < 3:
            continue

        options = [answer.lower()] + wrong
        rng.shuffle(options)
        questions.append(
            {
                "question": "Fill in the blank: " + blanked,
                "options": options,
                "answer": options.index(answer.lower()),
            }
        )
        if len(questions) == n:
            break
    return questions


# ---------- AI questions ----------
def parse_quiz_json(raw):
    """Pull a list of valid questions out of the LLM reply (ignores broken items)."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return []

    good = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q, opts, ans = item.get("question"), item.get("options"), item.get("answer")
        if (
            isinstance(q, str)
            and isinstance(opts, list)
            and len(opts) == 4
            and all(isinstance(o, str) for o in opts)
            and isinstance(ans, int)
            and 0 <= ans < 4
        ):
            good.append({"question": q, "options": opts, "answer": ans})
    return good


def generate_quiz_llm(text, n=5):
    prompt = (
        f"Make {n} multiple-choice questions from the study notes below. "
        'Return ONLY a JSON list. Each item must look like: {"question": "...", '
        '"options": ["A", "B", "C", "D"], "answer": 0} where "answer" is the index (0-3) '
        "of the correct option.\n\nNotes:\n" + text[:6000]
    )
    raw = llm.ask_llm(prompt, system="You write clear exam questions for students.", max_tokens=2000)
    return parse_quiz_json(raw)


def build_quiz(text, n=5, topic="", prefer_llm=True):
    """Returns (questions, mode) where mode is "ai" or "offline"."""
    questions, mode = [], "offline"
    if prefer_llm and llm.llm_available():
        try:
            questions = generate_quiz_llm(text, n)[:n]
            mode = "ai"
        except Exception:
            questions = []
    if not questions:
        questions, mode = generate_quiz_offline(text, n), "offline"
    for q in questions:
        q["topic"] = topic
    return questions, mode
