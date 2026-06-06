# ⚠️ SUPERSEDED — Legacy QMS tree

**As of 2026-06-05, this `qms/` folder is retired as a controlled-document source.**

The single source of truth for GHI controlled QMS / NQA-1 / AI / engineering / compliance
documents — all Dragon Seal–attested — is now:

```
~/Documents/AutoQMS_Platform/QMS_Controlled_Documents/
```

That canonical set (QMS-000→012, AI-001→007 + AI-007-A, NQA-001→018, ENG-001→003,
CMP-001→004, FORM-001, and the AIIA records under `Records_AIIA/`) is what the AutoQMS app
reads for the Document Library and Dragon Seal Signing.

## Why this folder was retired
It used an **older, conflicting numbering scheme** — e.g. `QMS-001` here was a *Scope Statement*,
while the canonical `QMS-001` is the *Quality Manual*; the `AIMS-0xx` series was replaced by
`AI-0xx`. Keeping both as live sources produced collisions an auditor would flag.

## Status
- **Not deleted** — retained for history/reference only.
- The app no longer treats this tree as a controlled-document root (see
  `autoqms-app/services.py::controlled_doc_roots`). It is a fallback only if the canonical
  folder is missing.
- Do **not** add new controlled documents here. Add them to the canonical folder and seal with
  `dragon_seal.py`.

## If you want these in version control
Sync the canonical set into the repo deliberately (e.g. copy
`~/Documents/AutoQMS_Platform/QMS_Controlled_Documents/` → a new `qms_controlled/` tracked
folder) rather than editing this legacy tree.
