"""Engine-wide constants. Changing one of these changes every status - document why."""

VALUE_PER_CONVERSION = 60.0  # USD per conversion, used for ROAS and retest cost
WINDOW_DAYS = 42  # trailing window for each effectiveness estimate
STEP_DAYS = 7  # spacing between consecutive window end dates
EVIDENCE_MAX_AGE_DAYS = 180  # evidence older than this is "ageing" (YELLOW)
RED_CONFIDENCE = 0.7  # drift confidence at/above which a channel is RED
YELLOW_CONFIDENCE = 0.4  # drift confidence at/above which a channel is at least YELLOW
POSTERIOR_SHIFT_Z = 2.58  # |z| beyond which the current estimate contradicts the ledger (99%)
