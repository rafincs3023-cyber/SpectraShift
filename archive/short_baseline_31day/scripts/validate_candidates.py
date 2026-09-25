import matplotlib
matplotlib.use("Agg")

from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


FILE_A = "level2_2025W19_2B_0166_3D3_spx_l2b-v20-2025-247.fits"
FILE_C = "level2_2025W22_1B_0226_1D3_spx_l2b-v20-2025-250.fits"
FILE_B = "level2_2025W24_1A_0099_1D3_spx_l2b-v20-2025-252.fits"

INPUT_CSV = "three_epoch_motion_candidates.csv"
OUTPUT_CSV = "validated_three_epoch_candidates.csv"
OUTPUT_PNG = "top_candidate_tracks.png"

C_POSITION_TOLERANCE = 4.0   # arcsec, same tolerance used in three_epoch_compare.py

# Rejection thresholds. These are deliberately generous "clearly wrong"
# cutoffs (not tight cuts on a good sample) since the goal here is to
# drop trajectories/fluxes that are obviously inconsistent with a single
# moving real source, not to hand-pick a final answer.
MAX_DIRECTION_DIFF_DEG = 90.0     # A->C vs C->B heading must not reverse/right-angle
MIN_RATE_CONSISTENCY = 0.30       # min(rate)/max(rate) between the two legs
MAX_FLUX_VARIATION = 1.5          # coefficient of variation of flux_A/C/B

TOP_N_PLOT = 10


def get_mjd(filename):
    with fits.open(filename) as hdul:
        return hdul["IMAGE"].header.get("MJD-OBS")


print("1/5 Loading candidates and epoch timing")

df = pd.read_csv(INPUT_CSV)
# an empty candidate file (no track survived the linker) has no numeric
# dtypes to infer; make every coordinate/flux column numeric explicitly
numeric_cols = [c for c in df.columns if c.endswith(("_ra", "_dec", "_arcsec", "_per_day")) or c.startswith("flux_")]
df[numeric_cols] = df[numeric_cols].astype(float)
print("Input candidates:", len(df))

mjd_a = get_mjd(FILE_A)
mjd_c = get_mjd(FILE_C)
mjd_b = get_mjd(FILE_B)

dt_ac = mjd_c - mjd_a
dt_cb = mjd_b - mjd_c

print("A MJD:", mjd_a)
print("C MJD:", mjd_c)
print("B MJD:", mjd_b)
print("dt A->C (days):", round(dt_ac, 4))
print("dt C->B (days):", round(dt_cb, 4))


print("\n2/5 Computing per-leg motion, rate and direction")

coord_a = SkyCoord(df["A_ra"].values * u.deg, df["A_dec"].values * u.deg)
coord_c = SkyCoord(df["C_ra"].values * u.deg, df["C_dec"].values * u.deg)
coord_b = SkyCoord(df["B_ra"].values * u.deg, df["B_dec"].values * u.deg)

motion_ac = coord_a.separation(coord_c).arcsec
motion_cb = coord_c.separation(coord_b).arcsec

rate_ac = motion_ac / dt_ac
rate_cb = motion_cb / dt_cb

pa_ac = coord_a.position_angle(coord_c).to(u.deg).value
pa_cb = coord_c.position_angle(coord_b).to(u.deg).value

# wrap heading difference into [0, 180] degrees
direction_diff = np.abs((pa_cb - pa_ac + 180.0) % 360.0 - 180.0)

df["motion_AC_arcsec"] = motion_ac
df["motion_CB_arcsec"] = motion_cb
df["rate_AC_arcsec_per_day"] = rate_ac
df["rate_CB_arcsec_per_day"] = rate_cb
df["position_angle_AC_deg"] = pa_ac
df["position_angle_CB_deg"] = pa_cb
df["direction_diff_deg"] = direction_diff


print("\n3/5 Computing flux consistency")

flux_stack = df[["flux_A", "flux_C", "flux_B"]].values
flux_mean = flux_stack.mean(axis=1)
flux_std = flux_stack.std(axis=1)

# coefficient of variation across the three epochs
flux_variation = flux_std / flux_mean

df["flux_mean"] = flux_mean
df["flux_variation"] = flux_variation


print("\n4/5 Scoring and filtering")

rate_max = np.maximum(rate_ac, rate_cb)
rate_min = np.minimum(rate_ac, rate_cb)
rate_consistency = np.where(rate_max > 0, rate_min / rate_max, 0.0)

df["rate_consistency"] = rate_consistency

trajectory_score = np.clip(1.0 - direction_diff / 180.0, 0.0, 1.0)
rate_score = np.clip(rate_consistency, 0.0, 1.0)
c_error_score = np.clip(
    1.0 - df["C_prediction_error_arcsec"].values / C_POSITION_TOLERANCE,
    0.0,
    1.0
)
flux_score = np.clip(1.0 - flux_variation, 0.0, 1.0)

df["trajectory_score"] = trajectory_score
df["rate_consistency_score"] = rate_score
df["c_error_score"] = c_error_score
df["flux_consistency_score"] = flux_score

df["validation_score"] = 100.0 * (
    0.30 * trajectory_score
    + 0.30 * rate_score
    + 0.20 * c_error_score
    + 0.20 * flux_score
)

reject_mask = (
    (direction_diff > MAX_DIRECTION_DIFF_DEG)
    | (rate_consistency < MIN_RATE_CONSISTENCY)
    | (flux_variation > MAX_FLUX_VARIATION)
)

print("Rejected (bad trajectory/rate/flux):", int(reject_mask.sum()))

validated = df.loc[~reject_mask].copy()
validated = validated.sort_values("validation_score", ascending=False)

validated.insert(
    0,
    "rank",
    range(1, len(validated) + 1)
)

print("Validated candidates:", len(validated))


print("\n5/5 Saving results")

validated.to_csv(OUTPUT_CSV, index=False)


# --- Visualization: A -> C -> B tracks for the top candidates ---

top = validated.head(TOP_N_PLOT)

n = len(top)

if n > 0:

    ncols = min(5, n)
    nrows = int(np.ceil(n / ncols))

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(4 * ncols, 4 * nrows),
        squeeze=False
    )

    for i, (_, row) in enumerate(top.iterrows()):

        ax = axes[i // ncols][i % ncols]

        # sky-plane offsets in arcsec relative to Epoch A position,
        # RA offset scaled by cos(dec) so the plot is angle-true
        cosd = np.cos(np.deg2rad(row["A_dec"]))

        ra0 = row["A_ra"]
        dec0 = row["A_dec"]

        xa, ya = 0.0, 0.0
        xc = (row["C_ra"] - ra0) * cosd * 3600.0
        yc = (row["C_dec"] - dec0) * 3600.0
        xb = (row["B_ra"] - ra0) * cosd * 3600.0
        yb = (row["B_dec"] - dec0) * 3600.0

        ax.plot(
            [xa, xc, xb],
            [ya, yc, yb],
            "-",
            color="0.6",
            linewidth=1,
            zorder=1
        )

        ax.annotate(
            "",
            xy=(xc, yc),
            xytext=(xa, ya),
            arrowprops=dict(arrowstyle="->", color="tab:blue"),
        )
        ax.annotate(
            "",
            xy=(xb, yb),
            xytext=(xc, yc),
            arrowprops=dict(arrowstyle="->", color="tab:red"),
        )

        ax.scatter(
            [xa, xc, xb],
            [ya, yc, yb],
            c=["tab:blue", "tab:green", "tab:red"],
            s=40,
            zorder=2
        )

        for label, x, y in [
            ("A", xa, ya),
            ("C", xc, yc),
            ("B", xb, yb)
        ]:
            ax.annotate(
                label,
                (x, y),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8
            )

        ax.set_title(
            f"{row['candidate_id']}  score={row['validation_score']:.1f}",
            fontsize=9
        )
        ax.set_xlabel("RA offset (arcsec)", fontsize=7)
        ax.set_ylabel("Dec offset (arcsec)", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axhline(0, color="0.85", linewidth=0.5, zorder=0)
        ax.axvline(0, color="0.85", linewidth=0.5, zorder=0)

    # hide any unused axes
    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    fig.suptitle(
        "Top validated three-epoch candidates: A (blue) -> C (green) -> B (red)",
        fontsize=12
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(OUTPUT_PNG, dpi=150)
    plt.close(fig)

    print("Created:", OUTPUT_PNG)

else:
    # replace any previous run's figure so no stale tracks are left behind
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.axis("off")
    ax.text(0.5, 0.5, "No validated three-epoch candidates in this run\n"
            "(every linked track was rejected by the stationary-source veto;\n"
            "see rejected_three_epoch_tracks.csv)", ha="center", va="center", fontsize=11)
    plt.savefig(OUTPUT_PNG, dpi=150)
    plt.close(fig)
    print("No validated candidates to plot; wrote placeholder", OUTPUT_PNG)


print()
print("==============================")
print("THREE-EPOCH VALIDATION RESULTS")
print("==============================")
print(f"Input candidates: {len(df)}")
print(f"Validated candidates: {len(validated)}")

if len(validated) > 0:

    print()
    print(
        validated[
            [
                "rank",
                "candidate_id",
                "rate_AC_arcsec_per_day",
                "rate_CB_arcsec_per_day",
                "direction_diff_deg",
                "C_prediction_error_arcsec",
                "flux_variation",
                "validation_score"
            ]
        ].head(10).to_string(index=False)
    )

    print()
    print("Created:", OUTPUT_CSV)

else:
    print("No candidate survived validation.")
