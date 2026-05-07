---
quick_id: 260508-8tn
status: completed
completed_at: 2026-05-07
mode: quick-validate
---

# Quick Task 260508-8tn Summary

## Task

Đọc `mql5/OpenAlgo.mq5`, hiểu cách tích hợp OpenAlgo, tích hợp OpenAlgo vào `mql5/AureusProvider_v2.mq5`, rồi build theo `mql5/Build_Rules.md`.

## OpenAlgo Pattern Read

`mql5/OpenAlgo.mq5` uses:

```mql5
#include OpenAlgo/OpenAlgoApi.mqh
```

Core order API:

```mql5
PlaceOrder("BUY", Quantity, ApiUrl, ApiKey, Strategy, Symbol, Exchange, Product, PriceType);
PlaceOrder("SELL", Quantity, ApiUrl, ApiKey, Strategy, Symbol, Exchange, Product, PriceType);
```

`OpenAlgoApi.mqh` implements `/api/v1/placeorder` with fields:

- `apikey`
- `strategy`
- `symbol`
- `action`
- `exchange`
- `pricetype`
- `product`
- `quantity`
- optional `price`
- optional `trigger_price`

Important: stock `PlaceOrder(...)` returns `void`, so caller cannot know API success/failure.

## Changes

File changed:

- `mql5/AureusProvider_v2.mq5`

Added include:

```mql5
#include <OpenAlgo/OpenAlgoApi.mqh>
```

Added inputs:

```mql5
input bool     InpUseOpenAlgoBridge  = false;
input string   InpOpenAlgoApiUrl     = "http://127.0.0.1:5000";
input string   InpOpenAlgoApiKey     = "your_app_apikey";
input string   InpOpenAlgoStrategy   = "AureusProvider_v2";
input string   InpOpenAlgoSymbol     = "";
input Exchanges InpOpenAlgoExchange  = NSE;
input ProductTypes InpOpenAlgoProduct = MIS;
```

Default remains `InpUseOpenAlgoBridge=false`, so current native MT5 execution path stays default.

Added helpers:

- `MapOpenAlgoPriceType(...)`
- `SendOpenAlgoOrder(...)`
- `TryExecuteOpenAlgoOrder(...)`

## OPEN_ORDER Mapping

| Aureus field | OpenAlgo field |
|---|---|
| `direction` | `action` (`BUY`/`SELL`) |
| `volume` | `quantity` via `MathRound(volume)`, min `1` |
| `symbol` | OpenAlgo `symbol`, unless `InpOpenAlgoSymbol` override set |
| `comment`/strategy name | OpenAlgo `strategy`, fallback `InpOpenAlgoStrategy` |
| `order_type=MARKET` | `pricetype=MARKET` |
| `order_type=LIMIT` | `pricetype=LIMIT`, `price=entry price` |
| `order_type=STOP` | `pricetype=SL-M`, `trigger_price=entry price` |

Unsupported/invalid types emit failure and do not fall through into native MT5 bridge mode.

## Success/Failure Contract

Did not use stock `PlaceOrder(...)` directly because it returns `void`.

Instead, `SendOpenAlgoOrder(...)` builds same request shape and calls:

```mql5
WebReqWithRetry(req, res, "AureusOpenAlgoPlaceOrder")
```

It returns `true` only when HTTP status is 2xx. On failure, provider emits:

```mql5
ORDER_FAILED reason=OPENALGO_PLACEORDER_FAILED
```

`ORDER_OPENED` is emitted only after OpenAlgo request success.

## Integration Point

OpenAlgo branch runs after command validation/idempotency/pre-ACK rejects and before native MT5 ACK/order side effects:

```mql5
if(InpUseOpenAlgoBridge)
  {
   TryExecuteOpenAlgoOrder(...);
   return;
  }
```

When disabled, native MT5 path remains unchanged.

## GitNexus Impact

Command:

```text
npx gitnexus impact ExecuteOpenOrder --repo Aureus --direction upstream
```

Result:

```text
Target 'ExecuteOpenOrder' not found
```

MQL5 symbols are not indexed as function nodes in current GitNexus graph. Manual blast radius:

- Directly affects `OPEN_ORDER` handling in `AureusProvider_v2.mq5` only when `InpUseOpenAlgoBridge=true`.
- Default disabled path preserves current MT5 behavior.
- New include depends on existing `mql5/OpenAlgo/*` files.

## Build

Build command per `mql5/Build_Rules.md` attempted:

```text
cmd /c ""E:\Openclaw\MetaTrader5\MetaEditor64.exe" /compile:"D:\Aureus\mql5\AureusProvider_v2.mq5" /log:"D:\Aureus\mql5\AureusProvider_v2_compile.log""
```

Shell returned quoting error:

```text
'ompile:D:Aureusmql5AureusProvider_v2.mq5' is not recognized as an internal or external command
```

However, MetaEditor still produced `mql5/AureusProvider_v2_compile.log` with result:

```text
Result: 0 errors, 0 warnings, 1565 msec elapsed, cpu='X64 Regular'
```

## Result

OpenAlgo is integrated as an opt-in bridge. Native MT5 execution remains default. Build log reports 0 errors and 0 warnings.
