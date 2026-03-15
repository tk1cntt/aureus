//+------------------------------------------------------------------+
//|                                            AureusProvider.mq5     |
//|                    Aureus Data Provider — Multi-Symbol Streaming   |
//|                    Sends market data to Aureus Gateway via TCP     |
//+------------------------------------------------------------------+
#property copyright   "Aureus Project"
#property version     "2.00"
#property description "Streams M1 candles for multiple symbols and optional ticks for chart symbol"
#property strict

//--- Includes
#include "AureusSocketLib.mqh"

//+------------------------------------------------------------------+
//| Input Parameters                                                   |
//+------------------------------------------------------------------+
input string   InpGatewayHost        = "localhost";              // Gateway Host
input int      InpGatewayPort        = 5556;                     // Gateway TCP Port
input string   InpSymbols            = "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD";  // Symbols (comma-separated)
input bool     InpSendTicks          = true;                     // Send ticks (chart symbol only)
input bool     InpSendCandles        = true;                     // Send M1 Candles (all symbols)
input int      InpHeartbeatSec       = 5;                        // Heartbeat Interval (sec)
input bool     InpBackfillOnReconnect= false;                    // Auto-backfill on reconnect (Disabled by default, let Server dictate)
input int      InpMaxBackfillBars    = 300;                      // Max backfill candles on reconnect
input int      InpInitialBars        = 1440;                     // Initial backfill candles (24h @ M1)
input int      InpTimerMs            = 100;                      // Timer interval (ms)

//+------------------------------------------------------------------+
//| Per-Symbol State                                                   |
//+------------------------------------------------------------------+
struct SymbolContext
{
   string   symbol;
   datetime lastCandleTime;
   int      candlesSent;
   bool     initialBackfillDone;
};

//+------------------------------------------------------------------+
//| Global Variables                                                   |
//+------------------------------------------------------------------+
AureusSocket  g_socket;                // TCP socket
SymbolContext g_contexts[];             // Per-symbol state array
int           g_symbolCount;           // Number of configured symbols
long          g_lastTickMs;            // Last tick timestamp (ms) — for dedup (chart symbol)
int           g_ticksSent;             // Counter (chart symbol ticks)
bool          g_wasDisconnected;       // Track if we were disconnected
datetime      g_disconnectTime;        // When we lost connection

//+------------------------------------------------------------------+
//| Initialization                                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Parse InpSymbols
   string parts[];
   g_symbolCount = StringSplit(InpSymbols, ',', parts);

   if(g_symbolCount <= 0)
   {
      PrintFormat("[AureusProvider] ERROR: No symbols configured in InpSymbols!");
      return INIT_FAILED;
   }

   ArrayResize(g_contexts, g_symbolCount);

   for(int i = 0; i < g_symbolCount; i++)
   {
      string sym = parts[i];
      StringTrimLeft(sym);
      StringTrimRight(sym);
      g_contexts[i].symbol = sym;
      g_contexts[i].lastCandleTime = 0;
      g_contexts[i].candlesSent = 0;
      g_contexts[i].initialBackfillDone = false;

      // Ensure the symbol is in MarketWatch (needed for CopyRates on non-chart symbols)
      if(!SymbolSelect(g_contexts[i].symbol, true))
      {
         PrintFormat("[AureusProvider] WARNING: Could not select symbol %s in MarketWatch",
                     g_contexts[i].symbol);
      }
   }

   PrintFormat("[AureusProvider] Configured %d symbols: %s", g_symbolCount, InpSymbols);
   PrintFormat("[AureusProvider] Tick streaming: %s (chart symbol: %s)",
              InpSendTicks ? "ON" : "OFF", _Symbol);

   //--- Configure socket
   g_socket.SetHost(InpGatewayHost);
   g_socket.SetPort(InpGatewayPort);
   g_socket.SetReconnectDelay(3);
   g_socket.SetConnectTimeout(3000);
   g_socket.SetSendTimeout(1000);

   //--- Initialize state
   g_lastTickMs         = 0;
   g_ticksSent          = 0;
   g_wasDisconnected    = false;
   g_disconnectTime     = 0;

   //--- Attempt initial connection
   if(g_socket.Connect())
   {
      // PrintFormat("[AureusProvider] Connected to %s:%d", InpGatewayHost, InpGatewayPort);

      //--- Initialize last candle time for each symbol
      for(int i = 0; i < g_symbolCount; i++)
      {
         datetime barTimes[];
         if(CopyTime(g_contexts[i].symbol, PERIOD_M1, 0, 1, barTimes) > 0)
            g_contexts[i].lastCandleTime = barTimes[0];
      }

      PrintFormat("[AureusProvider] Passive mode enabled. Waiting for recovery commands.");
   }
   else
   {
      PrintFormat("[AureusProvider] Initial connection failed — will retry on timer");
      g_wasDisconnected = true;
      g_disconnectTime  = TimeCurrent();
   }

   //--- Start timer
   EventSetMillisecondTimer(InpTimerMs);

   //--- Chart comment
   Comment(StringFormat("Aureus Provider v2.0 [%d symbols → %s:%d]",
           g_symbolCount, InpGatewayHost, InpGatewayPort));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Deinitialization                                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   g_socket.Disconnect();

   int totalCandles = 0;
   for(int i = 0; i < g_symbolCount; i++)
      totalCandles += g_contexts[i].candlesSent;

   PrintFormat("[AureusProvider] Stopped. Ticks sent: %d, Candles sent: %d (across %d symbols)",
               g_ticksSent, totalCandles, g_symbolCount);
}

//+------------------------------------------------------------------+
//| Find context index for a symbol (-1 if not found)                 |
//+------------------------------------------------------------------+
int FindContextIndex(string symbol)
{
   for(int i = 0; i < g_symbolCount; i++)
   {
      if(g_contexts[i].symbol == symbol)
         return i;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Build Tick JSON                                                    |
//+------------------------------------------------------------------+
string BuildTickJSON(string symbol, const MqlTick &tick)
{
   long timeMs = tick.time_msc;

   return StringFormat(
      "{\"type\":\"TICK\",\"symbol\":\"%s\",\"t\":%lld,\"bid\":%.5f,\"ask\":%.5f,\"vol\":%.2f}",
      symbol, timeMs, tick.bid, tick.ask, tick.volume_real > 0 ? tick.volume_real : (double)tick.volume
   );
}

//+------------------------------------------------------------------+
//| Build Candle JSON                                                  |
//+------------------------------------------------------------------+
string BuildCandleJSON(string symbol, const MqlRates &rate, string timeframe)
{
   long timeMs = (long)rate.time * 1000;

   return StringFormat(
      "{\"type\":\"CANDLE\",\"symbol\":\"%s\",\"t\":%lld,\"o\":%.5f,\"h\":%.5f,\"l\":%.5f,\"c\":%.5f,\"v\":%.2f,\"tf\":\"%s\"}",
      symbol, timeMs, rate.open, rate.high, rate.low, rate.close,
      rate.real_volume > 0 ? (double)rate.real_volume : (double)rate.tick_volume,
      timeframe
   );
}

//+------------------------------------------------------------------+
//| Build Backfill JSON (array of candles)                            |
//+------------------------------------------------------------------+
string BuildBackfillJSON(string symbol, MqlRates &rates[], int count)
{
   string json = StringFormat("{\"type\":\"BACKFILL\",\"symbol\":\"%s\",\"candles\":[", symbol);

   for(int i = 0; i < count; i++)
   {
      if(i > 0) json += ",";
      long timeMs = (long)rates[i].time * 1000;
      json += StringFormat(
         "{\"t\":%lld,\"o\":%.5f,\"h\":%.5f,\"l\":%.5f,\"c\":%.5f,\"v\":%.2f,\"tf\":\"M1\"}",
         timeMs, rates[i].open, rates[i].high, rates[i].low, rates[i].close,
         rates[i].real_volume > 0 ? (double)rates[i].real_volume : (double)rates[i].tick_volume
      );
   }

   json += "]}";
   return json;
}

//+------------------------------------------------------------------+
//| Check and send new M1 candle for a specific symbol               |
//+------------------------------------------------------------------+
bool CheckAndSendCandleForSymbol(int ctxIndex)
{
   if(!InpSendCandles) return false;

   string sym = g_contexts[ctxIndex].symbol;

   // Get current and previous bar times
   datetime barTimes[];
   if(CopyTime(sym, PERIOD_M1, 0, 2, barTimes) < 2)
      return false;

   datetime currentBarTime = barTimes[1]; // newest bar
   datetime prevBarTime    = barTimes[0]; // previous bar

   // New candle detected?
   if(prevBarTime <= g_contexts[ctxIndex].lastCandleTime)
      return false;

   // The closed candle is the one at prevBarTime — get its OHLCV
   MqlRates rates[];
   if(CopyRates(sym, PERIOD_M1, 1, 1, rates) < 1)
      return false;

   string json = BuildCandleJSON(sym, rates[0], "M1");
   if(g_socket.SendJSON(json))
   {
      g_contexts[ctxIndex].lastCandleTime = prevBarTime;
      g_contexts[ctxIndex].candlesSent++;
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Initial backfill for a specific symbol                            |
//+------------------------------------------------------------------+
void DoInitialBackfillForSymbol(int ctxIndex)
{
   if(!InpSendCandles) return;

   string sym = g_contexts[ctxIndex].symbol;
   int totalBars = InpInitialBars;
   PrintFormat("[AureusProvider] [%s] Sending initial backfill: %d M1 candles", sym, totalBars);

   MqlRates allRates[];
   int copied = CopyRates(sym, PERIOD_M1, 1, totalBars, allRates);
   if(copied <= 0)
   {
      PrintFormat("[AureusProvider] [%s] Initial CopyRates failed: %d", sym, GetLastError());
      return;
   }

   // Send in chunks of 200
   int chunkSize = 200;
   int totalSent = 0;

   for(int start = 0; start < copied; start += chunkSize)
   {
      int end = MathMin(start + chunkSize, copied);
      int count = end - start;

      MqlRates chunk[];
      ArrayResize(chunk, count);
      for(int i = 0; i < count; i++)
         chunk[i] = allRates[start + i];

      string json = BuildBackfillJSON(sym, chunk, count);
      if(g_socket.SendJSON(json))
      {
         totalSent += count;
         PrintFormat("[AureusProvider] [%s] BACKFILL chunk %d-%d sent (%d candles)",
                     sym, start + 1, end, count);
      }
      else
      {
         // PrintFormat("[AureusProvider] [%s] BACKFILL chunk send failed at %d", sym, start);
         break;
      }

      Sleep(100);
   }

   if(totalSent > 0 && copied > 0)
   {
      g_contexts[ctxIndex].lastCandleTime = allRates[copied - 1].time;
      g_contexts[ctxIndex].candlesSent += totalSent;
      PrintFormat("[AureusProvider] [%s] Initial backfill complete: %d/%d candles (%s to %s)",
                  sym, totalSent, copied,
                  TimeToString(allRates[0].time),
                  TimeToString(allRates[copied - 1].time));
   }
}

//+------------------------------------------------------------------+
//| Perform backfill of missing candles (Range-based) for a symbol   |
//+------------------------------------------------------------------+
void DoBackfillForSymbol(int ctxIndex, datetime fromTime=0, datetime toTime=0)
{
   if(!InpSendCandles)
      return;

   string sym = g_contexts[ctxIndex].symbol;
   datetime start = fromTime;
   datetime end   = (toTime > 0) ? toTime : TimeCurrent();

   if(start == 0)
   {
      if(g_contexts[ctxIndex].lastCandleTime == 0)
      {
         PrintFormat("[AureusProvider] [%s] No lastCandleTime — skipping backfill", sym);
         return;
      }
      start = g_contexts[ctxIndex].lastCandleTime;
   }

   int missedSeconds = (int)(end - start);
   int missedBars = missedSeconds / 60;

   if(missedBars <= 0)
   {
      PrintFormat("[AureusProvider] [%s] No candle gap detected", sym);
      return;
   }

   if(toTime == 0 && missedBars > InpMaxBackfillBars)
   {
      PrintFormat("[AureusProvider] [%s] Gap too large (%d bars), limiting to %d",
                  sym, missedBars, InpMaxBackfillBars);
      missedBars = InpMaxBackfillBars;
      start = end - (missedBars * 60);
   }

   PrintFormat("[AureusProvider] [%s] Backfilling %d M1 bars from %s to %s",
               sym, missedBars, TimeToString(start), TimeToString(end));

   MqlRates rates[];
   // Use time bounds directly instead of iBarShift to force MT5 to download/sync history
   int copied = CopyRates(sym, PERIOD_M1, start, end, rates);
   if(copied <= 0)
   {
      PrintFormat("[AureusProvider] [%s] CopyRates by time failed: %d", sym, GetLastError());
      return;
   }

   // Filter to only candles strictly in range
   MqlRates filtered[];
   int filteredCount = 0;
   ArrayResize(filtered, copied);

   for(int i = 0; i < copied; i++)
   {
      if(rates[i].time > start && rates[i].time <= end)
      {
         filtered[filteredCount] = rates[i];
         filteredCount++;
       }
   }

   if(filteredCount == 0)
   {
      PrintFormat("[AureusProvider] [%s] No new candles to backfill in range", sym);
      return;
   }

   ArrayResize(filtered, filteredCount);

   // Send in chunks of 100
   int chunkSize = 100;
   for(int i = 0; i < filteredCount; i += chunkSize)
   {
      int cnt = MathMin(chunkSize, filteredCount - i);
      MqlRates chunk[];
      ArrayResize(chunk, cnt);
      for(int j = 0; j < cnt; j++) chunk[j] = filtered[i + j];

      string json = BuildBackfillJSON(sym, chunk, cnt);
      if(g_socket.SendJSON(json))
      {
         if(chunk[cnt-1].time > g_contexts[ctxIndex].lastCandleTime)
            g_contexts[ctxIndex].lastCandleTime = chunk[cnt-1].time;

         g_contexts[ctxIndex].candlesSent += cnt;
      }
      else
      {
         PrintFormat("[AureusProvider] [%s] Backfill chunk send failed", sym);
         break;
      }
   }

   PrintFormat("[AureusProvider] [%s] Targeted backfill complete: %d candles sent",
               sym, filteredCount);
}

//+------------------------------------------------------------------+
//| Perform backfill of missing candles (Count-based) for a symbol   |
//+------------------------------------------------------------------+
void DoBackfillCountForSymbol(int ctxIndex, int count)
{
   if(!InpSendCandles || count <= 0)
      return;

   string sym = g_contexts[ctxIndex].symbol;
   if(count > InpMaxBackfillBars) count = InpMaxBackfillBars;

   PrintFormat("[AureusProvider] [%s] Backfilling last %d M1 bars", sym, count);

   MqlRates rates[];
   int copied = CopyRates(sym, PERIOD_M1, 1, count, rates);
   if(copied <= 0)
   {
      PrintFormat("[AureusProvider] [%s] CopyRates failed for count backfill: %d", sym, GetLastError());
      return;
   }

   int chunkSize = 100;
   for(int i = 0; i < copied; i += chunkSize)
   {
      int currentCount = MathMin(chunkSize, copied - i);
      MqlRates chunk[];
      ArrayResize(chunk, currentCount);
      for(int j = 0; j < currentCount; j++) chunk[j] = rates[i + j];

      string json = BuildBackfillJSON(sym, chunk, currentCount);
      if(g_socket.SendJSON(json))
      {
         if(chunk[currentCount-1].time > g_contexts[ctxIndex].lastCandleTime)
            g_contexts[ctxIndex].lastCandleTime = chunk[currentCount-1].time;

         g_contexts[ctxIndex].candlesSent += currentCount;
      }
      else
      {
         PrintFormat("[AureusProvider] [%s] Count-based backfill chunk send failed", sym);
         break;
      }
   }

   PrintFormat("[AureusProvider] [%s] Count-based backfill complete: %d candles sent", sym, copied);
}

//+------------------------------------------------------------------+
//| Main tick handler — only sends ticks for chart symbol             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!InpSendTicks) return;

   //--- Ensure connection
   if(!g_socket.IsConnected())
   {
      if(!g_socket.EnsureConnected())
         return;
   }

   //--- Get latest tick for chart symbol
   MqlTick lastTick;
   if(!SymbolInfoTick(_Symbol, lastTick))
      return;

   //--- Dedup: skip if same timestamp as last tick
   if(lastTick.time_msc <= g_lastTickMs)
      return;

   //--- Build and send tick JSON
   string tickJSON = BuildTickJSON(_Symbol, lastTick);
   if(g_socket.SendJSON(tickJSON))
   {
      g_lastTickMs = lastTick.time_msc;
      g_ticksSent++;
   }
}

//+------------------------------------------------------------------+
//| Parse a simple JSON string field: "key":"value"                   |
//+------------------------------------------------------------------+
string ParseJSONString(const string &raw, const string key)
{
   string searchKey = "\"" + key + "\":\"";
   int pos = StringFind(raw, searchKey);
   if(pos < 0) return "";

   int startPos = pos + StringLen(searchKey);
   int endPos = StringFind(raw, "\"", startPos);
   if(endPos < 0) return "";

   return StringSubstr(raw, startPos, endPos - startPos);
}

//+------------------------------------------------------------------+
//| Listen and process commands from Gateway                           |
//+------------------------------------------------------------------+
void ProcessIncomingCommands()
{
   if(!g_socket.IsConnected())
      return;

   string raw = g_socket.Receive();
   if(raw == "") return;

   //--- Extract symbol from command
   string cmdSymbol = ParseJSONString(raw, "symbol");

   if(StringFind(raw, "REQUEST_BACKFILL_COUNT") >= 0)
   {
      int countPos = StringFind(raw, "\"count\":");
      if(countPos > 0)
      {
         long count = (long)StringToInteger(StringSubstr(raw, countPos + 8));

         // If symbol specified, backfill only that symbol
         if(cmdSymbol != "")
         {
            int idx = FindContextIndex(cmdSymbol);
            if(idx >= 0)
            {
               PrintFormat("[AureusProvider] [%s] Received REQUEST_BACKFILL_COUNT: %d candles",
                           cmdSymbol, count);
               DoBackfillCountForSymbol(idx, (int)count);
            }
            else
               PrintFormat("[AureusProvider] Unknown symbol in command: %s", cmdSymbol);
         }
         else
         {
            // No symbol specified → backfill all
            PrintFormat("[AureusProvider] Received REQUEST_BACKFILL_COUNT (all): %d candles", count);
            for(int i = 0; i < g_symbolCount; i++)
               DoBackfillCountForSymbol(i, (int)count);
         }
      }
      return;
   }

   if(StringFind(raw, "REQUEST_BACKFILL") >= 0)
   {
      int startPos = StringFind(raw, "\"start\":");
      int endPos   = StringFind(raw, "\"end\":");

      if(startPos > 0 && endPos > 0)
      {
         long startMs = (long)StringToInteger(StringSubstr(raw, startPos + 8));
         long endMs   = (long)StringToInteger(StringSubstr(raw, endPos + 6));

         datetime fromTime = (datetime)(startMs / 1000);
         datetime toTime   = (datetime)(endMs / 1000);

         if(cmdSymbol != "")
         {
            int idx = FindContextIndex(cmdSymbol);
            if(idx >= 0)
            {
               PrintFormat("[AureusProvider] [%s] Received REQUEST_BACKFILL range: %s - %s",
                           cmdSymbol, TimeToString(fromTime), TimeToString(toTime));
               DoBackfillForSymbol(idx, fromTime, toTime);
            }
            else
               PrintFormat("[AureusProvider] Unknown symbol in command: %s", cmdSymbol);
         }
         else
         {
            // No symbol specified → backfill all
            PrintFormat("[AureusProvider] Received REQUEST_BACKFILL (all): %s - %s",
                        TimeToString(fromTime), TimeToString(toTime));
            for(int i = 0; i < g_symbolCount; i++)
               DoBackfillForSymbol(i, fromTime, toTime);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Timer event — candle polling, heartbeat, and status               |
//+------------------------------------------------------------------+
void OnTimer()
{
   //--- Process commands from Gateway
   ProcessIncomingCommands();

   //--- Connection health check
   if(!g_socket.IsConnected())
   {
      if(!g_wasDisconnected)
      {
         g_wasDisconnected = true;
         g_disconnectTime  = TimeCurrent();
      }

      if(g_socket.EnsureConnected())
      {
         // PrintFormat("[AureusProvider] Timer: Reconnected — waiting for Server gap detection commands");
         g_wasDisconnected = false;
         g_disconnectTime  = 0;
      }
      else
      {
         int downSec = (g_disconnectTime > 0) ? (int)(TimeCurrent() - g_disconnectTime) : 0;
         if(downSec % 10 == 0) // Log every ~10 seconds
            PrintFormat("[AureusProvider] Timer: Still disconnected (%d sec)", downSec);
      }
      return;
   }

   //--- Poll candles for ALL symbols
   for(int i = 0; i < g_symbolCount; i++)
   {
      CheckAndSendCandleForSymbol(i);
   }

   //--- Status comment on chart
   string statusLines = "Aureus Provider v2.0\n";
   statusLines += StringFormat("Gateway: %s:%d | Status: CONNECTED\n",
                               InpGatewayHost, InpGatewayPort);
   statusLines += StringFormat("Ticks Sent: %d (chart: %s, %s)\n",
                               g_ticksSent, _Symbol, InpSendTicks ? "ON" : "OFF");
   statusLines += "─── Symbol Candles ───\n";

   for(int i = 0; i < g_symbolCount; i++)
   {
      statusLines += StringFormat("%s: %d candles | Last: %s\n",
                                  g_contexts[i].symbol,
                                  g_contexts[i].candlesSent,
                                  g_contexts[i].lastCandleTime > 0
                                     ? TimeToString(g_contexts[i].lastCandleTime)
                                     : "N/A");
   }

   Comment(statusLines);
}
//+------------------------------------------------------------------+
