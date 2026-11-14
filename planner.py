"""Smart study planner.

Every day, your free hours are shared between the subjects whose exam is still
to come. A subject gets a bigger share when
  * its exam is closer          -> urgency  = 1 / sqrt(days_left)
  * you are weaker in it        -> weakness = 1 - quiz accuracy (0.5 if no quiz yet)

    priority = (0.2 + weakness) * urgency

Hours are handed out in 30-minute blocks using the "largest remainder" method,
so the day's hours are always used up exactly.
"""
from datetime import date, timedelta

DEFAULT_WEAKNESS = 0.5
BLOCK_HOURS = 0.5


def weakness_from_accuracy(accuracy_by_subject, subjects):
    """Weakness 0..1 per subject. Subjects without quiz data get a neutral 0.5."""
    return {
        s: (1 - accuracy_by_subject[s]) if s in accuracy_by_subject else DEFAULT_WEAKNESS
        for s in subjects
    }


def _priority(weakness, days_left):
    return (0.2 + weakness) / (days_left ** 0.5)


def _allocate(weights, total_blocks):
    total_weight = sum(weights.values())
    raw = {s: w / total_weight * total_blocks for s, w in weights.items()}
    blocks = {s: int(v) for s, v in raw.items()}
    leftover = total_blocks - sum(blocks.values())
    for s in sorted(raw, key=lambda s: raw[s] - blocks[s], reverse=True)[:leftover]:
        blocks[s] += 1
    return blocks


def build_plan(exams, hours_by_weekday, weakness, start=None):
    """exams: [{"subject": str, "exam_date": date}]
    hours_by_weekday: 7 numbers, Monday first.
    Returns [{"date": date, "subject": str, "hours": float}], one row per subject per day.
    No studying is planned on or after a subject's exam day."""
    start = start or date.today()
    exams = [e for e in exams if e["exam_date"] > start]
    if not exams:
        return []

    last_day = max(e["exam_date"] for e in exams)
    rows = []
    day = start
    while day < last_day:
        blocks = int(round(hours_by_weekday[day.weekday()] / BLOCK_HOURS))
        active = [e for e in exams if e["exam_date"] > day]
        if blocks > 0 and active:
            weights = {
                e["subject"]: _priority(weakness.get(e["subject"], DEFAULT_WEAKNESS), (e["exam_date"] - day).days)
                for e in active
            }
            for subject, b in _allocate(weights, blocks).items():
                if b > 0:
                    rows.append({"date": day, "subject": subject, "hours": b * BLOCK_HOURS})
        day += timedelta(days=1)
    return rows


def plan_by_day(rows):
    """One line per day, e.g. 'Machine Learning 2h, Python 1h'."""
    days = {}
    for r in rows:
        days.setdefault(r["date"], []).append(r)
    table = []
    for d in sorted(days):
        items = sorted(days[d], key=lambda r: -r["hours"])
        table.append(
            {
                "date": d,
                "day": d.strftime("%a %d %b"),
                "plan": ", ".join(f"{r['subject']} {r['hours']:g}h" for r in items),
                "total_hours": sum(r["hours"] for r in items),
            }
        )
    return table


def hours_by_subject(rows):
    totals = {}
    for r in rows:
        totals[r["subject"]] = totals.get(r["subject"], 0) + r["hours"]
    return totals


def priority_table(exams, weakness, today=None):
    """Today's priority per subject, highest first (for showing the student why)."""
    today = today or date.today()
    table = []
    for e in exams:
        days_left = (e["exam_date"] - today).days
        if days_left < 1:
            continue
        w = weakness.get(e["subject"], DEFAULT_WEAKNESS)
        table.append(
            {
                "subject": e["subject"],
                "exam_date": e["exam_date"],
                "days_left": days_left,
                "weakness": round(w, 2),
                "priority": round(_priority(w, days_left), 3),
            }
        )
    return sorted(table, key=lambda r: -r["priority"])
