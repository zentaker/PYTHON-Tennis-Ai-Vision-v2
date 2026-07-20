# ADR: Core Python and Web product separation

## Status

Accepted for Stage 0A productization.

## Decisions

1. Core remains Python and contains analysis contracts, models and bundle writing;
   it contains no product UI.
2. Web is TypeScript, created later, and never executes models.
3. Core and Web communicate through versioned Analysis Bundles and later an API.
4. Overlays are rendered from data; source MP4 files are not permanently burned.
5. Models load on demand; experimental modules are disabled by default.
6. Pose runs only on frames required by the selected processing profile.
7. Outputs are reproducible, versioned and linked to the source-video checksum.

This ADR deliberately does not create the Web repository or refactor runtime code.
