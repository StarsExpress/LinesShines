"""Position names, rounding, and the notes that explain each metric."""

ROUNDING_DECIMALS = 3  # Better precision alleviates overlaps in plots.
DISPLAY_DECIMALS = 1  # For UI displays only.


FRONT_7_NAMES = {"DI": "Defensive Interior", "ED": "Edge", "LB": "Linebacker"}
OL_NAMES = {"T": "Offensive Tackles", "G": "Guards", "C": "Centers"}


HAVOC_RATE_NOTE = "Havoc Rate = (Sacks + QB Hits) / Pass Rush Opportunities."
ALLOWED_HAVOC_RATE_NOTE = (
    "Allowed Havoc Rate = (Sacks + QB Hits) / Non Spike Pass Block Snaps."
)

PRP_NOTE = "PRP = (Sacks + 0.5 x (QB Hits + Hurries)) / Pass Rush Opportunities x 100."
PASS_COV_PERCENT_NOTE = "Pass Cov Percent = 100 - Pass Rush Percent, where Pass Rush Percent = Pass Rush Snaps / Pass Play Snaps x 100."
PBE_NOTE = "PBE = 100 - (Sacks + 0.5 x (QB Hits + Hurries)) / Non Spike Pass Block Snaps x 100."

# Shared across every "TPS "-prefixed metric — not a per-metric formula, so
# it lives once here rather than duplicated into a TPS_*_NOTE per metric.
# The frontend appends this to whatever a TPS metric's own note/formula
# already says, keyed off the "TPS " prefix rather than a per-metric flag
# (see main.py's /api/metadata: exposed once at the top level, not per metric).
TPS_NOTE = (
    "True Pass Set: excludes plays with less than 4 rushers, play action, "
    "screens, short dropbacks and time-to-throws under 2 seconds."
)
