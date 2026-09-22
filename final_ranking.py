"""
Build the final ranked candidate list from already-completed results:
  - validated_three_epoch_candidates.csv  (trajectory/rate/flux/C-error scores)
  - catalogue_crossmatch_results.csv      (Gaia/SIMBAD + Solar System status)

No validation, Gaia/SIMBAD, or Solar System cross-match is rerun here -- this
script only combines existing, already-verified numbers into a single
priority ranking.

Scoring components (0-100 each):
  - validation_score          : from the three-epoch validation step
                                 (trajectory + rate consistency + C-prediction
                                 error + flux consistency; unchanged here)
  - catalog_confidence_score  : all 22 candidates carry a Gaia "Known" status,
                                 but each is from a SINGLE epoch's incidental
                                 coincidence with a field star (never all
                                 three epochs -- see catalogue_crossmatch
                                 notes), consistent with expected ~49%/epoch
                                 chance coincidence in this dense field. A
                                 tighter coincidence is treated as a mildly
                                 higher contamination risk; this component
                                 rewards candidates whose nearest Gaia/SIMBAD
                                 coincidence is farther away (safer).
  - solar_system_score        : constant/neutral for all 22 (all "Unmatched"
                                 against the 19-body JPL Horizons major/bright
                                 -body check only). Included for methodological
                                 completeness and so the pipeline is ready to
                                 use this signal once a full SkyBoT/MPC search
                                 is available; it does NOT currently
                                 discriminate between candidates. "Unmatched"
                                 here reflects only the limited check that was
                                 actually performed -- NOT a confirmation that
                                 a candidate is absent from the full
                                 minor-planet catalogue, and NOT evidence of
                                 being a new/real object.

final_priority_score = 0.70 * validation_score
                      + 0.20 * catalog_confidence_score
                      + 0.10 * solar_system_score

No candidate is labeled Planet X or confirmed real.
"""

import numpy as np
import pandas as pd

VALIDATED_CSV = "validated_three_epoch_candidates.csv"
CROSSMATCH_CSV = "catalogue_crossmatch_results.csv"
OUTPUT_CSV = "final_ranked_candidates.csv"

GAIA_KNOWN_RADIUS_ARCSEC = 4.0   # same "known" radius used in catalogue_crossmatch.py

W_VALIDATION = 0.70
W_CATALOG = 0.20
W_SSO = 0.10


print("1/3 Loading existing validation and cross-match results")

validated = pd.read_csv(VALIDATED_CSV)
crossmatch = pd.read_csv(CROSSMATCH_CSV)

print("Validated candidates:", len(validated))
print("Cross-match rows:", len(crossmatch))

df = validated.drop(columns=["rank"]).merge(
    crossmatch,
    on="candidate_id",
    how="left"
)

assert len(df) == len(validated), "Row count changed during merge"


print("\n2/3 Computing final priority score")

# --- catalogue (Gaia/SIMBAD) confidence component ---
# angular_separation_arcsec is the nearest Gaia/SIMBAD coincidence at any of
# the 3 epochs. Larger separation (weaker coincidence) -> higher score.
sep = df["angular_separation_arcsec"].values
catalog_confidence_score = 100.0 * np.clip(
    sep / GAIA_KNOWN_RADIUS_ARCSEC,
    0.0,
    1.0
)
df["catalog_confidence_score"] = catalog_confidence_score

# --- solar system component ---
# Neutral/constant: every candidate was checked (solar_system_checked=True)
# against the same 19-body Horizons list and came back Unmatched. This does
# not currently separate candidates from each other; kept for transparency
# and so the formula is ready for a future full MPC/SkyBoT pass.
sso_status = df["solar_system_match"].fillna("Unmatched")
sso_score_map = {"Known": 0.0, "Possible": 50.0, "Unmatched": 100.0}
df["solar_system_score"] = sso_status.map(sso_score_map).fillna(100.0)

df["final_priority_score"] = (
    W_VALIDATION * df["validation_score"]
    + W_CATALOG * df["catalog_confidence_score"]
    + W_SSO * df["solar_system_score"]
)

df = df.sort_values("final_priority_score", ascending=False).reset_index(drop=True)
df.insert(0, "final_rank", range(1, len(df) + 1))


def make_reason(row):
    parts = []
    parts.append(f"direction change={row['direction_diff_deg']:.1f} deg")
    parts.append(
        f"rate A-C={row['rate_AC_arcsec_per_day']:.2f}, "
        f"C-B={row['rate_CB_arcsec_per_day']:.2f} arcsec/day"
    )
    parts.append(f"C pred. err={row['C_prediction_error_arcsec']:.2f} arcsec")
    parts.append(f"flux CV={row['flux_variation']:.2f}")
    parts.append(
        f"nearest Gaia/SIMBAD coincidence {row['angular_separation_arcsec']:.2f} arcsec "
        f"at epoch {row['matched_epoch']} (1 of 3 epochs only)"
    )
    parts.append("no match in the 19-body JPL Horizons SSO check")
    return "; ".join(parts)


df["reason"] = df.apply(make_reason, axis=1)


print("\n3/3 Saving final ranked candidate list")

output_cols = [
    "final_rank",
    "candidate_id",
    "final_priority_score",
    "validation_score",
    "catalog_confidence_score",
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
    "match_status",
    "angular_separation_arcsec",
    "matched_epoch",
    "solar_system_checked",
    "solar_system_match",
    "reason",
]

df[output_cols].to_csv(OUTPUT_CSV, index=False)

print()
print("==============================")
print("FINAL RANKED CANDIDATE LIST")
print("==============================")
print("Total candidates ranked:", len(df))
print()

top10 = df.head(10)

for _, row in top10.iterrows():
    print(
        f"#{row['final_rank']:>2}  {row['candidate_id']}  "
        f"score={row['final_priority_score']:.1f}"
    )
    print(f"     {row['reason']}")

print()
print("Created:", OUTPUT_CSV)
