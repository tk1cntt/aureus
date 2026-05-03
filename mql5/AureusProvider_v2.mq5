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
#include <Trade/Trade.mqh>
//+------------------------------------------------------------------+
//| Input Parameters                                                   |
//+------------------------------------------------------------------+
input string   InpGatewayHost        = "localhost";              // Gateway Host
input int      InpGatewayPort        = 5556;                     // Gateway TCP Port
input string   InpSymbols            = "USDJPY,EURUSD,GBPUSD,AUDUSD";  // Symbols (comma-separated)
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
input double   InpBEProfitTarget     = 20.0;                     // Profit target ($) to activate breakeven management
input string   InpMagicManagementProfiles = "607000:breakout_protect;2603000:trend_runner;1391000:basket_escape"; // magic:profile pairs
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

struct SetupInfo
  {
   bool              active;
   double            priceLevel;
   datetime          setupTime;
  };

struct CISDDCAState
  {
   int               h1_signalType;
   int               previous_h1_signalType;
   datetime          h1_signalTime;
   datetime          ltf_scan_start_time;
   datetime          last_trade_signal_time;
   datetime          current_h1_signal_time;
   SetupInfo         bull_setup;
   SetupInfo         bear_setup;
  };

struct HistoryCooldownState
  {
   string            symbol;
   long              magic;
   string            direction;
   datetime          cooldown_until;
   datetime          last_close_time;
   ulong             last_close_deal;
   ulong             processed_deals[];
  };

struct MarketClosedCloseGuardState
  {
   string            symbol;
   long              magic;
   string            direction;
   datetime          guard_until;
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
CTrade        trade;

CISDDCAState g_cisdDCAStates[];         // Per-symbol provider-local DCA gate state
HistoryCooldownState g_historyCooldowns[]; // Provider-local history cooldown by symbol + magic + direction
MarketClosedCloseGuardState g_marketClosedCloseGuards[]; // Provider-local close guard by symbol + magic + direction

const string PROFILE_CONSERVATIVE     = "conservative";
const string PROFILE_TREND_RUNNER     = "trend_runner";
const string PROFILE_BREAKOUT_PROTECT = "breakout_protect";
const string PROFILE_BASKET_ESCAPE    = "basket_escape";
const string PROFILE_LEGACY           = "legacy";

string TrimProfileToken(string value)
  {
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
  }

bool IsKnownManagementProfile(string profile)
  {
   return profile == PROFILE_CONSERVATIVE ||
          profile == PROFILE_TREND_RUNNER ||
          profile == PROFILE_BREAKOUT_PROTECT ||
          profile == PROFILE_BASKET_ESCAPE;
  }

string ResolveManagementProfile(long magic, bool &fallback_used)
  {
   fallback_used = true;
   string pairs[];
   int pair_count = StringSplit(InpMagicManagementProfiles, ';', pairs);
   for(int i = 0; i < pair_count; i++)
     {
      string pair = TrimProfileToken(pairs[i]);
      if(pair == "")
         continue;

      int sep = StringFind(pair, ":");
      if(sep <= 0 || sep >= StringLen(pair) - 1)
         continue;

      string magic_text = TrimProfileToken(StringSubstr(pair, 0, sep));
      string profile = TrimProfileToken(StringSubstr(pair, sep + 1));
      long mapped_magic = StringToInteger(magic_text);
      if(mapped_magic == 0 || mapped_magic != magic)
         continue;

      if(IsKnownManagementProfile(profile))
        {
         fallback_used = false;
         return profile;
        }

      PrintFormat("[ManagePositionProfitBreakEvent] magic=%lld unknown_profile=%s fallback_profile=%s", magic, profile, PROFILE_CONSERVATIVE);
      return PROFILE_CONSERVATIVE;
     }

   return PROFILE_LEGACY;
  }

void LogManagementDecision(string symbol,
                           long magic,
                           string direction,
                           string profile,
                           string action,
                           string reason,
                           int positions_count,
                           double net_profit,
                           int age_seconds,
                           string primitive,
                           ulong ticket = 0,
                           double target_sl = 0)
  {
   string target = (ticket > 0)
                   ? StringFormat(" ticket=%I64u target_sl=%.5f", ticket, target_sl)
                   : "";
   PrintFormat("[ManagePositionDecision] symbol=%s magic=%lld direction=%s profile=%s action=%s reason=%s primitive=%s positions_count=%d net_profit=%.2f age_seconds=%d%s",
               symbol, magic, direction, profile, action, reason, primitive, positions_count, net_profit, age_seconds, target);
  }
//+------------------------------------------------------------------+
//| Market-closed close guard helpers                                  |
//+------------------------------------------------------------------+
int FindMarketClosedCloseGuardIndex(string symbol, long magic, string direction)
  {
   for(int i = 0; i < ArraySize(g_marketClosedCloseGuards); i++)
     {
      if(g_marketClosedCloseGuards[i].symbol == symbol &&
         g_marketClosedCloseGuards[i].magic == magic &&
         g_marketClosedCloseGuards[i].direction == direction)
         return i;
     }
   return -1;
  }

int EnsureMarketClosedCloseGuardState(string symbol, long magic, string direction)
  {
   int idx = FindMarketClosedCloseGuardIndex(symbol, magic, direction);
   if(idx >= 0)
      return idx;

   idx = ArraySize(g_marketClosedCloseGuards);
   ArrayResize(g_marketClosedCloseGuards, idx + 1);
   g_marketClosedCloseGuards[idx].symbol = symbol;
   g_marketClosedCloseGuards[idx].magic = magic;
   g_marketClosedCloseGuards[idx].direction = direction;
   g_marketClosedCloseGuards[idx].guard_until = 0;
   return idx;
  }

bool IsMarketClosedCloseGuardActive(string symbol, long magic, string direction, datetime &guardUntil)
  {
   int idx = FindMarketClosedCloseGuardIndex(symbol, magic, direction);
   if(idx < 0)
      return false;
   guardUntil = g_marketClosedCloseGuards[idx].guard_until;
   return guardUntil > TimeCurrent();
  }

void SetMarketClosedCloseGuard(string symbol, long magic, string direction)
  {
   int idx = EnsureMarketClosedCloseGuardState(symbol, magic, direction);
   datetime guardUntil = TimeCurrent() + 5 * 60;
   if(guardUntil <= g_marketClosedCloseGuards[idx].guard_until)
      return;

   g_marketClosedCloseGuards[idx].guard_until = guardUntil;
   PrintFormat("[MarketClosedCloseGuard] Set guard symbol=%s magic=%lld direction=%s until=%s reason=MARKET_CLOSED",
               symbol,
               magic,
               direction,
               TimeToString(guardUntil, TIME_DATE | TIME_SECONDS));
  }

bool IsSymbolCloseAvailableNow(string symbol, string &reason)
  {
   long trade_mode = SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
   if(trade_mode == SYMBOL_TRADE_MODE_DISABLED)
     {
      reason = "trade_mode_disabled";
      return false;
     }

   MqlDateTime now;
   TimeToStruct(TimeTradeServer(), now);
   int now_seconds = now.hour * 3600 + now.min * 60 + now.sec;
   datetime session_from = 0;
   datetime session_to = 0;
   bool has_sessions = false;

   for(uint session = 0; SymbolInfoSessionTrade(symbol, (ENUM_DAY_OF_WEEK)now.day_of_week, session, session_from, session_to); session++)
     {
      has_sessions = true;
      MqlDateTime from_dt;
      MqlDateTime to_dt;
      TimeToStruct(session_from, from_dt);
      TimeToStruct(session_to, to_dt);
      int from_seconds = from_dt.hour * 3600 + from_dt.min * 60 + from_dt.sec;
      int to_seconds = to_dt.hour * 3600 + to_dt.min * 60 + to_dt.sec;

      if(from_seconds <= to_seconds)
        {
         if(now_seconds >= from_seconds && now_seconds <= to_seconds)
            return true;
        }
      else if(now_seconds >= from_seconds || now_seconds <= to_seconds)
         return true;
     }

   if(has_sessions)
     {
      reason = "outside_trade_session";
      return false;
     }

   reason = "no_trade_session_data";
   return true;
  }

//+------------------------------------------------------------------+
//| History cooldown helpers                                           |
//+------------------------------------------------------------------+
int FindHistoryCooldownIndex(string symbol, long magic, string direction)
  {
   for(int i = 0; i < ArraySize(g_historyCooldowns); i++)
     {
      if(g_historyCooldowns[i].symbol == symbol &&
         g_historyCooldowns[i].magic == magic &&
         g_historyCooldowns[i].direction == direction)
         return i;
     }
   return -1;
  }

int EnsureHistoryCooldownState(string symbol, long magic, string direction)
  {
   int idx = FindHistoryCooldownIndex(symbol, magic, direction);
   if(idx >= 0)
      return idx;

   idx = ArraySize(g_historyCooldowns);
   ArrayResize(g_historyCooldowns, idx + 1);
   g_historyCooldowns[idx].symbol = symbol;
   g_historyCooldowns[idx].magic = magic;
   g_historyCooldowns[idx].direction = direction;
   g_historyCooldowns[idx].cooldown_until = 0;
   g_historyCooldowns[idx].last_close_time = 0;
   g_historyCooldowns[idx].last_close_deal = 0;
   ArrayResize(g_historyCooldowns[idx].processed_deals, 0);
   return idx;
  }

string DirectionFromCloseDealType(long dealType)
  {
   if(dealType == DEAL_TYPE_BUY)
      return "SELL";
   if(dealType == DEAL_TYPE_SELL)
      return "BUY";
   return "";
  }

bool IsHistoryCooldownDealProcessed(HistoryCooldownState &state, ulong dealTicket)
  {
   for(int i = 0; i < ArraySize(state.processed_deals); i++)
     {
      if(state.processed_deals[i] == dealTicket)
         return true;
     }
   return false;
  }

void MarkHistoryCooldownDealProcessed(HistoryCooldownState &state, ulong dealTicket)
  {
   int size = ArraySize(state.processed_deals);
   ArrayResize(state.processed_deals, size + 1);
   state.processed_deals[size] = dealTicket;
  }

void SetHistoryCooldown(int idx, datetime cooldownUntil, string reason, string source)
  {
   if(cooldownUntil <= TimeCurrent())
      return;
   if(cooldownUntil <= g_historyCooldowns[idx].cooldown_until)
      return;

   g_historyCooldowns[idx].cooldown_until = cooldownUntil;
   PrintFormat("[HistoryCooldown] Set cooldown symbol=%s magic=%lld direction=%s until=%s reason=%s source=%s",
               g_historyCooldowns[idx].symbol,
               g_historyCooldowns[idx].magic,
               g_historyCooldowns[idx].direction,
               TimeToString(cooldownUntil, TIME_DATE | TIME_SECONDS),
               reason,
               source);
  }

void ApplyCloseDealToHistoryCooldown(ulong dealTicket, string source)
  {
   if(dealTicket == 0 || !HistoryDealSelect(dealTicket))
      return;
   if(HistoryDealGetInteger(dealTicket, DEAL_ENTRY) != DEAL_ENTRY_OUT)
      return;

   long magic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
   if(magic == 0)
      return;

   string symbol = HistoryDealGetString(dealTicket, DEAL_SYMBOL);
   if(FindContextIndex(symbol) < 0)
      return;

   string direction = DirectionFromCloseDealType(HistoryDealGetInteger(dealTicket, DEAL_TYPE));
   if(direction == "")
      return;

   int idx = EnsureHistoryCooldownState(symbol, magic, direction);
   if(IsHistoryCooldownDealProcessed(g_historyCooldowns[idx], dealTicket))
      return;

   datetime closeTime = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
   long reason = HistoryDealGetInteger(dealTicket, DEAL_REASON);
   if(g_historyCooldowns[idx].last_close_time > 0 && MathAbs((int)(closeTime - g_historyCooldowns[idx].last_close_time)) <= 2)
      SetHistoryCooldown(idx, closeTime + 60 * 60, "multi_close_2s", source);
   else
      if(reason == DEAL_REASON_SL)
         SetHistoryCooldown(idx, closeTime + 30 * 60, "single_sl", source);

   g_historyCooldowns[idx].last_close_time = closeTime;
   g_historyCooldowns[idx].last_close_deal = dealTicket;
   MarkHistoryCooldownDealProcessed(g_historyCooldowns[idx], dealTicket);
  }

bool IsHistoryCooldownActive(string symbol, long magic, string direction, datetime &cooldownUntil)
  {
   int idx = FindHistoryCooldownIndex(symbol, magic, direction);
   if(idx < 0)
      return false;
   cooldownUntil = g_historyCooldowns[idx].cooldown_until;
   return cooldownUntil > TimeCurrent();
  }

void BootstrapHistoryCooldowns()
  {
   datetime toTime = TimeCurrent();
   datetime fromTime = toTime - 24 * 60 * 60;
   PrintFormat("[HistoryCooldown] Bootstrap start from=%s to=%s", TimeToString(fromTime, TIME_DATE | TIME_SECONDS), TimeToString(toTime, TIME_DATE | TIME_SECONDS));
   if(!HistorySelect(fromTime, toTime))
     {
      PrintFormat("[HistoryCooldown] Bootstrap HistorySelect failed: %d", GetLastError());
      return;
     }

   int totalDeals = HistoryDealsTotal();
   for(int i = 0; i < totalDeals; i++)
     {
      ulong dealTicket = HistoryDealGetTicket(i);
      ApplyCloseDealToHistoryCooldown(dealTicket, "bootstrap");
     }
   PrintFormat("[HistoryCooldown] Bootstrap complete states=%d deals=%d", ArraySize(g_historyCooldowns), totalDeals);
  }

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
   ArrayResize(g_cisdDCAStates, g_symbolCount);
   ArrayResize(g_historyCooldowns, 0);
   ArrayResize(g_marketClosedCloseGuards, 0);

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

   BootstrapHistoryCooldowns();

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


struct PositionInfo
  {
   ulong             ticket;
   long              open_time;
   double            open_price;
  };

double commission_per_lot = 12.0;
double max_loss_amount = InpRiskFixedAmountBudget * 2;
int buffer_profit = 5;

//+------------------------------------------------------------------+
//| Check bullish imbalance for a specific symbol/timeframe          |
//+------------------------------------------------------------------+
bool IsImbalanceUp(string symbol, ENUM_TIMEFRAMES timeframe, int index)
  {
   if(index < 2 || Bars(symbol, timeframe) <= index)
      return false;
   return iLow(symbol, timeframe, index - 2) > iHigh(symbol, timeframe, index);
  }

//+------------------------------------------------------------------+
//| Check bearish imbalance for a specific symbol/timeframe          |
//+------------------------------------------------------------------+
bool IsImbalanceDown(string symbol, ENUM_TIMEFRAMES timeframe, int index)
  {
   if(index < 2 || Bars(symbol, timeframe) <= index)
      return false;
   return iHigh(symbol, timeframe, index - 2) < iLow(symbol, timeframe, index);
  }

//+------------------------------------------------------------------+
//| Manage one provider-scoped symbol + magic + direction group      |
//+------------------------------------------------------------------+
double GetPositionCommissionCostPerLot(string symbol)
  {
   if(!IsForexPair(symbol) && !(StringFind(symbol, "XAU") >= 0))
      return 0;
   return commission_per_lot;
  }

void CalculatePositionGroupCosts(string symbol,
                                 const ulong &tickets[],
                                 double total_profit,
                                 double total_volume,
                                 double &total_commission,
                                 double &total_swap,
                                 double &net_profit)
  {
   total_commission = total_volume * GetPositionCommissionCostPerLot(symbol);
   total_swap = 0;
   for(int i = 0; i < ArraySize(tickets); i++)
     {
      if(PositionSelectByTicket(tickets[i]))
         total_swap += PositionGetDouble(POSITION_SWAP);
     }
   net_profit = total_profit - total_commission + total_swap;
  }

bool ClosePositionTickets(string symbol,
                          long magic,
                          string pos_type_str,
                          string profile,
                          const ulong &tickets[],
                          double net_profit,
                          int age_seconds,
                          string reason,
                          string primitive)
  {
   int positions_count = ArraySize(tickets);
   datetime guardUntil = 0;
   if(IsMarketClosedCloseGuardActive(symbol, magic, pos_type_str, guardUntil))
      return false;

   string close_unavailable_reason = "";
   if(!IsSymbolCloseAvailableNow(symbol, close_unavailable_reason))
     {
      SetMarketClosedCloseGuard(symbol, magic, pos_type_str);
      return false;
     }

   LogManagementDecision(symbol, magic, pos_type_str, profile, "CLOSE", reason, positions_count, net_profit, age_seconds, primitive);
   int success_count = 0;
   for(int i = 0; i < positions_count; i++)
     {
      bool ok = trade.PositionClose(tickets[i]);
      if(ok)
        {
         success_count++;
         continue;
        }

      int retcode = (int)trade.ResultRetcode();
      string retcode_reason = RetcodeToReason(retcode);
      string result_comment = trade.ResultComment();
      PrintFormat("[ManagePositionProfitBreakEvent] Close failed symbol=%s magic=%lld direction=%s ticket=%I64u retcode=%d reason=%s comment=%s",
                  symbol,
                  magic,
                  pos_type_str,
                  tickets[i],
                  retcode,
                  retcode_reason,
                  result_comment);
      if(retcode == TRADE_RETCODE_MARKET_CLOSED || retcode == 10018)
        {
         SetMarketClosedCloseGuard(symbol, magic, pos_type_str);
         return success_count > 0;
        }
     }
   return success_count > 0;
  }

bool MovePositionsSL(string symbol,
                     long magic,
                     ENUM_POSITION_TYPE target_type,
                     string profile,
                     const ulong &tickets[],
                     double net_profit,
                     int age_seconds,
                     double proposed_sl_price,
                     string action,
                     string reason,
                     string primitive)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   string log_prefix = StringFormat("[ManagePositionProfitBreakEvent] [%s:%lld:%s] ", symbol, magic, pos_type_str);
   int symbol_digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   int positions_count = ArraySize(tickets);
   proposed_sl_price = NormalizeDouble(proposed_sl_price, symbol_digits);
   int success_count = 0;

   for(int i = 0; i < positions_count; i++)
     {
      double tp_for_this_pos = 0;
      if(PositionSelectByTicket(tickets[i]))
         tp_for_this_pos = PositionGetDouble(POSITION_TP);
      if(trade.PositionModify(tickets[i], proposed_sl_price, tp_for_this_pos))
        {
         success_count++;
         LogManagementDecision(symbol, magic, pos_type_str, profile, action, reason, positions_count, net_profit, age_seconds, primitive, tickets[i], proposed_sl_price);
        }
      else
         Print(log_prefix, "SL modify failed for ticket ", tickets[i], ": ", trade.ResultComment());
     }

   Print(log_prefix, StringFormat("Moved SL to %.*f for %d/%d positions.", symbol_digits, proposed_sl_price, success_count, positions_count));
   return success_count > 0;
  }

bool FindStructureSLTarget(string symbol, ENUM_POSITION_TYPE target_type, double current_sl, double &proposed_sl_price)
  {
   if(target_type == POSITION_TYPE_BUY && IsImbalanceUp(symbol, PERIOD_CURRENT, 2))
     {
      double imbalance_sl_candidate = iLow(symbol, PERIOD_CURRENT, 2);
      if(imbalance_sl_candidate > current_sl)
        {
         proposed_sl_price = imbalance_sl_candidate;
         return true;
        }
     }
   else if(target_type == POSITION_TYPE_SELL && IsImbalanceDown(symbol, PERIOD_CURRENT, 2))
     {
      double imbalance_sl_candidate = iHigh(symbol, PERIOD_CURRENT, 2);
      if(imbalance_sl_candidate < current_sl || current_sl == 0)
        {
         proposed_sl_price = imbalance_sl_candidate;
         return true;
        }
     }

   return false;
  }

bool IsSLProfitable(string symbol,
                    ENUM_POSITION_TYPE target_type,
                    double proposed_sl_price,
                    double weighted_avg_open_price,
                    double total_volume,
                    double total_commission,
                    double total_swap)
  {
   double cost_offset_in_price = 0;
   double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double point_size = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double tick_value_for_total_volume = total_volume * tick_value;
   if(tick_value_for_total_volume > 0)
      cost_offset_in_price = ((total_commission + total_swap) / tick_value_for_total_volume) * point_size;

   double breakeven_price_with_costs = (target_type == POSITION_TYPE_BUY)
                                      ? weighted_avg_open_price + cost_offset_in_price
                                      : weighted_avg_open_price - cost_offset_in_price;
   return (target_type == POSITION_TYPE_BUY && proposed_sl_price > breakeven_price_with_costs) ||
          (target_type == POSITION_TYPE_SELL && proposed_sl_price < breakeven_price_with_costs);
  }

void ProcessLegacyPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   int positions_count = ArraySize(tickets);
   if(positions_count <= 0 || total_volume <= 0)
      return;

   double total_commission = 0;
   double total_swap = 0;
   double net_profit = 0;
   CalculatePositionGroupCosts(symbol, tickets, total_profit, total_volume, total_commission, total_swap, net_profit);
   int age_seconds = (earliest_open_time > 0) ? (int)(TimeCurrent() - earliest_open_time) : 0;

   if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount / 2 && positions_count == 1))
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_LEGACY, tickets, net_profit, age_seconds, "severe_risk_guard", "P-05/P-06");
      return;
     }
   if(positions_count == 4 && net_profit > 0)
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_LEGACY, tickets, net_profit, age_seconds, "legacy_basket_recovery_profit", "P-07");
      return;
     }
   if(positions_count == 1 && age_seconds > 1800 && net_profit > 0)
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_LEGACY, tickets, net_profit, age_seconds, "legacy_stale_profitable_single", "P-08");
      return;
     }

   LogManagementDecision(symbol, magic, pos_type_str, PROFILE_LEGACY, "HOLD", "legacy_no_rule_matched", positions_count, net_profit, age_seconds, "P-03");
  }

void ProcessConservativePositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   int positions_count = ArraySize(tickets);
   if(positions_count <= 0 || total_volume <= 0)
      return;

   double total_commission = 0;
   double total_swap = 0;
   double net_profit = 0;
   CalculatePositionGroupCosts(symbol, tickets, total_profit, total_volume, total_commission, total_swap, net_profit);
   int age_seconds = (earliest_open_time > 0) ? (int)(TimeCurrent() - earliest_open_time) : 0;

   if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount / 2 && positions_count == 1))
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_CONSERVATIVE, tickets, net_profit, age_seconds, "severe_risk_guard", "P-05/P-06");
      return;
     }

   LogManagementDecision(symbol, magic, pos_type_str, PROFILE_CONSERVATIVE, "HOLD", "conservative_hold_only", positions_count, net_profit, age_seconds, "P-08");
  }

void ProcessTrendRunnerPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   int positions_count = ArraySize(tickets);
   if(positions_count <= 0 || total_volume <= 0)
      return;

   double total_commission = 0;
   double total_swap = 0;
   double net_profit = 0;
   CalculatePositionGroupCosts(symbol, tickets, total_profit, total_volume, total_commission, total_swap, net_profit);
   int age_seconds = (earliest_open_time > 0) ? (int)(TimeCurrent() - earliest_open_time) : 0;

   if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount / 2 && positions_count == 1))
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_TREND_RUNNER, tickets, net_profit, age_seconds, "severe_risk_guard", "P-05/P-06");
      return;
     }
   if(net_profit <= positions_count * InpBEProfitTarget / 2)
     {
      LogManagementDecision(symbol, magic, pos_type_str, PROFILE_TREND_RUNNER, "HOLD", "trend_profit_below_trailing_threshold", positions_count, net_profit, age_seconds, "P-09/P-14");
      return;
     }

   double current_sl = 0;
   if(PositionSelectByTicket(tickets[0]))
      current_sl = PositionGetDouble(POSITION_SL);

   double proposed_sl_price = current_sl;
   if(!FindStructureSLTarget(symbol, target_type, current_sl, proposed_sl_price))
     {
      LogManagementDecision(symbol, magic, pos_type_str, PROFILE_TREND_RUNNER, "HOLD", "trend_no_structure_trailing_target", positions_count, net_profit, age_seconds, "P-10/P-11/P-15");
      return;
     }

   double weighted_avg_open_price = weighted_price_sum / total_volume;
   if(!IsSLProfitable(symbol, target_type, proposed_sl_price, weighted_avg_open_price, total_volume, total_commission, total_swap))
     {
      LogManagementDecision(symbol, magic, pos_type_str, PROFILE_TREND_RUNNER, "HOLD", "trend_sl_target_not_profitable", positions_count, net_profit, age_seconds, "P-12");
      return;
     }

   MovePositionsSL(symbol, magic, target_type, PROFILE_TREND_RUNNER, tickets, net_profit, age_seconds, proposed_sl_price, "TRAIL_SL", "trend_structure_trailing", "P-10/P-11/P-12/P-13");
  }

void ProcessBreakoutProtectPositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   int positions_count = ArraySize(tickets);
   if(positions_count <= 0 || total_volume <= 0)
      return;

   double total_commission = 0;
   double total_swap = 0;
   double net_profit = 0;
   CalculatePositionGroupCosts(symbol, tickets, total_profit, total_volume, total_commission, total_swap, net_profit);
   int age_seconds = (earliest_open_time > 0) ? (int)(TimeCurrent() - earliest_open_time) : 0;

   if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount / 2 && positions_count == 1))
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_BREAKOUT_PROTECT, tickets, net_profit, age_seconds, "severe_risk_guard", "P-05/P-06");
      return;
     }

   double weighted_avg_open_price = weighted_price_sum / total_volume;
   if(positions_count == 1 && age_seconds > 1800 && net_profit > 0)
     {
      MovePositionsSL(symbol, magic, target_type, PROFILE_BREAKOUT_PROTECT, tickets, net_profit, age_seconds, weighted_avg_open_price, "MOVE_SL", "breakout_time_stop_tighten", "P-13/P-15");
      return;
     }
   if(net_profit <= positions_count * InpBEProfitTarget / 2)
     {
      LogManagementDecision(symbol, magic, pos_type_str, PROFILE_BREAKOUT_PROTECT, "HOLD", "breakout_profit_below_protection_threshold", positions_count, net_profit, age_seconds, "P-09/P-14");
      return;
     }

   double current_sl = 0;
   if(PositionSelectByTicket(tickets[0]))
      current_sl = PositionGetDouble(POSITION_SL);

   double proposed_sl_price = current_sl;
   if(!FindStructureSLTarget(symbol, target_type, current_sl, proposed_sl_price))
     {
      LogManagementDecision(symbol, magic, pos_type_str, PROFILE_BREAKOUT_PROTECT, "HOLD", "breakout_no_structure_protection_target", positions_count, net_profit, age_seconds, "P-10/P-11/P-15");
      return;
     }
   if(!IsSLProfitable(symbol, target_type, proposed_sl_price, weighted_avg_open_price, total_volume, total_commission, total_swap))
     {
      LogManagementDecision(symbol, magic, pos_type_str, PROFILE_BREAKOUT_PROTECT, "HOLD", "breakout_sl_target_not_profitable", positions_count, net_profit, age_seconds, "P-12");
      return;
     }

   MovePositionsSL(symbol, magic, target_type, PROFILE_BREAKOUT_PROTECT, tickets, net_profit, age_seconds, proposed_sl_price, "TRAIL_SL", "breakout_structure_protection", "P-10/P-11/P-12/P-13");
  }

void ProcessBasketEscapePositionsByType(string symbol, long magic, ENUM_POSITION_TYPE target_type, const ulong &tickets[], double total_profit, double total_volume, double weighted_price_sum, datetime earliest_open_time)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   int positions_count = ArraySize(tickets);
   if(positions_count <= 0 || total_volume <= 0)
      return;

   double total_commission = 0;
   double total_swap = 0;
   double net_profit = 0;
   CalculatePositionGroupCosts(symbol, tickets, total_profit, total_volume, total_commission, total_swap, net_profit);
   int age_seconds = (earliest_open_time > 0) ? (int)(TimeCurrent() - earliest_open_time) : 0;

   if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount / 2 && positions_count == 1))
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_BASKET_ESCAPE, tickets, net_profit, age_seconds, "severe_risk_guard", "P-05/P-06");
      return;
     }
   if(positions_count >= 4 && net_profit > 0)
     {
      ClosePositionTickets(symbol, magic, pos_type_str, PROFILE_BASKET_ESCAPE, tickets, net_profit, age_seconds, "basket_recovery_profit", "P-07");
      return;
     }

   LogManagementDecision(symbol, magic, pos_type_str, PROFILE_BASKET_ESCAPE, "HOLD", "basket_wait_for_recovery", positions_count, net_profit, age_seconds, "P-07/P-08");
  }

void ProcessPositionsByType(string symbol,
                            long magic,
                            ENUM_POSITION_TYPE target_type,
                            const ulong &tickets[],
                            double total_profit,
                            double total_volume,
                            double weighted_price_sum,
                            datetime earliest_open_time)
  {
   bool profile_fallback = false;
   string profile = ResolveManagementProfile(magic, profile_fallback);
   if(profile_fallback)
     {
      string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
      int positions_count = ArraySize(tickets);
      int age_seconds = (earliest_open_time > 0) ? (int)(TimeCurrent() - earliest_open_time) : 0;
      LogManagementDecision(symbol, magic, pos_type_str, profile, "HOLD", "profile_fallback", positions_count, total_profit, age_seconds, "P-03/P-16");
     }

   if(profile == PROFILE_CONSERVATIVE)
      ProcessConservativePositionsByType(symbol, magic, target_type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time);
   else if(profile == PROFILE_TREND_RUNNER)
      ProcessTrendRunnerPositionsByType(symbol, magic, target_type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time);
   else if(profile == PROFILE_BREAKOUT_PROTECT)
      ProcessBreakoutProtectPositionsByType(symbol, magic, target_type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time);
   else if(profile == PROFILE_BASKET_ESCAPE)
      ProcessBasketEscapePositionsByType(symbol, magic, target_type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time);
   else
      ProcessLegacyPositionsByType(symbol, magic, target_type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time);
  }

//+------------------------------------------------------------------+
//| Manage profit/breakeven for configured provider positions        |
//+------------------------------------------------------------------+
void ManagePositionProfitBreakEvent()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long magic = PositionGetInteger(POSITION_MAGIC);
      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      if(magic == 0 || FindContextIndex(symbol) < 0)
         continue;

      // Group identity must include symbol, magic, and direction so strategies stay isolated.
      bool already_processed = false;
      for(int j = PositionsTotal() - 1; j > i; j--)
        {
         ulong previous_ticket = PositionGetTicket(j);
         if(previous_ticket == 0 || !PositionSelectByTicket(previous_ticket))
            continue;
         if(PositionGetString(POSITION_SYMBOL) == symbol &&
            PositionGetInteger(POSITION_MAGIC) == magic &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
           {
            already_processed = true;
            break;
           }
        }
      if(already_processed)
         continue;

      ulong tickets[];
      double total_profit = 0;
      double total_volume = 0;
      double weighted_price_sum = 0;
      datetime earliest_open_time = 0;

      for(int j = PositionsTotal() - 1; j >= 0; j--)
        {
         ulong group_ticket = PositionGetTicket(j);
         if(group_ticket == 0 || !PositionSelectByTicket(group_ticket))
            continue;
         if(PositionGetString(POSITION_SYMBOL) != symbol ||
            PositionGetInteger(POSITION_MAGIC) != magic ||
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)
            continue;

         double volume = PositionGetDouble(POSITION_VOLUME);
         double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
         int current_size = ArraySize(tickets);
         ArrayResize(tickets, current_size + 1);
         tickets[current_size] = group_ticket;
         total_profit += PositionGetDouble(POSITION_PROFIT);
         total_volume += volume;
         weighted_price_sum += open_price * volume;
         if(earliest_open_time == 0 || open_time < earliest_open_time)
            earliest_open_time = open_time;
        }

      ProcessPositionsByType(symbol, magic, type, tickets, total_profit, total_volume, weighted_price_sum, earliest_open_time);
     }
  }

//+------------------------------------------------------------------+
//| Hàm xử lý logic cho một nhóm lệnh đã được phân loại              |
//+------------------------------------------------------------------+
void DoDCA(int order_type_signal, string symbol, long magic)
  {
   string log_prefix = StringFormat("[DoDCA] [%s:%lld] ", symbol, magic);

   if(order_type_signal != 1 && order_type_signal != -1)
     {
      Print(log_prefix, "Invalid order signal: ", order_type_signal);
      return;
     }

   ENUM_POSITION_TYPE target_position_type = (order_type_signal == 1) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   string pos_type_str = (order_type_signal == 1) ? "BUY" : "SELL";

   double total_volume = 0;
   double total_profit = 0;
   double total_swap = 0;
   double net_profit = 0;
   int positions_of_type = 0;
   double weighted_price_sum = 0;
   double first_position_entry_price = 0;

   PositionInfo target_positions[];
   datetime earliest_open_time = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetString(POSITION_SYMBOL) == symbol &&
            PositionGetInteger(POSITION_MAGIC) == magic &&
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == target_position_type)
           {
            datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
            if(earliest_open_time == 0 || open_time < earliest_open_time)
               earliest_open_time = open_time;
            positions_of_type++;
            double volume = PositionGetDouble(POSITION_VOLUME);
            double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
            total_volume += volume;
            total_profit += PositionGetDouble(POSITION_PROFIT);
            total_swap += PositionGetDouble(POSITION_SWAP);
            weighted_price_sum += open_price * volume;

            int arr_size = ArraySize(target_positions);
            ArrayResize(target_positions, arr_size + 1);
            target_positions[arr_size].ticket = ticket;
            target_positions[arr_size].open_time = PositionGetInteger(POSITION_TIME);
            target_positions[arr_size].open_price = open_price;
           }
        }
     }

   net_profit = total_profit - total_swap - total_volume * commission_per_lot;

   if(positions_of_type == 0 || positions_of_type >= 4)
      return;

   Print(log_prefix, "Checking DCA conditions for ", pos_type_str);

   for(int i = 0; i < positions_of_type - 1; i++)
     {
      for(int j = 0; j < positions_of_type - i - 1; j++)
        {
         if(target_positions[j].open_time > target_positions[j + 1].open_time)
           {
            PositionInfo temp = target_positions[j];
            target_positions[j] = target_positions[j + 1];
            target_positions[j + 1] = temp;
           }
        }
     }
   first_position_entry_price = target_positions[0].open_price;

   if(net_profit >= -(positions_of_type * InpBEProfitTarget))
     {
      Print(log_prefix, "Net profit ", DoubleToString(net_profit, 2), " has not exceeded DCA loss threshold. Skip.");
      return;
     }

   int min_seconds_between_orders = 5 * 60;
   int max_seconds_between_orders = 2 * 60 * 60;
   if(positions_of_type >= 1)
      min_seconds_between_orders = 15 * 60;
   if(positions_of_type >= 2 && net_profit < -50)
      min_seconds_between_orders = 30 * 60;

   long last_order_time = target_positions[positions_of_type - 1].open_time;
   long time_elapsed_since_last = TimeCurrent() - last_order_time;
   if(time_elapsed_since_last < min_seconds_between_orders)
     {
      Print(log_prefix, StringFormat("Last order age %d seconds is below minimum. Skip.", time_elapsed_since_last));
      return;
     }
   if(time_elapsed_since_last > max_seconds_between_orders)
     {
      Print(log_prefix, StringFormat("Last order age %d seconds exceeds maximum. Skip.", time_elapsed_since_last));
      return;
     }

   if(positions_of_type == 3)
     {
      double entry_price_3 = target_positions[2].open_price;
      if(target_position_type == POSITION_TYPE_BUY)
        {
         double current_ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
         bool condition1_met = (current_ask > entry_price_3);
         datetime time_order_1 = (datetime)target_positions[0].open_time;
         datetime time_order_3 = (datetime)target_positions[2].open_time;
         int bar_index_1 = iBarShift(symbol, _Period, time_order_1);
         int bar_index_3 = iBarShift(symbol, _Period, time_order_3);
         bool condition2_met = false;
         if(bar_index_1 >= 0 && bar_index_3 >= 0)
           {
            int count1 = bar_index_1 - bar_index_3 + 1;
            int lowest_bar_index_1 = iLowest(symbol, _Period, MODE_LOW, count1, bar_index_3);
            double lowest_low_1 = iLow(symbol, _Period, lowest_bar_index_1);
            int count2 = bar_index_3 + 1;
            int lowest_bar_index_2 = iLowest(symbol, _Period, MODE_LOW, count2, 0);
            double lowest_low_2 = iLow(symbol, _Period, lowest_bar_index_2);
            condition2_met = (lowest_low_2 > lowest_low_1);
           }
         if(!condition1_met && !condition2_met)
           {
            Print(log_prefix, "Fourth BUY DCA conditions not met. Skip.");
            return;
           }
        }
      else
        {
         double current_bid = SymbolInfoDouble(symbol, SYMBOL_BID);
         bool condition1_met = (current_bid < entry_price_3);
         datetime time_order_1 = (datetime)target_positions[0].open_time;
         datetime time_order_3 = (datetime)target_positions[2].open_time;
         int bar_index_1 = iBarShift(symbol, _Period, time_order_1);
         int bar_index_3 = iBarShift(symbol, _Period, time_order_3);
         bool condition2_met = false;
         if(bar_index_1 >= 0 && bar_index_3 >= 0)
           {
            int count1 = bar_index_1 - bar_index_3 + 1;
            int highest_bar_index_1 = iHighest(symbol, _Period, MODE_HIGH, count1, bar_index_3);
            double highest_high_1 = iHigh(symbol, _Period, highest_bar_index_1);
            int count2 = bar_index_3 + 1;
            int highest_bar_index_2 = iHighest(symbol, _Period, MODE_HIGH, count2, 0);
            double highest_high_2 = iHigh(symbol, _Period, highest_bar_index_2);
            condition2_met = (highest_high_2 < highest_high_1);
           }
         if(!condition1_met && !condition2_met)
           {
            Print(log_prefix, "Fourth SELL DCA conditions not met. Skip.");
            return;
           }
        }
     }

   double volume_to_open = 0;
   if(positions_of_type == 1)
     {
      long time_elapsed_since_first = TimeCurrent() - target_positions[0].open_time;
      const long time_threshold = 15 * 60;
      volume_to_open = (time_elapsed_since_first > time_threshold) ? total_volume * 3 : total_volume * 2;
     }
   else
      volume_to_open = total_volume;

   double new_tp_price = 0;
   if(positions_of_type == 1)
     {
      double market_price = (target_position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_BID) : SymbolInfoDouble(symbol, SYMBOL_ASK);
      double tp_base_price = (first_position_entry_price + market_price) / 2.0;
      double future_total_volume = total_volume + volume_to_open;
      double point_size = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      double current_spread_in_points = (SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / point_size;
      double commission_cost_per_lot = commission_per_lot;
      if(!IsForexPair(symbol) && !(StringFind(symbol, "XAU") >= 0))
         commission_cost_per_lot = 0;
      double total_commission_cost = future_total_volume * commission_cost_per_lot;
      double total_spread_cost_in_money = total_commission_cost + current_spread_in_points * tick_value * future_total_volume;
      double tick_value_for_total_volume = future_total_volume * tick_value;
      double spread_cost_offset_in_price = 0;
      if(tick_value_for_total_volume > 0)
         spread_cost_offset_in_price = (total_spread_cost_in_money / tick_value_for_total_volume) * point_size;
      new_tp_price = (target_position_type == POSITION_TYPE_BUY) ? tp_base_price + spread_cost_offset_in_price : tp_base_price - spread_cost_offset_in_price;
     }
   else
     {
      double future_total_volume = total_volume + volume_to_open;
      double future_weighted_price_sum = weighted_price_sum;
      double current_price_for_new_order = (target_position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
      future_weighted_price_sum += current_price_for_new_order * volume_to_open;
      double breakeven_price = future_weighted_price_sum / future_total_volume;
      double commission_cost_per_lot = commission_per_lot;
      if(!IsForexPair(symbol) && !(StringFind(symbol, "XAU") >= 0))
         commission_cost_per_lot = 0;
      double total_commission_cost = future_total_volume * commission_cost_per_lot;
      double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      double point_size = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double current_spread_in_points = (SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / point_size;
      double total_spread_cost = current_spread_in_points * tick_value * future_total_volume;
      double total_cost = buffer_profit + total_commission_cost + total_spread_cost;
      double tick_value_for_total_volume = future_total_volume * tick_value;
      double total_cost_offset_in_price = 0;
      if(tick_value_for_total_volume > 0)
         total_cost_offset_in_price = (total_cost / tick_value_for_total_volume) * point_size;
      new_tp_price = (target_position_type == POSITION_TYPE_BUY) ? breakeven_price + total_cost_offset_in_price : breakeven_price - total_cost_offset_in_price;
     }

   int symbol_digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   new_tp_price = NormalizeDouble(new_tp_price, symbol_digits);

   double min_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   volume_to_open = MathMax(min_vol, MathMin(max_vol, volume_to_open));
   volume_to_open = MathFloor(volume_to_open / step_vol) * step_vol;
   volume_to_open = NormalizeDouble(volume_to_open, 2);

   if(volume_to_open < min_vol)
     {
      Print(log_prefix, "Calculated volume is below broker minimum. Skip.");
      return;
     }

   Print(log_prefix, "Opening ", pos_type_str, " DCA volume: ", DoubleToString(volume_to_open, 2));
   trade.SetExpertMagicNumber(magic);
   bool result = false;
   if(order_type_signal == 1)
      result = trade.Buy(volume_to_open, symbol, 0, 0, 0, "DCA Buy");
   else
      result = trade.Sell(volume_to_open, symbol, 0, 0, 0, "DCA Sell");

   if(result)
     {
      Print(log_prefix, "DCA order opened. Updating TP to ", DoubleToString(new_tp_price, symbol_digits));
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket))
           {
            if(PositionGetString(POSITION_SYMBOL) == symbol &&
               PositionGetInteger(POSITION_MAGIC) == magic &&
               (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == target_position_type)
              {
               double current_sl = PositionGetDouble(POSITION_SL);
               if(!trade.PositionModify(ticket, current_sl, new_tp_price))
                  Print(log_prefix, "TP modify failed for ticket ", ticket, ": ", trade.ResultComment());
              }
           }
        }
      Print(log_prefix, "DCA completed for ", pos_type_str, " at price ", DoubleToString((target_position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID), symbol_digits), ", TP=", DoubleToString(new_tp_price, symbol_digits));
     }
   else
      Print(log_prefix, "DCA order failed. Error: ", (string)GetLastError(), " - ", trade.ResultComment());
  }

//+------------------------------------------------------------------+
//| Scan H1 CISD state needed by provider-local DCA gate               |
//+------------------------------------------------------------------+
void UpdateCISDDCAH1State(string symbol, CISDDCAState &state)
  {
   int h1_bars = Bars(symbol, PERIOD_H1);
   if(h1_bars < 3)
      return;

   int signalType = 0;
   datetime signalTime = 0;
   for(int i = 1; i < MathMin(h1_bars - 1, 24); i++)
     {
      bool isBearish = iClose(symbol, PERIOD_H1, i) < iOpen(symbol, PERIOD_H1, i);
      bool wasBullish = iClose(symbol, PERIOD_H1, i + 1) > iOpen(symbol, PERIOD_H1, i + 1);
      if(isBearish && wasBullish)
        {
         double level = iOpen(symbol, PERIOD_H1, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(symbol, PERIOD_H1, k) > level)
              {
               signalType = 1;
               signalTime = iTime(symbol, PERIOD_H1, k);
               break;
              }
           }
        }
      if(signalType != 0)
         break;

      bool isBullish = iClose(symbol, PERIOD_H1, i) > iOpen(symbol, PERIOD_H1, i);
      bool wasBearish = iClose(symbol, PERIOD_H1, i + 1) < iOpen(symbol, PERIOD_H1, i + 1);
      if(isBullish && wasBearish)
        {
         double level = iOpen(symbol, PERIOD_H1, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(symbol, PERIOD_H1, k) < level)
              {
               signalType = -1;
               signalTime = iTime(symbol, PERIOD_H1, k);
               break;
              }
           }
        }
      if(signalType != 0)
         break;
     }

   if(signalType != state.previous_h1_signalType || signalTime != state.h1_signalTime)
     {
      state.last_trade_signal_time = 0;
      state.previous_h1_signalType = signalType;
     }

   state.h1_signalType = signalType;
   state.h1_signalTime = signalTime;
   state.ltf_scan_start_time = (signalTime > 0) ? signalTime + PeriodSeconds(PERIOD_H1) : 0;
  }

//+------------------------------------------------------------------+
//| Find active strategy magic for a scoped DCA group                 |
//+------------------------------------------------------------------+
long FindDCAMagicForSymbolDirection(string symbol, ENUM_POSITION_TYPE position_type)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == symbol &&
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == position_type)
         return PositionGetInteger(POSITION_MAGIC);
     }
   return 0;
  }

//+------------------------------------------------------------------+
//| Provider-local CISD confirmation gate for DoDCA                   |
//+------------------------------------------------------------------+
void CheckDCAEntryConditionFromCISD(string symbol, CISDDCAState &state)
  {
   UpdateCISDDCAH1State(symbol, state);
   if(state.h1_signalType == 0 || state.ltf_scan_start_time == 0 || TimeCurrent() < state.ltf_scan_start_time)
      return;

   int start_bar = 12;
   if(state.h1_signalTime != state.current_h1_signal_time)
     {
      start_bar = iBarShift(symbol, _Period, state.h1_signalTime);
      if(start_bar < 0)
         start_bar = Bars(symbol, _Period) - 1;
      state.bull_setup.active = false;
      state.bear_setup.active = false;
      state.current_h1_signal_time = state.h1_signalTime;
     }
   else
     {
      datetime scan_start_time = 0;
      if(state.h1_signalType == 1 && state.bear_setup.active)
         scan_start_time = state.bear_setup.setupTime;
      else
         if(state.h1_signalType == -1 && state.bull_setup.active)
            scan_start_time = state.bull_setup.setupTime;
      if(scan_start_time > 0)
        {
         start_bar = iBarShift(symbol, _Period, scan_start_time);
         if(start_bar < 0)
            start_bar = 12;
        }
     }

   int sub_bars = Bars(symbol, _Period);
   if(sub_bars < start_bar + 2)
      return;

   for(int i = start_bar; i >= 1; i--)
     {
      double close_i = iClose(symbol, _Period, i);
      datetime time_i = iTime(symbol, _Period, i);

      if(state.bear_setup.active && close_i > state.bear_setup.priceLevel)
        {
         if(i == 1 && time_i > state.last_trade_signal_time)
           {
            long magic = FindDCAMagicForSymbolDirection(symbol, POSITION_TYPE_BUY);
            if(magic != 0)
              {
               state.last_trade_signal_time = time_i;
               DoDCA(1, symbol, magic);
              }
           }
         state.bear_setup.active = false;
        }

      if(state.bull_setup.active && close_i < state.bull_setup.priceLevel)
        {
         if(i == 1 && time_i > state.last_trade_signal_time)
           {
            long magic = FindDCAMagicForSymbolDirection(symbol, POSITION_TYPE_SELL);
            if(magic != 0)
              {
               state.last_trade_signal_time = time_i;
               DoDCA(-1, symbol, magic);
              }
           }
         state.bull_setup.active = false;
        }

      double open_i = iOpen(symbol, _Period, i);
      bool isBullish_i = close_i > open_i;
      bool isBearish_i = close_i < open_i;
      bool wasBearish_ip1 = (i + 1 < sub_bars) ? (iClose(symbol, _Period, i + 1) < iOpen(symbol, _Period, i + 1)) : false;
      bool wasBullish_ip1 = (i + 1 < sub_bars) ? (iClose(symbol, _Period, i + 1) > iOpen(symbol, _Period, i + 1)) : false;

      if(state.h1_signalType == -1 && isBullish_i && wasBearish_ip1)
        {
         state.bull_setup.active = true;
         state.bull_setup.priceLevel = open_i;
         state.bull_setup.setupTime = time_i;
        }
      if(state.h1_signalType == 1 && isBearish_i && wasBullish_ip1)
        {
         state.bear_setup.active = true;
         state.bear_setup.priceLevel = open_i;
         state.bear_setup.setupTime = time_i;
        }
     }
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
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Reject OPEN_ORDER: cmd_id=%s symbol=%s reason=SYMBOL_NOT_ALLOWED", cmdId, symbol);
      // SendNACK(cmdId, "SYMBOL_NOT_ALLOWED");
      return;
     }

// Reject history cooldown before ACK/order side effects
   datetime cooldownUntil = 0;
   if(IsHistoryCooldownActive(symbol, magic, direction, cooldownUntil))
     {
      PrintFormat("[HistoryCooldown] Reject OPEN_ORDER cmd_id=%s symbol=%s magic=%lld direction=%s until=%s reason=HISTORY_COOLDOWN_ACTIVE",
                  cmdId, symbol, magic, direction, TimeToString(cooldownUntil, TIME_DATE | TIME_SECONDS));
      SendNACK(cmdId, "HISTORY_COOLDOWN_ACTIVE");
      return;
     }

// Reject duplicate active strategy order on the same symbol and side before ACK/order side effects
   ENUM_POSITION_TYPE requested_position_type = (direction == "BUY") ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) == symbol &&
         PositionGetInteger(POSITION_MAGIC) == magic &&
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == requested_position_type)
        {
         if(InpDebugMode)
            PrintFormat("[AureusProvider] Reject OPEN_ORDER: cmd_id=%s symbol=%s magic=%lld side=%s existing_position=%llu reason=STRATEGY_ORDER_EXISTS",
                        cmdId, symbol, magic, direction, ticket);
         SendNACK(cmdId, "STRATEGY_ORDER_EXISTS");
         return;
        }
     }

   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(!OrderSelect(ticket))
         continue;

      ENUM_ORDER_TYPE existing_order_type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      bool existing_order_same_side = false;
      if(direction == "BUY")
         existing_order_same_side = (existing_order_type == ORDER_TYPE_BUY_LIMIT ||
                                     existing_order_type == ORDER_TYPE_BUY_STOP ||
                                     existing_order_type == ORDER_TYPE_BUY_STOP_LIMIT);
      else
         existing_order_same_side = (existing_order_type == ORDER_TYPE_SELL_LIMIT ||
                                     existing_order_type == ORDER_TYPE_SELL_STOP ||
                                     existing_order_type == ORDER_TYPE_SELL_STOP_LIMIT);

      if(OrderGetString(ORDER_SYMBOL) == symbol &&
         OrderGetInteger(ORDER_MAGIC) == magic &&
         existing_order_same_side)
        {
         if(InpDebugMode)
            PrintFormat("[AureusProvider] Reject OPEN_ORDER: cmd_id=%s symbol=%s magic=%lld side=%s existing_order=%llu type=%lld reason=STRATEGY_ORDER_EXISTS",
                        cmdId, symbol, magic, direction, ticket, OrderGetInteger(ORDER_TYPE));
         SendNACK(cmdId, "STRATEGY_ORDER_EXISTS");
         return;
        }
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

         DoDCA(direction == "BUY" ? 1 : -1, symbol, magic);
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
      if(InpDebugMode)
         PrintFormat("[AureusProvider] Reject CLOSE_ORDER: cmd_id=%s symbol=%s reason=SYMBOL_NOT_ALLOWED", cmdId, symbol);
      // SendNACK(cmdId, "SYMBOL_NOT_ALLOWED");
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
      double commission   = 0.0;
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
//| Process one complete command from Gateway                         |
//+------------------------------------------------------------------+
void ProcessSingleCommand(const string &raw)
  {
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
//| Listen and process commands from Gateway                           |
//+------------------------------------------------------------------+
void ProcessIncomingCommands()
  {
   if(!g_socket.IsConnected())
      return;

   string raw = g_socket.Receive();
   if(raw == "")
      return;

   int depth = 0;
   int startPos = -1;
   int processed = 0;
   bool inString = false;
   bool escaped = false;
   int rawLen = StringLen(raw);

   for(int i = 0; i < rawLen; i++)
     {
      ushort ch = StringGetCharacter(raw, i);

      if(inString)
        {
         if(escaped)
           {
            escaped = false;
            continue;
           }
         if(ch == '\\')
           {
            escaped = true;
            continue;
           }
         if(ch == '"')
            inString = false;
         continue;
        }

      if(ch == '"')
        {
         inString = true;
         continue;
        }

      if(ch == '{')
        {
         if(depth == 0)
            startPos = i;
         depth++;
         continue;
        }

      if(ch == '}' && depth > 0)
        {
         depth--;
         if(depth == 0 && startPos >= 0)
           {
            string command = StringSubstr(raw, startPos, i - startPos + 1);
            ProcessSingleCommand(command);
            processed++;
            startPos = -1;
           }
        }
     }

   if(processed > 1)
      PrintFormat("[AureusProvider] Processed %d commands from one socket read", processed);
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

   ApplyCloseDealToHistoryCooldown(trans.deal, "realtime");

// Must be connected to push events
   if(!g_socket.IsConnected())
      return;

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

//--- Provider-safe profit/breakeven management for ALL configured symbols
   ManagePositionProfitBreakEvent();

//--- Provider-local CISD DCA gate for ALL configured symbols
   for(int i = 0; i < g_symbolCount; i++)
     {
      CheckDCAEntryConditionFromCISD(g_contexts[i].symbol, g_cisdDCAStates[i]);
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
