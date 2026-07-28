# Governed LingBot-Map adapter

The adapter is pinned to source commit `1f480aeb8a47a24656090d46d053115b7fe60435`. Source-code approval is not checkpoint, dataset, output-rights, privacy, or commercial approval. The repository contains no model weights. Runtime authorization is server-side and fail-closed; the current checkpoint manifest is explicitly denied.

The deterministic CPU reconstruction lane remains available without this adapter. Source acquisition requires an explicit environment gate and writes per-file hashes. The container entry point cannot perform inference directly; the SIP worker must first authorize a signed model manifest and then use an approved derivative image.
