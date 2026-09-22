# SpectraShift

**A SPHEREx Spectral & Multi-Epoch Sky Explorer.**

A public-facing frontend for browsing SPHEREx sky imagery, comparing
observations across epochs, and inspecting preliminary, unconfirmed
three-epoch motion candidates and their catalogue cross-match evidence.
Built with React, TypeScript, and Vite; talks to the project's FastAPI
backend (`../backend`) via `VITE_API_BASE_URL` (see `.env.example`).

No candidate shown by this app is a confirmed discovery.

## Development

```bash
npm install
npm run dev      # start the dev server (expects the backend running)
npm run build    # type-check + production build
```
