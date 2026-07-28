# SIP Web

The web app is a Next.js 16/React 19 application with renderer-independent scene state and a Three.js-compatible adapter boundary. It never treats visual or interaction geometry as authoritative.

`npm test` runs deterministic runtime checks without a browser or installed renderer. `npm run build`, `npm run typecheck`, and `npm run lint` require the pinned dependency installation.
