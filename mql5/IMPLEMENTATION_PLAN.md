# MT5 Data Provider — Implementation Plan

## Problem

Phase 1 hiện chỉ có **receiver side** (aureus-gateway). Cần bổ sung **sender side** — MQL5 Indicator chạy trên MT5 gửi tick/candle real-time.

### Yêu cầu:
1. **Tick-by-tick streaming** — đọc `SymbolInfoTick()` và gửi JSON
2. **Latency < 100ms** — từ MT5 đến hệ thống Aureus
3. **Missing Candle Detection** — phát hiện candle bị thiếu khi mất mạng
4. **Auto-Backfill** — khi reconnect, tự động gửi bù dữ liệu thiếu

---

## Architecture Decision: Native TCP Sockets

> **Không dùng ZMQ DLL** — quá phức tạp, cần cài đặt thêm thư viện bên ngoài.
> **Dùng MQL5 native TCP sockets** (`SocketCreate`, `SocketConnect`, `SocketSend`) — zero dependencies.

Gateway sẽ được update thêm **TCP listener** song song với ZMQ, nhận JSON thuần qua TCP (newline-delimited).

```
MT5 Indicator ──[TCP raw JSON]──> Gateway TCP Listener ──> Redis ──> DB
                                  Gateway ZMQ Listener ──> Redis ──> DB  (giữ nguyên cho test)
```

---

## Files

| File | Mô tả |
|:---|:---|
| `mql5/AureusProvider.mq5` | Indicator chính — tick streaming + candle + backfill |
| `mql5/AureusSocketLib.mqh` | TCP socket helper (connect, send JSON, reconnect) |
| `services/aureus-gateway/main.py` | Update: thêm TCP listener + BACKFILL handler |
| `phase-1/test_mt5_provider.py` | Test suite: latency, integrity, backfill, reconnect |

---

## Message Formats

**Tick:** `{"type":"TICK","symbol":"XAUUSD","t":1708300000000,"bid":2000.50,"ask":2000.60,"vol":10.0}\n`

**Candle:** `{"type":"CANDLE","symbol":"XAUUSD","t":1708300000000,"o":2000.0,"h":2005.0,"l":1999.0,"c":2002.0,"v":100.0,"tf":"M1"}\n`

**Backfill:** `{"type":"BACKFILL","symbol":"XAUUSD","candles":[{...},{...}]}\n`

---

## Compile

```
MetaEditor64.exe /compile:"E:\Openclaw\aureus\workspace\aureus\mql5\AureusProvider.mq5" /log:"E:\Openclaw\aureus\workspace\aureus\mql5\compile.log"
```
