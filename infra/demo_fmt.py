"""Pretty-printers for infra/demo.sh. Usage: demo_fmt.py status|clock < json"""

import json
import sys

data = json.load(sys.stdin)
if sys.argv[1] == "clock":
    print(f"== Simulated today: {data['date']} (day {data['day']}) ==")
else:
    for c in data:
        print(f"   {c['status']:<6} {c['display_name']:<14} score {c['score']:>3}   "
              f"{c['drift_summary']}")
