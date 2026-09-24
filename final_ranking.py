"""
Build the final ranked candidate list from already-completed results:
  - validated_candidates_with_catalogue.csv  (three-epoch validation scores +
    catalogue_crossmatch_v3.py classification, one row per candidate)

No detection, linking, validation or catalogue cross-match is rerun here --
this script only combines the existing numbers into one priority ranking,
and regenerates every ranking note from the current values (nothing is
carried over from earlier runs).

Scoring components (0-100 each):
  - validation_score   : three-epoch validation (trajectory + rate
                         consistency + C-prediction error + flux consistency)
  - catalogue_score    : from the v3 catalogue status. A candidate whose
                         detections are explained by catalogued objects is
                         not a priority for follow-up:
                           KNOWN_OBJECT 0, UNCERTAIN 50,
                           UNMATCHED_AFTER_CHECKS 100
  - solar_system_score : 0 if a known Solar System small body explains the
                         track (JPL sb_ident + Horizons), else 100

final_priority_score = 0.70 * validation_score
                      + 0.20 * catalogue_score
                      + 0.10 * solar_system_score

A high priority means "most worth checking", never "confirmed". No
candidate is labeled Planet X, a discovery, or a confirmed unknown object.
"""

import numpy as np
import pandas as pd

INPUT_CSV = "validated_candidates_with_catalogue.csv"
OUTPUT_CSV = "final_ranked_candidates.csv"

W_VALIDATION = 0.70
W_CATALOG = 0.20
W_SSO = 0.10

CATALOGUE_SCORE = {"KNOWN_OBJECT": 0.0, "UNCERTAIN": 50.0, "UNMATCHED_AFTER_CHECKS": 100.0}

OUTPUT_COLS = [
    "final_rank",
    "candidate_id",
    "final_priority_score",
    "validation_score",
    "catalogue_score",
    "solar_system_score",
    "trajectory_score",
    "rate_consistency_score",
    "c_error_score",
    "flux_consistency_score",
    "direction_diff_deg",
    "rate_AC_arcsec_per_day",
    "rate_CB_arcsec_per_day",
    "C_prediction_error_arcsec",
    "flux_variation",
    "final_catalogue_status",
    "catalogue_explanation",
    "match_confidence",
    "reason",
]


print("1/3 Loading validated, catalogue-classified candidates")

df = pd.read_csv(INPUT_CSV)
print("Candidates:", len(df))


print("\n2/3 Computing final priority score")

df["catalogue_score"] = df["final_catalogue_status"].map(CATALOGUE_SCORE).fillna(50.0)
df["solar_system_score"] = np.where(
    df["catalogue_explanation"] == "KNOWN_SOLAR_SYSTEM_OBJECT", 0.0, 100.0
)
df["final_priority_score"] = (
    W_VALIDATION * df["validation_score"]
    + W_CATALOG * df["catalogue_score"]
    + W_SSO * df["solar_system_score"]
)

df = df.sort_values("final_priority_score", ascending=False).reset_index(drop=True)
df.insert(0, "final_rank", range(1, len(df) + 1))


def make_reason(row):
    parts = [
        f"direction change={row['direction_diff_deg']:.1f} deg",
        f"rate A-C={row['rate_AC_arcsec_per_day']:.2f}, "
        f"C-B={row['rate_CB_arcsec_per_day']:.2f} arcsec/day",
        f"C pred. err={row['C_prediction_error_arcsec']:.2f} arcsec",
        f"flux CV={row['flux_variation']:.2f}",
        f"catalogue: {row['final_catalogue_status']} ({row['catalogue_explanation']}, "
        f"{str(row['match_confidence']).lower()} confidence)",
    ]
    return "; ".join(parts)


df["reason"] = df.apply(make_reason, axis=1) if len(df) else pd.Series(dtype=str)


print("\n3/3 Saving final ranked candidate list")

df.reindex(columns=OUTPUT_COLS).to_csv(OUTPUT_CSV, index=False)

print()
print("==============================")
print("FINAL RANKED CANDIDATE LIST")
print("==============================")
print("Total candidates ranked:", len(df))
print()
for _, row in df.head(10).iterrows():
    print(f"#{row['final_rank']:>2}  {row['candidate_id']}  score={row['final_priority_score']:.1f}")
    print(f"     {row['reason']}")
print()
print("Created:", OUTPUT_CSV)
