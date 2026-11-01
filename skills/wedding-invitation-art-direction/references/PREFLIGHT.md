# Invitation art preflight and release gates

**Use this as a checklist, not as an automated certification.** Mark each item PASS / FAIL / UNKNOWN / NOT_APPLICABLE. A print-ready claim requires reviewed evidence and explicit approval; marked UNKNOWN is never PASS.

## 1. Approval and factual integrity
- [ ] Exact spelling, accents, capitalization, titles and requested naming conventions approved.
- [ ] Exact date, local time, time zone if relevant, venue/location, RSVP cutoff/method approved.
- [ ] No private information has been put into background art prompts or publicly indexed assets without approval.
- [ ] Language, script, bidi/RTL, correct glyph shaping and reading order inspected.
- [ ] Client confirms which side/page contains which copy and which proof version is final.

## 2. Visual integrity and accessibility
- [ ] Background contains no hallucinated/invented invitation text or signatures.
- [ ] Text exists as separate editable objects in a genuine editable deliverable (if requested).
- [ ] No crop/clipping or awkward seam in background/ornaments; sufficient negative space.
- [ ] Contrast measured against the actual final digital background: normal text ≥4.5:1; large text ≥3:1 (WCAG 2.2 SC 1.4.3 target).
- [ ] Size, leading, capitalization and script remain readable at actual digital/print scale; handwritten lettering not used for dense details.
- [ ] Meaningful alt text/plain-text invitation provided for digital distribution.

## 3. Printer-specific file acceptance
- [ ] Print provider + product documented; final trim W×H and orientation/side count confirmed.
- [ ] Required bleed b on every edge confirmed; full export W+2b by H+2b verified (adjust per uneven bleed if printer specifies).
- [ ] Safe inset s from trim confirmed; all live text/logos inside actual safe region.
- [ ] Output profile/required color mode (CMYK/spot/etc.) supplied by provider and verified in output.
- [ ] Effective placed-art PPI checked at final size. Target resolution comes from provider; 300 PPI is illustrative, not universal.
- [ ] Crop marks, registration, special finishes and export flavor (PDF/X etc.) included only when specified and verifiable.
- [ ] Actual font license, embedding rights and glyph rendering verified; no bundled unlicensed font binary.
- [ ] Real exported artifact inspected: dimensions, page count, text appearance, rendering artifacts, metadata and link/QR if present.
- [ ] 100% scale physical proof checked if obtainable, with printer and client approval.

## 4. Rights, traceability and tools
- [ ] Source and usage scope for each external element recorded; no competitor template cloned.
- [ ] External image generation/editing/upload permissions granted where necessary; tool and model/version logged if used.
- [ ] File paths/URLs refer to actual created files; no mocked outputs described as created.
- [ ] Human approval explicitly recorded before publication, sending, ordering, or print release.

## Status rule
- **BRIEF_ONLY**: no asset created; preflight plan only.
- **ART_ASSET_CREATED**: actual background generated/inspected; print-ready status not implied.
- **PROOF_CREATED**: actual editable or proof artifact exists but awaiting approval/checks.
- **PRINT_READY**: all applicable print gates pass against real artifacts and explicit client/printer approval; otherwise BLOCKED.

References: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html ; https://www.canva.com/help/margins-bleed-crop-marks/ ; https://www.canva.com/en_gb/help/proof-designs-print/ . Canva examples do not substitute for the selected print vendor's contract/specification.
