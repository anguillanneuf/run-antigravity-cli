# Specification: Workload Identity Federation Authentication for PR Review Engine

## Overview
Update the `run-antigravity-cli` GitHub Action and Python PR review engine (`src/review_engine.py` and `src/entrypoint.py`) to support Workload Identity Federation (WIF) and Application Default Credentials (ADC) for Google Cloud / Vertex AI authentication, alongside maintaining fallback support for Gemini API Keys.

## Objectives & Scope
- **Primary Goal**: Enable keyless, enterprise-grade authentication using GCP Workload Identity Federation (WIF) in GitHub Actions.
- **Fallback Strategy**: Prefer Workload Identity Federation / ADC when configured (`workload-identity-provider` & `service-account` inputs, or `GOOGLE_APPLICATION_CREDENTIALS` / ADC environment variables). If WIF is not configured or fails to initialize, fall back gracefully to `GEMINI_API_KEY`.
- **Inputs**: Update `action.yml` to define optional inputs for `workload-identity-provider` and `service-account`.

## Functional Requirements
1. **Action Inputs Update (`action.yml`)**:
   - Add `workload-identity-provider` (optional): The full GCP Workload Identity Provider resource name (e.g., `projects/123/locations/global/workloadIdentityPools/my-pool/providers/my-provider`).
   - Add `service-account` (optional): The GCP service account email to impersonate.
   - Forward new inputs as `INPUT_WORKLOAD_IDENTITY_PROVIDER` and `INPUT_SERVICE_ACCOUNT` environment variables to `src/entrypoint.py`.

2. **Orchestrator Entrypoint (`src/entrypoint.py`)**:
   - Parse `workload_identity_provider`, `service_account`, `gcp_project_id`, `gcp_location`, and `api_key` from environment variables.
   - Pass authentication settings to `AntigravityReviewEngine`.

3. **Review Engine Authentication & Settings (`src/review_engine.py`)**:
   - Update `AntigravityReviewEngine.__init__` to accept WIF parameters (`workload_identity_provider`, `service_account`, `gcp_project_id`, `gcp_location`).
   - In `ensure_settings_configured()`:
     - Update `~/.gemini/antigravity-cli/settings.json` non-destructively.
     - Configure WIF/ADC settings (`auth_mode`, `workload_identity_provider`, `service_account`, `gcp_project_id`, `gcp_location`).
     - Preserve `gemini_api_key` in `settings.json` if provided for fallback support.
     - Validate ADC / WIF credentials before leasing the Antigravity agent, falling back to API Key if ADC is unavailable.

## Non-Functional Requirements
- **Backwards Compatibility**: Maintain seamless backward compatibility for existing users who rely solely on `GEMINI_API_KEY`.
- **Security**: Prevent hardcoded credentials or leaking WIF tokens in logs.

## Acceptance Criteria
- [ ] `action.yml` defines `workload-identity-provider` and `service-account` inputs.
- [ ] `src/entrypoint.py` reads and passes WIF inputs to `AntigravityReviewEngine`.
- [ ] `src/review_engine.py` generates appropriate `settings.json` supporting WIF/ADC authentication mode with fallback to Gemini API Key.
- [ ] Unit test suite in `tests/test_review_engine.py` covers WIF configuration, ADC detection, fallback logic, and `settings.json` generation.
- [ ] All unit tests pass with >80% coverage.
