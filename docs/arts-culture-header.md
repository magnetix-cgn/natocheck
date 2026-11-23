# Arts and Culture header identity

## Request and delivery
Add the Arts & Culture Germany e.V. logo to the NatoCheck header, matching the existing Eventhacker identity. The header now includes the white association signet and name beside the Eventhacker logo, with responsive rows for the wordmark, language controls, version and alphabet toggle. No additional external links were introduced.

The 96x96 transparent lossless WebP was previously delivered through the configured private AgentUp. A fresh authenticated readback matched the bundled bytes and SHA-256 `a3eb2908a6e0f8697fa0fd2aa7ef889db1d70175c54f9512c0c114d39abff280`. The app explicitly serves the new asset as image/webp. Private intake details are excluded.

## Verification
All 60 existing unit tests passed. Chromium checked 320, 390, 590, 1000 and 1280 px: logo decoded, partner identities did not overlap, no horizontal page overflow, English switch and alphabet toggle passed. The 390 px screenshot was visually inspected. Physical iPhone/Safari was not tested. Generated browser evidence remains in skill-local output outside Git.

## Release and handover
Implementation commit: `f4bb765`, pushed to origin/main on 23 November 2026. Implemented and locally tested; production deployment, live verification and external publication remain unconfirmed.

Automatic approval review rejected `bash scripts/deploy-to-ai.sh` before execution because the live release restarts the production service and the review requires explicit user authorization for that action. No deployment workaround was attempted. Next crew: obtain explicit production deployment approval, run the established release script from the clean pushed checkout, require its HTTP/exercise/synthetic speech checks to pass, then repeat responsive header checks against public HTTPS. Send an accurate deployment completion update through localmail after live verification.
