# Provider Implementations

This directory contains concrete implementations of the provider interfaces defined in `mil.kernel.providers`. The platform core has no compile-time dependency on any module here.

## Structure

```
providers/
├── ocr/        — OCRProvider implementations
├── extraction/ — ExtractionProvider implementations
├── inference/  — InferenceProvider implementations
├── policy/     — PolicyProvider implementations
├── storage/    — StorageProvider implementations
└── los/        — LOSAdapter implementations (one module per LOS platform)
```

## Registration

Implementations are registered in `mil.kernel.container` at application startup. The active implementation for each provider category is determined by deployment configuration — not by import statements in the domain code.

## Adding a new implementation

1. Create a module under the appropriate sub-package (e.g., `providers/ocr/my_ocr_backend.py`).
2. Implement the interface from `mil.kernel.providers`.
3. Ensure the implementation returns a version identifier on every method that produces AI output.
4. Run the conformance test suite: `pytest tests/providers/ -k <provider_name>`.
5. Register the implementation in `mil.kernel.container` under the appropriate deployment profile.

Do not register an implementation that has not passed its conformance tests.
