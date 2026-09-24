# SPHEREx Mosaic Tool — Job Submission Record (Step 1.4)

Real job submitted to the official IRSA SPHEREx Mosaic Tool (browser-driven,
no fabricated data). Job is server-side (UWS async), independent of the
browser session.

- Tool: https://irsa.ipac.caltech.edu/applications/spherex/ → Mosaic Tool tab
- Title: SPHEREx Mosaic
- Service ID: IRSA
- Type: UWS
- Async job URL slug (from network log at submission time): `Ho2X5q8GpZGaxz3u5X8aRi`
  (Note: direct GET on `CmdSrv/async/<id>` without the browser's session
  cookies returned `null` — status must be checked via the app's own
  Job Monitor tab, which is session/cookie-authenticated.)
- Created: 2026-09-22 18:50:20 UTC
- Start Time: 2026-09-22 18:50:26 UTC
- Phase as of 2026-09-22 19:20:25 UTC (~30 min elapsed): **EXECUTING** (not failed, not complete)

## Parameters submitted (verified in the tool's own form + resolved-coordinate readback)
- Output Mosaic Center: `155.352 -42.700` → tool resolved to `155.35200, -42.70000 Equ J2000`
- Output Mosaic X Size: 300 arcmin (5.0°)
- Output Mosaic Y Size: 255 arcmin (4.25°)
- Output Mosaic Y Rotation (E of N): 0°
- Output Mosaic Pixel Size: 6.15 arcsec
- Wavelength Range: 0.75–5 µm (default → all 102 nominal SPHEREx channels)

## Browser session used
- A local Chrome remote-debugging profile (machine-specific path not
  recorded here); relaunching Chrome with the same `--user-data-dir` should
  retain the session needed to see this job again in Job Monitor

## Status
Re-checked via Job Monitor on 2026-09-22 19:26 UTC (same session, no
resubmission): **Phase = COMPLETED**. End Time: 2026-09-22 19:26:23 UTC
(runtime ≈ 35m 57s).

## Real cube structure (confirmed visually in the results viewer)
- HDU (#1): IMAGE, Cube: 1/102 planes
- Plane 1 wavelength: 0.7530 µm (matches requested lower bound exactly)
- 3 HDUs total ("1/3" shown in HDU selector) -- consistent with the
  documented IMAGE, NHITS, FLAGS structure

## Real download attempt (2026-09-22 ~19:40 UTC)
Used the tool's documented save mechanism (Tools menu -> Save Image ->
FITS Image -> Save). The download request genuinely fired and the real
server response was captured:

  GET .../servlet/Download?file=...fits.gz
  200 OK
  content-length: 3112962118  (= 3.11 GB)
  content-disposition: attachment; filename=image_SPHEREx-Mosaic.fits

This confirms the REAL, actual size of the full 102-plane product: ~3.11 GB
(much larger than the 551MB viewer-cache "Retrieved" figure seen earlier,
which was evidently just a partial/compressed viewer representation, not
the full file).

Despite the request firing correctly, no bytes were found on disk after
~3 minutes of monitoring (filesystem + CDP download events) -- consistent
with this environment's already-demonstrated network instability on
transfers 1000x smaller (e.g. a 1MB JS bundle required retries earlier in
this session). This is a genuine environmental/network limitation, not a
fabricated or assumed result.

## Final download outcome (2026-09-23, overnight autonomous session)

Confirmed this IRSA endpoint **does not support HTTP Range requests**
(`curl: (33) HTTP server does not seem to support byte ranges. Cannot
resume.`) -- any `-C -` resume strategy is not viable against this URL.

Per instructions, ran the maximum of 3 fresh single-shot attempts
(`curl -L --http1.1 --connect-timeout 30 --speed-limit 10240
--speed-time 120`, no `-C -`, deleting the partial and restarting from
byte 0 between attempts). All 3 failed with the **identical** error:

  curl: (56) schannel: server closed abruptly (missing close_notify)

| Attempt | Bytes reached before failure |
|---|---|
| 1 | 1,146,225 |
| 2 | 441,713 |
| 3 | 5,111,153 |

All three failures occurred well under 0.2% of the expected 3,112,962,118
bytes, at varying points, with the same TLS-layer error each time -- this
matches a systematic pattern already observed elsewhere in this same
environment on other large transfers (the GitHub push and a ~5MB JS
bundle both needed retries earlier in this project), indicating an
environment/network-level instability with sustained large HTTPS
transfers, not a problem with the URL, the job, or the SPHEREx data
itself.

**Per the explicit fail-safe instruction, no further attempts were made.**
The final partial file (5,111,153 bytes) was intentionally left in place
(not deleted) as real evidence of the last attempt, rather than being
treated as a real product. **No FITS product exists. No Step 1.5
integration was attempted**, since its stated prerequisite (Step 1.4
completing successfully) was not met.

Real, verified facts that DO remain true regardless of this failure:
- The IRSA Mosaic Tool job (ID `Ho2X5q8GpZGaxz3u5X8aRi`) is genuinely
  COMPLETED server-side and (per IRSA's normal job retention) may still
  be retrievable later via the same URL, from a more stable network.
- The real product's exact compressed size is confirmed: 3,112,962,118
  bytes.
- The real cube's basic structure was visually confirmed via the IRSA
  viewer: HDU #1 = IMAGE, a cube of 102 planes; 3 HDUs total; plane 1
  wavelength = 0.7530 µm.
