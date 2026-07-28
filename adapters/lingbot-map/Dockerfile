# syntax=docker/dockerfile:1.7
# Source-only build boundary. A checkpoint is never copied by this image.
FROM python:3.10.19-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e AS source
ARG LINGBOT_SOURCE_REVISION=1f480aeb8a47a24656090d46d053115b7fe60435
RUN test "$LINGBOT_SOURCE_REVISION" = "1f480aeb8a47a24656090d46d053115b7fe60435"
COPY vendor/lingbot-map/ /opt/lingbot-map/
RUN test -f /opt/lingbot-map/LICENSE.txt \
 && test "$(cat /opt/lingbot-map/.sip-source-revision)" = "$LINGBOT_SOURCE_REVISION"

FROM python:3.10.19-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e
RUN useradd --system --uid 10001 --create-home lingbot
COPY --from=source --chown=lingbot:lingbot /opt/lingbot-map /opt/lingbot-map
USER 10001:10001
WORKDIR /opt/lingbot-map
ENV SIP_MODEL_APPROVAL_REQUIRED=true SIP_MODEL_CHECKPOINT_PATH=""
ENTRYPOINT ["python", "-c", "raise SystemExit('MODEL_EXECUTION_DENIED: inject an approved signed model manifest through the SIP worker, never directly')"]
