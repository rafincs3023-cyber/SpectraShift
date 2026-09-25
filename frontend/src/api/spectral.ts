// Spectral View API: the 102-channel SPHEREx mosaic cubes served by
// backend/spectral_api.py (/api/spectral/*). Kept separate from the
// Time Compare client so the two features stay independent.

import { API_BASE_URL, ApiError } from "./client";

export interface SpectralChannel {
  channel: number;
  source_file: string;
  source_plane: number;
  detector: number | null;
  subchannel: number | null;
  wavelength_um: number | null;
  wavelength_min_um: number | null;
  wavelength_max_um: number | null;
  bandwidth_um: number | null;
  resolving_power: number | null;
  resolving_power_std: number | null;
  coverage_fraction: number | null;
  preview_url: string;
}

export interface SpectralMetadata {
  dataset: string;
  purpose: string;
  total_channels: number;
  image: {
    width: number;
    height: number;
    unit: string | null;
    pixel_scale_arcsec: (number | null)[];
    center: { ra_deg: number | null; dec_deg: number | null };
    corners: { ra_deg: number | null; dec_deg: number | null }[];
    pixel_convention: string;
  };
  wavelength_range_um: {
    min: number | null;
    max: number | null;
    center_min: number | null;
    center_max: number | null;
  };
  sources: {
    file: string;
    first_channel: number;
    last_channel: number;
    n_channels: number;
  }[];
  channels: SpectralChannel[];
  warnings: string[];
}

export interface SpectralSample {
  channel: number;
  detector: number | null;
  subchannel: number | null;
  wavelength_um: number | null;
  bandwidth_um: number | null;
  value: number | null;
  valid: boolean;
}

export interface SpectrumResponse {
  query: { ra_deg?: number; dec_deg?: number; x?: number; y?: number };
  pixel: {
    x: number;
    y: number;
    x_index: number;
    y_index: number;
    x_frac: number;
    y_frac: number;
  };
  pixel_center: { ra_deg: number | null; dec_deg: number | null };
  in_footprint: boolean;
  unit: string | null;
  quantity: string;
  n_channels: number;
  n_valid: number;
  has_data: boolean;
  samples: SpectralSample[];
  note: string;
}

export type SpectrumQuery = { x: number; y: number } | { ra: number; dec: number };

/** ApiError plus the backend's machine-readable error code
 * (invalid_channel, outside_footprint, spectral_data_missing, ...). */
export class SpectralApiError extends ApiError {
  code: string | null;

  constructor(message: string, status: number, code: string | null) {
    super(message, status);
    this.name = "SpectralApiError";
    this.code = code;
  }
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { signal });
  } catch (err) {
    if ((err as Error)?.name === "AbortError") throw err;
    throw new SpectralApiError(
      `Could not reach the API at ${API_BASE_URL}. Is the backend running?`,
      0,
      "backend_unavailable"
    );
  }

  if (!response.ok) {
    let message = response.statusText;
    let code: string | null = null;
    try {
      const body = await response.json();
      const detail = body?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail.message === "string") {
        message = detail.message;
        code = typeof detail.code === "string" ? detail.code : null;
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        message = String(detail[0].msg);
      }
    } catch {
      // body wasn't JSON; keep statusText
    }
    throw new SpectralApiError(message, response.status, code);
  }
  return (await response.json()) as T;
}

// Metadata is ~35 KB and never changes while the app is open, so it is
// fetched once and shared across page visits. A failed fetch is not cached.
let metadataPromise: Promise<SpectralMetadata> | null = null;

export function getSpectralMetadata(): Promise<SpectralMetadata> {
  if (!metadataPromise) {
    metadataPromise = request<SpectralMetadata>("/api/spectral/metadata").catch((err) => {
      metadataPromise = null;
      throw err;
    });
  }
  return metadataPromise;
}

// Spectra for a given pixel never change either; cache by query.
const spectrumCache = new Map<string, SpectrumResponse>();

export async function getSpectrum(
  query: SpectrumQuery,
  signal?: AbortSignal
): Promise<SpectrumResponse> {
  const qs =
    "x" in query
      ? `x=${query.x}&y=${query.y}`
      : `ra=${encodeURIComponent(query.ra)}&dec=${encodeURIComponent(query.dec)}`;
  const cached = spectrumCache.get(qs);
  if (cached) return cached;
  const res = await request<SpectrumResponse>(`/api/spectral/spectrum?${qs}`, signal);
  spectrumCache.set(qs, res);
  spectrumCache.set(`x=${res.pixel.x_index}&y=${res.pixel.y_index}`, res);
  return res;
}

export function spectralPreviewUrl(channel: number): string {
  return `${API_BASE_URL}/api/spectral/channels/${channel}/preview`;
}

// Preview images are requested at most once per URL per session: each is
// decoded into an off-screen Image and remembered, so revisiting a channel
// (or prefetching a neighbour) never issues a duplicate request.
const previewLoads = new Map<string, Promise<string>>();
const previewLoaded = new Set<number>();

export function loadPreview(channel: number): Promise<string> {
  const url = spectralPreviewUrl(channel);
  let p = previewLoads.get(url);
  if (!p) {
    p = new Promise<string>((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        previewLoaded.add(channel);
        resolve(url);
      };
      img.onerror = () => {
        previewLoads.delete(url); // allow a retry
        reject(new Error(`The preview image for channel ${channel} could not be loaded.`));
      };
      img.src = url;
    });
    previewLoads.set(url, p);
  }
  return p;
}

export function isPreviewLoaded(channel: number): boolean {
  return previewLoaded.has(channel);
}
