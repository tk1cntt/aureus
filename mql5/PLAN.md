# EA Backfill Capability Plan

Enable the EA to receive and process range-based backfill requests from the Gateway.

## Proposed Changes
1. **AureusSocketLib.mqh**:
   - Add `SocketIsReadable()` check.
   - Add `Receive(string &out_data)` method for non-blocking reads.
2. **AureusProvider.mq5**:
   - Add `ProcessIncomingCommands()` to check for messages from Gateway.
   - Implement `HandleRequestBackfill(string json)` to parse and trigger data fetch.
   - Refactor `DoBackfill(datetime from, datetime to)` to fetch specific ranges.

## Verification
- Connect EA to a mock TCP server sending `REQUEST_BACKFILL` JSON.
- Verify EA logs show the request and subsequent data transmission.
