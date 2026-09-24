// Types mirror the FastAPI backend response shapes exactly
// (see backend/main.py). Keep in sync if the backend changes.

export type CatalogueStatus =
  | "KNOWN_OBJECT"
  | "UNMATCHED_AFTER_CHECKS"
  | "UNCERTAIN";

export interface HealthFileStatus {
  loaded: boolean;
  rows: number;
  error: string | null;
}

export interface HealthFitsStatus {
  found: boolean;
  error: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  timestamp_utc: string;
  csv_files: Record<string, HealthFileStatus>;
  fits_files: Record<string, HealthFitsStatus>;
  note: string;
}

export interface Observation {
  epoch: "A" | "C" | "B";
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

export interface ObservationsResponse {
  count: number;
  observations: Observation[];
  errors: Record<string, string> | null;
}

// One row of GET /api/candidates
export interface CandidateSummary {
  candidate_id: string;
  rank: number | null;
  A_ra: number | null;
  A_dec: number | null;
  C_ra: number | null;
  C_dec: number | null;
  B_ra: number | null;
  B_dec: number | null;
  total_motion_arcsec: number | null;
  motion_arcsec_per_day: number | null;
  direction_diff_deg: number | null;
  C_prediction_error_arcsec: number | null;
  flux_variation: number | null;
  validation_score: number | null;
  final_catalogue_status: CatalogueStatus | null;
  best_match_catalogue: string | null;
  best_match_separation_arcsec: number | null;
  /** v3 classification detail (catalogue_crossmatch_v3.py) */
  catalogue_explanation?: CatalogueExplanation | null;
  match_confidence?: MatchConfidence | null;
  status_reason?: string | null;
  final_rank: number | null;
  final_priority_score: number | null;
}

export interface CandidatesResponse {
  count: number;
  candidates: CandidateSummary[];
  valid_catalogue_statuses: CatalogueStatus[];
}

export interface EpochPosition {
  ra_deg: number | null;
  dec_deg: number | null;
  source_id: number | null;
  flux: number | null;
}

export interface CandidateMotion {
  total_motion_arcsec: number | null;
  motion_arcsec_per_day: number | null;
  motion_AC_arcsec: number | null;
  motion_CB_arcsec: number | null;
  rate_AC_arcsec_per_day: number | null;
  rate_CB_arcsec_per_day: number | null;
  position_angle_AC_deg: number | null;
  position_angle_CB_deg: number | null;
  direction_diff_deg: number | null;
}

export interface CandidateValidation {
  trajectory_score: number | null;
  rate_consistency_score: number | null;
  c_error_score: number | null;
  flux_consistency_score: number | null;
  validation_score: number | null;
  C_prediction_error_arcsec: number | null;
  flux_variation: number | null;
  flux_mean: number | null;
}

export type CatalogueExplanation =
  | "KNOWN_SOLAR_SYSTEM_OBJECT"
  | "STATIC_KNOWN_STAR"
  | "LINKED_KNOWN_STARS"
  | "HIGH_PM_STAR_CANDIDATE"
  | "NO_ASSOCIATION"
  | "INSUFFICIENT_OR_AMBIGUOUS";

export type MatchConfidence = "HIGH" | "MEDIUM" | "LOW" | "NONE";

export interface CatalogueEpochMatch {
  epoch: "A" | "C" | "B";
  match_object: string | null;
  separation_arcsec: number | null;
  chi2: number | null;
  sigma_total_arcsec: number | null;
  /** catalogue position propagated to this epoch */
  expected_ra_deg: number | null;
  expected_dec_deg: number | null;
  p_chance: number | null;
  n_consistent: number | null;
  mag_residual: number | null;
  /** forced-photometry SNR at this epoch's position in the other epochs, e.g. "C:12.3;B:10.1" */
  persistence_snr: string | null;
}

export interface CandidateCatalogue {
  final_catalogue_status: CatalogueStatus | null;
  best_match_catalogue: string | null;
  best_match_object: string | null;
  best_match_separation_arcsec: number | null;
  best_match_epoch: string | null;
  services_succeeded: string[];
  services_failed: string[];
  notes: string | null;
  explanation?: CatalogueExplanation | null;
  match_confidence?: MatchConfidence | null;
  status_reason?: string | null;
  catalogues_checked?: string[];
  optional_services_unavailable?: string[];
  joint_p_chance?: number | null;
  observed_motion?: {
    rate_arcsec_per_day: number | null;
    position_angle_deg: number | null;
  };
  expected_motion?: {
    rate_arcsec_per_day: number | null;
    position_angle_deg: number | null;
    source: string | null;
  };
  per_epoch?: CatalogueEpochMatch[];
}

// GET /api/candidates/{id}
export interface CandidateDetail {
  candidate_id: string;
  rank: number | null;
  final_rank: number | null;
  final_priority_score: number | null;
  positions: {
    A: EpochPosition;
    C: EpochPosition;
    B: EpochPosition;
  };
  motion: CandidateMotion;
  validation: CandidateValidation;
  catalogue: CandidateCatalogue;
  ranking_reason: string | null;
}

// One row of GET /api/catalogue-crossmatch/{id}
export interface CrossmatchRecord {
  candidate_id: string;
  epoch: "A" | "C" | "B";
  mjd: number | null;
  candidate_ra: number | null;
  candidate_dec: number | null;
  catalogue: string;
  matched_object: string | null;
  object_type: string | null;
  matched_ra: number | null;
  matched_dec: number | null;
  separation_arcsec: number | null;
  match_status: "MATCH" | "NO_MATCH" | "SERVICE_UNAVAILABLE";
  notes: string | null;
}

export interface CrossmatchSummary {
  best_match_catalogue: string | null;
  best_match_object: string | null;
  best_match_separation_arcsec: number | null;
  best_match_epoch: string | null;
  services_succeeded: string | null;
  services_failed: string | null;
  notes: string | null;
}

export interface CrossmatchResponse {
  candidate_id: string;
  final_catalogue_status: CatalogueStatus | null;
  record_count: number;
  records: CrossmatchRecord[];
  summary: CrossmatchSummary | null;
}

// GET /api/linking-summary -- outcome of the latest three_epoch_compare.py run
export interface LinkingSummary {
  accepted_tracks: number;
  rejected_tracks: number;
  rejected_by_reason: {
    STATIONARY_SOURCE: number;
    BLEND_MISLINK: number;
    INCONSISTENT_TRAJECTORY: number;
  };
  rejected_tracks_file: string | null;
  genuine_mover_veto_probability: number | null;
  detection_sigma: number | null;
  note: string;
}

// ---------------------------------------------------------------------
// Compare page

export type EpochLabel = "A" | "C" | "B";

/** What the Compare image components need for one side of a pair. */
export interface CompareImageSide {
  epoch: EpochLabel;
  observation: Observation | null;
  preview_url: string;
  /** Display label; components fall back to "Epoch {epoch}". */
  label?: string;
}

export interface ComparePairSide extends CompareImageSide {
  markers_url: string;
}

export interface ComparePairResponse {
  epoch_a: ComparePairSide;
  epoch_b: ComparePairSide;
  pixel_aligned: boolean;
  alignment_note: string;
  difference_available: boolean;
  difference_preview_url: string | null;
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

export interface CandidateMarker {
  candidate_id: string;
  x_frac: number;
  y_frac: number;
}

export interface CandidateMarkersResponse {
  epoch: string;
  count: number;
  markers: CandidateMarker[];
}

// ---------------------------------------------------------------------
// Explore page: per-candidate spectral sample points

export interface SpectrumPoint {
  epoch: EpochLabel;
  mjd: number | null;
  wavelength_um: number | null;
  wavelength_bandwidth_um: number | null;
  flux: number | null;
  flux_uncertainty: number | null;
}

export interface CandidateSpectrumResponse {
  candidate_id: string;
  points: SpectrumPoint[];
  note: string;
}
