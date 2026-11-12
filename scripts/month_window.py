"""Print the completed calendar month in Vietnam, or validated manual dates."""

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import os

today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
last = today.replace(day=1) - timedelta(days=1)
since = os.environ.get("INPUT_SINCE") or last.replace(day=1).isoformat()
until = os.environ.get("INPUT_UNTIL") or last.isoformat()
if (
    date.fromisoformat(since) > date.fromisoformat(until)
    or date.fromisoformat(until) > today
):
    raise ValueError("Invalid crawl dates")
print(f"since={since}\nuntil={until}")
