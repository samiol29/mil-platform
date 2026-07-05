"""InferenceProvider implementations. Interface: mil.kernel.providers.inference.InferenceProvider

Concrete providers:
  - GeminiInferenceProvider (Google Gemini AI Studio) — the first real provider.

Additional providers (Claude, OpenAI, Azure OpenAI, vLLM, Ollama) are added by
implementing ``InferenceProvider`` here and selecting them via
``Settings.inference_provider`` in ``mil.kernel.container`` — no business-logic
change (ARCHITECTURE.md §5/§6).
"""
