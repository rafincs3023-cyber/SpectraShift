import type {
  CandidateDetail,
  CandidateMarkersResponse,
  CandidateSpectrumResponse,
  CandidatesResponse,
  ComparePairResponse,
  CrossmatchResponse,
  EpochLabel,
  HealthResponse,
  LinkingSummary,
  ObservationsResponse,
  SixMonthCompareResponse,
} from "./types";

// Backend URL is environment-based (see .env / .env.example) so the same
// build can point at a different backend without code changes.
// Without VITE_API_BASE_URL, development talks to the local backend and a
// production build uses same-origin "/api/..." paths (backend or reverse
// proxy on the same host), so no localhost URL ever ships in a public build.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`);
  } catch {
    throw new ApiError(
      `Could not reach the API at ${API_BASE_URL}. Is the backend running?`,
      0
    );
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  getHealth: () => request<HealthResponse>("/api/health"),
  getObservations: () => request<ObservationsResponse>("/api/observations"),
  getCandidates: () => request<CandidatesResponse>("/api/candidates"),
  getLinkingSummary: () => request<LinkingSummary>("/api/linking-summary"),
  getCandidate: (candidateId: string) =>
    request<CandidateDetail>(
      `/api/candidates/${encodeURIComponent(candidateId)}`
    ),
  getCatalogueCrossmatch: (candidateId: string) =>
    request<CrossmatchResponse>(
      `/api/catalogue-crossmatch/${encodeURIComponent(candidateId)}`
    ),
  getComparePair: (epochA: EpochLabel, epochB: EpochLabel) =>
    request<ComparePairResponse>(
      `/api/compare/pair?epoch_a=${epochA}&epoch_b=${epochB}`
    ),
  getSixMonthCompare: () =>
    request<SixMonthCompareResponse>("/api/compare/6month"),
  getCandidateMarkers: (epochKey: string) =>
    request<CandidateMarkersResponse>(
      `/api/compare/candidate-markers?epoch=${encodeURIComponent(epochKey)}`
    ),
  getCandidateSpectrum: (candidateId: string) =>
    request<CandidateSpectrumResponse>(
      `/api/candidates/${encodeURIComponent(candidateId)}/spectrum`
    ),
  /** Fetch a backend-relative path as-is (used for the markers_url values
   * returned inline by /api/compare/pair, so the frontend doesn't need to
   * re-derive the aligned-epoch-key logic that already lives server-side). */
  getByPath: <T,>(path: string) => request<T>(path),
};

/** Full URL for a backend-served image path (e.g. a preview_url from
 * ComparePairResponse). Images are loaded directly via <img>/canvas, not
 * through the JSON `request` helper. */
export function imageUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
