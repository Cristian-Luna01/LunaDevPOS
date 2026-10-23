"""Límites UTC indexables, calculados con la misma zona local que SQLite."""
import datetime as dt

def utc_bounds(db,start,end):
    next_day=(dt.date.fromisoformat(end)+dt.timedelta(days=1)).isoformat()
    row=db.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ',?,'utc'),strftime('%Y-%m-%dT%H:%M:%fZ',?,'utc')",(start,next_day)).fetchone()
    return tuple(row)
