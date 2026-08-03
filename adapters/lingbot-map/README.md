# Governed LingBot-Map adapter

The adapter is pinned to source commit `1f480aeb8a47a24656090d46d053115b7fe60435`. The repository contains no model weights. Configure a local checkpoint with its exact hash, source, input/output terms, supported purposes, and quality profile before enabling this worker. Runtime admission remains server-side and fail-closed when that technical record is missing or does not match.

The deterministic CPU reconstruction lane remains available without this adapter. Source acquisition requires an explicit environment gate and writes per-file hashes. The container entry point cannot perform inference directly; the SIP worker must first authorize a signed model manifest and then use an approved derivative image.
