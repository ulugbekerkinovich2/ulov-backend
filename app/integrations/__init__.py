"""External service clients.

Each integration is a thin wrapper with:
  * typed request/response models (pydantic),
  * retry with exponential backoff via ``tenacity``,
  * a circuit-breaker (after N failures the module raises ``IntegrationDown``),
  * VCR-cassette based tests so CI never hits the real provider.

Added as phases progress:
    Phase 4  → s3 (MinIO / Amazon S3 / Yandex Object Storage)
    Phase 7  → eskiz, playmobile, payme, click, fcm
"""
