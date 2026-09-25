// Types mirror the FastAPI backend response shapes exactly (backend/main.py,
// time_compare_6month.py, candidates_api.py). Keep in sync if the backend
// changes. Spectral View types live in spectral.ts.

export interface HealthResponse {
  status: "ok" | "degraded";
  timestamp_utc: string;
  time_compare_6month: { available: boolean; missing_files: string[] };
  two_epoch_candidates: { results_file: string; precomputed: boolean; pipeline: string };
  note: string;
}

/** A = earlier observation (2025-06-19), B = later observation (2025-12-17). */
export type EpochLabel = "A" | "B";

export interface Observation {
  epoch: EpochLabel;
  filename: string;
  obs_id: string | null;
  detector: number | null;
  mjd_obs: number | null;
  date_obs: string | null;
  naxis1: number | null;
  naxis2: number | null;
  ra_center_deg: number | null;
  dec_center_deg: number | null;
  bunit: string | null;
}

/** What the Compare image components need for one side of the pair. */
export interface CompareImageSide {
  epoch: EpochLabel;
  observation: Observation | null;
  preview_url: string;
  /** Display label; components fall back to "Epoch {epoch}". */
  label?: string;
}

// GET /api/compare/6month -- the ~6-month (Jun 19 vs Dec 17 2025) pair.
// Scientific values come from data/time_compare_6month/metadata.json and
// the FITS headers; the frontend does not duplicate them.

export interface SixMonthSide extends CompareImageSide {
  figure_url: string;
  wavelength_um: number;
  psf_fwhm_arcsec: number | null;
  source_file: string;
}

export interface SixMonthCompareResponse {
  dataset: "6month";
  title: string;
  /** The pointing used to select this pair -- NOT the frame centre. */
  target: {
    ra_deg: number;
    dec_deg: number;
    crop_pixel: { x: number; y: number };
    in_display_region: boolean;
    x_frac: number | null;
    y_frac: number | null;
    offset_from_display_px: number;
    offset_from_display_arcsec: number;
  };
  /** Centre of the displayed region (what the image footers show). */
  frame_center: { ra_deg: number; dec_deg: number };
  /** The single rectangle, fully inside the common footprint, that every
   * preview is cut to (numpy bounds in the aligned-crop grid). */
  display_region: {
    x0: number;
    x1: number;
    y0: number;
    y1: number;
    width: number;
    height: number;
    valid_pixels: number;
    invalid_pixels: number;
    valid_fraction: number;
    pixel_scale_arcsec: number;
  };
  epoch_a: SixMonthSide;
  epoch_b: SixMonthSide;
  time_gap_days: number;
  time_gap_months: number;
  wavelength_delta_um: number;
  delta_over_bandwidth: number | null;
  bunit: string | null;
  crop: {
    x0: number;
    x1: number;
    y0: number;
    y1: number;
    width: number;
    height: number;
  };
  overlap_pixels: number;
  pixel_aligned: boolean;
  alignment_note: string;
  difference_primary: string;
  difference_meaning: string;
  difference_available: boolean;
  difference_preview_url: string;
  difference_figure_url: string;
}

// ---------------------------------------------------------------------
// Two-epoch candidates (GET /api/candidates, /api/candidates/{id},
// /api/candidates/markers). Built only from the ~6-month pair.

export type CandidateKind =
  | "possible_position_change"
  | "shifted_match"
  | "seen_only_earlier"
  | "seen_only_later";

/** One detection of a candidate in the earlier or later image. */
export interface CandidateSighting {
  ra: number;
  dec: number;
  /** pixel position on the shared (aligned) grid */
  x: number;
  y: number;
  snr: number;
  /** aperture sum of MJy/sr within a 2-pixel radius */
  brightness: number | null;
  peak: number | null;
  sharpness: number | null;
  roundness: number | null;
  centroid_error_arcsec: number | null;
  /** single-image candidates only */
  forced_snr_in_other_image?: number | null;
  difference_snr?: number | null;
}

export interface TwoEpochCandidate {
  candidate_id: string;
  kind: CandidateKind;
  kind_label: string;
  earlier_date: string;
  later_date: string;
  time_baseline_days: number;
  earlier: CandidateSighting | null;
  later: CandidateSighting | null;
  angular_displacement_arcsec: number | null;
  apparent_motion_arcsec_per_day: number | null;
  position_angle_deg: number | null;
  brightness_ratio_later_over_earlier: number | null;
  alternative_partners?: number;
  shift_significance_sigma?: number | null;
  stationary_tolerance_arcsec?: number | null;
  status: "passed_current_checks";
  caveats: string[];
}

export interface CandidateMeasured {
  fwhm_arcsec: Record<EpochLabel, number>;
  median_noise_mjy_sr: Record<EpochLabel, number>;
  detections: Record<EpochLabel, number>;
  matched_in_both: number;
  alignment_residual_shift_arcsec: [number, number];
  alignment_scatter_arcsec: number;
  bright_stars_used_for_alignment: number;
  psf_matched_fwhm_arcsec: number;
  position_error_model: { sigma_floor_arcsec: number; k_arcsec: number; formula: string };
  matched_beyond_stationary_tolerance: number;
  gaussian_expectation_beyond_tolerance: number;
}

export interface CandidatesResponse {
  pipeline: string;
  earlier_date: string;
  later_date: string;
  time_baseline_days: number;
  count: number;
  counts: Record<CandidateKind | "total", number>;
  kind_labels: Record<CandidateKind, string>;
  candidates: TwoEpochCandidate[];
  rejected_by_reason: Record<string, number>;
  rejection_reasons: Record<string, string>;
  measured: CandidateMeasured;
  thresholds: Record<string, number | string>;
  inputs: {
    earlier: { date: string; file: string; grid_file: string; wavelength_um: number };
    later: { date: string; file: string; grid_file: string; wavelength_um: number };
    overlap_mask: string;
    difference: string;
    time_baseline_days: number;
    pixel_scale_arcsec: number;
  };
  flag_notes: string[];
  limitations: string[];
}

export interface CandidateCutoutSet {
  at: "earlier" | "later";
  earlier: string;
  later: string;
  difference: string;
}

export interface CandidateDetailResponse extends TwoEpochCandidate {
  cutouts: CandidateCutoutSet[];
  cutout_size_arcsec: number;
  rejection_reasons: Record<string, string>;
  limitations: string[];
}

export interface CandidateMarker {
  candidate_id: string;
  kind?: CandidateKind;
  x_frac: number;
  y_frac: number;
  /** false: marked where the source is in the OTHER image */
  detected_here?: boolean;
}

export interface CandidateMarkersResponse {
  image: "earlier" | "later";
  count: number;
  markers: CandidateMarker[];
  outside_display: string[];
}
