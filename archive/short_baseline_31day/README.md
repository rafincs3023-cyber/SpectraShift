# Archive: retired short-baseline (31-day) work

**Not part of the current product.** Nothing in this folder is imported by
the backend, served by the API, shown in the web interface or included in
the production image (see `.dockerignore`).

It holds the earlier three-observation (May–June 2025) linker, catalogue
classification and their outputs, kept only for repository history. The
scripts were written to run from the project root and are not maintained.

The active product uses only the ~6-month SPHEREx pair (June 19 and
December 17, 2025) in `data/time_compare_6month/` and the two-epoch
candidate pipeline in `backend/two_epoch_candidates.py`.

The three Level-2 FITS frames of that earlier set remain at the project
root unchanged (FITS files are not moved or modified); they are unused.
