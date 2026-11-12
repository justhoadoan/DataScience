"""GitHub output and readable evaluation summary; rejection is a valid outcome."""

import json
import os
from pathlib import Path

result = json.loads(Path("reports/pipeline_latest.json").read_text())
decision = result["evaluation"]
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write(f"promoted={str(decision['promoted']).lower()}\n")
with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
    summary.write("# Monthly rental model evaluation\n\n")
    summary.write(
        f"Input: {result['input_rows']}; eligible: {result['eligible_rows']}.\n\n"
    )
    summary.write(
        f"Candidate: `{decision['candidate']}`; approved champion: `{decision['champion']}`.\n\n"
    )
    summary.write("Promoted.\n" if decision["promoted"] else "Champion retained.\n")
    for reason in decision["reasons"]:
        summary.write(f"- {reason}\n")
