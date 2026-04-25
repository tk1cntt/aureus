//+------------------------------------------------------------------+
//|                                            AureusProvider.mq5     |
//|                    Aureus Data Provider — Multi-Symbol Streaming   |
//|                    Streams market data + receives order commands   |
//+------------------------------------------------------------------+
#property copyright   "Aureus Project"
#property version     "3.00"
#property description "Bidirectional: streams M1 candles/ticks + executes order commands from gateway"
#property strict

//--- Includes
#include "AureusSocketLib.mqh"

//+------------------------------------------------------------------+
//| Input Parameters                                                   |
//+------------------------------------------------------------------+
input string   InpGatewayHost        = "localhost";              // Gateway Host
input int      InpGatewayPort        = 5556;                     // Gateway TCP Port
input string   InpSymbols            = "XAUUSD,BTCUSD,ETHUSD,USTEC,USDJPY,EURUSD,GBPUSD,AUDUSD";  // Symbols (comma-separated)
input bool     InpSendTicks          = false;                    // Send ticks (chart symbol only)
input bool     InpSendCandles        = true;                     // Send M1 Candles (all symbols)
input int      InpHeartbeatSec       = 5;                        // Heartbeat Interval (sec)
input bool     InpBackfillOnReconnect= false;                    // Auto-backfill on reconnect (Disabled by default, let Server dictate)
input int      InpMaxBackfillBars    = 300;                      // Max backfill candles on reconnect
input int      InpInitialBars        = 1440;                     // Initial backfill candles (24h @ M1)
input int      InpTimerMs            = 100;                      // Timer interval (ms)
input int      InpMaxSlippage        = 20;                       // Max slippage for market orders (points)
input int      InpMaxCmdIdHistory    = 500;                      // Max command ID history for dedup
input double   InpRiskFixedAmountBudget = 50.0;                  // Default budget for RISK_FIXED_AMOUNT mode ($)
input bool     InpDebugMode          = false;
//+------------------------------------------------------------------+
//| Per-Symbol State                                                   |
//+------------------------------------------------------------------+
struct SymbolContext
  {
   string            symbol;
   datetime          lastCandleTime;
   int               candlesSent;
   bool              initialBackfillDone;
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

// Command dedup
string        g_processedCmdIds[];     // Dedup: processed command IDs
int           g_cmdIdCount;            // Count of stored cmd IDs

// Order execution stats
int           g_ordersExecuted;        // Successful order count
int           g_ordersFailed;          // Failed order count

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
      if(InpDebugMode)
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
         if(InpDebugMode)
            PrintFormat("[AureusProvider] WARNING: Could not select symbol %s in MarketWatch",
                        g_contexts[i].symbol);
        }
     }

   if(InpDebugMode)
      PrintFormat("[AureusProvider] Configured %d symbols: %s", g_symbolCount, InpSymbols);
   if(InpDebugMode)
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

//--- Initialize command dedup
   ArrayResize(g_processedCmdIds, InpMaxCmdIdHistory);
   g_cmdIdCount = 0;

//--- Initialize order stats
   g_ordersExecuted = 0;
   g_ordersFailed   = 0;

//--- Attempt initial connection
   if(g_socket.Connect())
     {
      // if(InpDebugMode) PrintFormat("[AureusProvider] Connected to %s:%d", InpGatewayHost, InpGatewayPort);

      //--- Initialize last candle time for each symbol
      for(int i = 0; i < g_symbolCount; i++)
        {
         datetime barTimes[];
         if(CopyTime(g_contexts[i].symbol, PERIOD_M1, 0, 1, barTimes) > 0)
            g_contexts[i].lastCandleTime = barTimes[0];
        }

      if(InpDebugMode)
         PrintFormat("[AureusProvider] Passive mode enabled. Waiting for recovery commands.");
     }
   else
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Initial connection failed — will retry on timer");
      g_wasDisconnected = true;
      g_disconnectTime  = TimeCurrent();
     }

//--- Start timer
   EventSetMillisecondTimer(InpTimerMs);

//--- Chart comment
   Comment(StringFormat("Aureus Provider v3.0 [%d symbols â†’ %s:%d]",
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

   if(InpDebugMode)
      PrintFormat("[AureusProvider] Stopped. Ticks: %d, Candles: %d, Orders: %d executed/%d failed",
                  g_ticksSent, totalCandles, g_ordersExecuted, g_ordersFailed);
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
      if(i > 0)
         json += ",";
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
//| Build TRADE_HISTORY JSON (array of closed trades)                 |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Build JSON with all open positions                                 |
//+------------------------------------------------------------------+
string BuildPositionsJSON()
  {
   string json = "{\"type\":\"POSITION_REPORT\",\"positions\":[";
   int total = PositionsTotal();
   bool first = true;
   double totalProfit = 0.0;

   for(int i = 0; i < total; i++)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long magic = PositionGetInteger(POSITION_MAGIC);
      long posType = PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      double profit = PositionGetDouble(POSITION_PROFIT);
      double swap = PositionGetDouble(POSITION_SWAP);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
      string direction = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";

      // Calculate pips based on symbol digits
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double pipSize = (digits == 3 || digits == 5) ? point * 10 : point;
      double pips = 0.0;
      if(pipSize > 0)
         pips = (direction == "BUY")
                ? (currentPrice - openPrice) / pipSize
                : (openPrice - currentPrice) / pipSize;

      totalProfit += profit + swap;

      if(!first)
         json += ",";
      first = false;

      json += StringFormat(
                 "{\"ticket\":%lld,\"symbol\":\"%s\",\"magic\":%lld,"
                 "\"direction\":\"%s\",\"volume\":%.2f,\"open_price\":%.5f,"
                 "\"current_price\":%.5f,\"profit\":%.2f,\"swap\":%.2f,"
                 "\"sl\":%.5f,\"tp\":%.5f,\"pips\":%.1f,\"open_time\":%lld}",
                 ticket, symbol, magic, direction, volume, openPrice,
                 currentPrice, profit, swap, sl, tp, pips, (long)openTime * 1000);
     }

   json += StringFormat("],\"total\":%d,\"total_profit\":%.2f,\"t\":%lld}",
                        total, totalProfit, (long)TimeCurrent() * 1000);
   return json;
  }

//+------------------------------------------------------------------+
//| Execute REQUEST_POSITIONS command                                   |
//+------------------------------------------------------------------+
void ExecutePositionsRequest()
  {
   string json = BuildPositionsJSON();
   if(g_socket.SendJSON(json))
      if(InpDebugMode)
         PrintFormat("[AureusProvider] POSITION_REPORT sent: %d positions", PositionsTotal());
      else
         if(InpDebugMode)
            PrintFormat("[AureusProvider] ERROR: Failed to send POSITION_REPORT");
  }

//+------------------------------------------------------------------+
//| Build JSON with trade history (closed deals)                       |
//+------------------------------------------------------------------+
string BuildTradeHistoryJSON(datetime fromTime, datetime toTime, long filterMagic=0, string filterSymbol="")
  {
   if(!HistorySelect(fromTime, toTime))
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] HistorySelect failed: %d", GetLastError());
      return "{\"type\":\"TRADE_HISTORY\",\"trades\":[],\"error\":\"HistorySelect failed\"}";
     }

   int totalDeals = HistoryDealsTotal();
   string json = "{\"type\":\"TRADE_HISTORY\",\"trades\":[";
   bool first = true;
   int count = 0;

   for(int i = 0; i < totalDeals; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;

      // Only position close deals
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT)
         continue;

      // Filter by magic number if specified
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(filterMagic > 0 && magic != filterMagic)
         continue;

      // Filter by symbol if specified
      string sym = HistoryDealGetString(ticket, DEAL_SYMBOL);
      if(filterSymbol != "" && sym != filterSymbol)
         continue;

      // Skip manual trades
      if(magic == 0)
         continue;

      long   posTicket   = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
      double volume      = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      double closePrice  = HistoryDealGetDouble(ticket, DEAL_PRICE);
      double profit      = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double commission  = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      double swap        = HistoryDealGetDouble(ticket, DEAL_SWAP);
      long   dealType    = HistoryDealGetInteger(ticket, DEAL_TYPE);
      datetime openTime  = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      datetime closeTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      string direction   = (dealType == DEAL_TYPE_BUY) ? "BUY" : "SELL";

      // Try to get open price from history order
      double openPrice = 0.0;
      double sl = 0.0;
      double tp = 0.0;
      if(HistoryOrderSelect(posTicket))
        {
         openPrice = HistoryOrderGetDouble(posTicket, ORDER_PRICE_OPEN);
         sl = HistoryOrderGetDouble(posTicket, ORDER_SL);
         tp = HistoryOrderGetDouble(posTicket, ORDER_TP);
        }

      if(!first)
         json += ",";
      first = false;
      count++;

      // Build trade JSON object — use milliseconds for timestamps
      long openTimeMs = (long)openTime * 1000;
      long closeTimeMs = (long)closeTime * 1000;

      long digits = SymbolInfoInteger(sym, SYMBOL_DIGITS);
      double mult = (digits == 3 || digits == 5) ? MathPow(10, digits - 1) : MathPow(10, digits);
      double pips = (closePrice - openPrice) * mult;
      // dealType == DEAL_TYPE_BUY means the closing deal is a BUY -> original position was SELL
      if(dealType == DEAL_TYPE_BUY)
         pips = -pips;

      json += StringFormat(
                 "{\"ticket\":%lld,\"symbol\":\"%s\",\"magic_number\":%lld,"
                 "\"direction\":\"%s\",\"entry_price\":%.5f,\"exit_price\":%.5f,"
                 "\"sl\":%.5f,\"tp\":%.5f,\"volume\":%.2f,\"commission\":%.2f,"
                 "\"swap\":%.2f,\"profit\":%.2f,\"open_time\":%lld,\"close_time\":%lld,"
                 "\"digits\":%lld,\"pips\":%.1f}",
                 posTicket, sym, magic, direction, openPrice, closePrice,
                 sl, tp, volume, commission, swap, profit, openTimeMs, closeTimeMs,
                 digits, pips
              );
     }

   json += StringFormat("],\"count\":%d,\"from_time\":%lld,\"to_time\":%lld}", count, (long)fromTime * 1000, (long)toTime * 1000);
   return json;
  }


//+------------------------------------------------------------------+
//| Check and send new M1 candle for a specific symbol               |
//+------------------------------------------------------------------+
bool CheckAndSendCandleForSymbol(int ctxIndex)
  {
   if(!InpSendCandles)
      return false;

   string sym = g_contexts[ctxIndex].symbol;

// Get current and previous bar times
   datetime barTimes[];
   if(CopyTime(sym, PERIOD_M1, 0, 2, barTimes) < 2)
      return false;

   datetime prevBarTime    = barTimes[0]; // previous closed bar

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
   if(!InpSendCandles)
      return;

   string sym = g_contexts[ctxIndex].symbol;
   int totalBars = InpInitialBars;
   if(InpDebugMode)
      PrintFormat("[AureusProvider] [%s] Sending initial backfill: %d M1 candles", sym, totalBars);

   MqlRates allRates[];
   int copied = CopyRates(sym, PERIOD_M1, 1, totalBars, allRates);
   if(copied <= 0)
     {
      if(InpDebugMode)
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
         if(InpDebugMode)
            PrintFormat("[AureusProvider] [%s] BACKFILL chunk %d-%d sent (%d candles)",
                        sym, start + 1, end, count);
        }
      else
        {
         // if(InpDebugMode) PrintFormat("[AureusProvider] [%s] BACKFILL chunk send failed at %d", sym, start);
         break;
        }

      Sleep(100);
     }

   if(totalSent > 0 && copied > 0)
     {
      g_contexts[ctxIndex].lastCandleTime = allRates[copied - 1].time;
      g_contexts[ctxIndex].candlesSent += totalSent;
      if(InpDebugMode)
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
         if(InpDebugMode)
            PrintFormat("[AureusProvider] [%s] No lastCandleTime — skipping backfill", sym);
         return;
        }
      start = g_contexts[ctxIndex].lastCandleTime;
     }

   int missedSeconds = (int)(end - start);
   int missedBars = missedSeconds / 60;

   if(missedBars <= 0)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] [%s] No candle gap detected", sym);
      return;
     }

   if(toTime == 0 && missedBars > InpMaxBackfillBars)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] [%s] Gap too large (%d bars), limiting to %d",
                     sym, missedBars, InpMaxBackfillBars);
      missedBars = InpMaxBackfillBars;
      start = end - (missedBars * 60);
     }

   if(InpDebugMode)
      PrintFormat("[AureusProvider] [%s] Backfilling %d M1 bars from %s to %s",
                  sym, missedBars, TimeToString(start), TimeToString(end));

   MqlRates rates[];
// Use time bounds directly instead of iBarShift to force MT5 to download/sync history
   int copied = CopyRates(sym, PERIOD_M1, start, end, rates);
   if(copied <= 0)
     {
      if(InpDebugMode)
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
      if(InpDebugMode)
         PrintFormat("[AureusProvider] [%s] No new candles to backfill in range", sym);
      return;
     }

   ArrayResize(filtered, filteredCount);

// Send in chunks of 100
   int chunkSize = 100;
   int sentCount = 0;
   for(int i = 0; i < filteredCount; i += chunkSize)
     {
      int cnt = MathMin(chunkSize, filteredCount - i);
      MqlRates chunk[];
      ArrayResize(chunk, cnt);
      for(int j = 0; j < cnt; j++)
         chunk[j] = filtered[i + j];

      string json = BuildBackfillJSON(sym, chunk, cnt);
      if(g_socket.SendJSON(json))
        {
         if(chunk[cnt-1].time > g_contexts[ctxIndex].lastCandleTime)
            g_contexts[ctxIndex].lastCandleTime = chunk[cnt-1].time;

         g_contexts[ctxIndex].candlesSent += cnt;
         sentCount += cnt;
        }
      else
        {
         if(InpDebugMode)
            PrintFormat("[AureusProvider] [%s] Backfill chunk send failed after %d/%d candles",
                        sym, sentCount, filteredCount);
         break;
        }
     }

   if(InpDebugMode)
      PrintFormat("[AureusProvider] [%s] Targeted backfill finished: %d/%d candles sent",
                  sym, sentCount, filteredCount);
  }

//+------------------------------------------------------------------+
//| Perform backfill of missing candles (Count-based) for a symbol   |
//+------------------------------------------------------------------+
void DoBackfillCountForSymbol(int ctxIndex, int count)
  {
   if(!InpSendCandles || count <= 0)
      return;

   string sym = g_contexts[ctxIndex].symbol;
   if(count > InpMaxBackfillBars)
      count = InpMaxBackfillBars;

   if(InpDebugMode)
      PrintFormat("[AureusProvider] [%s] Backfilling last %d M1 bars", sym, count);

   MqlRates rates[];
   int copied = CopyRates(sym, PERIOD_M1, 1, count, rates);
   if(copied <= 0)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] [%s] CopyRates failed for count backfill: %d", sym, GetLastError());
      return;
     }

   int chunkSize = 100;
   int sentCount = 0;
   for(int i = 0; i < copied; i += chunkSize)
     {
      int currentCount = MathMin(chunkSize, copied - i);
      MqlRates chunk[];
      ArrayResize(chunk, currentCount);
      for(int j = 0; j < currentCount; j++)
         chunk[j] = rates[i + j];

      string json = BuildBackfillJSON(sym, chunk, currentCount);
      if(g_socket.SendJSON(json))
        {
         if(chunk[currentCount-1].time > g_contexts[ctxIndex].lastCandleTime)
            g_contexts[ctxIndex].lastCandleTime = chunk[currentCount-1].time;

         g_contexts[ctxIndex].candlesSent += currentCount;
         sentCount += currentCount;
        }
      else
        {
         if(InpDebugMode)
            PrintFormat("[AureusProvider] [%s] Count-based backfill chunk send failed after %d/%d candles",
                        sym, sentCount, copied);
         break;
        }
     }

   if(InpDebugMode)
      PrintFormat("[AureusProvider] [%s] Count-based backfill finished: %d/%d candles sent", sym, sentCount, copied);
  }

//+------------------------------------------------------------------+
//| Main tick handler — only sends ticks for chart symbol             |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!InpSendTicks)
      return;

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
//| Parse a simple JSON string field: "key":"value" or "key": "value" |
//+------------------------------------------------------------------+
string ParseJSONString(const string &raw, const string key)
  {
   string searchKey = "\"" + key + "\"";
   int keyPos = StringFind(raw, searchKey);
   if(keyPos < 0)
      return "";

   int colonPos = StringFind(raw, ":", keyPos + StringLen(searchKey));
   if(colonPos < 0)
      return "";

   int startPos = colonPos + 1;
// Skip whitespace between colon and opening quote
   while(startPos < StringLen(raw) && StringGetCharacter(raw, startPos) == ' ')
      startPos++;
// Expect opening quote
   if(startPos >= StringLen(raw) || StringGetCharacter(raw, startPos) != '"')
      return "";
   startPos++; // Skip opening quote

   int endPos = StringFind(raw, "\"", startPos);
   if(endPos < 0)
      return "";

   return StringSubstr(raw, startPos, endPos - startPos);
  }

//+------------------------------------------------------------------+
//| Parse a JSON double field: "key":123.45                           |
//+------------------------------------------------------------------+
double ParseJSONDouble(const string &raw, const string key)
  {
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(raw, searchKey);
   if(pos < 0)
      return 0.0;
   int startPos = pos + StringLen(searchKey);
// Skip whitespace
   while(startPos < StringLen(raw) && StringGetCharacter(raw, startPos) == ' ')
      startPos++;
   int endPos = startPos;
   while(endPos < StringLen(raw))
     {
      ushort ch = StringGetCharacter(raw, endPos);
      if(ch != '-' && ch != '.' && (ch < '0' || ch > '9'))
         break;
      endPos++;
     }
   if(endPos == startPos)
      return 0.0;
   return StringToDouble(StringSubstr(raw, startPos, endPos - startPos));
  }

//+------------------------------------------------------------------+
//| Parse a JSON long (integer) field: "key":12345                    |
//+------------------------------------------------------------------+
long ParseJSONLong(const string &raw, const string key)
  {
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(raw, searchKey);
   if(pos < 0)
      return 0;
   int startPos = pos + StringLen(searchKey);
   while(startPos < StringLen(raw) && StringGetCharacter(raw, startPos) == ' ')
      startPos++;
   int endPos = startPos;
   while(endPos < StringLen(raw))
     {
      ushort ch = StringGetCharacter(raw, endPos);
      if(ch != '-' && (ch < '0' || ch > '9'))
         break;
      endPos++;
     }
   if(endPos == startPos)
      return 0;
   return StringToInteger(StringSubstr(raw, startPos, endPos - startPos));
  }

//+------------------------------------------------------------------+
//| Check if command ID was already processed (idempotency)           |
//+------------------------------------------------------------------+
bool IsDuplicateCmd(string cmdId)
  {
   for(int i = 0; i < g_cmdIdCount; i++)
     {
      if(g_processedCmdIds[i] == cmdId)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Record command ID in dedup history (FIFO)                         |
//+------------------------------------------------------------------+
void RecordCmdId(string cmdId)
  {
   if(g_cmdIdCount >= InpMaxCmdIdHistory)
     {
      // FIFO: shift array left, drop oldest
      for(int i = 0; i < g_cmdIdCount - 1; i++)
         g_processedCmdIds[i] = g_processedCmdIds[i + 1];
      g_cmdIdCount--;
     }
   g_processedCmdIds[g_cmdIdCount] = cmdId;
   g_cmdIdCount++;
  }

//+------------------------------------------------------------------+
//| Send ACK response                                                  |
//+------------------------------------------------------------------+
void SendACK(string cmdId)
  {
   long timeMs = (long)TimeCurrent() * 1000;
   string json = StringFormat(
                    "{\"type\":\"ACK\",\"cmd_id\":\"%s\",\"t\":%lld}",
                    cmdId, timeMs);
   g_socket.SendJSON(json);
   if(InpDebugMode)
      PrintFormat("[AureusProvider] ACK sent for cmd_id=%s", cmdId);
  }

//+------------------------------------------------------------------+
//| Send NACK response                                                 |
//+------------------------------------------------------------------+
void SendNACK(string cmdId, string reason)
  {
   long timeMs = (long)TimeCurrent() * 1000;
   string json = StringFormat(
                    "{\"type\":\"NACK\",\"cmd_id\":\"%s\",\"reason\":\"%s\",\"t\":%lld}",
                    cmdId, reason, timeMs);
   g_socket.SendJSON(json);
   if(InpDebugMode)
      PrintFormat("[AureusProvider] NACK sent for cmd_id=%s reason=%s", cmdId, reason);
  }

//+------------------------------------------------------------------+
//| Map trade retcode to reason string                                 |
//+------------------------------------------------------------------+
string RetcodeToReason(int retcode)
  {
   switch(retcode)
     {
      case 10004: // TRADE_RETCODE_REQUOTE: requote
         return "REQUOTE";
      case 10006: // TRADE_RETCODE_REJECT: request bị từ chối
         return "REJECTED";
      case 10007: // TRADE_RETCODE_CANCEL: request bị cancel bởi trader
         return "CANCELED";
      case 10008: // TRADE_RETCODE_PLACED: order đã được đặt
         return "ORDER_PLACED";
      case 10009: // TRADE_RETCODE_DONE: request xử lý thành công
         return "DONE";
      case 10010: // TRADE_RETCODE_DONE_PARTIAL: khớp lệnh một phần
         return "DONE_PARTIAL";
      case 10011: // TRADE_RETCODE_ERROR: lỗi xử lý request
         return "SERVER_ERROR";
      case 10012: // TRADE_RETCODE_TIMEOUT: request timeout
         return "TIMEOUT";
      case 10013: // TRADE_RETCODE_INVALID: request không hợp lệ
         return "REQUEST_DENIED";
      case 10014: // TRADE_RETCODE_INVALID_VOLUME: volume không hợp lệ
         return "INVALID_VOLUME";
      case 10015: // TRADE_RETCODE_INVALID_PRICE: giá không hợp lệ
         return "INVALID_PRICE";
      case 10016: // TRADE_RETCODE_INVALID_STOPS: SL/TP không hợp lệ
         return "INVALID_STOPS";
      case 10017: // TRADE_RETCODE_TRADE_DISABLED: trading bị disable
         return "TRADE_DISABLED";
      case 10018: // TRADE_RETCODE_MARKET_CLOSED: market đóng cửa
         return "MARKET_CLOSED";
      case 10019: // TRADE_RETCODE_NO_MONEY: không đủ margin/funds
         return "INSUFFICIENT_MARGIN";
      case 10020: // TRADE_RETCODE_PRICE_CHANGED: giá đã thay đổi
         return "PRICE_CHANGED";
      case 10021: // TRADE_RETCODE_PRICE_OFF: không có quote giá
         return "PRICE_OFF";
      case 10022: // TRADE_RETCODE_INVALID_EXPIRATION: expiration không hợp lệ
         return "INVALID_EXPIRATION";
      case 10023: // TRADE_RETCODE_ORDER_CHANGED: trạng thái order đã đổi
         return "ORDER_CHANGED";
      case 10024: // TRADE_RETCODE_TOO_MANY_REQUESTS: quá nhiều request
         return "TOO_MANY_REQUESTS";
      case 10025: // TRADE_RETCODE_NO_CHANGES: modify không có thay đổi
         return "NO_CHANGES";
      case 10026: // TRADE_RETCODE_SERVER_DISABLES_AT: server tắt autotrading
         return "SERVER_DISABLES_AT";
      case 10027: // TRADE_RETCODE_CLIENT_DISABLES_AT: terminal tắt autotrading
         return "CLIENT_DISABLES_AT";
      case 10028: // TRADE_RETCODE_LOCKED: request đang bị lock
         return "LOCKED";
      case 10029: // TRADE_RETCODE_FROZEN: order/position bị frozen
         return "FROZEN";
      case 10030: // TRADE_RETCODE_INVALID_FILL: filling type không hợp lệ
         return "INVALID_FILL";
      case 10031: // TRADE_RETCODE_CONNECTION: không có kết nối trade server
         return "CONNECTION";
      case 10032: // TRADE_RETCODE_ONLY_REAL: chỉ cho phép trên tài khoản real
         return "ONLY_REAL";
      case 10033: // TRADE_RETCODE_LIMIT_ORDERS: vượt giới hạn pending orders
         return "LIMIT_ORDERS";
      case 10034: // TRADE_RETCODE_LIMIT_VOLUME: vượt giới hạn volume cho symbol
         return "LIMIT_VOLUME";
      case 10035: // TRADE_RETCODE_INVALID_ORDER: loại order không hợp lệ/bị cấm
         return "INVALID_ORDER";
      case 10036: // TRADE_RETCODE_POSITION_CLOSED: position đã đóng
         return "POSITION_CLOSED";
      case 10038: // TRADE_RETCODE_INVALID_CLOSE_VOLUME: close volume vượt position volume
         return "INVALID_CLOSE_VOLUME";
      case 10039: // TRADE_RETCODE_CLOSE_ORDER_EXIST: đã có close order cho position
         return "CLOSE_ORDER_EXIST";
      case 10040: // TRADE_RETCODE_LIMIT_POSITIONS: vượt giới hạn số positions
         return "TRADE_LIMIT_POSITIONS";
      case 10041: // TRADE_RETCODE_REJECT_CANCEL: request activate/cancel bị reject
         return "REJECT_CANCEL";
      case 10042: // TRADE_RETCODE_LONG_ONLY: chỉ cho phép vị thế Buy
         return "LONG_ONLY";
      case 10043: // TRADE_RETCODE_SHORT_ONLY: chỉ cho phép vị thế Sell
         return "SHORT_ONLY";
      case 10044: // TRADE_RETCODE_CLOSE_ONLY: chỉ cho phép đóng vị thế
         return "CLOSE_ONLY";
      case 10045: // TRADE_RETCODE_FIFO_CLOSE: bắt buộc đóng theo FIFO
         return "FIFO_CLOSE";
      case 10046: // TRADE_RETCODE_HEDGE_PROHIBITED: hedging bị cấm
         return "HEDGE_PROHIBITED";
      default:
         return StringFormat("ERROR_%d", retcode);
     }
  }

//+------------------------------------------------------------------+
//| Push ORDER_OPENED event                                            |
//+------------------------------------------------------------------+
void PushOrderOpened(string cmdId, string symbol, long ticket, string direction,
                     string orderType, double volume, double openPrice,
                     double sl, double tp, long magic, string strategyName = "", string traceId = "")
  {
   long timeMs = (long)TimeCurrent() * 1000;
   string json = StringFormat(
                    "{\"type\":\"ORDER_OPENED\",\"cmd_id\":\"%s\",\"symbol\":\"%s\",\"ticket\":%lld,"
                    "\"direction\":\"%s\",\"order_type\":\"%s\",\"volume\":%.2f,\"open_price\":%.5f,"
                    "\"sl\":%.5f,\"tp\":%.5f,\"magic\":%lld,\"strategy_name\":\"%s\",\"trace_id\":\"%s\",\"t\":%lld}",
                    cmdId, symbol, ticket, direction, orderType, volume, openPrice, sl, tp, magic, strategyName, traceId, timeMs);
   g_socket.SendJSON(json);
   if(InpDebugMode)
      PrintFormat("[AureusProvider] ORDER_OPENED pushed: ticket=%lld symbol=%s strategy=%s", ticket, symbol, strategyName);
  }

//+------------------------------------------------------------------+
//| Push ORDER_FAILED event                                            |
//+------------------------------------------------------------------+
void PushOrderFailed(string cmdId, string symbol, string reason, int retcode,
                     double entryPrice = 0.0, double ask = 0.0, double bid = 0.0)
  {
   long timeMs = (long)TimeCurrent() * 1000;
   string json = StringFormat(
                    "{\"type\":\"ORDER_FAILED\",\"cmd_id\":\"%s\",\"symbol\":\"%s\","
                    "\"reason\":\"%s\",\"retcode\":%d,\"entry_price\":%.5f,\"ask\":%.5f,\"bid\":%.5f,\"t\":%lld}",
                    cmdId, symbol, reason, retcode, entryPrice, ask, bid, timeMs);
   g_socket.SendJSON(json);
   PrintFormat("[AureusProvider] ORDER_FAILED pushed: cmd_id=%s reason=%s retcode=%d entry_price=%.5f ask=%.5f bid=%.5f",
               cmdId, reason, retcode, entryPrice, ask, bid);
  }

//+------------------------------------------------------------------+
//| Push ORDER_CLOSED event                                            |
//+------------------------------------------------------------------+
void PushOrderClosed(string symbol, long ticket, string direction, double volume,
                     double openPrice, double closePrice, double profit,
                     double commission, double swap, long magic,
                     string strategyName = "", string traceId = "")
  {
   long timeMs = (long)TimeCurrent() * 1000;
   string json = StringFormat(
                    "{\"type\":\"ORDER_CLOSED\",\"symbol\":\"%s\",\"ticket\":%lld,"
                    "\"direction\":\"%s\",\"volume\":%.2f,\"open_price\":%.5f,\"close_price\":%.5f,"
                    "\"profit\":%.2f,\"commission\":%.2f,\"swap\":%.2f,\"magic\":%lld,\"strategy_name\":\"%s\",\"trace_id\":\"%s\",\"t\":%lld}",
                    symbol, ticket, direction, volume, openPrice, closePrice, profit, commission, swap,
                    magic, strategyName, traceId, timeMs);
   g_socket.SendJSON(json);
   if(InpDebugMode)
      PrintFormat("[AureusProvider] ORDER_CLOSED pushed: ticket=%lld profit=%.2f strategy=%s", ticket, profit, strategyName);
  }


string forexPairs[] =
  {
   "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
   "EURJPY", "EURGBP", "EURCHF", "EURCAD", "EURAUD", "EURNZD",
   "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "GBPNZD",
   "AUDJPY", "AUDCHF", "AUDCAD", "AUDNZD",
   "NZDJPY", "NZDCHF", "NZDCAD",
   "CADJPY", "CADCHF", "CHFJPY"
  };

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsForexPair(string symbol)
  {
   for(int i = 0; i < ArraySize(forexPairs); i++)
      if(StringCompare(symbol, forexPairs[i]) == 0)
         return true;
   return false;
  }
//+------------------------------------------------------------------+
//| Tính toán Lot Size từ fixed budget và tự động điều chỉnh SL nếu cần |
//| Dùng SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE (broker-native) |
//| Khi lot > max_lot → nới rộng SL để giữ nguyên riskAmount            |
//+------------------------------------------------------------------+
double CalculateLotFromBudget(string symbol, string direction,
                              double entryPriceRequested, double &slRequested,
                              double riskAmount)
  {
   if(riskAmount <= 0)
      return 0.0;

// --- Lấy tick info từ broker ---
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0)
     {
      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] Invalid tick info — tickValue=%.5f tickSize=%.5f",
                     symbol, tickValue, tickSize);
      return SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
     }

// --- Get actual entry price from market ---
   double actualEntry = entryPriceRequested;
   if(actualEntry <= 0)
     {
      actualEntry = (direction == "BUY")
                    ? SymbolInfoDouble(symbol, SYMBOL_ASK)
                    : SymbolInfoDouble(symbol, SYMBOL_BID);
     }

// --- SL distance ---
   double slDistance = MathAbs(actualEntry - slRequested);
   if(slDistance < tickSize)
     {
      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] SL too close — dist=%.5f tickSize=%.5f",
                     symbol, slDistance, tickSize);
      return SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
     }

// --- Tiền lỗ cho 1 lot nếu SL bị hit ---
   double lossPerLot = (slDistance / tickSize) * tickValue;
   if(lossPerLot <= 0)
     {
      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] Zero lossPerLot — dist=%.5f tickVal=%.2f tickSize=%.5f",
                     symbol, slDistance, tickValue, tickSize);
      return SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
     }

// --- Lot size lý thuyết ---
   double lot = riskAmount / lossPerLot;
   double originalBudget = riskAmount;



// --- Volume limits ---
   double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double stepVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(stepVol <= 0)
      stepVol = 0.01;

// --- Normalize theo step ---
   lot = MathFloor(lot / stepVol) * stepVol;

   if(IsForexPair(symbol) || StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "USTEC") >= 0)
     {
      if(StringFind(symbol, "USTEC") >= 0)
         maxVol = 1.5;
      if(IsForexPair(symbol))
         maxVol = 0.2;
      if(StringFind(symbol, "XAU") >= 0)
         maxVol = 0.1;
     }

// --- Nếu lot > maxVol → nới rộng SL để giữ nguyên risk ---
   if(lot > maxVol)
     {
      lot = maxVol;
      // Đảo ngược công thức: slDistance = (riskAmount / lot) * (tickSize / tickValue)
      double newSlDistance = (riskAmount / lot) * (tickSize / tickValue);

      // Xác định hướng SL so với entry
      bool slBelowEntry = (slRequested < actualEntry);
      slRequested = slBelowEntry
                    ? NormalizeDouble(actualEntry - newSlDistance, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS))
                    : NormalizeDouble(actualEntry + newSlDistance, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS));

      slDistance = newSlDistance;
      lossPerLot = (slDistance / tickSize) * tickValue;

      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] Lot %.2f > max %.2f — SL widened: dist=%.5f → new SL=%.5f",
                     symbol, riskAmount / lossPerLot, maxVol, slDistance, slRequested);
     }

// --- Nếu lot < minVol → từ chối (không tăng budget) ---
   if(lot < minVol)
     {
      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] Calculated lot %.4f < min %.2f — SL too wide for budget $%.2f",
                     symbol, lot, minVol, originalBudget);
      return 0.0;
     }

// --- Final clamp ---
   if(lot > maxVol)
      lot = maxVol;

// --- Kiểm tra Margin ---
   ENUM_ORDER_TYPE orderType = (direction == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double marginRequired = 0;
   if(!OrderCalcMargin(orderType, symbol, lot,
                       (direction == "BUY")
                       ? SymbolInfoDouble(symbol, SYMBOL_ASK)
                       : SymbolInfoDouble(symbol, SYMBOL_BID),
                       marginRequired))
     {
      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] Failed to calc margin — error=%d",
                     symbol, GetLastError());
      return 0.0;
     }

   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(freeMargin < marginRequired)
     {
      if(InpDebugMode)
         PrintFormat("[lot_calc] [%s] Insufficient margin — need=%.2f free=%.2f",
                     symbol, marginRequired, freeMargin);
      return 0.0;
     }

   if(InpDebugMode)
      PrintFormat("[lot_calc] [%s] %s | budget=$%.2f | entry=%.5f | SL=%.5f | "
                  "dist=%.5f | tickVal=%.2f tickSize=%.5f | loss/lot=$%.2f | lot=%.2f | margin=%.2f",
                  symbol, direction, originalBudget, actualEntry, slRequested,
                  slDistance, tickValue, tickSize, lossPerLot, lot, marginRequired);

   return lot;
  }

//+------------------------------------------------------------------+
//| Execute OPEN_ORDER command                                         |
//+------------------------------------------------------------------+
void ExecuteOpenOrder(const string &raw)
  {
// Parse command fields
   string cmdId     = ParseJSONString(raw, "cmd_id");
   string symbol    = ParseJSONString(raw, "symbol");
   string direction = ParseJSONString(raw, "direction");
   string orderType = ParseJSONString(raw, "order_type");
   double volume    = ParseJSONDouble(raw, "volume");
   double price     = ParseJSONDouble(raw, "price");
   double sl        = ParseJSONDouble(raw, "sl");
   double tp        = ParseJSONDouble(raw, "tp");
   long   magic     = ParseJSONLong(raw, "magic");
   string comment   = ParseJSONString(raw, "comment");
   string sizeMode  = ParseJSONString(raw, "size_mode");
   double riskAmount = ParseJSONDouble(raw, "risk_amount");
   double tpRRRatio  = ParseJSONDouble(raw, "tp_rr_ratio");
   string traceId    = ParseJSONString(raw, "trace_id");
   string strategyName = comment;
   int commentSep = StringFind(comment, "|");
   if(commentSep > 0)
      strategyName = StringSubstr(comment, 0, commentSep);

   if(tpRRRatio == 0)
      tpRRRatio = 1.5;

// Validate required fields (volume check skipped if MT5 will calculate)
   if(cmdId == "" || symbol == "" || direction == "" || orderType == "")
     {
      SendNACK(cmdId != "" ? cmdId : "unknown", "INVALID_COMMAND");
      return;
     }

// Check idempotency
   if(IsDuplicateCmd(cmdId))
     {
      SendNACK(cmdId, "DUPLICATE");
      return;
     }

// Check symbol is declared in InpSymbols before ACK/order side effects
   if(FindContextIndex(symbol) < 0)
     {
      PrintFormat("[AureusProvider] Reject OPEN_ORDER: cmd_id=%s symbol=%s reason=SYMBOL_NOT_ALLOWED", cmdId, symbol);
      SendNACK(cmdId, "SYMBOL_NOT_ALLOWED");
      return;
     }

// Check AutoTrading enabled
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
     {
      SendNACK(cmdId, "TRADE_DISABLED");
      return;
     }

// ACK — command accepted
   SendACK(cmdId);
   RecordCmdId(cmdId);

   bool terminalEventSent = false;

// Build MqlTradeRequest
   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

// Normalize stops for Market orders
   int symDigits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double pointVal = SymbolInfoDouble(symbol, SYMBOL_POINT);
   long stopLevel = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);

   price = NormalizeDouble(price, symDigits);
   sl = NormalizeDouble(sl, symDigits);
   tp = NormalizeDouble(tp, symDigits);

   double g_point_value = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double g_point_per_pips = (symDigits == 3 || symDigits == 5) ? 10 : 1;
   double sell_stop_buffer = 2 * g_point_value;

   long spread_points = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if(spread_points == 0)
      spread_points = long((SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / g_point_value);

   double spread_in_price = spread_points * g_point_value;
   double buffer_in_price = 1 * g_point_per_pips * g_point_value;
   double total_adjustment = spread_in_price + buffer_in_price;

   double entry_price = 0, sl_price = 0, tp_price = 0, lot_size = 0;


   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   if(direction == "BUY")
     {
      // Vào lệnh BUY ngay
      if(orderType == "MARKET")
         entry_price = ask;
      else
         entry_price = price;
      sl = sl - buffer_in_price;
      volume = CalculateLotFromBudget(symbol, direction, entry_price, sl, InpRiskFixedAmountBudget);
      tp = entry_price + (entry_price - sl) * tpRRRatio;
     }
   else
      if(direction == "SELL")
        {
         // Vào lệnh SELL ngay
         if(orderType == "MARKET")
            entry_price = bid;
         else
            entry_price = price;
         sl = sl + total_adjustment;
         volume = CalculateLotFromBudget(symbol, direction, entry_price, sl, InpRiskFixedAmountBudget);
         tp = entry_price - (sl - entry_price) * tpRRRatio;
        }


   if(InpDebugMode)
      PrintFormat("[AureusProvider] [%s] TP recalculated from actual entry: ratio=%.2f slDist=%.5f tp=%.5f",
                  symbol, tpRRRatio, sl_price, tp_price);

// Normalize volume
   double min_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step_vol > 0)
      volume = MathRound(volume / step_vol) * step_vol;

   if(volume < min_vol)
      volume = min_vol;
   if(volume > max_vol)
      volume = max_vol;

   request.volume   = volume;
   request.symbol   = symbol;
   request.sl       = NormalizeDouble(sl, symDigits);
   request.tp       = NormalizeDouble(tp, symDigits);
   request.magic    = magic;
   request.comment  = comment;
   request.deviation = InpMaxSlippage;

// Determine supported filling mode for MARKET orders
   int fillingMode = (int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   ENUM_ORDER_TYPE_FILLING fillType = ORDER_FILLING_IOC; // Default
   if((fillingMode & SYMBOL_FILLING_FOK) != 0)
      fillType = ORDER_FILLING_FOK;
   else
      if((fillingMode & SYMBOL_FILLING_IOC) != 0)
         fillType = ORDER_FILLING_IOC;
      else
         fillType = ORDER_FILLING_RETURN; // Fallback

   if(orderType == "MARKET")
     {
      request.action = TRADE_ACTION_DEAL;
      request.type   = (direction == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      request.price  = entry_price;
      request.type_filling = fillType;
     }
   else
      if(orderType == "LIMIT")
        {
         request.action = TRADE_ACTION_PENDING;
         request.price  = NormalizeDouble(price, symDigits);
         request.type   = (direction == "BUY") ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
         request.type_filling = fillType;
         request.type_time = ORDER_TIME_GTC;
        }
      else
         if(orderType == "STOP")
           {
            request.action = TRADE_ACTION_PENDING;
            request.price  = NormalizeDouble(price, symDigits);
            request.type   = (direction == "BUY") ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
            request.type_filling = fillType;
            request.type_time = ORDER_TIME_GTC;
           }
         else
           {
            PushOrderFailed(cmdId, symbol, "UNKNOWN_ORDER_TYPE", 0, entry_price, ask, bid);
            g_ordersFailed++;
            return;
           }

   /*
   // --- DEBUG LOGGING FOR INVALID_STOPS DIAGNOSIS ---
      double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
      double minVol    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
      double maxVol    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);

      string fillingStr = "UNKNOWN";
      if(fillType == ORDER_FILLING_FOK)
         fillingStr = "FOK";
      else
         if(fillType == ORDER_FILLING_IOC)
            fillingStr = "IOC";
         else
            if(fillType == ORDER_FILLING_RETURN)
               fillingStr = "RETURN";

      if(InpDebugMode) PrintFormat("[AureusProvider] [DEBUG] Order %s %s %s: vol=%.2f (min=%.2f,max=%.2f) | ask=%.5f bid=%.5f | SL=%.5f TP=%.5f | stopLevel=%ld pts | digits=%d | filling=%s",
                  symbol, direction, orderType,
                  request.volume, minVol, maxVol,
                  askPrice, bidPrice,
                  request.sl, request.tp,
                  stopLevel, symDigits, fillingStr);

      if(orderType == "MARKET")
        {
         if(direction == "BUY")
            if(InpDebugMode) PrintFormat("[AureusProvider] [DEBUG] BUY check: ask-SL=%.5f (need>%.5f) | TP-ask=%.5f (need>%.5f)",
                        askPrice - request.sl, (stopLevel + 1) * pointVal,
                        request.tp - askPrice, (stopLevel + 1) * pointVal);
         else
            if(InpDebugMode) PrintFormat("[AureusProvider] [DEBUG] SELL check: SL-bid=%.5f (need>%.5f) | bid-TP=%.5f (need>%.5f)",
                        request.sl - bidPrice, (stopLevel + 1) * pointVal,
                        bidPrice - request.tp, (stopLevel + 1) * pointVal);
        }
   // --- END DEBUG LOGGING ---
   //*/
// Pre-validate with OrderCheck
   MqlTradeCheckResult checkResult;
   ZeroMemory(checkResult);
   if(!OrderCheck(request, checkResult))
     {
      PushOrderFailed(cmdId, symbol, RetcodeToReason(checkResult.retcode), checkResult.retcode, entry_price, ask, bid);
      g_ordersFailed++;
      return;
     }

// Execute OrderSend
   if(!OrderSend(request, result))
     {
      int err = GetLastError();
      PushOrderFailed(cmdId, symbol, RetcodeToReason(result.retcode != 0 ? result.retcode : err), result.retcode, entry_price, ask, bid);
      g_ordersFailed++;
      return;
     }

   if(result.retcode == TRADE_RETCODE_DONE)
     {
      if(orderType == "MARKET")
        {
         // Safety layer 1: deterministic resolve from opened position (source of truth)
         bool positionResolved = false;
         ulong positionTicket = 0;
         double filledEntry = 0.0;

         if(PositionSelect(symbol))
           {
            long posMagic = PositionGetInteger(POSITION_MAGIC);
            if(posMagic == magic)
              {
               positionResolved = true;
               positionTicket = (ulong)PositionGetInteger(POSITION_TICKET);
               filledEntry = PositionGetDouble(POSITION_PRICE_OPEN);
              }
           }

         if(!positionResolved)
           {
            if(result.price > 0)
              {
               filledEntry = result.price;
               positionTicket = (ulong)result.order;
               positionResolved = true;
              }
           }

         if(!positionResolved || filledEntry <= 0)
           {
            // Post-fill finalize is optional: fallback to execution result
            filledEntry = (result.price > 0) ? result.price : request.price;
            positionTicket = (ulong)result.order;
            positionResolved = (filledEntry > 0);
            if(InpDebugMode)
               PrintFormat("[PF_FILL_FALLBACK] cmd_id=%s symbol=%s fallback_entry=%.5f", cmdId, symbol, filledEntry);
           }

         if(!positionResolved)
           {
            if(!terminalEventSent)
              {
               PushOrderOpened(cmdId, symbol, result.order, direction, orderType,
                               volume, result.price, request.sl, request.tp, magic, strategyName, traceId);
               terminalEventSent = true;
               g_ordersExecuted++;
              }
            return;
           }

         double tpBefore = request.tp;
         double slFinal = request.sl;
         double tpAfter = tpBefore;

         if(direction == "BUY")
            tpAfter = filledEntry + (filledEntry - slFinal) * tpRRRatio;
         else
            tpAfter = filledEntry - (slFinal - filledEntry) * tpRRRatio;

         tpAfter = NormalizeDouble(tpAfter, symDigits);

         if(InpDebugMode)
            PrintFormat("[PF_FILL] cmd_id=%s symbol=%s position_ticket=%llu filled_entry=%.5f", cmdId, symbol, positionTicket, filledEntry);
         if(InpDebugMode)
            PrintFormat("[PF_RECALC] cmd_id=%s symbol=%s tp_before=%.5f tp_after=%.5f rr=%.2f sl=%.5f", cmdId, symbol, tpBefore, tpAfter, tpRRRatio, slFinal);

         // Safety layer 2: stop/freeze guards before modify
         long freezeLevel = SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
         double minStopDist = (stopLevel + 1) * pointVal;
         double minFreezeDist = (freezeLevel + 1) * pointVal;
         double bidNow = SymbolInfoDouble(symbol, SYMBOL_BID);
         double askNow = SymbolInfoDouble(symbol, SYMBOL_ASK);

         bool validStops = true;
         bool validFreeze = true;
         if(direction == "BUY")
           {
            validStops = ((filledEntry - slFinal) > minStopDist && (tpAfter - filledEntry) > minStopDist);
            validFreeze = ((bidNow - slFinal) > minFreezeDist && (tpAfter - bidNow) > minFreezeDist);
           }
         else
           {
            validStops = ((slFinal - filledEntry) > minStopDist && (filledEntry - tpAfter) > minStopDist);
            validFreeze = ((slFinal - askNow) > minFreezeDist && (askNow - tpAfter) > minFreezeDist);
           }

         if(!validStops || !validFreeze)
           {
            string guardReason = validStops ? "FREEZE_GUARD" : "INVALID_STOPS";
            if(InpDebugMode)
               PrintFormat("[PF_MODIFY_GUARD_BYPASS] cmd_id=%s symbol=%s guard=%s", cmdId, symbol, guardReason);
            if(!terminalEventSent)
              {
               PushOrderOpened(cmdId, symbol, (long)positionTicket, direction, orderType,
                               volume, filledEntry, slFinal, tpBefore, magic, strategyName, traceId);
               terminalEventSent = true;
               g_ordersExecuted++;
              }
            return;
           }

         MqlTradeRequest modReq;
         MqlTradeResult modRes;
         ZeroMemory(modReq);
         ZeroMemory(modRes);
         if(InpDebugMode)
            PrintFormat("[PF_MODIFY_ATTEMPT] cmd_id=%s symbol=%s position=%llu sl=%.5f tp=%.5f", cmdId, symbol, positionTicket, slFinal, tpAfter);
         modReq.action = TRADE_ACTION_SLTP;
         modReq.symbol = symbol;
         modReq.magic = magic;
         modReq.sl = slFinal;
         modReq.tp = tpAfter;
         modReq.position = positionTicket;

         bool modOk = OrderSend(modReq, modRes) && modRes.retcode == TRADE_RETCODE_DONE;
         if(InpDebugMode)
            PrintFormat("[PF_MODIFY] cmd_id=%s symbol=%s modify_result=retcode:%d", cmdId, symbol, (int)modRes.retcode);

         if(!modOk)
           {
            int modRetcode = (int)(modRes.retcode != 0 ? modRes.retcode : result.retcode);
            if(InpDebugMode)
               PrintFormat("[PF_MODIFY_BYPASS] cmd_id=%s symbol=%s retcode=%d", cmdId, symbol, modRetcode);
            if(!terminalEventSent)
              {
               PushOrderOpened(cmdId, symbol, (long)positionTicket, direction, orderType,
                               volume, filledEntry, slFinal, tpBefore, magic, strategyName, traceId);
               terminalEventSent = true;
               g_ordersExecuted++;
              }
            return;
           }

         if(!terminalEventSent)
           {
            PushOrderOpened(cmdId, symbol, (long)positionTicket, direction, orderType,
                            volume, filledEntry, slFinal, tpAfter, magic, strategyName, traceId);
            terminalEventSent = true;
            g_ordersExecuted++;
           }
        }
      else
        {
         if(!terminalEventSent)
           {
            PushOrderOpened(cmdId, symbol, result.order, direction, orderType,
                            volume, result.price, sl, tp, magic, strategyName, traceId);
            terminalEventSent = true;
            g_ordersExecuted++;
           }
        }
     }
   else
     {
      if(!terminalEventSent)
        {
         PushOrderFailed(cmdId, symbol, RetcodeToReason(result.retcode), result.retcode, entry_price, ask, bid);
         terminalEventSent = true;
         g_ordersFailed++;
        }
     }

// Safety layer 3: hard terminal event gate (exactly one terminal event)
   if(!terminalEventSent)
     {
      PushOrderFailed(cmdId, symbol, "TERMINAL_EVENT_NOT_EMITTED", (int)result.retcode, entry_price, ask, bid);
      g_ordersFailed++;
     }
  }

//+------------------------------------------------------------------+
//| Execute CLOSE_ORDER command                                        |
//+------------------------------------------------------------------+
void ExecuteCloseOrder(const string &raw)
  {
   string cmdId  = ParseJSONString(raw, "cmd_id");
   string symbol = ParseJSONString(raw, "symbol");
   long   ticket = ParseJSONLong(raw, "ticket");
   long   magic  = ParseJSONLong(raw, "magic");

   if(cmdId == "" || symbol == "" || ticket == 0)
     {
      SendNACK(cmdId != "" ? cmdId : "unknown", "INVALID_COMMAND");
      return;
     }

   if(IsDuplicateCmd(cmdId))
     {
      SendNACK(cmdId, "DUPLICATE");
      return;
     }

   if(FindContextIndex(symbol) < 0)
     {
      PrintFormat("[AureusProvider] Reject CLOSE_ORDER: cmd_id=%s symbol=%s reason=SYMBOL_NOT_ALLOWED", cmdId, symbol);
      SendNACK(cmdId, "SYMBOL_NOT_ALLOWED");
      return;
     }

   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
     {
      SendNACK(cmdId, "TRADE_DISABLED");
      return;
     }

   SendACK(cmdId);
   RecordCmdId(cmdId);

// Select the position to close
   if(!PositionSelectByTicket(ticket))
     {
      PushOrderFailed(cmdId, symbol, "POSITION_NOT_FOUND", 0);
      g_ordersFailed++;
      return;
     }

// Verify magic number ownership
   long posMagic = PositionGetInteger(POSITION_MAGIC);
   if(posMagic != magic)
     {
      PushOrderFailed(cmdId, symbol, "MAGIC_MISMATCH", 0);
      g_ordersFailed++;
      return;
     }

   double posVolume = PositionGetDouble(POSITION_VOLUME);
   long   posType   = PositionGetInteger(POSITION_TYPE);

   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action   = TRADE_ACTION_DEAL;
   request.position = ticket;
   request.symbol   = symbol;
   request.volume   = posVolume;
   request.magic    = magic;
   request.deviation = InpMaxSlippage;
// Opposite direction to close
   request.type = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   request.price = (posType == POSITION_TYPE_BUY)
                   ? SymbolInfoDouble(symbol, SYMBOL_BID)
                   : SymbolInfoDouble(symbol, SYMBOL_ASK);
   request.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(request, result))
     {
      PushOrderFailed(cmdId, symbol, RetcodeToReason(result.retcode), result.retcode);
      g_ordersFailed++;
      return;
     }

   if(result.retcode != TRADE_RETCODE_DONE)
     {
      PushOrderFailed(cmdId, symbol, RetcodeToReason(result.retcode), result.retcode);
      g_ordersFailed++;
     }
// ORDER_CLOSED will be pushed by OnTradeTransaction when deal completes
  }

//+------------------------------------------------------------------+
//| Execute REQUEST_ORDERS command — return all open positions         |
//+------------------------------------------------------------------+
void ExecuteRequestOrders(const string &raw)
  {
   string cmdId = ParseJSONString(raw, "cmd_id");
   long   filterMagic = ParseJSONLong(raw, "magic_number");
   string filterSymbol = ParseJSONString(raw, "symbol");

   if(InpDebugMode)
      PrintFormat("[AureusProvider] REQUEST_ORDERS: cmdId=%s magic=%lld symbol=%s",
                  cmdId, filterMagic, filterSymbol != "" ? filterSymbol : "ALL");

   string json = BuildOpenOrdersJSON(filterMagic, filterSymbol);

   if(g_socket.SendJSON(json))
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] ORDERS response sent");
     }
   else
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] ERROR: Failed to send ORDERS response");
     }
  }

//+------------------------------------------------------------------+
//| Build JSON array of open positions                                 |
//+------------------------------------------------------------------+
string BuildOpenOrdersJSON(long filterMagic, string filterSymbol)
  {
   string json = "{\"type\":\"ORDERS\",\"positions\":[";
   int count = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long   magic  = PositionGetInteger(POSITION_MAGIC);

      if(filterMagic > 0 && magic != filterMagic)
         continue;
      if(filterSymbol != "" && symbol != filterSymbol)
         continue;

      long   posType      = PositionGetInteger(POSITION_TYPE);
      double volume       = PositionGetDouble(POSITION_VOLUME);
      double entryPrice   = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl           = PositionGetDouble(POSITION_SL);
      double tp           = PositionGetDouble(POSITION_TP);
      double profit       = PositionGetDouble(POSITION_PROFIT);
      double swap         = PositionGetDouble(POSITION_SWAP);
      double commission   = PositionGetDouble(POSITION_COMMISSION);
      long   posTime      = PositionGetInteger(POSITION_TIME);
      string comment      = PositionGetString(POSITION_COMMENT);
      string direction    = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";

      if(count > 0)
         json += ",";
      json += StringFormat(
                 "{\"ticket\":%llu,\"symbol\":\"%s\",\"direction\":\"%s\",\"volume\":%.2f,\"entry_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"magic\":%lld,\"profit\":%.2f,\"swap\":%.2f,\"commission\":%.2f,\"time\":%lld,\"comment\":\"%s\"}",
                 ticket, symbol, direction, volume, entryPrice, sl, tp, magic,
                 profit, swap, commission, posTime, comment
              );
      count++;
     }

   json += StringFormat("],\"count\":%d}", count);
   if(InpDebugMode)
      PrintFormat("[AureusProvider] Built ORDERS JSON: %d positions", count);
   return json;
  }

//+------------------------------------------------------------------+
//| Execute REQUEST_TRADE_HISTORY command                             |
//+------------------------------------------------------------------+
void ExecuteTradeHistoryRequest(const string &raw)
  {
// Parse time range
   long fromTimeMs = ParseJSONLong(raw, "from_time");
   long toTimeMs   = ParseJSONLong(raw, "to_time");
   long filterMagic = ParseJSONLong(raw, "magic_number");
   string filterSymbol = ParseJSONString(raw, "symbol");

   datetime fromTime = (datetime)(fromTimeMs / 1000);
   datetime toTime   = (datetime)(toTimeMs / 1000);

   if(fromTime >= toTime)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] REQUEST_TRADE_HISTORY: invalid time range from=%d to=%d", fromTime, toTime);
      string errorJson = "{\"type\":\"TRADE_HISTORY\",\"trades\":[],\"error\":\"invalid_time_range\"}";
      g_socket.SendJSON(errorJson);
      return;
     }

   if(InpDebugMode)
      PrintFormat("[AureusProvider] REQUEST_TRADE_HISTORY: from=%s to=%s magic=%lld symbol=%s",
                  TimeToString(fromTime), TimeToString(toTime), filterMagic, filterSymbol != "" ? filterSymbol : "ALL");

   string json = BuildTradeHistoryJSON(fromTime, toTime, filterMagic, filterSymbol);

   if(g_socket.SendJSON(json))
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] TRADE_HISTORY response sent");
     }
   else
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] ERROR: Failed to send TRADE_HISTORY response");
     }
  }

//+------------------------------------------------------------------+
//| Listen and process commands from Gateway                           |
//+------------------------------------------------------------------+
void ProcessIncomingCommands()
  {
   if(!g_socket.IsConnected())
      return;

   string raw = g_socket.Receive();
   if(raw == "")
      return;

//--- Extract symbol from command
   string cmdSymbol = ParseJSONString(raw, "symbol");

// â”€â”€ Order Commands â”€â”€
   if(StringFind(raw, "\"OPEN_ORDER\"") >= 0)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Received OPEN_ORDER command");
      ExecuteOpenOrder(raw);
      return;
     }

   if(StringFind(raw, "\"CLOSE_ORDER\"") >= 0)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Received CLOSE_ORDER command");
      ExecuteCloseOrder(raw);
      return;
     }

// ── Position Report Request ──
   if(StringFind(raw, "\"REQUEST_POSITIONS\"") >= 0)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Received REQUEST_POSITIONS command");
      ExecutePositionsRequest();
      return;
     }

   if(StringFind(raw, "REQUEST_BACKFILL_COUNT") >= 0)

      // â"€â"€ Open Orders Request â"€â"€
      if(StringFind(raw, "\"REQUEST_ORDERS\"") >= 0)
        {
         if(InpDebugMode)
            PrintFormat("[AureusProvider] Received REQUEST_ORDERS command");
         ExecuteRequestOrders(raw);
         return;
        }

// â"€â"€ Trade History Request â"€â"€
   if(StringFind(raw, "\"REQUEST_TRADE_HISTORY\"") >= 0)
     {
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Received REQUEST_TRADE_HISTORY command");
      ExecuteTradeHistoryRequest(raw);
      return;
     }

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
               if(InpDebugMode)
                  PrintFormat("[AureusProvider] [%s] Received REQUEST_BACKFILL_COUNT: %d candles",
                              cmdSymbol, count);
               DoBackfillCountForSymbol(idx, (int)count);
              }
            else
               if(InpDebugMode)
                  PrintFormat("[AureusProvider] Unknown symbol in command: %s", cmdSymbol);
           }
         else
           {
            // No symbol specified â†’ backfill all
            if(InpDebugMode)
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
               if(InpDebugMode)
                  PrintFormat("[AureusProvider] [%s] Received REQUEST_BACKFILL range: %s - %s",
                              cmdSymbol, TimeToString(fromTime), TimeToString(toTime));
               DoBackfillForSymbol(idx, fromTime, toTime);
              }
            else
               if(InpDebugMode)
                  PrintFormat("[AureusProvider] Unknown symbol in command: %s", cmdSymbol);
           }
         else
           {
            // No symbol specified â†’ backfill all
            if(InpDebugMode)
               PrintFormat("[AureusProvider] Received REQUEST_BACKFILL (all): %s - %s",
                           TimeToString(fromTime), TimeToString(toTime));
            for(int i = 0; i < g_symbolCount; i++)
               DoBackfillForSymbol(i, fromTime, toTime);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Trade Transaction handler — detects position closes               |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
  {
// Only process deal additions
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;

// Must be connected to push events
   if(!g_socket.IsConnected())
      return;

// Select the deal from history
   if(!HistoryDealSelect(trans.deal))
      return;

// Only process position close/reduce deals
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT)
      return;

// Filter by magic number — only report bot-managed positions
   long magic = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   if(magic == 0)
      return;  // Manual trade, skip

// Extract deal properties
   string symbol      = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
   long   ticket      = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   double volume      = HistoryDealGetDouble(trans.deal, DEAL_VOLUME);
   double closePrice  = HistoryDealGetDouble(trans.deal, DEAL_PRICE);
   double profit      = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
   double commission  = HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   double swap        = HistoryDealGetDouble(trans.deal, DEAL_SWAP);
   long   dealType    = HistoryDealGetInteger(trans.deal, DEAL_TYPE);

// Determine original direction (close deal is opposite direction)
   string direction = (dealType == DEAL_TYPE_BUY) ? "SELL" : "BUY";

// Get open price from position info (if still available)
   double openPrice = 0.0;
   if(PositionSelectByTicket(ticket))
      openPrice = PositionGetDouble(POSITION_PRICE_OPEN);

   if(InpDebugMode)
      PrintFormat("[AureusProvider] OnTradeTransaction: DEAL_ENTRY_OUT detected — "
                  "symbol=%s ticket=%lld direction=%s profit=%.2f magic=%lld",
                  symbol, ticket, direction, profit, magic);

   string dealComment = HistoryDealGetString(trans.deal, DEAL_COMMENT);
   string strategyName = dealComment;
   string traceId = "";
   int commentSep = StringFind(dealComment, "|");
   if(commentSep > 0)
     {
      strategyName = StringSubstr(dealComment, 0, commentSep);
      traceId = StringSubstr(dealComment, commentSep + 1);
     }

   PushOrderClosed(symbol, ticket, direction, volume,
                   openPrice, closePrice, profit, commission, swap, magic,
                   strategyName, traceId);
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
         // if(InpDebugMode) PrintFormat("[AureusProvider] Timer: Reconnected — waiting for Server gap detection commands");
         g_wasDisconnected = false;
         g_disconnectTime  = 0;
        }
      else
        {
         int downSec = (g_disconnectTime > 0) ? (int)(TimeCurrent() - g_disconnectTime) : 0;
         if(downSec % 10 == 0) // Log every ~10 seconds
            if(InpDebugMode)
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
   string statusLines = "Aureus Provider v3.0\n";
   statusLines += StringFormat("Gateway: %s:%d | Status: CONNECTED\n",
                               InpGatewayHost, InpGatewayPort);
   statusLines += StringFormat("Ticks Sent: %d (chart: %s, %s)\n",
                               g_ticksSent, _Symbol, InpSendTicks ? "ON" : "OFF");
   statusLines += StringFormat("Orders: %d executed, %d failed | Cmd IDs: %d\n",
                               g_ordersExecuted, g_ordersFailed, g_cmdIdCount);
   statusLines += "â”€â”€â”€ Symbol Candles â”€â”€â”€\n";

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
//+------------------------------------------------------------------+
