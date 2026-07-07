/**
 * Shared class string for collapsible-group-header buttons (Product
 * Experience phase, Phase 10 audit) — `UploadSection.tsx` and
 * `ApplicationWorkspace.tsx`'s `EvidenceRegion` each had their own
 * copy-pasted version of this button, and all three were missing
 * `focus-visible` treatment (evidently copied before that utility was
 * added elsewhere). One shared constant instead of three independent
 * copies, so they can't drift out of sync again.
 */
export const COLLAPSIBLE_GROUP_HEADER_CLASS =
  'bg-surface-secondary text-label text-text-secondary flex w-full items-center gap-1.5 px-3 py-2 font-medium outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2';
