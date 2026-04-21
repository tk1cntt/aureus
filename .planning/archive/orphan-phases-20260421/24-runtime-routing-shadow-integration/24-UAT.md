---
status: testing
phase: 24-runtime-routing-shadow-integration
source: [24-01-SUMMARY.md]
started: 2026-04-04T13:10:00Z
updated: 2026-04-04T13:10:00Z
---

## Current Test
number: 1
name: Cold Start Smoke Test
expected: |
  Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, any seed/migration completes, and a primary query (health check, homepage load, or basic API call) returns live data.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Clear ephemeral state (temp DBs, caches, lock files). Start the application from scratch. Server boots without errors, any seed/migration completes, and a primary query (health check, homepage load, or basic API call) returns live data.
result: pending

### 2. Provider Mode Configuration
expected: Change provider_mode toggle to ta_primary and ta_shadow while live_engine.py is running, then verify logs show routing changing dynamically without reboot.
result: pending

### 3. Background Analysis Telemetry Logging
expected: With provider_mode set to ta_shadow, check Redis aureus:ai:shadow:{symbol} keys and ensure new AI decisions populate within 1 block length.
result: pending

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
