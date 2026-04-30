//+------------------------------------------------------------------+
//|                                                      ProjectName |
//|                                      Copyright 2020, CompanyName |
//|                                       http://www.companyname.net |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, FAI.ABC PrivateGPT"
#property link "https://fai.abc"
#property version "6.48"
#property description "Optimizes H4 drawing logic to prevent terminal freeze on recompile/initialization."

#include <Arrays/ArrayString.mqh>
#include <Trade/Trade.mqh>
#include <Arrays/ArrayObj.mqh>

//==================================================================
// SECTION 1: ENUMS, STRUCTS, AND GLOBAL VARIABLES
//==================================================================
enum ENUM_LANGUAGE
  {
   VIETNAMESE,
   ENGLISH
  };
enum ENUM_ARROW_STYLE
  {
   ARROW_Arrow,
   ARROW_Dot
  };

struct SetupInfo
  {
   bool              active;
   double            priceLevel;
   datetime          setupTime;
  };
struct TrendAnalysisResult
  {
   int               close_state, ema_state;
   double            close_slope, ema_slope;
   string            close_status_text, ema_status_text;
   color             close_color, ema_color;
   string            market_diagnosis_text;
   color             market_diagnosis_color;
  };
struct TranslationStrings
  {
   string            short_term, long_term, close, ema, market;
   string            fomo_up, fomo_down, breakout_up, breakout_down;
   string            strong_trend_up, strong_trend_down, has_trend_up, has_trend_down, sideways;
   string            level_p3, level_p2, level_p1, level_0, level_n1, level_n2, level_n3;
  };
struct TradeSignalInfo
  {
   int               signal;
   double            stopLossLevel;
   double            ltf_cisd_close;
  };
struct CustomCandleInfo
  {
   double            open;
   double            high;
   double            low;
   double            close;
   datetime          openTime;
  };
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
class RangeInfo : public CObject
  {
public:
   bool              isActive;
   double            high;
   double            low;
   datetime          rangeStartTime;
   datetime          rangeEndTime;
   string            timeframeLabel;
   string            breakoutDirection;
   double            breakoutPrice;
  };

//+------------------------------------------------------------------+
//| Class để tính toán Stochastic một cách tối ưu, cập nhật real-time |
//+------------------------------------------------------------------+
class CStochasticOptimizer
  {
private:
   //--- Tham số của chỉ báo
   string            m_symbol;
   ENUM_TIMEFRAMES   m_timeframe;
   int               m_k_period;
   int               m_d_period;
   int               m_slowing;

   //--- Biến trạng thái
   bool              m_is_initialized;
   datetime          m_last_bar_time; // Thời gian của cây nến cuối cùng được tính toán lịch sử

   //--- Buffer dữ liệu (cache)
   double            m_high[];
   double            m_low[];
   double            m_close[];
   double            m_raw_k_buffer[];
   double            m_final_k_buffer[];

   //--- Hàm tính toán lịch sử (chỉ chạy khi có nến mới)
   bool              UpdateHistoricalCalculations();

public:
                     CStochasticOptimizer(); // Constructor
   bool              Init(string symbol, ENUM_TIMEFRAMES timeframe, int k_period, int d_period, int slowing);
   bool              Calculate(double &k_value_out, double &d_value_out);
  };

//--- Constructor: Khởi tạo giá trị mặc định
CStochasticOptimizer::CStochasticOptimizer() : m_is_initialized(false), m_last_bar_time(0)
  {
  }

//--- Init: Thiết lập các tham số cho chỉ báo
bool CStochasticOptimizer::Init(string symbol, ENUM_TIMEFRAMES timeframe, int k_period, int d_period, int slowing)
  {
   m_symbol = symbol;
   m_timeframe = timeframe;
   m_k_period = k_period;
   m_d_period = d_period;
   m_slowing = slowing;

// Sắp xếp các mảng dữ liệu
   ArraySetAsSeries(m_high, true);
   ArraySetAsSeries(m_low, true);
   ArraySetAsSeries(m_close, true);
   ArraySetAsSeries(m_raw_k_buffer, true);
   ArraySetAsSeries(m_final_k_buffer, true);

   m_is_initialized = true;
   return true;
  }

//--- Hàm chính được gọi trong OnTick
bool CStochasticOptimizer::Calculate(double &k_value_out, double &d_value_out)
  {
   if(!m_is_initialized)
      return false;

//--- Lấy thời gian của cây nến hiện tại trên khung thời gian đích
   datetime current_bar_time = (datetime)SeriesInfoInteger(m_symbol, m_timeframe, SERIES_LASTBAR_DATE);

//--- Nếu có nến mới, tính toán lại toàn bộ lịch sử
   if(current_bar_time > m_last_bar_time)
     {
      if(!UpdateHistoricalCalculations())
         return false;
      m_last_bar_time = current_bar_time;
     }

//--- Cập nhật real-time cho cây nến hiện tại (index 0)
   MqlTick last_tick;
   SymbolInfoTick(m_symbol, last_tick);
   double current_price = last_tick.last;
   if(current_price == 0)
      current_price = last_tick.bid;

// Cập nhật giá của nến 0
   m_close[0] = current_price;
   if(current_price > m_high[0])
      m_high[0] = current_price;
   if(current_price < m_low[0])
      m_low[0] = current_price;

//--- Chỉ tính toán lại các giá trị cho nến 0
// 1. Tính %K thô cho nến 0
   double highest_high = 0;
   double lowest_low = 999999;
   for(int i = 0; i < m_k_period; i++)
     {
      if(m_high[i] > highest_high)
         highest_high = m_high[i];
      if(m_low[i] < lowest_low)
         lowest_low = m_low[i];
     }
   double range = highest_high - lowest_low;
   m_raw_k_buffer[0] = (range > 0) ? 100 * (m_close[0] - lowest_low) / range : 50;

// 2. Tính %K cuối cùng cho nến 0 (làm mượt %K thô)
   double sum_k = 0;
   for(int i = 0; i < m_slowing; i++)
     {
      sum_k += m_raw_k_buffer[i];
     }
   m_final_k_buffer[0] = sum_k / m_slowing;

// 3. Tính %D cho nến 0 (làm mượt %K cuối cùng)
   double sum_d = 0;
   for(int i = 0; i < m_d_period; i++)
     {
      sum_d += m_final_k_buffer[i];
     }

// Gán giá trị đầu ra
   k_value_out = m_final_k_buffer[0];
   d_value_out = sum_d / m_d_period;

   return true;
  }


//--- Hàm tính toán lại lịch sử (chỉ chạy khi có nến mới)
bool CStochasticOptimizer::UpdateHistoricalCalculations()
  {
   int bars_needed = m_k_period + m_d_period + m_slowing + 5;

// Lấy dữ liệu giá mới
   if(CopyHigh(m_symbol, m_timeframe, 0, bars_needed, m_high) < bars_needed ||
      CopyLow(m_symbol, m_timeframe, 0, bars_needed, m_low) < bars_needed ||
      CopyClose(m_symbol, m_timeframe, 0, bars_needed, m_close) < bars_needed)
     {
      Print("Lỗi không thể lấy đủ dữ liệu giá để tính toán lịch sử Stochastic.");
      return false;
     }

// Thay đổi kích thước buffer tính toán
   ArrayResize(m_raw_k_buffer, bars_needed);
   ArrayResize(m_final_k_buffer, bars_needed);

//--- Tính toán cho toàn bộ các cây nến đã có trong buffer
// Bắt đầu từ nến cũ nhất để các giá trị sau đó có thể dựa vào
   for(int i = bars_needed - m_k_period; i >= 0; i--)
     {
      // 1. Tính %K thô
      double highest_high = 0;
      double lowest_low = 999999;
      for(int j = 0; j < m_k_period; j++)
        {
         if(m_high[i+j] > highest_high)
            highest_high = m_high[i+j];
         if(m_low[i+j] < lowest_low)
            lowest_low = m_low[i+j];
        }
      double range = highest_high - lowest_low;
      m_raw_k_buffer[i] = (range > 0) ? 100 * (m_close[i] - lowest_low) / range : 50;
     }

// 2. Tính %K cuối cùng
   for(int i = bars_needed - m_k_period - m_slowing; i >= 0; i--)
     {
      double sum = 0;
      for(int j = 0; j < m_slowing; j++)
        {
         sum += m_raw_k_buffer[i+j];
        }
      m_final_k_buffer[i] = sum / m_slowing;
     }

   return true;
  }

// Enum để định nghĩa đường đi của giá
enum ENUM_CANDLE_PATH
  {
   PATH_UNKNOWN, // Không xác định được
   PATH_OHLC,    // Đỉnh (High) được tạo trước Đáy (Low)
   PATH_OLHC,    // Đáy (Low) được tạo trước Đỉnh (High)
   PATH_WHIPSAW  // Biến động hai chiều mạnh (chưa triển khai, có thể thêm sau)
  };

// Enum để định nghĩa thân nến
enum ENUM_CANDLE_BODY
  {
   BODY_UNKNOWN,
   BODY_BULLISH, // Nến tăng (Close > Open)
   BODY_BEARISH, // Nến giảm (Close < Open)
   BODY_DOJI     // Nến Doji/trung tính (Close ≈ Open)
  };

// Struct để chứa kết quả phân tích
struct CandleAnalysisResult
  {
   ENUM_CANDLE_PATH  path;
   ENUM_CANDLE_BODY  body;
   string            description;
  };

enum ENUM_SETUP_FAMILY
  {
   SETUP_FAMILY_NONE,

// --- Họ kịch bản MUA ---
   SETUP_FAMILY_BUY_STRONG_TREND_PULLBACK,
   SETUP_FAMILY_BUY_TREND_MOMENTUM,
   SETUP_FAMILY_BUY_BREAKOUT_CONFIRMATION,
   SETUP_FAMILY_BUY_BREAKOUT_RANGE,
   SETUP_FAMILY_BUYLIMIT_BREAKOUT_RANGE,
   SETUP_FAMILY_BUY_CISD,
   SETUP_FAMILY_BUY_CISD_PULLBACK,
   SETUP_FAMILY_BUY_CISD_FLOW_TREND,

// --- Họ kịch bản BÁN ---
   SETUP_FAMILY_SELL_STRONG_TREND_PULLBACK,
   SETUP_FAMILY_SELL_TREND_MOMENTUM,
   SETUP_FAMILY_SELL_BREAKOUT_CONFIRMATION,
   SETUP_FAMILY_SELL_BREAKOUT_RANGE,
   SETUP_FAMILY_SELLLIMIT_BREAKOUT_RANGE,
   SETUP_FAMILY_SELL_CISD,
   SETUP_FAMILY_SELL_CISD_PULLBACK,
   SETUP_FAMILY_SELL_CISD_FLOW_TREND,

// NHÓM A: STATIC PATTERNS
   SETUP_FAMILY_BUY_CISD_CONSOLIDATION_H1,
   SETUP_FAMILY_SELL_CISD_CONSOLIDATION_H1,
// NHÓM B: CONTEXTUAL COMPRESSION
   SETUP_FAMILY_BUY_CISD_COMPRESSION_M15_FLAG,
   SETUP_FAMILY_BUY_CISD_COMPRESSION_M15_QUIET,
   SETUP_FAMILY_SELL_CISD_COMPRESSION_M15_FLAG,
   SETUP_FAMILY_SELL_CISD_COMPRESSION_M15_QUIET,
// NHÓM C: REAL-TIME ENTRIES
   SETUP_FAMILY_BUY_CISD_RT_EARLY_BREAK,
   SETUP_FAMILY_BUY_CISD_RT_PULLBACK_M30,
   SETUP_FAMILY_BUY_CISD_RT_BUILDUP_M15,
   SETUP_FAMILY_SELL_CISD_RT_EARLY_BREAK,
   SETUP_FAMILY_SELL_CISD_RT_PULLBACK_M30,
   SETUP_FAMILY_SELL_CISD_RT_BUILDUP_M15
  };

// Cấu trúc dữ liệu hoàn chỉnh, chứa tất cả thông tin phân tích cho một tín hiệu
struct SignalAnalysis
  {
   // --- Thông tin cơ bản ---
   int               signal;            // 1 = Bullish, -1 = Bearish, 0 = No Signal
   string            signal_type;    // "Bullish" hoặc "Bearish"
   datetime          signal_time;  // Thời gian của nến xác nhận
   double            ltf_cisd_price; // Giá đóng cửa của nến xác nhận
   double            stoploss_level; // Mức Stop Loss đề xuất
   double            breakout_level; // Mức Entry Breakout đề xuất

   // --- Phân tích cấu trúc nến ---
   CandleAnalysisResult daily_analysis;
   CandleAnalysisResult yesterday_analysis;
   CandleAnalysisResult h1_analysis;

   // --- CHECKLIST HỢP LƯU & ĐIỀU KIỆN (Dạng Y/N như bạn yêu cầu) ---
   bool              is_h1_range_breakout;
   bool              is_h4_range_breakout;

   // Checklist "Other Conditions"
   bool              is_daily_body_aligned; // Nến D1 có cùng màu với tín hiệu không?
   bool              is_h1_cisd_aligned;    // H1 CISD có cùng chiều D.Open không?
   bool              is_ltf_cisd_aligned;   // LTF CISD có cùng chiều D.Open không?
   bool              is_d1_path_aligned;    // D1 Path có thuận theo tín hiệu không?
   bool              is_h1_path_aligned;    // H1 Path có thuận theo tín hiệu không?
  };


//+------------------------------------------------------------------+
//| Cấu trúc (Struct) để lưu trữ thông tin của một giao dịch đã đóng   |
//+------------------------------------------------------------------+
struct TradeHistoryInfo
  {
   long              position_id;      // ID của vị thế
   ENUM_ORDER_TYPE   type;             // Loại lệnh (BUY hoặc SELL)
   double            volume;           // Khối lượng
   datetime          open_time;        // Thời gian mở lệnh
   double            open_price;       // Giá mở lệnh
   datetime          close_time;       // Thời gian đóng lệnh
   double            close_price;      // Giá đóng lệnh
   double            profit;           // Lợi nhuận
   double            commission;       // Phí hoa hồng
   double            swap;             // Phí qua đêm
   ENUM_DEAL_REASON  close_reason;     // Lý do đóng lệnh (TP, SL, Manual, etc.)
   long              entry_deal_ticket; // Ticket của deal vào lệnh
   long              exit_deal_ticket;  // Ticket của deal thoát lệnh
  };

struct ZigZagPoint
  {
   int               index;
   double            price;
   datetime          time;
   string            type;
   bool              isHigh;
   bool              isCHOCH;
   string            chochType;
   datetime          chochBreakoutTime;
   int               chochConfirmingPointIndex;
   int               chochZoneBasePointIndex;
  };
//--- Global Variables for State Management
static ZigZagPoint prev_points[];
static ZigZagPoint g_processed_points[];
static int         g_nPoints = 0;
//--- Global Variables
TranslationStrings T;
CTrade trade;
CArrayString g_managed_objects;
CArrayObj *g_historical_ranges;
int g_h1_signalType = 0, g_m30_signalType = 0, g_m15_signalType = 0, g_m5_signalType = 0, g_m1_signalType = 0, g_previous_h1_signalType = 0;
double g_h1_breakoutPrice = 0;
bool g_h1_signal_active = false, g_h1_buy_signal_active = false, g_h1_sell_signal_active = false, g_m30_signal_active = false, g_m30_buy_signal_active = false, g_m30_sell_signal_active = false, g_m5_signal_active = false;
datetime g_h1_signalTime = 0, g_m30_signalTime = 0, g_buy_signal_active_time = 0, g_sell_signal_active_time = 0;
TrendAnalysisResult g_short_term, g_long_term;
datetime g_last_h1_alert_time = 0, g_ltf_scan_start_time = 0, g_last_trade_signal_time = 0;
datetime g_last_h1_processed_bar_time = 0, g_last_m30_processed_bar_time = 0, g_last_m5_processed_bar_time = 0, g_last_m1_processed_bar_time = 0;
datetime g_last_processed_bar_time = 0;
datetime g_last_st_breakout_alert_time[3], g_last_lt_breakout_alert_time[3];
double g_daily_percent = 0.0, g_h4_percent = 0.0, g_h1_percent = 0.0, g_m30_percent = 0.0, g_m15_percent = 0.0, g_m5_percent = 0.0;
double g_daily_pre_percent = 0.0, g_h4_pre_percent = 0.0, g_h1_pre_percent = 0.0, g_m30_pre_percent = 0.0, g_m15_pre_percent = 0.0;
double g_h1_pre_pre_percent;
double g_m30_pre_pre_percent;
double g_m15_pre_pre_percent;
// Mảng chứa % của 4 nến M15 đã đóng cửa gần nhất (M15[1] -> M15[4])
double g_m15_last4_percents[4];

int EmaHandle, AtrHandle;
color c_level_colors[7];
#define RANGE_DIAGNOSIS 0
#define RANGE_PRICE 1
#define RANGE_EMA 2
RangeInfo g_st_ranges[3], g_lt_ranges[3];

const string G_OBJECT_PREFIX = "FAI_EA_";
#define OBJ_ID_SLOPE_PANEL_SHORT "SlopePanel_ShortTerm"
#define OBJ_ID_SLOPE_PANEL_LONG "SlopePanel_LongTerm"
#define OBJ_ID_SLOPE_PANEL_CLOSE "SlopePanel_CloseDetail"
#define OBJ_ID_SLOPE_PANEL_EMA "SlopePanel_EMADetail"
#define OBJ_ID_SLOPE_PANEL_DAILY "SlopePanel_Daily"
#define OBJ_ID_SLOPE_PANEL_H4 "SlopePanel_H4"
#define OBJ_ID_SLOPE_PANEL_H1 "SlopePanel_H1"
#define OBJ_ID_SLOPE_PANEL_M30 "SlopePanel_M30"
#define OBJ_ID_SLOPE_PANEL_M15 "SlopePanel_M15"
#define OBJ_ID_SLOPE_PANEL_M5 "SlopePanel_M5"
#define OBJ_ID_SLOPE_PANEL_YESTERDAY_Pre "SlopePanel_Yesterday"
#define OBJ_ID_SLOPE_PANEL_H4_Pre "SlopePanel_H4_Pre"
#define OBJ_ID_SLOPE_PANEL_H1_Pre "SlopePanel_H1_Pre"
#define OBJ_ID_SLOPE_PANEL_M30_Pre "SlopePanel_M30_Pre"
#define OBJ_ID_SLOPE_PANEL_M15_Pre "SlopePanel_M15_Pre"
#define OBJ_ID_SLOPE_PANEL_STOCH_D2 "SlopePanel_Stoch_D2"
#define OBJ_ID_SLOPE_PANEL_STOCH_D1 "SlopePanel_Stoch_D1"
#define OBJ_ID_SLOPE_PANEL_STOCH_4H "SlopePanel_Stoch_4H"
#define OBJ_ID_SLOPE_PANEL_STOCH_1H "SlopePanel_Stoch_1H"
#define OBJ_ID_H1_PRIMARY_LINE "H1PrimaryLine"
#define OBJ_ID_H1_PRIMARY_LABEL "H1PrimaryLabel"
#define OBJ_ID_DAILY_OPEN_LINE "DailyOpenLine"
#define OBJ_ID_DAILY_GAP_RECT "DailyGapRect"
#define OBJ_ID_SLOPE_PANEL_H1_CISD "SlopePanel_H1_CISD"
#define OBJ_ID_SLOPE_PANEL_M30_CISD "SlopePanel_M30_CISD"
#define OBJ_ID_SLOPE_PANEL_M15_CISD "SlopePanel_M15_CISD"
#define OBJ_ID_SLOPE_PANEL_M5_CISD "SlopePanel_M5_CISD"

//==================================================================
// SECTION 2: INPUT PARAMETERS
//==================================================================
input group "EA Trading Settings";
input bool InpEnableTrading = true; // Enable Trading
input ulong InpMagicNumber = 13579; // Magic Number
input double InpRiskAmount = 10.0;  // Risk Amount per Trade ($)
double InpRRRatio = 1.5;            // Reward/Risk Ratio (e.g., 1.0 for 1:1)
input int InpMaxSpreadPoints = 50;  // Max Spread to Allow Trading (in Points)
input int InpStopLossBufferPips = 1;
input int InpStopLossMaxInPips = 15;
input bool InpAllowOneTrade = true; // Allow Only One Trade at a Time
input group "CISD Strategy Timeframes";
ENUM_TIMEFRAMES InpPrimaryTimeframe = PERIOD_M30; // Primary Setup Timeframe
input group "Primary (H1) Line Style";
input bool InpShowH1Line = true;
input bool InpShowH1Label = false;
input bool InpShowH1CISD = true; // Show H1 CISD Status on Panel
input string InpH1LineLabelText = "H1 Level";
input color InpH1BullColor = clrCyan;
input color InpH1BearColor = clrOrangeRed;
input int InpH1LineWidth = 1;
input ENUM_LINE_STYLE InpH1LineStyle = STYLE_DASHDOTDOT;
input group "Confirmation (LTF) Signal Style";
input bool InpShowLTFLines = true;
input bool InpShowLTFLabels = false;
input bool InpShowLTFArrows = true;                  // Show Arrows on LTF Signal
input ENUM_ARROW_STYLE InpLTFArrowStyle = ARROW_Dot; // LTF Signal Symbol Style
input color InpBullColor = clrCyan;
input color InpBearColor = clrRed;
input int InpLTFLineWidth = 1;
input ENUM_LINE_STYLE InpInitialConfirmationStyle = STYLE_DASHDOT;
input ENUM_LINE_STYLE InpContinuationConfirmationStyle = STYLE_DASH;
input group "Alert Settings";
input bool InpEnableAlerts = true;
input bool InpAlertPopup = true;
input bool InpAlertPush = true;
input bool InpAlertEmail = false;
input bool InpAlertSound = true;
input string InpSoundFile = "alert2.wav";
input int InpAlertCooldownSeconds = 300;
input group "Telegram Settings";
input bool InpEnableTelegram = true;
input bool InpEnableTelegramDebug = false;
input string InpTelegramBotToken = "6222743350:AAHMnAup6KNfkwQfBgG0FlXlxhvD0I3d6Ps"; // Telegram: Bot Token
input string InpTelegramChatID = "2097632662";                                       // Telegram: Chat ID
input int InpTimeOffsetHours = 3;
input bool InpSendScreenshotOnSignal = true;
input int InpScreenshotWidth = 1280;
input int InpScreenshotHeight = 720;
input int InpCISDFontSize = 10;
input group "Slope Analysis Panel";
input ENUM_LANGUAGE InpLanguage = ENGLISH;
input bool InpShowShortTermStatus = true;
input bool InpShowLongTermStatus = true;
input bool InpShowDailyStatus = true; // Show Daily Candle Status
input bool InpShowH1Status = true;    // Show Daily Candle Status
input bool InpShowCloseDetails = true;
input bool InpShowEmaDetails = true;
input int InpPanelFontSize = 10;
input int InpPanelXDistance = 10;
int InpPanelYDistance = 20;
input int InpPanelLineSpacing = 20;
input group "Slope: General Indicator Settings";
input int InpEmaPeriod = 21;
input ENUM_APPLIED_PRICE InpEmaAppliedPrice = PRICE_CLOSE;
input int InpAtrPeriod = 14;
input double InpFomoThresholdAtr = 2.0;
input group "Slope: Short-Term Settings";
input int InpRegressionPeriod_Short = 60;
input double InpLastBarWeight_Short = 15.0;
input double InpThreshold_Close_L1_Short = 0.005;
input double InpThreshold_Close_L2_Short = 0.01;
input double InpThreshold_Close_L3_Short = 0.015;
input double InpThreshold_EMA_L1_Short = 0.003;
input double InpThreshold_EMA_L2_Short = 0.007;
input double InpThreshold_EMA_L3_Short = 0.01;
input group "Slope: Long-Term Settings";
input int InpRegressionPeriod_Long = 240;
input double InpLastBarWeight_Long = 15.0;
input double InpThreshold_Close_L1_Long = 0.005;
input double InpThreshold_Close_L2_Long = 0.01;
input double InpThreshold_Close_L3_Long = 0.015;
input double InpThreshold_EMA_L1_Long = 0.003;
input double InpThreshold_EMA_L2_Long = 0.007;
input double InpThreshold_EMA_L3_Long = 0.01;
input group "Slope: Diagnosis Color Settings";
input color c_Fomo = clrRed;
input color c_Breakout = clrDodgerBlue;
input color c_StrongTrend_Up = clrLawnGreen;
input color c_StrongTrend_Down = clrOrangeRed;
input color c_HasTrend_Up = clrLimeGreen;
input color c_HasTrend_Down = clrOrange;
input color c_Sideway = clrGray;
input group "Slope Checklist Panel";
input bool InpShowChecklistPanel = false;
input group "D1: Close Settings";
input int InpNumOfDaysToDraw = 5; // Number of Daily Open Lines to Draw
input int InpDOpenOffsetHours = 0;
input int InpDCloseOffsetHours = 0;
input group "H4: Close Settings";
input bool InpShowH4CloseLine = true;
input color InpH4CloseLineColor = clrWhite;
input int InpH4CloseLineWidth = 1;
input ENUM_LINE_STYLE InpH4CloseLineStyle = STYLE_DOT;
input group "Sideway Range Drawing";
input bool InpEnableRange_Diagnosis = false;   // Enable Range by Market Diagnosis
input bool InpEnableRange_PriceNeutral = true; // Enable Range by Neutral Price Slope
input bool InpEnableRange_EmaNeutral = false;  // Enable Range by Neutral EMA Slope
input color InpShortTermRectColor = clrYellow;
input color InpLongTermRectColor = clrBrown;
input group "--- BUY Setup Families ---" input bool Inp_EnableBuy_StrongTrendPullback = true;   // Bật/Tắt: Mua Pullback trong xu hướng mạnh
input bool Inp_EnableBuy_TrendMomentum = true;                                                  // Bật/Tắt: Mua theo động lượng xu hướng
input bool Inp_EnableBuy_BreakoutConfirm = true;                                                // Bật/Tắt: Mua xác nhận Breakout
input group "--- SELL Setup Families ---" input bool Inp_EnableSell_StrongTrendPullback = true; // Bật/Tắt: Bán Pullback trong xu hướng mạnh
input bool Inp_EnableSell_TrendMomentum = true;                                                 // Bật/Tắt: Bán theo động lượng xu hướng
input bool Inp_EnableSell_BreakoutConfirm = true;                                               // Bật/Tắt: Bán xác nhận Breakout

input group "ZigZag Settings"
input int    ZigZag_ExtPeriod         = 3;
input int    ZigZag_MinAmplitude      = 2;
input int    ZigZag_MinMotion         = 0;
input bool   ZigZag_UseSmallerTFforEB = true;

input group "Display Settings"
input bool   ZigZag_Show              = false;
input bool   ZigZag_CHOCH_Show        = true;
input bool   ZigZag_Label_Show        = false;
input double LabelOffsetPips          = 5.0;
input int    MaxBars                  = 1500;

// --- Cài đặt đầu vào cho EA ---
input double InpProfitTarget = 8.0;  // Lợi nhuận mục tiêu ($) để kích hoạt quản lý
input double InpClosePercent = 50.0; // Phần trăm khối lượng lệnh sẽ đóng
input double InpPipsPlus = 2.0;      // Số pips cộng thêm vào điểm hòa vốn cho SL
// --- Biến toàn cục để theo dõi trạng thái ---
long g_managed_profit_ticket = 0;   // Ticket của lệnh đang được quản lý
bool g_is_partially_closed = false; // Cờ báo hiệu lệnh đã được chốt lời một phần hay chưa
bool g_is_breakeven_set = false;
bool g_check_pending_orders = true; // hoặc false tùy ý bạn
// --- OPTIMIZATION: Biến toàn cục để lưu trữ các giá trị không đổi ---
double g_point_value;
double g_point_per_pips;
double g_volume_step;
double g_points_plus;
double sell_stop_buffer;
int buffer_profit = 5;
double max_lot_size = 0.5;

bool InpShowStochasticDetails = true;
int InpStoch_K_Period_Slow = 48;
int InpStoch_K_Period_Fast = 12;   // Chu kỳ K cho Stochastic nhanh (tín hiệu)
int InpStoch_D_Period      = 3;    // Chu kỳ D (chung cho cả hai)
int InpStoch_Slowing       = 3;    // Slowing (chung cho cả hai)

string GenerateObjectName(string object_type, string unique_id = "") { return G_OBJECT_PREFIX + (string)ChartID() + "_" + object_type + (unique_id != "" ? "_" + unique_id : ""); }

enum MarketState
  {
   STATE_EXTREME_BULL,      // Siêu tăng, cả 4 TF đồng thuận quá mua
   STATE_STRONG_BULL,       // Tăng mạnh, các TF dài hạn đồng thuận tăng
   STATE_MODERATE_BULL,     // Tăng vừa phải, có thể có TF không đồng thuận
   STATE_RANGING,           // Đi ngang
   STATE_CONFLICT,          // Các TF lớn xung đột (VD: D1 tăng, H4 giảm)
   STATE_MODERATE_BEAR,     // Giảm vừa phải
   STATE_STRONG_BEAR,       // Giảm mạnh
   STATE_EXTREME_BEAR       // Siêu giảm, cả 4 TF đồng thuận quá bán
  };

CStochasticOptimizer stoch_h1, stoch_h4, stoch_d1, stoch_d2;

//--- Global variables for indicator handles
//int stoch_handle_slow = INVALID_HANDLE;
//int stoch_handle_fast = INVALID_HANDLE;
double k_h1, d_h1, k_h4, d_h4, k_d1, d_d1, k_d2, d_d2;
MarketState state;
//==================================================================
// SECTION 3: MQL5 MAIN FUNCTIONS
//==================================================================
int zigzagHandle = INVALID_HANDLE;
double upBuffer[], dnBuffer[];
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(_Period >= InpPrimaryTimeframe)
     {
      Alert("Timeframe hierarchy error! Chart TF must be lower than Primary TF.");
      return (INIT_FAILED);
     }
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(_Symbol);
   g_managed_objects.Clear();
   InitializeTranslations(InpLanguage);
   EmaHandle = iMA(_Symbol, _Period, InpEmaPeriod, 0, MODE_EMA, InpEmaAppliedPrice);
   AtrHandle = iATR(_Symbol, _Period, InpAtrPeriod);
   if(EmaHandle == INVALID_HANDLE || AtrHandle == INVALID_HANDLE)
      return (INIT_FAILED);
   c_level_colors[0] = clrIndianRed;
   c_level_colors[1] = clrOrangeRed;
   c_level_colors[2] = clrOrange;
   c_level_colors[3] = c_Sideway;
   c_level_colors[4] = clrLimeGreen;
   c_level_colors[5] = clrLawnGreen;
   c_level_colors[6] = clrDeepSkyBlue;
   g_historical_ranges = new CArrayObj();
   if(CheckPointer(g_historical_ranges) == POINTER_INVALID)
     {
      Print("Error: Could not create CArrayObj for historical ranges!");
      return (INIT_FAILED);
     }
   for(int i = 0; i < 3; i++)
     {
      ResetRangeInfo(g_st_ranges[i]);
      ResetRangeInfo(g_lt_ranges[i]);
     }

   FindAndDrawH1Setup();
   g_m30_signalType = FindM30CISDStatusSetup(g_m30_signalType);
   g_m15_signalType = FindM15CISDStatusSetup(g_m15_signalType);
   g_m5_signalType = FindM5CISDStatusSetup(g_m5_signalType);
   if(g_h1_signalType != 0)
     {
      // TỐI ƯU: Hàm này quét lịch sử, chỉ cần chạy 1 lần mỗi nến.
      SignalAnalysis confirmedSignal = CheckSignalsAndDraw_Stateful();
     }
   DrawDailyOpenLine();
   DrawH4ClosesOnCurrentTimeframe();

   EventSetTimer(60);
// Reset trạng thái khi EA khởi động
   ResetTradeManagementState(0);

   g_point_value = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_point_per_pips = (_Digits == 3 || _Digits == 5) ? 10 : 1;
   g_volume_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   sell_stop_buffer = 2 * g_point_value;                           // buffer nhỏ để tránh quét nhầm
// Tính toán trước giá trị points cần cộng thêm
   g_points_plus = InpPipsPlus * g_point_per_pips * g_point_value; // Dành cho broker 5 số và 3 số

   g_last_m5_processed_bar_time = iTime(_Symbol, PERIOD_M5, 0);
   g_last_m30_processed_bar_time = iTime(_Symbol, PERIOD_M30, 0);
   g_last_h1_processed_bar_time = iTime(_Symbol, InpPrimaryTimeframe, 0);

//*
   g_h1_buy_signal_active = true;
   g_h1_sell_signal_active = true;
   g_m30_buy_signal_active = true;
   g_m30_sell_signal_active = true;
//*/

   ManagePositionByHistory();
   
   zigzagHandle = iCustom(_Symbol, PERIOD_CURRENT, "zigzag_pro2", ZigZag_ExtPeriod, ZigZag_MinAmplitude, ZigZag_MinMotion, ZigZag_UseSmallerTFforEB);

   stoch_h1.Init(_Symbol, PERIOD_M5, 12, 3, 3);   // Tương đương H1
   stoch_h4.Init(_Symbol, PERIOD_M5, 48, 3, 3);   // Tương đương H4
   stoch_d1.Init(_Symbol, PERIOD_M5, 288, 3, 3);  // Tương đương D1
   stoch_d2.Init(_Symbol, PERIOD_M5, 576, 3, 3);  // Tương đương D2

   return (INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(EmaHandle);
   IndicatorRelease(AtrHandle);

   for(int i = g_managed_objects.Total() - 1; i >= 0; i--)
      ObjectDelete(0, g_managed_objects.At(i));
   g_managed_objects.Clear();

// --- DỌN DẸP g_historical_ranges ĐỂ SỬA LỖI RÒ RỈ BỘ NHỚ ---
   if(CheckPointer(g_historical_ranges) != POINTER_INVALID)
     {
      // BƯỚC 1: DỌN DẸP "NỘI DUNG" (những "cuốn sách")
      // Lặp qua tất cả các "thẻ danh mục" trên "giá sách".
      for(int i = g_historical_ranges.Total() - 1; i >= 0; i--)
        {
         // Lấy ra con trỏ (thẻ danh mục)
         CObject *obj = g_historical_ranges.At(i);

         // Nếu con trỏ hợp lệ, hãy xóa đối tượng mà nó trỏ tới (vứt cuốn sách đi)
         if(CheckPointer(obj) != POINTER_INVALID)
           {
            delete obj;
           }
        }
      // Bây giờ tất cả các cuốn sách đã được dọn dẹp.
      // Lệnh Clear() giờ chỉ đơn thuần là xóa các thẻ danh mục đã vô giá trị.
      g_historical_ranges.Clear();

      // BƯỚC 2: DỌN DẸP "THÙNG CHỨA" (cái "giá sách")
      // Sau khi giá sách đã rỗng và sách đã được dọn, giờ ta phá hủy chính cái giá sách.
      delete g_historical_ranges;

      // BƯỚC 3: ĐẶT CON TRỎ VỀ NULL (một thói quen tốt)
      // Quên đi địa chỉ của cái giá sách đã không còn tồn tại.
      g_historical_ranges = NULL;
     }
   EventKillTimer();

   Print("EA Deinitialization finished. Reason: ", reason);
  }

// --- Tạo hàm OnTimer() ---
void OnTimer()
  {
   if(buy_total_count == 1)
      ManageTPByTimeAndLoss(_Symbol);
   if(sell_total_count == 1)
      ManageTPByTimeAndLoss(_Symbol);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnTick()
  {
// ==========================================================
// SECTION 1: CHẠY MỖI TICK (LOGIC NHẸ, REAL-TIME)
// ==========================================================
   ManagePositionProfitBreakEvent();
// CancelPendingOrdersIfOpenPosition(_Symbol);
// ManagePositionProfitPartialClose();
   string stateInfo = "";
   state = AnalyzeMarketState_MultiTF(stateInfo);
// 1.1. Lấy dữ liệu cần thiết cho việc cập nhật real-time
   MqlRates current_rates[];
   if(CopyRates(_Symbol, _Period, 0, 1, current_rates) < 1)
      return;

   double atr_arr[], ema_arr[];
   CopyBuffer(AtrHandle, 0, 0, 1, atr_arr);
   CopyBuffer(EmaHandle, 0, 0, 1, ema_arr);

   InitializeCISDPercentages();

// 1.2. Cập nhật phân tích xu hướng và bảng điều khiển THEO YÊU CẦU
   PerformTrendAnalysis(g_short_term, true, current_rates[0].close, atr_arr, ema_arr);
   PerformTrendAnalysis(g_long_term, false, current_rates[0].close, atr_arr, ema_arr);
   DrawSlopePanelBackground();
   UpdateSlopePanelDisplay();

// ==========================================================
// SECTION 2: CHẠY MỘT LẦN KHI CÓ NẾN MỚI (LOGIC NẶNG)
// ==========================================================

   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime == g_last_processed_bar_time)
     {
      return; // Nến chưa thay đổi, kết thúc xử lý OnTick tại đây.
     }
// Nếu có nến mới, cập nhật thời gian và tiếp tục xử lý
   g_last_processed_bar_time = currentBarTime;

// --- Bắt đầu khối xử lý nặng ---

   if(Bars(_Symbol, _Period) < InpRegressionPeriod_Long + InpEmaPeriod)
      return;

   ManagePositionByHistory();

// 2.1. Tìm kiếm setup H1 (chỉ cần chạy khi có nến mới)
// TỐI ƯU: Hàm này vẫn cần được refactor để không quét 500 nến mỗi lần.
   FindAndDrawH1Setup();
   g_m30_signalType = FindM30CISDStatusSetup(g_m30_signalType);
   g_m15_signalType = FindM15CISDStatusSetup(g_m15_signalType);
   g_m5_signalType = FindM5CISDStatusSetup(g_m5_signalType);

   if(g_h1_signalType != g_previous_h1_signalType)
     {
      g_last_trade_signal_time = 0;
      g_ltf_scan_start_time = 0;
      g_previous_h1_signalType = g_h1_signalType;
     }

// 2.2. Xử lý Sideway Ranges (logic này của bạn đã đúng)
//   MqlRates prev_rates[];
//   if(CopyRates(_Symbol, _Period, 1, 1, prev_rates) > 0)
//     {
//      CheckForBarCloseBreakouts(prev_rates[0]);
//     }
//   UpdateActiveRanges(current_rates[0]);
//   DrawSidewayRanges();

// 2.3. Tìm kiếm tín hiệu và thực thi giao dịch
   datetime currentM1BarTime = iTime(_Symbol, PERIOD_M1, 0);
   if(currentM1BarTime > g_last_m1_processed_bar_time)
     {
      g_last_m1_processed_bar_time = currentM1BarTime;
      if(g_h1_signalType != 0)
        {
         // TỐI ƯU: Hàm này quét lịch sử, chỉ cần chạy 1 lần mỗi nến.
         SignalAnalysis confirmedSignal = CheckSignalsAndDraw_Stateful();
         // UpdateChecklistPanel(confirmedSignal.signal, confirmedSignal.ltf_cisd_price);
         // ExecuteTrade(confirmedSignal);
        }
     }
// 2.4. Vẽ các đường D1 và H4
// Yêu cầu của bạn là update khi nến LTF kết thúc, logic này đáp ứng đúng điều đó.
   DrawDailyOpenLine();
// DrawH4ClosesOnCurrentTimeframe();

   datetime currentM5BarTime = iTime(_Symbol, PERIOD_M5, 0);
   if(currentM5BarTime > g_last_m5_processed_bar_time)
     {
      g_last_m5_processed_bar_time = currentM5BarTime;
      g_m5_signal_active = true;
     }

   datetime currentM30BarTime = iTime(_Symbol, PERIOD_M30, 0);
   if(currentM30BarTime > g_last_m30_processed_bar_time)
     {
      g_last_m30_processed_bar_time = currentM30BarTime;
      g_m30_signal_active = true;
      g_m30_buy_signal_active = true;
      g_m30_sell_signal_active = true;
     }

   datetime currentH1BarTime = iTime(_Symbol, InpPrimaryTimeframe, 0);
   if(currentH1BarTime > g_last_h1_processed_bar_time)
     {
      if(StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "BTC") >= 0)
         SendTelegramMessage(FormatAccountDashboardMessage());
      g_last_h1_processed_bar_time = currentH1BarTime;
      g_h1_signal_active = true;
      g_h1_buy_signal_active = true;
      g_h1_sell_signal_active = true;
     }

// 2.5. Dọn dẹp đối tượng (Quan trọng!)
// Bỏ logic hide/unhide/delete mỗi tick.
// Thay vào đó, nếu cần, hãy tạo một hàm dọn dẹp riêng chạy mỗi nến.
// CleanupOldObjects();
CalculateZigZag();
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CalculateZigZag()
  {
   if(CopyBuffer(zigzagHandle, 0, 0, MaxBars, upBuffer) < 0)
      return;
   if(CopyBuffer(zigzagHandle, 1, 0, MaxBars, dnBuffer) < 0)
      return;
   ArraySetAsSeries(upBuffer, true);
   ArraySetAsSeries(dnBuffer, true);

   ZigZagPoint current_points[];
   int n_current_points = ExtractRawZigZagPoints(current_points, MaxBars);
   if(n_current_points > 0)
     {
      bool needs_processing = false;
      if(g_nPoints <= 0)
        {
         needs_processing = true;
        }
      else
        {
         bool changed = (n_current_points != g_nPoints);
         if(!changed)
           {
            int limit = MathMin(n_current_points, g_nPoints);
            for(int i = 1; i <= limit; i++)
              {
               int current_idx = n_current_points - i;
               int prev_idx = g_nPoints - i;
               if(current_points[current_idx].time != g_processed_points[prev_idx].time || current_points[current_idx].price != g_processed_points[prev_idx].price)
                 {
                  changed = true;
                  break;
                 }
              }
           }
         if(changed)
           {
            needs_processing = true;
           }
        }
      if(needs_processing)
        {
         int recalc_start_idx = 0;
         ProcessZigZag(current_points, n_current_points, recalc_start_idx);
         UpdateChartObjects(current_points, n_current_points);
         CopyZigZagPointsArray(g_processed_points, current_points);
         g_nPoints = n_current_points;
        }
     }


  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
      ChartRedraw();
  }

//==================================================================
// SECTION 4: CORE LOGIC & REFACTORED HELPERS
//==================================================================

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int GetLatestCompletedTrades(const string symbol_name, TradeHistoryInfo &latest_trades_array[])
  {
// Bước 1: Lấy toàn bộ lịch sử giao dịch trong ngày
   TradeHistoryInfo all_today_trades[];
   int total_trades = GetTodayTradeHistory(symbol_name, all_today_trades);

// Bước 2: Kiểm tra xem có giao dịch nào không
   if(total_trades <= 0)
     {
      // Không có giao dịch nào trong ngày, trả về 0
      ArrayResize(latest_trades_array, 0);
      return 0;
     }

   /*
   if(total_trades > 0)
     {
      PrintFormat("=== TÌM THẤY %d GIAO DỊCH CHO %s HÔM NAY ===", total_trades, symbol_name);
      for(int i = 0; i < total_trades; i++)
        {
         TradeHistoryInfo trade = all_today_trades[i];
         string type_str = (trade.type == ORDER_TYPE_BUY) ? "BUY" : "SELL";

         PrintFormat("--- Lệnh #%d ---", i + 1);
         PrintFormat("  Loại lệnh: %s %.2f lot", type_str, trade.volume);
         PrintFormat("  Thời gian giữ lệnh: %.2f s", trade.close_time - trade.open_time);
         PrintFormat("  Thời gian: %s - %s", TimeToString(trade.open_time, TIME_DATE | TIME_SECONDS), TimeToString(trade.close_time, TIME_DATE | TIME_SECONDS));
         PrintFormat("  Lợi nhuận: %.2f | Commission: %.2f | Swap: %.2f", trade.profit, trade.commission, trade.swap);
         PrintFormat("  Lý do đóng: %s", GetDealCloseReason(trade.close_reason));
        }
     }
   //*/

// Bước 3: Xác định thời gian đóng của lệnh gần nhất
// Vì mảng đã được sắp xếp từ mới nhất -> cũ nhất, lệnh đầu tiên là lệnh gần nhất
   datetime latest_close_time = all_today_trades[0].close_time;

// Bước 4: Lọc ra tất cả các lệnh có cùng thời gian đóng gần nhất
   int latest_count = 0;
   ArrayResize(latest_trades_array, 0);

   for(int i = 0; i < total_trades; i++)
     {
      // So sánh thời gian đóng của lệnh hiện tại với thời gian gần nhất
      if(all_today_trades[i].close_time >= latest_close_time - 2)
        {
         // Nếu trùng khớp, thêm vào mảng kết quả
         latest_count++;
         ArrayResize(latest_trades_array, latest_count);
         latest_trades_array[latest_count - 1] = all_today_trades[i];
        }
      else
        {
         // Vì mảng đã được sắp xếp, ngay khi gặp một lệnh có thời gian khác,
         // chúng ta có thể dừng lại vì tất cả các lệnh sau đó sẽ cũ hơn.
         break;
        }
     }

// Trả về số lượng lệnh gần nhất đã tìm thấy
   return latest_count;
  }


//+------------------------------------------------------------------+
//| Hàm phụ trợ để chuyển ENUM_DEAL_REASON thành chuỗi dễ đọc         |
//+------------------------------------------------------------------+
string GetDealCloseReason(ENUM_DEAL_REASON reason)
  {
// Ép kiểu sang (int) để đảm bảo tính tương thích và tránh lỗi "not integral"
   switch((int)reason)
     {
      case DEAL_REASON_CLIENT:
         return "Manual Close";
      case DEAL_REASON_SL:
         return "Stop Loss";
      case DEAL_REASON_TP:
         return "Take Profit";
      case DEAL_REASON_EXPERT:
         return "Closed by EA";
      case DEAL_REASON_VMARGIN:
         return "Margin Call";
      // Thêm các trường hợp khác nếu cần
      default:
         return EnumToString(reason); // Trả về tên enum mặc định nếu không khớp
     }
  }

//+------------------------------------------------------------------+
//| Hàm chính: Lấy lịch sử giao dịch trong ngày cho một symbol       |
//| Sắp xếp từ mới nhất đến cũ nhất (đã sửa lỗi)                      |
//+------------------------------------------------------------------+
int GetTodayTradeHistory(const string symbol_name, TradeHistoryInfo &history_array[])
  {
// --- BƯỚC 1: XÁC ĐỊNH KHOẢNG THỜI GIAN "HÔM NAY" ---
   datetime from_date = iTime(symbol_name, PERIOD_D1, 0); // 00:00 của ngày hôm nay
   datetime to_date = TimeCurrent();                       // Thời gian hiện tại

// --- BƯỚC 2: TẢI LỊCH SỬ GIAO DỊCH VÀO BỘ NHỚ ---
   if(!HistorySelect(from_date, to_date))
     {
      Print("Lỗi khi chọn lịch sử giao dịch! Lỗi: ", GetLastError());
      return 0;
     }

// Mảng để theo dõi các position đã được xử lý, tránh trùng lặp
   long processed_positions[];
   int trade_count = 0;
   ArrayResize(history_array, 0); // Xóa mảng kết quả trước khi bắt đầu

// --- BƯỚC 3: DUYỆT QUA TẤT CẢ DEALS, BẮT ĐẦU TỪ DEAL MỚI NHẤT ---
// Vòng lặp chạy ngược để kết quả tự động được sắp xếp từ mới đến cũ
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket == 0)
         continue;

      // Chỉ xử lý các deal của symbol được chỉ định
      if(HistoryDealGetString(deal_ticket, DEAL_SYMBOL) != symbol_name)
         continue;

      // Chúng ta chỉ quan tâm đến các deal THOÁT lệnh (DEAL_ENTRY_OUT)
      ENUM_DEAL_ENTRY deal_entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
      if(deal_entry != DEAL_ENTRY_OUT)
         continue;

      long position_id = HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID);

      // Kiểm tra xem position này đã được xử lý chưa
      bool is_processed = false;
      for(int k = 0; k < ArraySize(processed_positions); k++)
        {
         if(processed_positions[k] == position_id)
           {
            is_processed = true;
            break;
           }
        }
      if(is_processed)
         continue;

      // Đánh dấu position này là đã xử lý
      int processed_size = ArraySize(processed_positions);
      ArrayResize(processed_positions, processed_size + 1);
      processed_positions[processed_size] = position_id;

      // --- BƯỚC 4: TÌM DEAL VÀO LỆNH TƯƠNG ỨNG ---
      ulong entry_deal_ticket = 0;
      // Duyệt lại để tìm deal vào lệnh có cùng position ID
      for(int j = 0; j < HistoryDealsTotal(); j++)
        {
         ulong potential_entry_ticket = HistoryDealGetTicket(j);
         if(HistoryDealGetInteger(potential_entry_ticket, DEAL_POSITION_ID) == position_id &&
            (ENUM_DEAL_ENTRY)HistoryDealGetInteger(potential_entry_ticket, DEAL_ENTRY) == DEAL_ENTRY_IN)
           {
            entry_deal_ticket = potential_entry_ticket;
            break; // Tìm thấy rồi, thoát vòng lặp
           }
        }

      if(entry_deal_ticket == 0)
         continue; // Không tìm thấy deal vào lệnh, bỏ qua

      // --- BƯỚC 5: TỔNG HỢP THÔNG TIN VÀO STRUCT ---
      trade_count++;
      ArrayResize(history_array, trade_count);

      // *** SỬA LỖI: Truy cập trực tiếp vào phần tử mảng thay vì dùng tham chiếu '&' ***
      int current_index = trade_count - 1;

      // Thông tin từ deal vào lệnh
      history_array[current_index].position_id       = position_id;
      history_array[current_index].open_time         = (datetime)HistoryDealGetInteger(entry_deal_ticket, DEAL_TIME);
      history_array[current_index].open_price        = HistoryDealGetDouble(entry_deal_ticket, DEAL_PRICE);
      history_array[current_index].volume            = HistoryDealGetDouble(entry_deal_ticket, DEAL_VOLUME);
      history_array[current_index].type              = (ENUM_ORDER_TYPE)HistoryDealGetInteger(entry_deal_ticket, DEAL_TYPE);

      // Thông tin từ deal thoát lệnh
      history_array[current_index].exit_deal_ticket  = deal_ticket;
      history_array[current_index].entry_deal_ticket = entry_deal_ticket;
      history_array[current_index].close_time        = (datetime)HistoryDealGetInteger(deal_ticket, DEAL_TIME);
      history_array[current_index].close_price       = HistoryDealGetDouble(deal_ticket, DEAL_PRICE);
      history_array[current_index].profit            = HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
      history_array[current_index].commission        = HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION);
      history_array[current_index].swap              = HistoryDealGetDouble(deal_ticket, DEAL_SWAP);

      // Lấy lý do đóng lệnh
      ENUM_DEAL_REASON reason = (ENUM_DEAL_REASON)HistoryDealGetInteger(deal_ticket, DEAL_REASON);
      history_array[current_index].close_reason = GetDealCloseReason(reason);
     }

   return trade_count;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ManagePositionByHistory()
  {
   TradeHistoryInfo latest_trades[]; // Mảng để chứa kết quả
   int latest_trade_found_count = GetLatestCompletedTrades(_Symbol, latest_trades);
   if(latest_trade_found_count > 0 && !PositionSelect(_Symbol))
     {
      // PrintFormat("Tìm thấy %d lệnh hoàn thành gần nhất vào lúc %s:", latest_trade_found_count, TimeToString(latest_trades[0].close_time, TIME_DATE | TIME_SECONDS));
      if(latest_trade_found_count == 1 && latest_trades[0].close_reason == DEAL_REASON_SL)
        {
         g_last_m30_processed_bar_time = latest_trades[0].close_time + 30 * 60;
         g_last_h1_processed_bar_time = latest_trades[0].close_time + 30 * 60;
         if(g_last_h1_processed_bar_time > TimeCurrent())
           {
            g_m30_buy_signal_active = false;
            g_m30_sell_signal_active = false;
            g_h1_buy_signal_active = false;
            g_h1_sell_signal_active = false;
           }
         // PrintFormat("Xu hướng yếu. Không nên vào lệnh sau 30 phút từ %s đến %s", TimeToString(latest_trades[0].close_time, TIME_DATE | TIME_SECONDS), TimeToString(latest_trades[0].close_time + 1800, TIME_DATE | TIME_SECONDS));
        }
      if((latest_trade_found_count == 1 && latest_trades[0].close_reason == DEAL_REASON_TP && latest_trades[0].close_time - latest_trades[0].open_time >= 30 * 60) || latest_trade_found_count > 1)
        {
         g_last_h1_processed_bar_time = latest_trades[0].close_time + 60 * 60;
         if(g_last_h1_processed_bar_time > TimeCurrent())
           {
            g_h1_buy_signal_active = false;
            g_h1_sell_signal_active = false;
           }
         /*
         if(latest_trade_found_count == 1 && latest_trades[0].close_reason == DEAL_REASON_TP && latest_trades[0].close_time - latest_trades[0].open_time >= 30 * 60)
            PrintFormat("Xu hướng sideway. Không nên vào lệnh sau 60 phút từ %s đến %s", TimeToString(latest_trades[0].close_time, TIME_DATE | TIME_SECONDS), TimeToString(latest_trades[0].close_time + 3600, TIME_DATE | TIME_SECONDS));
         if(latest_trade_found_count > 1)
            PrintFormat("Lệnh DCA. Không nên vào lệnh sau 60 phút từ %s đến %s", TimeToString(latest_trades[0].close_time, TIME_DATE | TIME_SECONDS), TimeToString(latest_trades[0].close_time + 3600, TIME_DATE | TIME_SECONDS));
         //*/
        }
     }
  }
//+------------------------------------------------------------------+
//| Hàm phân tích thị trường đa khung thời gian toàn diện            |
//+------------------------------------------------------------------+
MarketState AnalyzeMarketState_MultiTF(string &display_string)
  {

// Lấy tất cả các giá trị
   if(!stoch_h1.Calculate(k_h1, d_h1) || !stoch_h4.Calculate(k_h4, d_h4) ||
      !stoch_d1.Calculate(k_d1, d_d1) || !stoch_d2.Calculate(k_d2, d_d2))
     {
      return STATE_RANGING; // Lỗi hoặc chưa đủ dữ liệu
     }

// Hiển thị thông tin để debug
   display_string += StringFormat("D2 : K=%.2f, D=%.2f\n", k_d2, d_d2);
   display_string += StringFormat("D1 : K=%.2f, D=%.2f\n", k_d1, d_d1);
   display_string += StringFormat("H4 : K=%.2f, D=%.2f\n", k_h4, d_h4);
   display_string += StringFormat("H1 : K=%.2f, D=%.2f\n", k_h1, d_h1);

// --- Logic Phân Tích ---

// Xác định trạng thái của từng khung thời gian
   bool is_d2_bull = (k_d2 > 60 && d_d2 > 60);
   bool is_d1_bull = (k_d1 > 60 && d_d1 > 60);
   bool is_h4_bull = (k_h4 > 70 && d_h4 > 70);
   bool is_h1_bull = (k_h1 > 80 && d_h1 > 80);

   bool is_d2_bear = (k_d2 < 40 && d_d2 < 40);
   bool is_d1_bear = (k_d1 < 40 && d_d1 < 40);
   bool is_h4_bear = (k_h4 < 30 && d_h4 < 30);
   bool is_h1_bear = (k_h4 < 20 && d_h4 < 20);

// --- 1. KIỂM TRA CÁC TRẠNG THÁI CỰC ĐẠI (EXTREME) ---
   if(k_d2 > 80 && k_d1 > 80 && k_h4 > 80 && k_h1 > 80 && k_h1 > d_h1)
     {
      return STATE_EXTREME_BULL; // Giống hệt trường hợp trong ảnh của bạn
     }
   if(k_d2 < 20 && k_d1 < 20 && k_h4 < 20 && k_h1 < 20 && k_h1 < d_h1)
     {
      return STATE_EXTREME_BEAR;
     }

// --- 2. KIỂM TRA CÁC XU HƯỚNG MẠNH VÀ ĐỒNG THUẬN ---
// Xu hướng tăng mạnh: D2, D1, H4 đều đồng thuận tăng, và H1 cho tín hiệu mua
   if(is_d2_bull && is_d1_bull && is_h4_bull && is_h1_bull)
     {
      return STATE_STRONG_BULL;
     }
// Xu hướng giảm mạnh: D2, D1, H4 đều đồng thuận giảm, và H1 cho tín hiệu bán
   if(is_d2_bear && is_d1_bear && is_h4_bear && is_h1_bear)
     {
      return STATE_STRONG_BEAR;
     }

// --- 3. KIỂM TRA CÁC XU HƯỚNG VỪA PHẢI ---
// Chỉ cần D1 và H4 đồng thuận
   if(is_d1_bull && is_h4_bull && is_h1_bull)
     {
      return STATE_MODERATE_BULL;
     }
   if(is_d1_bear && is_h4_bear && is_h1_bear)
     {
      return STATE_MODERATE_BEAR;
     }

// --- 4. KIỂM TRA SỰ XUNG ĐỘT ---
// Ví dụ: D1 tăng nhưng H4 giảm -> thị trường đang giằng co
   if((is_d1_bull && is_h4_bear) || (is_d1_bear && is_h4_bull))
     {
      return STATE_CONFLICT;
     }

// --- 5. NẾU KHÔNG RƠI VÀO CÁC TRƯỜNG HỢP TRÊN -> ĐI NGANG
   return STATE_RANGING;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void InitializeCISDPercentages()
  {
// --- Tính toán cho Khung Ngày (Daily) ---
// Sử dụng shift=1 để lấy trạng thái của ngày giao dịch đã hoàn thành trước đó làm bối cảnh
   g_daily_percent = CalculateBarStatus(PERIOD_D1, 0);

// --- Tính toán cho Khung H1 ---
   g_h1_percent = CalculateBarStatus(PERIOD_H1, 0);         // Nến hiện tại
   g_h1_pre_percent = CalculateBarStatus(PERIOD_H1, 1);     // Nến trước đó
   g_h1_pre_pre_percent = CalculateBarStatus(PERIOD_H1, 2); // Nến trước đó nữa

// --- Tính toán cho Khung M30 ---
   g_m30_percent = CalculateBarStatus(PERIOD_M30, 0);
   g_m30_pre_percent = CalculateBarStatus(PERIOD_M30, 1);
   g_m30_pre_pre_percent = CalculateBarStatus(PERIOD_M30, 2);

// --- Tính toán cho Khung M15 ---
   g_m15_percent = CalculateBarStatus(PERIOD_M15, 0);
   g_m15_pre_percent = CalculateBarStatus(PERIOD_M15, 1);
   g_m15_pre_pre_percent = CalculateBarStatus(PERIOD_M15, 2);

   g_h4_percent = CalculateBarStatus(PERIOD_H4, 0);
   g_h4_pre_percent = CalculateBarStatus(PERIOD_H4, 1);

   g_m5_percent = CalculateBarStatus(PERIOD_M5, 0);

// --- Tính toán cho mảng 4 nến M15 đã đóng cửa ---
// Dùng cho việc phân tích nén giá trong nến H1[1]
   for(int i = 0; i < 4; i++)
     {
      // i=0 -> shift=1 (nến M15[1])
      // i=1 -> shift=2 (nến M15[2])
      // ...
      g_m15_last4_percents[i] = CalculateBarStatus(PERIOD_M15, i + 1);
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CancelPendingOrdersIfOpenPosition(string symbol)
  {
   if(!g_check_pending_orders)
      return;

   bool has_open_position = false;
   bool has_pending_order = false;

// Kiểm tra position đang mở
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) == symbol)
        {
         has_open_position = true;
         break;
        }
     }

// Kiểm tra và xóa lệnh pending nếu có position mở
   if(has_open_position)
     {
      for(int i = OrdersTotal() - 1; i >= 0; i--)
        {
         ulong ticket = OrderGetTicket(i);
         if(ticket == 0)
            continue;
         if(OrderGetString(ORDER_SYMBOL) == symbol)
           {
            int type = OrderGetInteger(ORDER_TYPE);
            if(type == ORDER_TYPE_BUY_LIMIT ||
               type == ORDER_TYPE_SELL_LIMIT ||
               type == ORDER_TYPE_BUY_STOP ||
               type == ORDER_TYPE_SELL_STOP ||
               type == ORDER_TYPE_BUY_STOP_LIMIT ||
               type == ORDER_TYPE_SELL_STOP_LIMIT)
              {
               if(trade.OrderDelete(ticket))
                  PrintFormat("✅ Đã hủy lệnh pending #%I64d cho %s", ticket, symbol);
               else
                  PrintFormat("❌ Hủy lệnh pending thất bại #%I64d: %s", ticket, trade.ResultRetcodeDescription());
              }
           }
        }
     }

   if(has_open_position)
      return;

// Kiểm tra lại: còn pending không? Còn position không?
   has_open_position = false;
   has_pending_order = false;

// Kiểm tra lại pending order
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) == symbol)
        {
         int type = OrderGetInteger(ORDER_TYPE);
         if(type == ORDER_TYPE_BUY_LIMIT ||
            type == ORDER_TYPE_SELL_LIMIT ||
            type == ORDER_TYPE_BUY_STOP ||
            type == ORDER_TYPE_SELL_STOP ||
            type == ORDER_TYPE_BUY_STOP_LIMIT ||
            type == ORDER_TYPE_SELL_STOP_LIMIT)
           {
            has_pending_order = true;
            break;
           }
        }
     }

// Nếu không còn pending và không còn position thì tắt biến kiểm tra
   if(!has_open_position && !has_pending_order)
     {
      g_check_pending_orders = false;
     }
  }

//+------------------------------------------------------------------+
//| Hàm quản lý SL động: Ưu tiên Imbalance, dự phòng Breakeven      |
//+------------------------------------------------------------------+
// --- Khai báo các biến riêng biệt cho nhóm BUY ---
int buy_total_count = 0;
double buy_total_profit = 0.0;
double buy_total_volume = 0.0;
double buy_weighted_price_sum = 0.0;
// --- Khai báo các biến riêng biệt cho nhóm SELL ---
int sell_total_count = 0;
double sell_total_profit = 0.0;
double sell_total_volume = 0.0;
double sell_weighted_price_sum = 0.0;
// --- BIẾN TOÀN CỤC ĐỂ THEO DÕI LỊCH SỬ TỔNG LỢI NHUẬN ---
double g_total_profit_max = 0.0;
double g_total_profit_min = 0.0;
int    g_previous_positions_count = 0; // Dùng để phát hiện chu kỳ giao dịch mới

// --- BIẾN MỚI ĐỂ THEO DÕI LỊCH SỬ PIPS ---
datetime g_cycle_start_time = 0;
double   g_cycle_initial_risk = 0.0;
double g_total_pips_max = 0.0; // Số pips dương cao nhất từng đạt được
double g_total_pips_min = 0.0; // Số pips âm thấp nhất từng đạt được
double g_total_pips_now = 0.0; // Số pips hiện tại đạt được
// --- ENUM ĐỊNH NGHĨA CẤP ĐỘ SỨC KHỎE CỦA GIAO DỊCH ---
enum ETradeHealthLevel
  {
   HEALTHY,      // Khỏe mạnh: Lệnh đang hoạt động tốt hoặc bình thường
   CONCERN,      // Đáng ngại: Có một dấu hiệu xấu nhỏ
   WARNING,      // Cảnh báo: Có dấu hiệu xấu rõ ràng hoặc nhiều dấu hiệu nhỏ
   CRITICAL      // Nguy cấp: Rủi ro rất cao, khả năng cao là mua đỉnh/bán đáy
  };

ETradeHealthLevel g_trade_health_level = HEALTHY;

double           g_cycle_initial_entry_price = 0.0; // Giá vào lệnh của lệnh đầu tiên
ENUM_POSITION_TYPE g_cycle_initial_type = WRONG_VALUE; // Loại lệnh (BUY/SELL) của lệnh đầu tiên
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void resetPositionStatus()
  {
   buy_total_count = 0;
   buy_total_profit = 0.0;
   buy_total_volume = 0.0;
   buy_weighted_price_sum = 0.0;

   sell_total_count = 0;
   sell_total_profit = 0.0;
   sell_total_volume = 0.0;
   sell_weighted_price_sum = 0.0;
  }

//+------------------------------------------------------------------+
//| Quản lý và theo dõi lợi nhuận của các lệnh                       |
//+------------------------------------------------------------------+
void ManagePositionProfitBreakEvent()
  {
   resetPositionStatus();
   long buy_tickets[];
   long sell_tickets[];
   datetime earliest_open_time = 0;
   double first_entry_price = 0;
   ENUM_POSITION_TYPE first_entry_type = WRONG_VALUE;

// --- BƯỚC 1: LẶP QUA TẤT CẢ CÁC LỆNH ĐỂ TÍNH TOÁN CÁC THÔNG SỐ HIỆN TẠI ---
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket_ulong = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket_ulong))
        {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol)
           {
            datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
            if(earliest_open_time == 0 || open_time < earliest_open_time)
              {
               earliest_open_time = open_time;
               first_entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
               first_entry_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
              }

            ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            long ticket = (long)ticket_ulong;
            double price_open = PositionGetDouble(POSITION_PRICE_OPEN);
            double volume = PositionGetDouble(POSITION_VOLUME);
            double profit = PositionGetDouble(POSITION_PROFIT); // Lợi nhuận đã bao gồm swap

            if(type == POSITION_TYPE_BUY)
              {
               int current_size = ArraySize(buy_tickets);
               ArrayResize(buy_tickets, current_size + 1);
               buy_tickets[current_size] = ticket;
               buy_total_count++;
               buy_total_profit += profit;
               buy_total_volume += volume;
               buy_weighted_price_sum += price_open * volume;
              }
            else
               if(type == POSITION_TYPE_SELL)
                 {
                  int current_size = ArraySize(sell_tickets);
                  ArrayResize(sell_tickets, current_size + 1);
                  sell_tickets[current_size] = ticket;
                  sell_total_count++;
                  sell_total_profit += profit;
                  sell_total_volume += volume;
                  sell_weighted_price_sum += price_open * volume;
                 }
           }
        }
     }

   int current_positions_count = buy_total_count + sell_total_count;
   double current_total_profit = buy_total_profit + sell_total_profit;

// --- Phần 2: Cập nhật lịch sử và trạng thái ---
   double current_total_pips = 0; // Khai báo ở đây để có thể dùng trong toàn bộ hàm

   if(current_positions_count > 0 && g_previous_positions_count == 0)
     {
      // Bắt đầu chu kỳ mới
      g_cycle_initial_entry_price = first_entry_price;
      g_cycle_initial_type = first_entry_type;

      // Tính pips lần đầu tiên
      if(g_cycle_initial_type == POSITION_TYPE_BUY)
         current_total_pips = (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_cycle_initial_entry_price) / _Point;
      else
         if(g_cycle_initial_type == POSITION_TYPE_SELL)
            current_total_pips = (g_cycle_initial_entry_price - SymbolInfoDouble(_Symbol, SYMBOL_ASK)) / _Point;

      // Gán trực tiếp giá trị khởi tạo
      g_total_profit_max = current_total_profit;
      g_total_profit_min = current_total_profit;
      g_total_pips_max = current_total_pips;
      g_total_pips_min = current_total_pips;
      g_total_pips_now = current_total_pips;
     }
   else
      if(current_positions_count > 0)
        {
         // Đang trong chu kỳ, tính pips hiện tại
         if(g_cycle_initial_type == POSITION_TYPE_BUY)
            current_total_pips = (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_cycle_initial_entry_price) / _Point;
         else
            if(g_cycle_initial_type == POSITION_TYPE_SELL)
               current_total_pips = (g_cycle_initial_entry_price - SymbolInfoDouble(_Symbol, SYMBOL_ASK)) / _Point;

         g_total_profit_max = MathMax(g_total_profit_max, current_total_profit);
         g_total_profit_min = MathMin(g_total_profit_min, current_total_profit);
         g_total_pips_max = MathMax(g_total_pips_max, current_total_pips);
         g_total_pips_min = MathMin(g_total_pips_min, current_total_pips);
         g_total_pips_now = current_total_pips;
        }
      else
        {
         // Kết thúc chu kỳ, reset tất cả các biến trạng thái
         g_cycle_initial_risk = 0;
         g_cycle_initial_entry_price = 0;
         g_cycle_initial_type = WRONG_VALUE;
         g_total_profit_max = 0.0;
         g_total_profit_min = 0.0;
         g_total_pips_max = 0.0;
         g_total_pips_min = 0.0;
         g_total_pips_now = 0.0;
        }
   g_previous_positions_count = current_positions_count;

// --- Phần 4 & 5: Chấm điểm và Hiển thị (giữ nguyên) ---
   int risk_score = 0;
   if(current_positions_count > 0 && g_cycle_initial_risk > 0)
     {
      if(g_total_pips_min < -50)
         risk_score += 3;
      if(g_total_pips_max <= 1)
         risk_score += 2;
      if(g_total_profit_max < g_cycle_initial_risk * 0.1)
         risk_score += 1;
      double pips_drawdown_from_peak = g_total_pips_max - current_total_pips;
      if(pips_drawdown_from_peak > 30)
         risk_score += 2;
      if((TimeCurrent() - earliest_open_time) > 1800 && current_total_pips < 0)
         risk_score += 2;
     }
   if(risk_score >= 6)
      g_trade_health_level = CRITICAL;
   else
      if(risk_score >= 4)
         g_trade_health_level = WARNING;
      else
         if(risk_score >= 2)
            g_trade_health_level = CONCERN;
         else
            g_trade_health_level = HEALTHY;

// --- BƯỚC 3: GỌI HÀM XỬ LÝ CHO TỪNG NHÓM NẾU CÓ DỮ LIỆU ---
   if(ArraySize(buy_tickets) > 0)
      ProcessPositionsByType(POSITION_TYPE_BUY, buy_tickets, buy_total_profit, buy_total_volume, buy_weighted_price_sum, earliest_open_time);

   if(ArraySize(sell_tickets) > 0)
      ProcessPositionsByType(POSITION_TYPE_SELL, sell_tickets, sell_total_profit, sell_total_volume, sell_weighted_price_sum, earliest_open_time);
  }

double commission_per_lot = 8.0;
int max_loss_amount = 100;
//+------------------------------------------------------------------+
//| Hàm xử lý logic cho một nhóm lệnh đã được phân loại              |
//+------------------------------------------------------------------+
void ProcessPositionsByType(ENUM_POSITION_TYPE target_type,
                            const long &tickets[],
                            double total_profit,
                            double total_volume,
                            double weighted_price_sum,
                            datetime earliest_open_time)
  {
   string pos_type_str = (target_type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   string log_message = "";
   int positions_count = ArraySize(tickets);

// --- XỬ LÝ ĐÓNG LỆNH KHI LỖ 100$ HOẶC RỦI RO CAO ---
   if(!IsForexPair(_Symbol) && !(StringFind(_Symbol, "XAU") >= 0))
      commission_per_lot = 0;
   double total_commission = total_volume * commission_per_lot;
   double net_profit = total_profit - total_commission; // Lợi nhuận ròng chưa tính swap

   if(net_profit < -max_loss_amount || (net_profit < -max_loss_amount/2 && positions_count == 1) || (positions_count == 4 && net_profit > 0))
     {
      Print(StringFormat("Có %d lệnh %s. Tổng lợi nhuận: %.2f, Phí: %.2f, Lợi nhuận ròng: %.2f",
                         positions_count, pos_type_str, total_profit, total_commission, net_profit));
      if(net_profit < -max_loss_amount/2 && positions_count == 1)
         Print("Xu hướng đảo chiều mạnh. Đang đóng thoát lệnh ", pos_type_str, " không DCA ...");
      if(net_profit < -max_loss_amount)
         Print("Lợi nhuận ròng < -" + max_loss_amount + ". Đang đóng tất cả các lệnh ", pos_type_str, "...");
      if(positions_count == 4 && net_profit > 0)
         Print("Rủi ro cao. Đang đóng tất cả các lệnh ", pos_type_str, "...");
      for(int i = 0; i < positions_count; i++)
         trade.PositionClose(tickets[i]);
      if(target_type == POSITION_TYPE_BUY)
         g_h1_buy_signal_active = false;
      if(target_type == POSITION_TYPE_SELL)
         g_h1_sell_signal_active = false;
      return;
     }

// --- QUẢN LÝ TÍN HIỆU ---
   if(net_profit > 0)
     {
      if(positions_count == 1 && TimeCurrent() - earliest_open_time > 1800)
        {
         Print("Thị trường sideway quá lâu. Đang đóng tất cả các lệnh ", pos_type_str, "...");
         for(int i = 0; i < positions_count; i++)
            trade.PositionClose(tickets[i]);
        }
      if(target_type == POSITION_TYPE_BUY)
        {
         if(positions_count >= 2)
           {
            g_m30_buy_signal_active = false;
            g_h1_buy_signal_active = false;
            g_last_m30_processed_bar_time = TimeCurrent() + 30 * 60;
            g_last_h1_processed_bar_time = TimeCurrent() + 30 * 60;
            if(positions_count >= 3)
              {
               // g_h1_buy_signal_active = false;
               g_last_h1_processed_bar_time = TimeCurrent() + 60 * 60;
              }
           }
        }
      else
         if(target_type == POSITION_TYPE_SELL)
           {
            if(positions_count >= 2)
              {
               g_m30_sell_signal_active = false;
               g_h1_sell_signal_active = false;
               g_last_m30_processed_bar_time = TimeCurrent() + 30 * 60;
               g_last_h1_processed_bar_time = TimeCurrent() + 30 * 60;
               if(positions_count >= 3)
                 {
                  // g_h1_sell_signal_active = false;
                  g_last_h1_processed_bar_time = TimeCurrent() + 60 * 60;
                 }
              }
           }
     }

   double weighted_avg_open_price = (total_volume > 0) ? weighted_price_sum / total_volume : 0;

// --- BƯỚC 2: KIỂM TRA ĐIỀU KIỆN KÍCH HOẠT QUẢN LÝ SL ---
   if(positions_count > 0 && net_profit > positions_count * InpProfitTarget / 2)
     {
      double current_sl = 0;
      if(PositionSelectByTicket(tickets[0]))
        {
         current_sl = PositionGetDouble(POSITION_SL);
        }

      double proposed_sl_price = current_sl;
      bool is_new_sl_found = false;

      if(target_type == POSITION_TYPE_BUY && IsImbalanceUp(_Symbol, PERIOD_CURRENT, 2))
        {
         double imbalance_sl_candidate = iLow(_Symbol, PERIOD_CURRENT, 2);
         if(imbalance_sl_candidate > current_sl)
           {
            proposed_sl_price = imbalance_sl_candidate;
            is_new_sl_found = true;
            // log_message += "BUY: Tìm thấy Imbalance mới tốt hơn. Đề xuất SL: " + DoubleToString(proposed_sl_price, _Digits) + ".\n";
           }
        }
      else
         if(target_type == POSITION_TYPE_SELL && IsImbalanceDown(_Symbol, PERIOD_CURRENT, 2))
           {
            double imbalance_sl_candidate = iHigh(_Symbol, PERIOD_CURRENT, 2);
            if(imbalance_sl_candidate < current_sl || current_sl == 0)
              {
               proposed_sl_price = imbalance_sl_candidate;
               is_new_sl_found = true;
               // log_message += "SELL: Tìm thấy Imbalance mới tốt hơn. Đề xuất SL: " + DoubleToString(proposed_sl_price, _Digits) + ".\n";
              }
           }

      // --- BƯỚC 3: KIỂM TRA ĐIỂM SL MỚI PHẢI ĐẢM BẢO LỢI NHUẬN DƯƠNG (SAU KHI TRỪ PHÍ) ---
      bool is_sl_profitable = false;
      if(is_new_sl_found)
        {
         // YÊU CẦU MỚI: Tính toán điểm hòa vốn thực tế bao gồm cả commission và swap
         // để đảm bảo SL mới phải có lợi nhuận ròng > 0.
         double total_swap = 0;
         for(int i = 0; i < positions_count; i++)
           {
            if(PositionSelectByTicket(tickets[i]))
              {
               total_swap += PositionGetDouble(POSITION_SWAP);
              }
           }

         double total_costs_in_money = total_commission + total_swap;

         // Chuyển đổi tổng chi phí (tiền) sang chênh lệch giá (price offset)
         double cost_offset_in_price = 0;
         double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
         double point_size = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         double tick_value_for_total_volume = total_volume * tick_value;

         if(tick_value_for_total_volume > 0)
           {
            // Chi phí âm (swap dương) sẽ làm giảm điểm hòa vốn, chi phí dương sẽ tăng điểm hòa vốn
            double points_needed = total_costs_in_money / tick_value_for_total_volume;
            cost_offset_in_price = points_needed * point_size;
           }

         double breakeven_price_with_costs = 0;
         if(target_type == POSITION_TYPE_BUY)
           {
            breakeven_price_with_costs = weighted_avg_open_price + cost_offset_in_price;
           }
         else
            if(target_type == POSITION_TYPE_SELL)
              {
               breakeven_price_with_costs = weighted_avg_open_price - cost_offset_in_price;
              }

         // log_message += StringFormat("Giá TB=%.5f, Phí Comm=%.2f, Phí Swap=%.2f (tương đương %.5f giá), Điểm hòa vốn thực tế=%.5f\n",
         //                            weighted_avg_open_price, total_commission, total_swap, cost_offset_in_price, breakeven_price_with_costs);

         // So sánh SL đề xuất với điểm hòa vốn thực tế
         if((target_type == POSITION_TYPE_BUY && proposed_sl_price > breakeven_price_with_costs) ||
            (target_type == POSITION_TYPE_SELL && proposed_sl_price < breakeven_price_with_costs))
           {
            is_sl_profitable = true;
            log_message += StringFormat("SL đề xuất (%.5f) tốt hơn điểm hòa vốn thực tế. ==> ĐIỀU KIỆN LỢI NHUẬN ĐẠT.\n", proposed_sl_price);
           }
        }

      // --- BƯỚC 4: THỰC HIỆN SỬA LỆNH ---
      if(is_new_sl_found && is_sl_profitable)
        {
         log_message += "--> Thực hiện dời SL cho " + (string)positions_count + " lệnh " + pos_type_str + "...";
         int success_count = 0;

         for(int i = 0; i < positions_count; i++)
           {
            long ticket_to_modify = tickets[i];
            double tp_for_this_pos = 0;

            if(PositionSelectByTicket(ticket_to_modify))
              {
               tp_for_this_pos = PositionGetDouble(POSITION_TP);
              }

            if(trade.PositionModify(ticket_to_modify, proposed_sl_price, tp_for_this_pos))
              {
               success_count++;
              }
            else
              {
               log_message += " | Lỗi dời SL lệnh " + (string)ticket_to_modify + ": " + (string)GetLastError();
              }
           }
         log_message += " --> Thành công: " + (string)success_count + "/" + (string)positions_count + ".\n";
        }
     }

   if(log_message != "")
      Print(log_message);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ManagePositionProfitPartialClose()
  {
   string log_message = "";

   if(g_managed_profit_ticket == 0)
     {
      if(PositionSelect(_Symbol))
        {
         g_managed_profit_ticket = PositionGetInteger(POSITION_TICKET);
         g_is_partially_closed = false; // Reset cờ
         log_message = "Phát hiện và bắt đầu quản lý lệnh mới (Ticket: " + (string)g_managed_profit_ticket + ").";
        }
      else
         return;
     }
   else
     {
      if(!PositionSelectByTicket(g_managed_profit_ticket))
        {
         log_message = "Lệnh (Ticket: " + (string)g_managed_profit_ticket + ") đã đóng. Reset trình quản lý.";
         g_managed_profit_ticket = 0;
         g_is_partially_closed = false;
         if(log_message != "")
            Print(log_message);
         return;
        }
     }

   if(g_is_partially_closed)
      return;

   double current_profit = PositionGetDouble(POSITION_PROFIT);

   if(current_profit > InpProfitTarget)
     {
      double current_volume = PositionGetDouble(POSITION_VOLUME);
      double volume_to_close = NormalizeDouble(current_volume * (InpClosePercent / 100.0), 2);

      if(volume_to_close >= g_volume_step)
        {
         log_message += "Lợi nhuận > $" + DoubleToString(InpProfitTarget) + ". Bắt đầu xử lý Ticket " + (string)g_managed_profit_ticket + ".\n";
         log_message += "--> Chuẩn bị chốt lời " + DoubleToString(InpClosePercent) + "% (" + DoubleToString(volume_to_close, 2) + " lots)... ";

         // --- CORE FIX V4.0: SỬ DỤNG HÀM PositionClosePartial() CHUẨN XÁC ---
         if(trade.PositionClosePartial(g_managed_profit_ticket, volume_to_close, -1))
           {
            // Yêu cầu đã được gửi đi thành công, bây giờ kiểm tra kết quả từ server
            if(trade.ResultRetcode() == TRADE_RETCODE_DONE || trade.ResultRetcode() == TRADE_RETCODE_DONE_PARTIAL)
              {
               log_message += "THÀNH CÔNG.\n";
               Sleep(500); // Chờ server cập nhật trạng thái

               if(PositionSelectByTicket(g_managed_profit_ticket))
                 {
                  double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
                  double current_tp = PositionGetDouble(POSITION_TP);
                  ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
                  double new_sl_price = (type == POSITION_TYPE_BUY) ? (open_price + g_points_plus) : (open_price - g_points_plus);

                  log_message += "--> Dời SL về BE + " + DoubleToString(InpPipsPlus) + " pips (Giá: " + DoubleToString(new_sl_price, _Digits) + ")... ";

                  if(trade.PositionModify(g_managed_profit_ticket, new_sl_price, current_tp))
                     log_message += "THÀNH CÔNG.\n";
                  else
                     log_message += "THẤT BẠI. Lỗi: " + (string)GetLastError() + ".\n";
                 }
               else
                  log_message += "--> Không thể chọn lại vị thế sau khi chốt lời một phần để dời SL.\n";
              }
            else
              {
               log_message += "THẤT BẠI. Phản hồi từ Server: " + (string)trade.ResultRetcode() + " - " + trade.ResultComment() + ".\n";
              }
           }
         else
           {
            log_message += "THẤT BẠI. Không thể gửi yêu cầu chốt lệnh. Lỗi: " + (string)GetLastError() + ".\n";
           }
        }
      else
        {
         log_message += "Khối lượng cần đóng (" + DoubleToString(volume_to_close, 2) + ") quá nhỏ, bỏ qua.\n";
        }

      g_is_partially_closed = true;
     }

   if(log_message != "")
      Print(log_message);
  }
//+------------------------------------------------------------------+
//| Tính toán % sức mạnh của nến Daily và lưu vào biến toàn cục.      |
//+------------------------------------------------------------------+
double CalculateBarStatus(ENUM_TIMEFRAMES tf, int shift)
  {
   double DOpen = iOpen(_Symbol, tf, shift);
   double DHigh = iHigh(_Symbol, tf, shift);
   double DLow = iLow(_Symbol, tf, shift);
   double DClose = iClose(_Symbol, tf, shift);
   double g_current_percent = 0.0;

// Tránh lỗi chia cho 0 nếu nến là một đường thẳng
   if(DHigh == DLow)
     {
      g_current_percent = (DClose == DOpen) ? 50.0 : 100.0;
      return g_current_percent;
     }

   if(DClose > DOpen)
     {
      // Nến tăng: tính % vị trí giá đóng cửa so với toàn bộ range
      g_current_percent = ((DClose - DLow) / (DHigh - DLow)) * 100.0;
     }
   else
      if(DClose < DOpen)
        {
         // Nến giảm: tính % độ "mạnh" của phe bán (giá đóng cửa càng gần đáy càng mạnh)
         g_current_percent = ((DHigh - DClose) / (DHigh - DLow)) * 100.0;
        }
      else
        {
         // Nến Doji
         g_current_percent = 50.0;
        }
   return g_current_percent;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void UpdateRangeByCondition(RangeInfo &range, bool is_sideways_condition, const string &tf_label, const MqlRates &current_rate)
  {
   if(is_sideways_condition)
     {
      // --- KHỐI KHỞI TẠO RANGE ---
      if(!range.isActive)
        {
         range.isActive = true;
         range.timeframeLabel = tf_label;
         range.rangeStartTime = iTime(_Symbol, PERIOD_M5, 11);

         // <<< THAY ĐỔI DUY NHẤT: Gọi các hàm pivot mới >>>
         // Tham số (12, 0) có nghĩa là tìm trong 12 nến, bắt đầu từ shift 0.
         range.high = GetHighestPivotPrice(_Symbol, PERIOD_M5, 12, 0);
         range.low = GetLowestPivotPrice(_Symbol, PERIOD_M5, 12, 0);
         // <<< KẾT THÚC THAY ĐỔI >>>
        }
      // --- KHỐI MỞ RỘNG RANGE (GIỮ NGUYÊN) ---
      else
        {
         range.high = MathMax(range.high, current_rate.high);
         range.low = MathMin(range.low, current_rate.low);
        }
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void UpdateActiveRanges(const MqlRates &current_rate)
  {
   if(InpEnableRange_Diagnosis)
      UpdateRangeByCondition(g_st_ranges[RANGE_DIAGNOSIS], g_short_term.market_diagnosis_text == T.sideways, "H1-Diagnosis", current_rate);
   if(InpEnableRange_PriceNeutral)
      UpdateRangeByCondition(g_st_ranges[RANGE_PRICE], g_short_term.close_state == 0, "H1-Price", current_rate);
   if(InpEnableRange_EmaNeutral)
      UpdateRangeByCondition(g_st_ranges[RANGE_EMA], g_short_term.ema_state == 0, "H1-Ema", current_rate);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ProcessBarCloseBreakout(RangeInfo &range, datetime &last_alert_time, const MqlRates &prev_bar)
  {
   if(!range.isActive || range.high <= 0)
      return;
   datetime current_time = TimeCurrent();
   if(current_time <= last_alert_time + InpAlertCooldownSeconds)
      return;

   int direction = 0;
   if(prev_bar.close > range.high)
      direction = 1;
   else
      if(prev_bar.close < range.low)
         direction = -1;

   if(direction != 0)
     {
      // Lấy 5 cây nến M1 của cây nến M5 này
      MqlRates m1_bars[5];
      int copied = CopyRates(_Symbol, PERIOD_M1, prev_bar.time - 4 * 60, 5, m1_bars);
      if(copied != 5)
         return; // Không đủ dữ liệu M1

      // Tìm cây nến M1 đầu tiên phá range
      int breakout_index = -1;
      for(int i = 0; i < 5; i++)
        {
         if(direction == 1 && m1_bars[i].close > range.high)  // Bullish
           {
            breakout_index = i;
            break;
           }
         else
            if(direction == -1 && m1_bars[i].close < range.low)  // Bearish
              {
               breakout_index = i;
               break;
              }
        }

      bool close_back_in_range = false;
      // Chỉ kiểm tra nếu đã có breakout_index hợp lệ
      if(breakout_index != -1)
        {
         for(int i = breakout_index; i < 5; i++)
           {
            if(m1_bars[i].close >= range.low && m1_bars[i].close <= range.high)
              {
               close_back_in_range = true;
               break;
              }
           }
        }

      // Nếu có breakout nhưng KHÔNG có cây nào close lại trong range thì vào lệnh
      string direction_text = (direction == 1) ? "Bullish" : "Bearish";
      if(breakout_index != -1 && !close_back_in_range)
        {
         double stoploss = direction == 1 ? range.low : range.high;
         double entry = direction == 1 ? range.high : range.low;
         // BreakoutTrade(direction, stoploss, entry);
         Alert(FormatBreakoutAlert(range.timeframeLabel, direction_text, prev_bar.close, prev_bar.time));
         if(InpEnableTelegramDebug)
           {
            string detailed_message = FormatBreakoutMessage(range.timeframeLabel, direction, prev_bar.close, prev_bar.time, stoploss, entry);
            if(InpSendScreenshotOnSignal)
               SendTelegramScreenshot(SanitizeHTML(detailed_message));
            else
               SendTelegramMessage(detailed_message);
           }
         last_alert_time = current_time;
        }

      // Luôn ghi nhận thông tin range vào lịch sử, bất kể có vào lệnh hay không
      last_alert_time = current_time;
      RangeInfo *historical_range = new RangeInfo();
      *historical_range = range;
      historical_range.rangeEndTime = prev_bar.time;
      historical_range.breakoutPrice = prev_bar.close;
      historical_range.breakoutDirection = direction_text;
      g_historical_ranges.Add(historical_range);
      ResetRangeInfo(range);
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CheckForBarCloseBreakouts(const MqlRates &prev_bar)
  {
   for(int i = 0; i < 3; i++)
     {
      bool check_st = (i == RANGE_DIAGNOSIS && InpEnableRange_Diagnosis) || (i == RANGE_PRICE && InpEnableRange_PriceNeutral) || (i == RANGE_EMA && InpEnableRange_EmaNeutral);
      if(check_st)
         ProcessBarCloseBreakout(g_st_ranges[i], g_last_st_breakout_alert_time[i], prev_bar);
     }
  }

//+------------------------------------------------------------------+
//| HÀM VÀO LỆNH CHÍNH - ĐÃ ĐƯỢC CẬP NHẬT HOÀN CHỈNH CHO MQL5          |
//+------------------------------------------------------------------+
struct PositionInfo
  {
   ulong             ticket;
   long              open_time;
   double            open_price;
  };

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DoDCA(int order_type_signal)
  {
   string log_prefix = "[DoDCA] ";

// --- BƯỚC 0: KIỂM TRA TÍN HIỆU ĐẦU VÀO ---
   if(order_type_signal != 1 && order_type_signal != -1)
     {
      Print(log_prefix, "Tín hiệu vào lệnh không hợp lệ: ", order_type_signal);
      return;
     }


   ENUM_POSITION_TYPE target_position_type = (order_type_signal == 1) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   string pos_type_str = (order_type_signal == 1) ? "BUY" : "SELL";

// --- BƯỚC 1: THU THẬP THÔNG TIN CÁC LỆNH CÙNG LOẠI TRÊN SYMBOL ---
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
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
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

// --- BƯỚC 2: KIỂM TRA CÁC ĐIỀU KIỆN DCA CƠ BẢN ---
   if(positions_of_type == 0 || positions_of_type >= 4)
     {
      return;
     }

   Print(log_prefix, "Bắt đầu kiểm tra điều kiện DCA ", pos_type_str);

// Sắp xếp các lệnh theo thời gian mở để xử lý logic theo thứ tự
   if(positions_of_type > 0)
     {
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
      // Sau khi sắp xếp, first_position_entry_price là của lệnh đầu tiên (cũ nhất)
      first_position_entry_price = target_positions[0].open_price;
     }

   if(net_profit >= -(positions_of_type * InpRiskAmount))
     {
      Print(log_prefix, "Có ", positions_of_type, " lệnh ", pos_type_str, " nhưng tổng lợi nhuận (", DoubleToString(net_profit, 2), ") chưa âm quá " + -InpRiskAmount + "$. Không DCA.");
      return;
     }

// --- BƯỚC 2.2: KIỂM TRA THỜI GIAN KỂ TỪ LỆNH CUỐI CÙNG ---
   if(positions_of_type > 0)
     {
      int min_seconds_between_orders = 5 * 60; // 5 phút
      int max_seconds_between_orders = 2 * 60 * 60; // 1h
      if(positions_of_type >= 1)
         min_seconds_between_orders = 15 * 60;
      if(positions_of_type >= 2 && net_profit < -50)
         min_seconds_between_orders = 30 * 60;
      // Mảng đã được sắp xếp, lệnh cuối cùng là lệnh mới nhất
      long last_order_time = target_positions[positions_of_type - 1].open_time;
      long time_elapsed_since_last = TimeCurrent() - last_order_time;

      if(time_elapsed_since_last < min_seconds_between_orders)
        {
         Print(log_prefix, StringFormat("Chưa đủ thời gian tối thiểu kể từ lệnh cuối cùng. Đã trôi qua: %d giây. HỦY DCA.", time_elapsed_since_last));
         return;
        }
      else
         if(time_elapsed_since_last > max_seconds_between_orders)
           {
            Print(log_prefix, StringFormat("Đã quá thời gian tối đa kể từ lệnh cuối cùng. Đã trôi qua: %d giây. HỦY DCA.", time_elapsed_since_last));
            return;
           }
      Print(log_prefix, StringFormat("Đã đủ thời gian (%d giây) kể từ lệnh cuối. Tiếp tục kiểm tra.", time_elapsed_since_last));
     }

// --- BƯỚC 2.5: KIỂM TRA CÁC ĐIỀU KIỆN NÂNG CAO KHI CÓ 3 LỆNH ---
   if(positions_of_type == 3)
     {
      double entry_price_3 = target_positions[2].open_price;

      if(target_position_type == POSITION_TYPE_BUY)
        {
         Print(log_prefix, "Phát hiện có 3 lệnh BUY, kiểm tra điều kiện VÀO LỆNH 4 (chỉ cần 1 trong 2 điều kiện đạt).");

         double current_ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         bool condition1_met = (current_ask > entry_price_3);
         Print(log_prefix, StringFormat("Kiểm tra ĐK1 (Giá): Ask hiện tại (%.5f) > Giá lệnh 3 (%.5f)? ==> %s",
                                        current_ask, entry_price_3, (condition1_met ? "ĐẠT" : "KHÔNG ĐẠT")));

         datetime time_order_1 = (datetime)target_positions[0].open_time;
         datetime time_order_3 = (datetime)target_positions[2].open_time;
         int bar_index_1 = iBarShift(_Symbol, _Period, time_order_1);
         int bar_index_3 = iBarShift(_Symbol, _Period, time_order_3);
         bool condition2_met = false;

         if(bar_index_1 < 0 || bar_index_3 < 0)
           {
            Print(log_prefix, "Không thể tìm thấy nến tương ứng với thời gian vào lệnh. Bỏ qua kiểm tra điều kiện đáy.");
           }
         else
           {
            int count1 = bar_index_1 - bar_index_3 + 1;
            int lowest_bar_index_1 = iLowest(_Symbol, _Period, MODE_LOW, count1, bar_index_3);
            double lowest_low_1 = iLow(_Symbol, _Period, lowest_bar_index_1);

            int count2 = bar_index_3 + 1;
            int lowest_bar_index_2 = iLowest(_Symbol, _Period, MODE_LOW, count2, 0);
            double lowest_low_2 = iLow(_Symbol, _Period, lowest_bar_index_2);

            condition2_met = (lowest_low_2 > lowest_low_1);
            Print(log_prefix, StringFormat("Kiểm tra ĐK2 (Đáy): Đáy 2 (%.5f) > Đáy 1 (%.5f)? ==> %s",
                                           lowest_low_2, lowest_low_1, (condition2_met ? "ĐẠT" : "KHÔNG ĐẠT")));
           }

         if(condition1_met || condition2_met)
           {
            Print(log_prefix, "Ít nhất một điều kiện được thỏa mãn. TIẾP TỤC DCA.");
           }
         else
           {
            Print(log_prefix, "Cả hai điều kiện đều không thỏa mãn. HỦY DCA.");
            return;
           }
        }
      else
         if(target_position_type == POSITION_TYPE_SELL)
           {
            // *** BẮT ĐẦU CODE MỚI CHO LỆNH SELL ***
            Print(log_prefix, "Phát hiện có 3 lệnh SELL, kiểm tra điều kiện VÀO LỆNH 4 (chỉ cần 1 trong 2 điều kiện đạt).");

            double current_bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            // Điều kiện 1: Giá đã bắt đầu hồi phục (thấp hơn giá vào lệnh 3)
            bool condition1_met = (current_bid < entry_price_3);
            Print(log_prefix, StringFormat("Kiểm tra ĐK1 (Giá): Bid hiện tại (%.5f) < Giá lệnh 3 (%.5f)? ==> %s",
                                           current_bid, entry_price_3, (condition1_met ? "ĐẠT" : "KHÔNG ĐẠT")));

            datetime time_order_1 = (datetime)target_positions[0].open_time;
            datetime time_order_3 = (datetime)target_positions[2].open_time;
            int bar_index_1 = iBarShift(_Symbol, _Period, time_order_1);
            int bar_index_3 = iBarShift(_Symbol, _Period, time_order_3);
            bool condition2_met = false;

            if(bar_index_1 < 0 || bar_index_3 < 0)
              {
               Print(log_prefix, "Không thể tìm thấy nến tương ứng với thời gian vào lệnh. Bỏ qua kiểm tra điều kiện đỉnh.");
              }
            else
              {
               // Đỉnh 1: Đỉnh cao nhất trong khoảng từ lệnh 1 đến lệnh 3
               int count1 = bar_index_1 - bar_index_3 + 1;
               int highest_bar_index_1 = iHighest(_Symbol, _Period, MODE_HIGH, count1, bar_index_3);
               double highest_high_1 = iHigh(_Symbol, _Period, highest_bar_index_1);

               // Đỉnh 2: Đỉnh cao nhất trong khoảng từ sau lệnh 3 đến hiện tại
               int count2 = bar_index_3 + 1;
               int highest_bar_index_2 = iHighest(_Symbol, _Period, MODE_HIGH, count2, 0);
               double highest_high_2 = iHigh(_Symbol, _Period, highest_bar_index_2);

               // Điều kiện 2: Cấu trúc đã tạo đỉnh thấp hơn (dấu hiệu đảo chiều)
               condition2_met = (highest_high_2 < highest_high_1);
               Print(log_prefix, StringFormat("Kiểm tra ĐK2 (Đỉnh): Đỉnh 2 (%.5f) < Đỉnh 1 (%.5f)? ==> %s",
                                              highest_high_2, highest_high_1, (condition2_met ? "ĐẠT" : "KHÔNG ĐẠT")));
              }

            if(condition1_met || condition2_met)
              {
               Print(log_prefix, "Ít nhất một điều kiện được thỏa mãn. TIẾP TỤC DCA.");
              }
            else
              {
               Print(log_prefix, "Cả hai điều kiện đều không thỏa mãn. HỦY DCA.");
               return;
              }
            // *** KẾT THÚC CODE MỚI CHO LỆNH SELL ***
           }
     }

// --- BƯỚC 3: THỰC HIỆN DCA ---
   Print(log_prefix, StringFormat("Có %d lệnh %s đang âm (Profit: %.2f). Bắt đầu DCA.", positions_of_type, pos_type_str, net_profit));

// --- BƯỚC 3.1: TÍNH TOÁN KHỐI LƯỢNG MỚI ---
   double volume_to_open = 0;
   if(positions_of_type == 1)
     {
      long time_elapsed_since_first = TimeCurrent() - target_positions[0].open_time;
      const long time_threshold = 15 * 60; // 15 phút tính bằng giây

      if(time_elapsed_since_first > time_threshold)
        {
         volume_to_open = total_volume * 3;
         Print(log_prefix, StringFormat("Trường hợp 1 lệnh (QUÁ 15 PHÚT): Lệnh đã mở %d giây. Volume mới = %.2f (x3)", time_elapsed_since_first, volume_to_open));
        }
      else
        {
         volume_to_open = total_volume * 2;
         Print(log_prefix, StringFormat("Trường hợp 1 lệnh (<= 15 PHÚT): Lệnh đã mở %d giây. Volume mới = %.2f (x2)", time_elapsed_since_first, volume_to_open));
        }
     }
   else
     {
      volume_to_open = total_volume;
      Print(log_prefix, "Trường hợp >=2 lệnh: Tổng khối lượng các lệnh trước là ", DoubleToString(total_volume, 2), ", khối lượng mới sẽ là ", DoubleToString(volume_to_open, 2));
     }

// --- BƯỚC 3.2: TÍNH TOÁN GIÁ TP MỚI ---
   double new_tp_price = 0;
   if(positions_of_type == 1)
     {
      double market_price = (target_position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      double tp_base_price = (first_position_entry_price + market_price) / 2.0;
      double future_total_volume = total_volume + volume_to_open;
      double point_size = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double current_spread_in_points = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / point_size;

      if(!IsForexPair(_Symbol) && !(StringFind(_Symbol, "XAU") >= 0))
         commission_per_lot = 0;
      double total_commission_cost = future_total_volume * commission_per_lot;
      // Tính chi phí spread bằng tiền
      double total_spread_cost_in_money = total_commission_cost + current_spread_in_points * tick_value * future_total_volume;

      // Chuyển chi phí spread từ tiền về chênh lệch giá (price offset)
      double tick_value_for_total_volume = future_total_volume * tick_value;
      double spread_cost_offset_in_price = 0;
      if(tick_value_for_total_volume > 0)
        {
         spread_cost_offset_in_price = (total_spread_cost_in_money / tick_value_for_total_volume) * point_size;
        }

      if(target_position_type == POSITION_TYPE_BUY)
        {
         new_tp_price = tp_base_price + spread_cost_offset_in_price;
        }
      else
         if(target_position_type == POSITION_TYPE_SELL)
           {
            new_tp_price = tp_base_price - spread_cost_offset_in_price;
           }

      Print(log_prefix, StringFormat("Tổng vol (cũ+mới)=%.2f, Spread offset=%.5f, TP mới=%.5f",
                                     future_total_volume, spread_cost_offset_in_price, new_tp_price));
     }
   else // Trường hợp có 2 lệnh trở lên
     {
      double future_total_volume = total_volume + volume_to_open;
      double future_weighted_price_sum = weighted_price_sum;
      double current_price_for_new_order = (target_position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      future_weighted_price_sum += current_price_for_new_order * volume_to_open;
      double breakeven_price = future_weighted_price_sum / future_total_volume;

      if(!IsForexPair(_Symbol) && !(StringFind(_Symbol, "XAU") >= 0))
         commission_per_lot = 0;
      double total_commission_cost = future_total_volume * commission_per_lot;
      double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double point_size = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double current_spread_in_points = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / point_size;
      double total_spread_cost = current_spread_in_points * tick_value * future_total_volume;
      double total_cost = buffer_profit + total_commission_cost + total_spread_cost;
      double tick_value_for_total_volume = future_total_volume * tick_value;
      double total_cost_offset_in_price = 0;
      if(tick_value_for_total_volume > 0)
        {
         double points_needed = total_cost / tick_value_for_total_volume;
         total_cost_offset_in_price = points_needed * point_size;
        }
      if(target_position_type == POSITION_TYPE_BUY)
        {
         new_tp_price = breakeven_price + total_cost_offset_in_price;
        }
      else
         if(target_position_type == POSITION_TYPE_SELL)
           {
            new_tp_price = breakeven_price - total_cost_offset_in_price;
           }
      Print(log_prefix, StringFormat("Trường hợp >=2 lệnh: BE=%.5f, Phí Comm=%.2f, Phí Spread=%.2f, TP hòa vốn mới=%.5f",
                                     breakeven_price, total_commission_cost, total_spread_cost, new_tp_price));
     }

   new_tp_price = NormalizeDouble(new_tp_price, _Digits);

// --- BƯỚC 3.3: Chuẩn hóa khối lượng và vào lệnh mới ---
   double min_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   volume_to_open = MathMax(min_vol, MathMin(max_vol, volume_to_open));
   volume_to_open = floor(volume_to_open / step_vol) * step_vol;
   volume_to_open = NormalizeDouble(volume_to_open, 2);

   if(volume_to_open < min_vol)
     {
      Print(log_prefix, "Khối lượng tính toán (", DoubleToString(volume_to_open, 2), ") nhỏ hơn mức tối thiểu (", DoubleToString(min_vol, 2), "). Hủy lệnh.");
      return;
     }

// --- BƯỚC 3.4: Thực thi lệnh mới ---
   Print(log_prefix, "Chuẩn bị vào lệnh ", pos_type_str, " với khối lượng: ", DoubleToString(volume_to_open, 2));
   bool result = false;
   if(order_type_signal == 1)
     {
      result = trade.Buy(volume_to_open, _Symbol, 0, 0, 0, "DCA Buy");
     }
   else
     {
      result = trade.Sell(volume_to_open, _Symbol, 0, 0, 0, "DCA Sell");
     }

// --- BƯỚC 3.5: Sau khi vào lệnh, cập nhật TP cho TẤT CẢ các lệnh cùng loại ---
   if(result)
     {
      Print(log_prefix, "Vào lệnh mới thành công. Cập nhật TP cho tất cả lệnh ", pos_type_str, " về ", DoubleToString(new_tp_price, _Digits));
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket))
           {
            if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
               (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == target_position_type)
              {
               double current_sl = PositionGetDouble(POSITION_SL);
               trade.PositionModify(ticket, current_sl, new_tp_price);
              }
           }
        }
      SendTradeExecutionToTelegram("DCA", pos_type_str, (target_position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID), 0, new_tp_price, g_short_term, g_long_term);
      Print(log_prefix, "Đã cập nhật TP thành công.");
     }
   else
     {
      Print(log_prefix, "VÀO LỆNH THẤT BẠI. Lỗi: ", (string)GetLastError(), " - ", trade.ResultComment());
     }
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AttemptTradeExecution(int direction, double breakout_level, double stoploss_level, ENUM_SETUP_FAMILY setup_family_id)
  {
   int entry_type = GetSymbolTradeState(_Symbol);
   if(entry_type == direction || entry_type == 2)
     {
      DoDCA(direction);
      return;
     }

   if(!isTradingTime())
      return;

   string symbol = _Symbol;
   long digits = SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   long spread_points = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if(spread_points == 0)
      spread_points = long((SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / g_point_value);

   double spread_in_price = spread_points * g_point_value;
   double buffer_in_price = InpStopLossBufferPips * g_point_per_pips * g_point_value;
   double total_adjustment = spread_in_price + buffer_in_price;

   double entry_price = 0, sl_price = 0, tp_price = 0, lot_size = 0;
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);

   string family_name = GetSetupFamilyName(setup_family_id);
   string comment = family_name;

   bool success = false;
   string order_type = ""; // Biến lưu loại lệnh

   datetime expiration = TimeCurrent() + 15 * 60; // 15 phút

   if(direction == 1)  // BUY
     {
      if(breakout_level == 0 || ask > breakout_level)
        {
         // Vào lệnh BUY ngay
         entry_price = ask;
         sl_price = stoploss_level - buffer_in_price;

         if(entry_price <= sl_price)
           {
            PrintFormat("Giá vào lệnh BUY (%.*f) đã quá gần hoặc vượt qua điểm SL (%.*f). Hủy vào lệnh.", (int)digits, entry_price, (int)digits, sl_price);
            return;
           }

         lot_size = CalculateLotSize(InpRiskAmount, sl_price, entry_price);
         if(lot_size <= 0)
           {
            Print("Không thể tính toán khối lượng lệnh hợp lệ. Hủy vào lệnh.");
            return;
           }

         tp_price = entry_price + (entry_price - sl_price) * InpRRRatio;

         sl_price = 0; // NormalizeDouble(sl_price, (int)digits);
         tp_price = NormalizeDouble(tp_price, (int)digits);

         order_type = "BUY"; // Gán loại lệnh
         success = trade.Buy(lot_size, symbol, entry_price, sl_price, tp_price, comment);
        }
      else
        {
         // Đặt lệnh BUY STOP tại breakout_level + spread
         double buy_stop_price = breakout_level + spread_in_price;
         sl_price = stoploss_level - buffer_in_price;

         if(buy_stop_price <= sl_price)
           {
            PrintFormat("Giá BUY STOP (%.*f) đã quá gần hoặc vượt qua điểm SL (%.*f). Hủy vào lệnh.", (int)digits, buy_stop_price, (int)digits, sl_price);
            return;
           }

         lot_size = CalculateLotSize(InpRiskAmount, sl_price, buy_stop_price);
         if(lot_size <= 0)
           {
            Print("Không thể tính toán khối lượng lệnh hợp lệ. Hủy vào lệnh.");
            return;
           }

         tp_price = buy_stop_price + (buy_stop_price - sl_price) * InpRRRatio;

         sl_price = NormalizeDouble(sl_price, (int)digits);
         tp_price = NormalizeDouble(tp_price, (int)digits);

         entry_price = buy_stop_price;

         order_type = "BUY STOP"; // Gán loại lệnh
         success = trade.BuyStop(lot_size, entry_price, symbol, sl_price, tp_price, ORDER_TIME_SPECIFIED, expiration, comment);
        }
     }
   else
      if(direction == -1)  // SELL
        {
         if(breakout_level == 0 || ask < breakout_level)
           {
            // Vào lệnh SELL ngay
            entry_price = bid;
            sl_price = stoploss_level + total_adjustment;

            if(entry_price >= sl_price)
              {
               PrintFormat("Giá vào lệnh SELL (%.*f) đã quá gần hoặc vượt qua điểm SL (%.*f). Hủy vào lệnh.", (int)digits, entry_price, (int)digits, sl_price);
               return;
              }

            lot_size = CalculateLotSize(InpRiskAmount, sl_price, entry_price);
            if(lot_size <= 0)
              {
               Print("Không thể tính toán khối lượng lệnh hợp lệ. Hủy vào lệnh.");
               return;
              }

            tp_price = entry_price - (sl_price - entry_price) * InpRRRatio;

            sl_price = 0; // NormalizeDouble(sl_price, (int)digits);
            tp_price = NormalizeDouble(tp_price, (int)digits);

            order_type = "SELL"; // Gán loại lệnh
            success = trade.Sell(lot_size, symbol, entry_price, sl_price, tp_price, comment);
           }
         else
           {
            // Đặt lệnh SELL STOP tại breakout_level
            double sell_stop_price = breakout_level - sell_stop_buffer;
            sl_price = stoploss_level + total_adjustment;

            if(sell_stop_price >= sl_price)
              {
               PrintFormat("Giá SELL STOP (%.*f) đã quá gần hoặc vượt qua điểm SL (%.*f). Hủy vào lệnh.", (int)digits, sell_stop_price, (int)digits, sl_price);
               return;
              }

            lot_size = CalculateLotSize(InpRiskAmount, sl_price, sell_stop_price);
            if(lot_size <= 0)
              {
               Print("Không thể tính toán khối lượng lệnh hợp lệ. Hủy vào lệnh.");
               return;
              }

            tp_price = sell_stop_price - (sl_price - sell_stop_price) * InpRRRatio;

            sl_price = NormalizeDouble(sl_price, (int)digits);
            tp_price = NormalizeDouble(tp_price, (int)digits);

            entry_price = sell_stop_price;

            order_type = "SELL STOP"; // Gán loại lệnh
            success = trade.SellStop(lot_size, sell_stop_price, symbol, sl_price, tp_price, ORDER_TIME_SPECIFIED, expiration, comment);
           }
        }
      else
        {
         return;
        }

// ------ BỔ SUNG LOẠI LỆNH VÀO THÔNG BÁO ------
   if(success)
     {
      PrintFormat("Vào lệnh %s %s thành công! Lot: %.2f, Entry: %.*f, SL: %.*f, TP: %.*f",
                  order_type, symbol, lot_size, (int)digits, trade.ResultPrice(), (int)digits, sl_price, (int)digits, tp_price);
      SendTradeExecutionToTelegram("NEW TRADE", order_type, entry_price, sl_price, tp_price, g_short_term, g_long_term);
     }
   else
     {
      PrintFormat("Vào lệnh %s thất bại. Mã lỗi: %d, Lời nhắn: %s", order_type, trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AttemptBreakoutExecution(int direction, double stoploss_level, double entry_level, ENUM_SETUP_FAMILY setup_family_id)
  {
   if(!isTradingTime())
      return;

   string symbol = _Symbol;
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   long spread_points = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if(spread_points == 0)
      spread_points = long((SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / g_point_value);

   double spread_in_price = spread_points * g_point_value;
   double buffer_in_price = InpStopLossBufferPips * g_point_per_pips * g_point_value;
   double total_adjustment = spread_in_price + buffer_in_price;

   double entry_price = 0, sl_price = 0, tp_price = 0, lot_size = 0;
   string comment = GetSetupFamilyName(setup_family_id);
   bool success = false;

//--- BUY direction
   if(direction == 1)
     {
      if(setup_family_id == SETUP_FAMILY_BUY_BREAKOUT_RANGE)
        {
         // BUY Market
         entry_price = SymbolInfoDouble(symbol, SYMBOL_ASK);
         sl_price = stoploss_level - total_adjustment;
        }
      else
         if(setup_family_id == SETUP_FAMILY_BUYLIMIT_BREAKOUT_RANGE)
           {
            // BUY Limit
            entry_price = entry_level;
            sl_price = stoploss_level - total_adjustment;
           }

      if(entry_price <= sl_price)
        {
         PrintFormat("⚠️ Giá BUY (%.5f) không hợp lệ so với SL (%.5f)", entry_price, sl_price);
         return;
        }

      lot_size = CalculateLotSize(InpRiskAmount, sl_price, entry_price);
      if(lot_size <= 0)
        {
         Print("❌ Lot size không hợp lệ.");
         return;
        }

      tp_price = entry_price + (entry_price - sl_price) * InpRRRatio;
     }
//--- SELL direction
   else
      if(direction == -1)
        {
         if(setup_family_id == SETUP_FAMILY_SELL_BREAKOUT_RANGE)
           {
            // SELL Market
            entry_price = SymbolInfoDouble(symbol, SYMBOL_BID);
            sl_price = stoploss_level + total_adjustment;
           }
         else
            if(setup_family_id == SETUP_FAMILY_SELLLIMIT_BREAKOUT_RANGE)
              {
               // SELL Limit
               entry_price = entry_level;
               sl_price = stoploss_level + total_adjustment;
              }

         if(entry_price >= sl_price)
           {
            PrintFormat("⚠️ Giá SELL (%.5f) không hợp lệ so với SL (%.5f)", entry_price, sl_price);
            return;
           }

         lot_size = CalculateLotSize(InpRiskAmount, sl_price, entry_price);
         if(lot_size <= 0)
           {
            Print("❌ Lot size không hợp lệ.");
            return;
           }

         tp_price = entry_price - (sl_price - entry_price) * InpRRRatio;
        }
      else
        {
         Print("⚠️ Hướng giao dịch không hợp lệ.");
         return;
        }

   sl_price = NormalizeDouble(sl_price, digits);
   tp_price = NormalizeDouble(tp_price, digits);
   entry_price = NormalizeDouble(entry_price, digits);

//--- Market Orders
   if(setup_family_id == SETUP_FAMILY_BUY_BREAKOUT_RANGE)
      success = trade.Buy(lot_size, symbol, entry_price, sl_price, tp_price, comment);

   else
      if(setup_family_id == SETUP_FAMILY_SELL_BREAKOUT_RANGE)
         success = trade.Sell(lot_size, symbol, entry_price, sl_price, tp_price, comment);

      //--- Limit Orders (tự hết hạn sau 30 phút)
      else
         if(setup_family_id == SETUP_FAMILY_BUYLIMIT_BREAKOUT_RANGE)
           {
            datetime expiration = TimeCurrent() + 30 * 60; // 30 phút
            success = trade.BuyLimit(lot_size, entry_price, symbol, sl_price, tp_price,
                                     ORDER_TIME_SPECIFIED, expiration, comment);
           }
         else
            if(setup_family_id == SETUP_FAMILY_SELLLIMIT_BREAKOUT_RANGE)
              {
               datetime expiration = TimeCurrent() + 30 * 60; // 30 phút
               success = trade.SellLimit(lot_size, entry_price, symbol, sl_price, tp_price,
                                         ORDER_TIME_SPECIFIED, expiration, comment);
              }

//--- Result
   if(success)
     {
      PrintFormat("✅ %s %s thành công! Lot: %.2f, Entry: %.5f, SL: %.5f, TP: %.5f",
                  comment, symbol, lot_size, entry_price, sl_price, tp_price);

      SendTradeExecutionToTelegram("NEW TRADE", (direction == 1 ? "BUY" : "SELL"),
                                   entry_price, sl_price, tp_price, g_short_term, g_long_term);
     }
   else
     {
      PrintFormat("❌ Vào lệnh thất bại. Mã lỗi: %d, Thông điệp: %s",
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AttemptBreakoutExecution(ENUM_SETUP_FAMILY setup_family_id)
  {
   string symbol = _Symbol;
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

// Lấy cây nến M5 vừa đóng
   MqlRates m5_candle[];
   if(CopyRates(symbol, PERIOD_M5, 1, 1, m5_candle) != 1)
     {
      Print("Không lấy được dữ liệu nến M5.");
      return;
     }
   double candle_high = m5_candle[0].high;
   double candle_low = m5_candle[0].low;

   long spread_points = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   if(spread_points == 0)
      spread_points = long((SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID)) / g_point_value);
   double spread_in_price = spread_points * g_point_value;
   double buffer_in_price = InpStopLossBufferPips * g_point_per_pips * g_point_value;
   double total_adjustment = spread_in_price + buffer_in_price;

   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);

   double sl_buy = NormalizeDouble(candle_low - buffer_in_price, digits);
   double sl_sell = NormalizeDouble(candle_high + total_adjustment, digits);

   double entry_buy = NormalizeDouble(candle_high + spread_in_price, digits);
   double entry_sell = NormalizeDouble(candle_low - sell_stop_buffer, digits);

   double lot_size_buy = CalculateLotSize(InpRiskAmount, sl_buy, entry_buy);    // Tùy bạn định nghĩa hàm này
   double lot_size_sell = CalculateLotSize(InpRiskAmount, sl_sell, entry_sell); // Tùy bạn định nghĩa hàm này
   if(lot_size_buy <= 0 || lot_size_sell <= 0)
     {
      Print("Lot size không hợp lệ.");
      return;
     }

   double tp_buy = entry_buy + (entry_buy - sl_buy) * InpRRRatio;
   double tp_sell = entry_sell - (sl_sell - entry_sell) * InpRRRatio;

   string comment = "Breakout";

   bool success = false;

// Nếu giá hiện tại vượt đỉnh/đáy thì vào lệnh Market luôn
   if(ask > candle_high)
     {
      Print("Giá đã vượt đỉnh nến breakout, BUY ngay!");
      success = trade.Buy(lot_size_buy, symbol, ask, sl_buy, tp_buy, comment);
     }
   else
      if(ask < candle_low)
        {
         Print("Giá đã thấp hơn đáy nến breakout, SELL ngay!");
         success = trade.Sell(lot_size_sell, symbol, bid, sl_sell, tp_sell, comment);
        }
      else
        {
         // Đặt 2 lệnh chờ BUY STOP và SELL STOP
         datetime expiration = TimeCurrent() + 15 * 60; // 15 phút
         bool buy_pending = trade.BuyStop(lot_size_buy, entry_buy, symbol, sl_buy, tp_buy, ORDER_TIME_SPECIFIED, expiration, comment);
         bool sell_pending = trade.SellStop(lot_size_sell, entry_sell, symbol, sl_sell, tp_sell, ORDER_TIME_SPECIFIED, expiration, comment);

         if(buy_pending)
           {
            PrintFormat("✅ %s %s thành công! Lot: %.2f, Entry: %.5f, SL: %.5f, TP: %.5f",
                        comment, symbol, lot_size_buy, entry_buy, sl_buy, tp_buy);

            SendTradeExecutionToTelegram("NEW TRADE", "BUY STOP", entry_buy, sl_buy, tp_buy, g_short_term, g_long_term);
           }
         if(sell_pending)
           {
            PrintFormat("✅ %s %s thành công! Lot: %.2f, Entry: %.5f, SL: %.5f, TP: %.5f",
                        comment, symbol, lot_size_sell, entry_sell, sl_sell, tp_sell);

            SendTradeExecutionToTelegram("NEW TRADE", "SELL STOP", entry_sell, sl_sell, tp_sell, g_short_term, g_long_term);
           }
         if(buy_pending && sell_pending)
            g_check_pending_orders = true;
         if(!buy_pending && !sell_pending)
            PrintFormat("❌ Vào lệnh thất bại. Mã lỗi: %d, Thông điệp: %s",
                        trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool HasOpenOrPendingOrderForSymbol(string symbol)
  {
// Kiểm tra các vị thế đang mở (Positions)
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == symbol)
         return true;
     }

// Kiểm tra các lệnh đang chờ xử lý (Orders/Pending Orders)
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(OrderGetString(ORDER_SYMBOL) == symbol)
        {
         int type = OrderGetInteger(ORDER_TYPE);
         // Kiểm tra các loại lệnh pending: BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP, BUY_STOP_LIMIT, SELL_STOP_LIMIT
         if(type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT ||
            type == ORDER_TYPE_BUY_STOP || type == ORDER_TYPE_SELL_STOP ||
            type == ORDER_TYPE_BUY_STOP_LIMIT || type == ORDER_TYPE_SELL_STOP_LIMIT)
           {
            return true;
           }
        }
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Lấy trạng thái giao dịch của một symbol (có lệnh BUY, SELL, cả hai, hay không) |
//| Trả về:                                                          |
//|  0 = Không có vị thế hay lệnh chờ nào                            |
//|  1 = Chỉ có vị thế/lệnh chờ BUY                                  |
//| -1 = Chỉ có vị thế/lệnh chờ SELL                                 |
//|  2 = Có cả vị thế/lệnh chờ BUY và SELL                           |
//+------------------------------------------------------------------+
int GetSymbolTradeState(string symbol)
  {
   bool has_buy = false;
   bool has_sell = false;

// --- BƯỚC 1: KIỂM TRA CÁC VỊ THẾ ĐANG MỞ (POSITIONS) ---
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      // Phải chọn vị thế trước khi lấy thông tin chi tiết
      if(PositionSelectByTicket(ticket))
        {
         if(PositionGetString(POSITION_SYMBOL) == symbol)
           {
            ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            if(type == POSITION_TYPE_BUY)
              {
               has_buy = true;
              }
            else
               if(type == POSITION_TYPE_SELL)
                 {
                  has_sell = true;
                 }

            // Tối ưu: Nếu đã tìm thấy cả hai loại, không cần tìm nữa
            if(has_buy && has_sell)
              {
               return 2;
              }
           }
        }
     }

// --- BƯỚC 2: KIỂM TRA CÁC LỆNH ĐANG CHỜ (PENDING ORDERS) ---
// Chỉ tiếp tục kiểm tra nếu chưa tìm thấy cả hai loại
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      // Chọn lệnh chờ trước khi lấy thông tin
      if(OrderSelect(ticket))
        {
         if(OrderGetString(ORDER_SYMBOL) == symbol)
           {
            ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);

            // Phân loại lệnh chờ
            if(type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_BUY_STOP || type == ORDER_TYPE_BUY_STOP_LIMIT)
              {
               has_buy = true;
              }
            else
               if(type == ORDER_TYPE_SELL_LIMIT || type == ORDER_TYPE_SELL_STOP || type == ORDER_TYPE_SELL_STOP_LIMIT)
                 {
                  has_sell = true;
                 }

            // Tối ưu: Nếu đã tìm thấy cả hai loại, không cần tìm nữa
            if(has_buy && has_sell)
              {
               return 2;
              }
           }
        }
     }

// --- BƯỚC 3: TRẢ VỀ KẾT QUẢ DỰA TRÊN CÁC CỜ ĐÃ TÌM THẤY ---
   if(has_buy && has_sell)
      return 2;
   if(has_buy)
      return 1;
   if(has_sell)
      return -1;

// Nếu không có cờ nào được bật, nghĩa là không có lệnh nào
   return 0;
  }
//+------------------------------------------------------------------+
//| Hàm điều phối chính, đã được cập nhật để sử dụng SignalAnalysis.  |
//+------------------------------------------------------------------+
/*
void ExecuteTrade(const SignalAnalysis &signal)
  {
// --- Các bước kiểm tra ban đầu được giữ nguyên ---
// if(!InpEnableTrading || (InpAllowOneTrade && PositionsTotal() > 0) || SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints)
   if(!InpEnableTrading || (InpAllowOneTrade && HasOpenOrPendingOrderForSymbol(_Symbol)))
      return;

   double stopRange = MathAbs(signal.breakout_level - signal.stoploss_level);
   double maxStopRange = InpStopLossMaxInPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT) * g_point_per_pips; // 10 point = 1 pip
   if(IsForexPair(_Symbol) && stopRange > maxStopRange)
     {
      PrintFormat("Stoploss quá rộng: %.5f, giới hạn: %.5f", stopRange, maxStopRange);
      return;
     }
// --- Gọi hàm kiểm tra điều kiện "A+" mới ---
// int setup_direction = CheckTradingSetups(signal);
   ENUM_SETUP_FAMILY valid_setup_family = CheckTradingSetups(signal.signal);
// --- Nếu tìm thấy một kịch bản hợp lệ, thực thi lệnh ---
// Điều kiện bây giờ là kiểm tra xem có phải là SETUP_FAMILY_NONE hay không
   if(valid_setup_family != SETUP_FAMILY_NONE)
     {
      // In log xác nhận kịch bản hợp lệ trước khi vào lệnh
      PrintFormat("--- [Trade Check] %s Signal for %s ACCEPTED ---", (signal.signal == 1 ? "BUY" : "SELL"), _Symbol);
      PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(valid_setup_family));
      // Truyền cả hướng đi (signal.signal) và ID của kịch bản (valid_setup_family)
      // vào hàm AttemptTradeExecution để xử lý.
      AttemptTradeExecution(signal.signal, signal.breakout_level, signal.stoploss_level, valid_setup_family);
     }
   else
     {
      if(g_m30_signalType == signal.signal && g_m30_signalType != 0)
        {
         valid_setup_family = CheckCISDSetups(signal.signal);
         if(valid_setup_family != SETUP_FAMILY_NONE)
           {
            PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", (signal.signal == 1 ? "BUY" : "SELL"), _Symbol);
            PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(valid_setup_family));
            AttemptTradeExecution(signal.signal, signal.breakout_level, signal.stoploss_level, valid_setup_family);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void BreakoutTrade(int direction, double stoploss_level, double entry_level)
  {
// --- Các bước kiểm tra ban đầu được giữ nguyên ---
// if(!InpEnableTrading || (InpAllowOneTrade && PositionsTotal() > 0) || SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPoints)
   if(!InpEnableTrading || (InpAllowOneTrade && HasOpenOrPendingOrderForSymbol(_Symbol)))
      return;

   double stopRange = MathAbs(entry_level - stoploss_level);
   double maxStopRange = InpStopLossMaxInPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT) * g_point_per_pips; // 10 point = 1 pip
   if(IsForexPair(_Symbol) && stopRange > maxStopRange)
     {
      PrintFormat("Stoploss quá rộng: %.5f, giới hạn: %.5f", stopRange, maxStopRange);
      return;
     }
// --- Gọi hàm kiểm tra điều kiện "A+" mới ---
// int setup_direction = CheckTradingSetups(signal);
   ENUM_SETUP_FAMILY valid_setup_family = CheckBreakoutSetups(direction);

// --- Nếu tìm thấy một kịch bản hợp lệ, thực thi lệnh ---
// Điều kiện bây giờ là kiểm tra xem có phải là SETUP_FAMILY_NONE hay không
   if(valid_setup_family != SETUP_FAMILY_NONE)
     {
      // In log xác nhận kịch bản hợp lệ trước khi vào lệnh
      PrintFormat("--- [Trade Breakout] %s Signal for %s ACCEPTED ---", (direction == 1 ? "BUY" : "SELL"), _Symbol);
      PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(valid_setup_family));
      // Truyền cả hướng đi (signal.signal) và ID của kịch bản (valid_setup_family)
      // vào hàm AttemptTradeExecution để xử lý.
      // AttemptBreakoutExecution(direction, stoploss_level, entry_level, valid_setup_family);
      AttemptBreakoutExecution(valid_setup_family);
     }
  }
*/
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
SignalAnalysis CheckSignalsAndDraw_Stateful()
  {
// =================== PHẦN TỐI ƯU HÓA (GIỮ NGUYÊN) ===================
   static datetime s_current_h1_signal_time = 0;
   static SetupInfo s_bull_setup = {false};
   static SetupInfo s_bear_setup = {false};
   static int s_local_ltf_lastTrend = 0;

   double D1Open = iOpen(_Symbol, PERIOD_D1, 0), D1Close = iClose(_Symbol, PERIOD_D1, 0), D1High = iHigh(_Symbol, PERIOD_D1, 0), D1Low = iLow(_Symbol, PERIOD_D1, 0);
   double H1Open = iOpen(_Symbol, PERIOD_H1, 0), H1Close = iClose(_Symbol, PERIOD_H1, 0), H1High = iHigh(_Symbol, PERIOD_H1, 0), H1Low = iLow(_Symbol, PERIOD_H1, 0);
   double M30Open = iOpen(_Symbol, PERIOD_M30, 0), M30Close = iClose(_Symbol, PERIOD_M30, 0), M30High = iHigh(_Symbol, PERIOD_M30, 0), M30Low = iLow(_Symbol, PERIOD_M30, 0);
   double M15Open = iOpen(_Symbol, PERIOD_M15, 0), M15Close = iClose(_Symbol, PERIOD_M15, 0), M15High = iHigh(_Symbol, PERIOD_M15, 0), M15Low = iLow(_Symbol, PERIOD_M15, 0);
   double M5Open = iOpen(_Symbol, PERIOD_M5, 0), M5Close = iClose(_Symbol, PERIOD_M5, 0);

   int start_bar;
   bool is_full_scan = false;

// --- Logic quyết định phạm vi quét (GIỮ NGUYÊN) ---
   if(g_h1_signalTime != s_current_h1_signal_time)
     {
      is_full_scan = true;
      start_bar = iBarShift(_Symbol, _Period, g_h1_signalTime);
      if(start_bar < 0)
         start_bar = Bars(_Symbol, _Period) - 1;
      s_bull_setup.active = false;
      s_bear_setup.active = false;
      s_local_ltf_lastTrend = 0;
      s_current_h1_signal_time = g_h1_signalTime;
     }
   else
     {
      is_full_scan = false;
      datetime scan_start_time = 0;
      if(g_h1_signalType == 1 && s_bear_setup.active)
         scan_start_time = s_bear_setup.setupTime;
      else
         if(g_h1_signalType == -1 && s_bull_setup.active)
            scan_start_time = s_bull_setup.setupTime;
      if(scan_start_time > 0)
        {
         start_bar = iBarShift(_Symbol, _Period, scan_start_time);
         if(start_bar < 0)
            start_bar = 12;
        }
      else
        {
         start_bar = 12;
        }
     }
// ====================================================================

   SignalAnalysis confirmedSignal;
   confirmedSignal.signal = 0; // Thay thế TradeSignalInfo

   if(g_ltf_scan_start_time == 0 || TimeCurrent() < g_ltf_scan_start_time)
      return (confirmedSignal);

   int sub_bars = Bars(_Symbol, _Period);
   if(sub_bars < start_bar + 2)
      return (confirmedSignal);

   for(int i = start_bar; i >= 1; i--)
     {
      double close_i = iClose(_Symbol, _Period, i);
      datetime time_i = iTime(_Symbol, _Period, i);

      // --- Logic xác nhận tín hiệu Tăng (Bullish Confirmation) (GIỮ NGUYÊN) ---
      if(s_bear_setup.active && close_i > s_bear_setup.priceLevel)
        {
         if(i == 1 && time_i > g_last_trade_signal_time)
           {
            DoDCA(1);
            // if(g_h1_signalType == 1 && g_m30_signalType == 1 && g_m15_signalType == 1 && g_m5_signalType == 1
            if(g_h1_signalType == 1 && g_m5_signalType == 1
               && H1Open < H1Close && M30Open < M30Close && M15Open < M15Close && M5Open < M5Close)
              {
               PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", "BUY", _Symbol);
               DrawConfirmationLine(s_bear_setup.setupTime, time_i, s_bear_setup.priceLevel, "Bullish", s_local_ltf_lastTrend == 1);
               if(InpShowLTFLabels)
                  DrawConfirmationLabel(time_i, s_bear_setup.priceLevel, "Bullish");
               if(InpShowLTFArrows)
                 {
                  double low_i = iLow(_Symbol, _Period, i);
                  double atr_arr[];
                  CopyBuffer(AtrHandle, 0, i, 1, atr_arr);
                  double price_offset = (ArraySize(atr_arr) > 0) ? atr_arr[0] * 0.1 : _Point * 10;
                  DrawSignalArrow(time_i, low_i - price_offset, 1);
                 }
               // 5. Gửi thông báo (sử dụng hàm format mới)
               // if(g_h1_buy_signal_active && g_m30_buy_signal_active && D1Open < D1Close && state == STATE_STRONG_BULL)
               if(g_h1_buy_signal_active && D1Open < D1Close  && (state == STATE_STRONG_BULL || state == STATE_EXTREME_BULL))
                 {
                  // g_m30_buy_signal_active = false;
                  datetime adjusted_time = time_i + (InpTimeOffsetHours * 3600);
                  string simple_message = StringFormat("%s Bullish @ %s | Price: %s", _Symbol, TimeToString(adjusted_time, TIME_MINUTES), DoubleToString(close_i, _Digits));
                  TriggerCISDAlerts(simple_message);

                  // <<< BẮT ĐẦU KHỐI THU THẬP DỮ LIỆU MỚI >>>
                  // 1. Điền thông tin cơ bản
                  confirmedSignal.signal = 1;
                  confirmedSignal.signal_type = "Bullish";
                  confirmedSignal.signal_time = time_i;
                  confirmedSignal.ltf_cisd_price = close_i;
                  g_last_trade_signal_time = time_i;

                  // 2. Tính toán Stop Loss (logic gốc được giữ nguyên)
                  int setup_bar = iBarShift(_Symbol, _Period, s_bear_setup.setupTime, true);
                  int breakout_bar = iBarShift(_Symbol, _Period, time_i, true);
                  double lowest = DBL_MAX, highest = DBL_MAX;
                  lowest = FindNearestSwingLow(_Symbol, _Period, setup_bar, breakout_bar, InpMaxLookback);
                  highest = FindNearestSwingHigh(_Symbol, _Period, setup_bar, breakout_bar, 0);
                  confirmedSignal.stoploss_level = MaxSL(_Symbol, close_i, lowest, true);
                  confirmedSignal.breakout_level = highest;

                  // 3. Thực hiện tất cả các phân tích cấu trúc
                  confirmedSignal.daily_analysis = AnalyzeCandleStructure(PERIOD_D1, PERIOD_H1, 0);
                  confirmedSignal.yesterday_analysis = AnalyzeCandleStructure(PERIOD_D1, PERIOD_H1, 1);
                  confirmedSignal.h1_analysis = AnalyzeCandleStructure(PERIOD_H1, PERIOD_M5, 0);

                  // 4. Điền vào checklist (Y/N)
                  confirmedSignal.is_h1_range_breakout = (g_st_ranges[RANGE_DIAGNOSIS].isActive && close_i > g_st_ranges[RANGE_DIAGNOSIS].high);
                  confirmedSignal.is_h4_range_breakout = (g_lt_ranges[RANGE_DIAGNOSIS].isActive && close_i > g_lt_ranges[RANGE_DIAGNOSIS].high);
                  double d_open = iOpen(_Symbol, PERIOD_D1, 0);
                  double d_close = iClose(_Symbol, PERIOD_D1, 0);
                  confirmedSignal.is_daily_body_aligned = (d_close > d_open);
                  confirmedSignal.is_h1_cisd_aligned = (g_h1_breakoutPrice > d_open);
                  confirmedSignal.is_ltf_cisd_aligned = (close_i > d_open);
                  confirmedSignal.is_d1_path_aligned = (confirmedSignal.daily_analysis.path == PATH_OLHC);
                  confirmedSignal.is_h1_path_aligned = (confirmedSignal.h1_analysis.path == PATH_OLHC);

                  // PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", (confirmedSignal.signal == 1 ? "BUY" : "SELL"), _Symbol);
                  PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(SETUP_FAMILY_BUY_CISD));
                  AttemptTradeExecution(confirmedSignal.signal, 0, confirmedSignal.stoploss_level, SETUP_FAMILY_BUY_CISD);
                  /*
                  if(g_h1_signal_active)
                    {
                     ENUM_SETUP_FAMILY valid_setup_family = CheckCISDM30Setups(confirmedSignal.signal);
                     if(valid_setup_family != SETUP_FAMILY_NONE)
                       {
                        g_m30_signal_active = false;
                        g_h1_signal_active = false;
                        PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", (confirmedSignal.signal == 1 ? "BUY" : "SELL"), _Symbol);
                        PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(valid_setup_family));
                        AttemptTradeExecution(confirmedSignal.signal, 0, confirmedSignal.stoploss_level, valid_setup_family);
                       }
                    }
                  string detailed_message = FormatLTFConfirmationMessage(confirmedSignal);
                  if(InpSendScreenshotOnSignal)
                     SendTelegramScreenshot(SanitizeHTML(detailed_message));
                  else
                     SendTelegramMessage(detailed_message);
                  //*/
                 }
              }
            // <<< KẾT THÚC KHỐI THU THẬP DỮ LIỆU MỚI >>>
           }
         s_local_ltf_lastTrend = 1;
         s_bear_setup.active = false;
        }

      // --- Logic xác nhận tín hiệu Giảm (Bearish Confirmation) (GIỮ NGUYÊN) ---
      if(s_bull_setup.active && close_i < s_bull_setup.priceLevel)
        {
         if(i == 1 && time_i > g_last_trade_signal_time)
           {
            DoDCA(-1);
            // if(g_h1_signalType == -1 && g_m30_signalType == -1 && g_m15_signalType == -1 && g_m5_signalType == -1
            if(g_h1_signalType == -1 && g_m5_signalType == -1
               && H1Open > H1Close && M30Open > M30Close && M15Open > M15Close && M5Open > M5Close)
              {
               PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", "SELL", _Symbol);
               DrawConfirmationLine(s_bull_setup.setupTime, time_i, s_bull_setup.priceLevel, "Bearish", s_local_ltf_lastTrend == -1);
               if(InpShowLTFLabels)
                  DrawConfirmationLabel(time_i, s_bull_setup.priceLevel, "Bearish");
               if(InpShowLTFArrows)
                 {
                  double high_i = iHigh(_Symbol, _Period, i);
                  double atr_arr[];
                  CopyBuffer(AtrHandle, 0, i, 1, atr_arr);
                  double price_offset = (ArraySize(atr_arr) > 0) ? atr_arr[0] * 0.1 : _Point * 10;
                  DrawSignalArrow(time_i, high_i + price_offset, -1);
                 }
               // 5. Gửi thông báo (sử dụng hàm format mới)
               // if(g_h1_sell_signal_active && g_m30_sell_signal_active && D1Open > D1Close && state == STATE_STRONG_BEAR)
               if(g_h1_sell_signal_active && D1Open > D1Close && (state == STATE_STRONG_BEAR || state == STATE_EXTREME_BEAR))
                 {
                  // g_m30_sell_signal_active = false;
                  datetime adjusted_time = time_i + (InpTimeOffsetHours * 3600);
                  string simple_message = StringFormat("%s Bearish @ %s | Price: %s", _Symbol, TimeToString(adjusted_time, TIME_MINUTES), DoubleToString(close_i, _Digits));
                  TriggerCISDAlerts(simple_message);
                  // <<< BẮT ĐẦU KHỐI THU THẬP DỮ LIỆU MỚI >>>
                  // 1. Điền thông tin cơ bản
                  confirmedSignal.signal = -1;
                  confirmedSignal.signal_type = "Bearish";
                  confirmedSignal.signal_time = time_i;
                  confirmedSignal.ltf_cisd_price = close_i;
                  g_last_trade_signal_time = time_i;

                  // 2. Tính toán Stop Loss (logic gốc được giữ nguyên)
                  int setup_bar = iBarShift(_Symbol, _Period, s_bull_setup.setupTime, true);
                  int breakout_bar = iBarShift(_Symbol, _Period, time_i, true);
                  double lowest = -DBL_MAX, highest = -DBL_MAX;
                  highest = FindNearestSwingHigh(_Symbol, _Period, setup_bar, breakout_bar, InpMaxLookback);
                  lowest = FindNearestSwingLow(_Symbol, _Period, setup_bar, breakout_bar, 0);
                  confirmedSignal.stoploss_level = MaxSL(_Symbol, close_i, highest, false);
                  confirmedSignal.breakout_level = lowest;

                  // 3. Thực hiện tất cả các phân tích cấu trúc
                  confirmedSignal.daily_analysis = AnalyzeCandleStructure(PERIOD_D1, PERIOD_H1, 0);
                  confirmedSignal.yesterday_analysis = AnalyzeCandleStructure(PERIOD_D1, PERIOD_H1, 1);
                  confirmedSignal.h1_analysis = AnalyzeCandleStructure(PERIOD_H1, PERIOD_M5, 0);

                  // 4. Điền vào checklist (Y/N)
                  confirmedSignal.is_h1_range_breakout = (g_st_ranges[RANGE_DIAGNOSIS].isActive && close_i < g_st_ranges[RANGE_DIAGNOSIS].low);
                  confirmedSignal.is_h4_range_breakout = (g_lt_ranges[RANGE_DIAGNOSIS].isActive && close_i < g_lt_ranges[RANGE_DIAGNOSIS].low);
                  double d_open = iOpen(_Symbol, PERIOD_D1, 0);
                  double d_close = iClose(_Symbol, PERIOD_D1, 0);
                  confirmedSignal.is_daily_body_aligned = (d_close < d_open);
                  confirmedSignal.is_h1_cisd_aligned = (g_h1_breakoutPrice < d_open);
                  confirmedSignal.is_ltf_cisd_aligned = (close_i < d_open);
                  confirmedSignal.is_d1_path_aligned = (confirmedSignal.daily_analysis.path == PATH_OHLC);
                  confirmedSignal.is_h1_path_aligned = (confirmedSignal.h1_analysis.path == PATH_OHLC);

                  // PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", (confirmedSignal.signal == 1 ? "BUY" : "SELL"), _Symbol);
                  PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(SETUP_FAMILY_SELL_CISD));
                  AttemptTradeExecution(confirmedSignal.signal, 0, confirmedSignal.stoploss_level, SETUP_FAMILY_SELL_CISD);
                  /*
                  if(g_h1_signal_active)
                    {
                     ENUM_SETUP_FAMILY valid_setup_family = CheckCISDM30Setups(confirmedSignal.signal);
                     if(valid_setup_family != SETUP_FAMILY_NONE)
                       {
                        g_m30_signal_active = false;
                        g_h1_signal_active = false;
                        PrintFormat("--- [Trade CISD] %s Signal for %s ACCEPTED ---", (confirmedSignal.signal == 1 ? "BUY" : "SELL"), _Symbol);
                        PrintFormat("  ✅ Setup Found: %s", GetSetupFamilyName(valid_setup_family));
                        AttemptTradeExecution(confirmedSignal.signal, 0, confirmedSignal.stoploss_level, valid_setup_family);
                       }
                    }
                  string detailed_message = FormatLTFConfirmationMessage(confirmedSignal);
                  if(InpSendScreenshotOnSignal)
                     SendTelegramScreenshot(SanitizeHTML(detailed_message));
                  else
                     SendTelegramMessage(detailed_message);
                  //*/
                 }
              }
            // <<< KẾT THÚC KHỐI THU THẬP DỮ LIỆU MỚI >>>
           }
         s_local_ltf_lastTrend = -1;
         s_bull_setup.active = false;
        }

      // --- Logic tìm kiếm setup mới (GIỮ NGUYÊN) ---
      double open_i = iOpen(_Symbol, _Period, i);
      bool isBullish_i = close_i > open_i;
      bool isBearish_i = close_i < open_i;
      bool wasBearish_ip1 = (i + 1 < sub_bars) ? (iClose(_Symbol, _Period, i + 1) < iOpen(_Symbol, _Period, i + 1)) : false;
      bool wasBullish_ip1 = (i + 1 < sub_bars) ? (iClose(_Symbol, _Period, i + 1) > iOpen(_Symbol, _Period, i + 1)) : false;

      if(g_h1_signalType == -1 && isBullish_i && wasBearish_ip1)
        {
         s_bull_setup.active = true;
         s_bull_setup.priceLevel = open_i;
         s_bull_setup.setupTime = time_i;
        }
      if(g_h1_signalType == 1 && isBearish_i && wasBullish_ip1)
        {
         s_bear_setup.active = true;
         s_bear_setup.priceLevel = open_i;
         s_bear_setup.setupTime = time_i;
        }
     }
   return confirmedSignal;
  }

int InpMaxLookback = 3;

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
//|                                                                  |
//+------------------------------------------------------------------+
double MaxSL(string symbol, double entryPrice, double swingPrice, bool isBuy)
  {
   double maxDistance = 0;
   double points_per_pip = (_Digits == 3 || _Digits == 5) ? 10 : 1;

   if(StringFind(symbol, "XAU") >= 0)  // Vàng
      maxDistance = 10.0;
   else
      if(StringFind(symbol, "USTEC") >= 0 || StringFind(symbol, "NAS") >= 0)  // US Tech 100
         maxDistance = 50.0;
      else
         // if(IsForexPair(symbol))
         //    maxDistance = 20 * points_per_pip; // 20 pips (pip = 10 point với digit 5)
         // else
         maxDistance = 0; // Nếu không thuộc danh sách, bạn có thể xử lý riêng hoặc cảnh báo

   double targetSL = 0;

   if(isBuy)
     {
      // Swing thấp hơn mức giới hạn thì lấy SL theo maxDistance
      if(maxDistance > 0 && swingPrice < entryPrice - maxDistance)
         targetSL = entryPrice - maxDistance;
      else
         targetSL = swingPrice;
     }
   else
     {
      // Swing cao hơn mức giới hạn thì lấy SL theo maxDistance
      if(maxDistance > 0 && swingPrice > entryPrice + maxDistance)
         targetSL = entryPrice + maxDistance;
      else
         targetSL = swingPrice;
     }

   return targetSL;
  }

//+------------------------------------------------------------------+
//| Hàm kiểm tra một nến có phải là Đáy Swing (Fractal 5 nến)       |
//+------------------------------------------------------------------+
bool IsSwingLow(string symbol, ENUM_TIMEFRAMES timeframe, int bar_index)
  {
   if(bar_index < 2 || bar_index >= Bars(symbol, timeframe) - 2)
      return false;

   double low_center = iLow(symbol, timeframe, bar_index);

   if(low_center > iLow(symbol, timeframe, bar_index + 1))
      return false;
   if(low_center > iLow(symbol, timeframe, bar_index + 2))
      return false;
   if(low_center > iLow(symbol, timeframe, bar_index - 1))
      return false;
   if(low_center > iLow(symbol, timeframe, bar_index - 2))
      return false;

   return true;
  }

//+------------------------------------------------------------------+
//| Hàm kiểm tra một nến có phải là Đỉnh Swing (Fractal 5 nến)      |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsSwingHigh(string symbol, ENUM_TIMEFRAMES timeframe, int bar_index)
  {
   if(bar_index < 2 || bar_index >= Bars(symbol, timeframe) - 2)
      return false;

   double high_center = iHigh(symbol, timeframe, bar_index);

   if(high_center < iHigh(symbol, timeframe, bar_index + 1))
      return false;
   if(high_center < iHigh(symbol, timeframe, bar_index + 2))
      return false;
   if(high_center < iHigh(symbol, timeframe, bar_index - 1))
      return false;
   if(high_center < iHigh(symbol, timeframe, bar_index - 2))
      return false;

   return true;
  }

//+------------------------------------------------------------------+
//| Cập nhật: Tìm 2 Swing Low gần nhất và trả về giá trị thấp hơn     |
//+------------------------------------------------------------------+
double FindNearestSwingLow(string symbol, ENUM_TIMEFRAMES timeframe, int startBar, int endBar, int maxLookback)
  {
   double firstSwingLowPrice = DBL_MAX;
   double secondSwingLowPrice = DBL_MAX;
   int swingLowCount = 0;

   int searchLimit = startBar + maxLookback;

   for(int k = endBar; k <= searchLimit; k++)
     {
      if(IsSwingLow(symbol, timeframe, k))
        {
         swingLowCount++;
         if(swingLowCount == 1)
            firstSwingLowPrice = iLow(symbol, timeframe, k);
         else
            if(swingLowCount == 2)
              {
               secondSwingLowPrice = iLow(symbol, timeframe, k);
               break;
              }
        }
     }

   if(swingLowCount == 2)
      return MathMin(firstSwingLowPrice, secondSwingLowPrice);
   else
      if(swingLowCount == 1)
         return firstSwingLowPrice;
      else // Trường hợp 3: Không tìm thấy swing low
        {
         // Bổ sung kiểm tra vùng IMB
         double imbPrice = DBL_MAX;
         int imbFound = -1;
         for(int k = endBar; k <= searchLimit; k++)
           {
            if(IsImbalanceUp(symbol, timeframe, k))
              {
               imbPrice = iLow(symbol, timeframe, k); // Lấy giá low của chân nến IMB
               imbFound = k;
               break; // Chỉ lấy nến IMB đầu tiên tìm thấy
              }
           }
         if(imbFound != -1)
            return imbPrice; // Nếu có IMB, trả về giá low của chân nến IMB

         // Nếu không có IMB, trả về giá thấp nhất trong vùng tìm kiếm như cũ
         int lowest_bar_index = iLowest(symbol, timeframe, MODE_LOW, searchLimit - endBar + 1, endBar);
         return iLow(symbol, timeframe, lowest_bar_index);
        }
  }

//+------------------------------------------------------------------+
//| Xác định Bullish Imbalance (FVG tăng) - Hàm này đã đúng         |
//| Có thể viết gọn lại bằng lệnh return trực tiếp.                  |
//+------------------------------------------------------------------+
bool IsImbalanceUp(string symbol, ENUM_TIMEFRAMES timeframe, int index)
  {
// Điều kiện cần ít nhất 3 nến lịch sử (index=2 sẽ dùng nến 3, 2, 1)
   if(index < 2)
      return false;

// Giá cao nhất của nến đầu tiên trong cụm 3 nến
   double high_Nen1 = iHigh(symbol, timeframe, index + 1);
// Giá thấp nhất của nến thứ ba trong cụm 3 nến
   double low_Nen3 = iLow(symbol, timeframe, index - 1);

// Nếu giá thấp của nến 3 cao hơn giá cao của nến 1 -> có imbalance
   return (low_Nen3 > high_Nen1);
  }

//+------------------------------------------------------------------+
//| Xác định Bearish Imbalance (FVG giảm) - PHIÊN BẢN ĐÃ SỬA LỖI     |
//+------------------------------------------------------------------+
bool IsImbalanceDown(string symbol, ENUM_TIMEFRAMES timeframe, int index)
  {
// Điều kiện cần ít nhất 3 nến lịch sử
   if(index < 2)
      return false;

// Giá thấp nhất của nến đầu tiên trong cụm 3 nến
   double low_Nen1 = iLow(symbol, timeframe, index + 1);
// Giá cao nhất của nến thứ ba trong cụm 3 nến
   double high_Nen3 = iHigh(symbol, timeframe, index - 1);

// SỬA LỖI: Điều kiện đúng là giá cao của nến 3 phải thấp hơn giá thấp của nến 1
   return (high_Nen3 < low_Nen1);
  }

//+------------------------------------------------------------------+
//| Cập nhật: Tìm 2 Swing High gần nhất và trả về giá trị cao hơn      |
//+------------------------------------------------------------------+
double FindNearestSwingHigh(string symbol, ENUM_TIMEFRAMES timeframe, int startBar, int endBar, int maxLookback)
  {
// --- Khởi tạo các biến để lưu trữ ---
   double firstSwingHighPrice = 0;  // Giá của swing high đầu tiên
   double secondSwingHighPrice = 0; // Giá của swing high thứ hai
   int swingHighCount = 0;          // Bộ đếm số swing high

   int searchLimit = startBar + maxLookback;

// --- Bắt đầu vòng lặp tìm kiếm ---
   for(int k = endBar; k <= searchLimit; k++)
     {
      if(IsSwingHigh(symbol, timeframe, k))
        {
         swingHighCount++;

         if(swingHighCount == 1)
           {
            firstSwingHighPrice = iHigh(symbol, timeframe, k);
           }
         else
            if(swingHighCount == 2)
              {
               secondSwingHighPrice = iHigh(symbol, timeframe, k);
               break; // Đã tìm đủ, thoát
              }
        }
     }

// --- Đưa ra quyết định ---

// Trường hợp 1: Tìm thấy cả 2 swing high
   if(swingHighCount == 2)
     {
      // Trả về giá trị cao hơn giữa hai swing high
      return MathMax(firstSwingHighPrice, secondSwingHighPrice);
     }
// Trường hợp 2: Chỉ tìm thấy 1 swing high
   else
      if(swingHighCount == 1)
        {
         return firstSwingHighPrice;
        }
      // Trường hợp 3 (Fallback): Không tìm thấy swing high nào
      else
        {
         // Bổ sung kiểm tra vùng IMB
         double imbPrice = DBL_MAX;
         int imbFound = -1;
         for(int k = endBar; k <= searchLimit; k++)
           {
            if(IsImbalanceDown(symbol, timeframe, k))
              {
               imbPrice = iHigh(symbol, timeframe, k); // Lấy giá low của chân nến IMB
               imbFound = k;
               break; // Chỉ lấy nến IMB đầu tiên tìm thấy
              }
           }
         if(imbFound != -1)
            return imbPrice; // Nếu có IMB, trả về giá low của chân nến IMB

         // Trả về giá cao nhất trong toàn bộ vùng đã tìm kiếm
         int highest_bar_index = iHighest(symbol, timeframe, MODE_HIGH, searchLimit - endBar + 1, endBar);
         return iHigh(symbol, timeframe, highest_bar_index);
        }
  }

enum EnumSwingSearchState
  {
   LOOKING_FOR_HIGH, // Đang trong trạng thái tìm một Swing High
   LOOKING_FOR_LOW   // Đang trong trạng thái tìm một Swing Low
  };
// --------------------------------------------------------------------

//+------------------------------------------------------------------+
//| Tìm 2 Đỉnh Swing trong một phạm vi xác định                      |
//| swing1_price: Đỉnh xa hơn trong quá khứ (hình thành trước)        |
//| swing2_price: Đỉnh gần hơn hiện tại (hình thành sau)             |
//+------------------------------------------------------------------+
bool FindLastTwoSwingHighs(string symbol, ENUM_TIMEFRAMES timeframe, int startBar, int searchLimit,
                           double &swing1_price, double &swing2_price)
  {
   swing1_price = 0;
   swing2_price = 0;
   int swingsFound = 0;
   EnumSwingSearchState currentState = LOOKING_FOR_LOW;

// Quét ngược từ startBar đến searchLimit
   for(int k = startBar; k <= searchLimit; k++)
     {
      if(currentState == LOOKING_FOR_LOW && IsSwingLow(symbol, timeframe, k))
        {
         currentState = LOOKING_FOR_HIGH;
        }
      else
         if(currentState == LOOKING_FOR_HIGH && IsSwingHigh(symbol, timeframe, k))
           {
            swingsFound++;
            if(swingsFound == 1)
              {
               swing2_price = iHigh(symbol, timeframe, k); // Đỉnh gần nhất (mới hơn)
              }
            else
               if(swingsFound == 2)
                 {
                  swing1_price = iHigh(symbol, timeframe, k); // Đỉnh xa hơn (cũ hơn)
                  return true;
                 }
            currentState = LOOKING_FOR_LOW;
           }
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Tìm 2 Đáy Swing trong một phạm vi xác định                       |
//| swing1_price: Đáy xa hơn trong quá khứ (hình thành trước)         |
//| swing2_price: Đáy gần hơn hiện tại (hình thành sau)              |
//+------------------------------------------------------------------+
bool FindLastTwoSwingLows(string symbol, ENUM_TIMEFRAMES timeframe, int startBar, int searchLimit,
                          double &swing1_price, double &swing2_price)
  {
   swing1_price = 0;
   swing2_price = 0;
   int swingsFound = 0;
   EnumSwingSearchState currentState = LOOKING_FOR_HIGH;

   for(int k = startBar; k <= searchLimit; k++)
     {
      if(currentState == LOOKING_FOR_HIGH && IsSwingHigh(symbol, timeframe, k))
        {
         currentState = LOOKING_FOR_LOW;
        }
      else
         if(currentState == LOOKING_FOR_LOW && IsSwingLow(symbol, timeframe, k))
           {
            swingsFound++;
            if(swingsFound == 1)
              {
               swing2_price = iLow(symbol, timeframe, k); // Đáy gần nhất (mới hơn)
              }
            else
               if(swingsFound == 2)
                 {
                  swing1_price = iLow(symbol, timeframe, k); // Đáy xa hơn (cũ hơn)
                  return true;
                 }
            currentState = LOOKING_FOR_HIGH;
           }
     }

   return false;
  }

//+------------------------------------------------------------------+
//| Quản lý TP dựa trên thời gian và trạng thái lời/lỗ               |
//+------------------------------------------------------------------+
void ManageTPByTimeAndLoss(string symbol)
  {
// --- 1. Chọn vị thế và kiểm tra trạng thái ---
   if(!PositionSelect(symbol))
     {
      // Nếu không có lệnh nào nhưng biến ticket vẫn còn -> lệnh đã đóng
      if(g_managed_ticket != 0)
        {
         ResetTradeManagementState(0);
        }
      return; // Không có lệnh để quản lý
     }

   long current_ticket = PositionGetInteger(POSITION_TICKET);

// Nếu ticket hiện tại khác ticket đang quản lý -> đây là lệnh mới
   if(current_ticket != g_managed_ticket)
     {
      ResetTradeManagementState(current_ticket);
     }

// --- 2. Lấy thông tin cần thiết ---
   double current_tp = PositionGetDouble(POSITION_TP);
   if(current_tp == 0)
      return; // Không quản lý lệnh không có TP

   datetime time_entry = (datetime)PositionGetInteger(POSITION_TIME);
   double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
   ENUM_POSITION_TYPE position_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

// --- 3. Kiểm tra các điều kiện ---
// Tính thời gian đã trôi qua (tính bằng giây)
   long elapsed_seconds = TimeCurrent() - time_entry;

// Kiểm tra xem lệnh có đang âm hay không
   bool is_in_loss = false;
   if(position_type == POSITION_TYPE_BUY)
     {
      is_in_loss = (SymbolInfoDouble(symbol, SYMBOL_BID) < open_price);
     }
   else
      if(position_type == POSITION_TYPE_SELL)
        {
         is_in_loss = (SymbolInfoDouble(symbol, SYMBOL_ASK) > open_price);
        }

// Nếu không âm, không làm gì cả
   if(!is_in_loss)
      return;

// --- 4. Áp dụng các quy tắc thời gian ---

// Quy tắc 1: Sau 15 phút (900 giây)
   if(elapsed_seconds >= 900 && !g_is_tp_adjusted_15_min)
     {
      // Tính TP mới = 1/2 khoảng cách từ giá mở cửa đến TP hiện tại
      double new_tp = open_price + (current_tp - open_price) / 2.0;

      if(trade.PositionModify(current_ticket, PositionGetDouble(POSITION_SL), new_tp))
        {
         PrintFormat("Lệnh #%d âm sau 15 phút. TP giảm xuống còn %s",
                     current_ticket, DoubleToString(new_tp, _Digits));
         g_is_tp_adjusted_15_min = true; // Đánh dấu đã xử lý
        }
      return; // Thoát ra để chờ lần kiểm tra tiếp theo
     }

// Quy tắc 2: Sau 30 phút (1800 giây)
   if(elapsed_seconds >= 1800 && !g_is_tp_adjusted_30_min)
     {
      // Tính TP mới = 1/2 khoảng cách từ giá mở cửa đến TP hiện tại
      double new_tp = open_price + (current_tp - open_price) / 2.0;

      if(trade.PositionModify(current_ticket, PositionGetDouble(POSITION_SL), new_tp))
        {
         PrintFormat("Lệnh #%d vẫn âm sau 30 phút. TP tiếp tục giảm xuống còn %s",
                     current_ticket, DoubleToString(new_tp, _Digits));
         g_is_tp_adjusted_30_min = true; // Đánh dấu đã xử lý
        }
     }
  }

long g_managed_ticket = 0;

// Cờ trạng thái để đánh dấu các mốc điều chỉnh TP
bool g_is_tp_adjusted_15_min = false;
bool g_is_tp_adjusted_30_min = false;

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ResetTradeManagementState(long new_ticket)
  {
   g_managed_ticket = new_ticket;
   g_is_tp_adjusted_15_min = false;
   g_is_tp_adjusted_30_min = false;
// dca_when_trend_reversal = false;
   if(new_ticket > 0)
     {
      Print("Bắt đầu theo dõi trạng thái TP cho lệnh #", new_ticket);
     }
   else
     {
      Print("Không còn lệnh nào để theo dõi. Đã reset trạng thái.");
     }
  }
//==================================================================
// SECTION 5: ANALYSIS & CALCULATION FUNCTIONS
//==================================================================
void FindAndDrawH1Setup()
  {
// =================== PHẦN TỐI ƯU HÓA ===================
   static datetime s_last_h1_analysis_time = 0; // Biến tĩnh để lưu thời gian
   datetime current_h1_bar_time = iTime(_Symbol, _Period, 0);

   if(current_h1_bar_time == s_last_h1_analysis_time && s_last_h1_analysis_time != 0)
     {
      // Chưa có nến H1 mới VÀ đây không phải lần chạy đầu tiên, thoát ngay.
      return;
     }
// Nếu có nến mới hoặc đây là lần đầu chạy, cập nhật thời gian và tiếp tục.
   s_last_h1_analysis_time = current_h1_bar_time;
// ==========================================================
   g_h1_signalType = 0;
   g_ltf_scan_start_time = 0;
   int h1_bars = (int)Bars(_Symbol, InpPrimaryTimeframe);
   if(h1_bars < 3)
      return;
   for(int i = 1; i < MathMin(h1_bars - 1, 24); i++)
     {
      bool isBearish = iClose(_Symbol, InpPrimaryTimeframe, i) < iOpen(_Symbol, InpPrimaryTimeframe, i);
      bool wasBullish = iClose(_Symbol, InpPrimaryTimeframe, i + 1) > iOpen(_Symbol, InpPrimaryTimeframe, i + 1);
      if(isBearish && wasBullish)
        {
         double level = iOpen(_Symbol, InpPrimaryTimeframe, i);
         datetime setupTime = iTime(_Symbol, InpPrimaryTimeframe, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, InpPrimaryTimeframe, k) > level)
              {
               g_h1_signalType = 1;
               g_h1_breakoutPrice = iClose(_Symbol, InpPrimaryTimeframe, k);
               g_h1_signalTime = iTime(_Symbol, InpPrimaryTimeframe, k);
               g_ltf_scan_start_time = g_h1_signalTime + PeriodSeconds(InpPrimaryTimeframe);
               if(InpShowH1Line)
                  DrawH1PrimaryLine(setupTime, g_ltf_scan_start_time, level, g_h1_signalType);
               return;
              }
           }
        }
      bool isBullish = iClose(_Symbol, InpPrimaryTimeframe, i) > iOpen(_Symbol, InpPrimaryTimeframe, i);
      bool wasBearish = iClose(_Symbol, InpPrimaryTimeframe, i + 1) < iOpen(_Symbol, InpPrimaryTimeframe, i + 1);
      if(isBullish && wasBearish)
        {
         double level = iOpen(_Symbol, InpPrimaryTimeframe, i);
         datetime setupTime = iTime(_Symbol, InpPrimaryTimeframe, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, InpPrimaryTimeframe, k) < level)
              {
               g_h1_signalType = -1;
               g_h1_breakoutPrice = iClose(_Symbol, InpPrimaryTimeframe, k);
               g_h1_signalTime = iTime(_Symbol, InpPrimaryTimeframe, k);
               g_ltf_scan_start_time = g_h1_signalTime + PeriodSeconds(InpPrimaryTimeframe);
               if(InpShowH1Line)
                  DrawH1PrimaryLine(setupTime, g_ltf_scan_start_time, level, g_h1_signalType);
               return;
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int FindM30CISDStatusSetup(int g_mtf_signalType)
  {
// =================== PHẦN TỐI ƯU HÓA ===================
   ENUM_TIMEFRAMES mtf = PERIOD_M30;
   static datetime s_last_m30_analysis_time = 0; // Biến tĩnh để lưu thời gian
   datetime current_m30_bar_time = iTime(_Symbol, mtf, 0);

   if(current_m30_bar_time == s_last_m30_analysis_time && s_last_m30_analysis_time != 0)
     {
      // Chưa có nến H1 mới VÀ đây không phải lần chạy đầu tiên, thoát ngay.
      return g_mtf_signalType;
     }
// Nếu có nến mới hoặc đây là lần đầu chạy, cập nhật thời gian và tiếp tục.
   s_last_m30_analysis_time = current_m30_bar_time;
// ==========================================================
   int mtf_bars = (int)Bars(_Symbol, mtf);
   if(mtf_bars < 3)
      return g_mtf_signalType;
   for(int i = 1; i < MathMin(mtf_bars - 1, 24); i++)
     {
      bool isBearish = iClose(_Symbol, mtf, i) < iOpen(_Symbol, mtf, i);
      bool wasBullish = iClose(_Symbol, mtf, i + 1) > iOpen(_Symbol, mtf, i + 1);
      if(isBearish && wasBullish)
        {
         double level = iOpen(_Symbol, mtf, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, mtf, k) > level)
              {
               g_mtf_signalType = 1;
               return g_mtf_signalType;
              }
           }
        }
      bool isBullish = iClose(_Symbol, mtf, i) > iOpen(_Symbol, mtf, i);
      bool wasBearish = iClose(_Symbol, mtf, i + 1) < iOpen(_Symbol, mtf, i + 1);
      if(isBullish && wasBearish)
        {
         double level = iOpen(_Symbol, mtf, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, mtf, k) < level)
              {
               g_mtf_signalType = -1;
               return g_mtf_signalType;
              }
           }
        }
     }
   return g_mtf_signalType = 0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int FindM15CISDStatusSetup(int g_mtf_signalType)
  {
// =================== PHẦN TỐI ƯU HÓA ===================
   ENUM_TIMEFRAMES mtf = PERIOD_M15;
   static datetime s_last_m15_analysis_time = 0; // Biến tĩnh để lưu thời gian
   datetime current_m15_bar_time = iTime(_Symbol, mtf, 0);

   if(current_m15_bar_time == s_last_m15_analysis_time && s_last_m15_analysis_time != 0)
     {
      // Chưa có nến H1 mới VÀ đây không phải lần chạy đầu tiên, thoát ngay.
      return g_mtf_signalType;
     }
// Nếu có nến mới hoặc đây là lần đầu chạy, cập nhật thời gian và tiếp tục.
   s_last_m15_analysis_time = current_m15_bar_time;
// ==========================================================
   int mtf_bars = (int)Bars(_Symbol, mtf);
   if(mtf_bars < 3)
      return g_mtf_signalType;
   for(int i = 1; i < MathMin(mtf_bars - 1, 24); i++)
     {
      bool isBearish = iClose(_Symbol, mtf, i) < iOpen(_Symbol, mtf, i);
      bool wasBullish = iClose(_Symbol, mtf, i + 1) > iOpen(_Symbol, mtf, i + 1);
      if(isBearish && wasBullish)
        {
         double level = iOpen(_Symbol, mtf, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, mtf, k) > level)
              {
               g_mtf_signalType = 1;
               return g_mtf_signalType;
              }
           }
        }
      bool isBullish = iClose(_Symbol, mtf, i) > iOpen(_Symbol, mtf, i);
      bool wasBearish = iClose(_Symbol, mtf, i + 1) < iOpen(_Symbol, mtf, i + 1);
      if(isBullish && wasBearish)
        {
         double level = iOpen(_Symbol, mtf, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, mtf, k) < level)
              {
               g_mtf_signalType = -1;
               return g_mtf_signalType;
              }
           }
        }
     }
   return g_mtf_signalType = 0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int FindM5CISDStatusSetup(int g_mtf_signalType)
  {
// =================== PHẦN TỐI ƯU HÓA ===================
   ENUM_TIMEFRAMES mtf = PERIOD_M5;
   static datetime s_last_m5_analysis_time = 0; // Biến tĩnh để lưu thời gian
   datetime current_m5_bar_time = iTime(_Symbol, mtf, 0);

   if(current_m5_bar_time == s_last_m5_analysis_time && s_last_m5_analysis_time != 0)
     {
      // Chưa có nến H1 mới VÀ đây không phải lần chạy đầu tiên, thoát ngay.
      return g_mtf_signalType;
     }
// Nếu có nến mới hoặc đây là lần đầu chạy, cập nhật thời gian và tiếp tục.
   s_last_m5_analysis_time = current_m5_bar_time;
// ==========================================================
   int mtf_bars = (int)Bars(_Symbol, mtf);
   if(mtf_bars < 3)
      return g_mtf_signalType;
   for(int i = 1; i < MathMin(mtf_bars - 1, 24); i++)
     {
      bool isBearish = iClose(_Symbol, mtf, i) < iOpen(_Symbol, mtf, i);
      bool wasBullish = iClose(_Symbol, mtf, i + 1) > iOpen(_Symbol, mtf, i + 1);
      if(isBearish && wasBullish)
        {
         double level = iOpen(_Symbol, mtf, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, mtf, k) > level)
              {
               g_mtf_signalType = 1;
               return g_mtf_signalType;
              }
           }
        }
      bool isBullish = iClose(_Symbol, mtf, i) > iOpen(_Symbol, mtf, i);
      bool wasBearish = iClose(_Symbol, mtf, i + 1) < iOpen(_Symbol, mtf, i + 1);
      if(isBullish && wasBearish)
        {
         double level = iOpen(_Symbol, mtf, i);
         for(int k = i - 1; k >= 1; k--)
           {
            if(iClose(_Symbol, mtf, k) < level)
              {
               g_mtf_signalType = -1;
               return g_mtf_signalType;
              }
           }
        }
     }
   return g_mtf_signalType = 0;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void PerformTrendAnalysis(TrendAnalysisResult &result, bool is_short_term, double current_close, const double &atr_arr[], const double &ema_arr[])
  {
   int reg_period = is_short_term ? InpRegressionPeriod_Short : InpRegressionPeriod_Long;
   double last_bar_weight = is_short_term ? InpLastBarWeight_Short : InpLastBarWeight_Long;
   double th_close_l1 = is_short_term ? InpThreshold_Close_L1_Short : InpThreshold_Close_L1_Long;
   double th_close_l2 = is_short_term ? InpThreshold_Close_L2_Short : InpThreshold_Close_L2_Long;
   double th_close_l3 = is_short_term ? InpThreshold_Close_L3_Short : InpThreshold_Close_L3_Long;
   double th_ema_l1 = is_short_term ? InpThreshold_EMA_L1_Short : InpThreshold_EMA_L1_Long;
   double th_ema_l2 = is_short_term ? InpThreshold_EMA_L2_Short : InpThreshold_EMA_L2_Long;
   double th_ema_l3 = is_short_term ? InpThreshold_EMA_L3_Short : InpThreshold_EMA_L3_Long;
   double chart_max = ChartGetDouble(0, CHART_PRICE_MAX, 0);
   double chart_min = ChartGetDouble(0, CHART_PRICE_MIN, 0);
   double current_atr = (ArraySize(atr_arr) > 0) ? atr_arr[0] : 0;
   double current_ema = (ArraySize(ema_arr) > 0) ? ema_arr[0] : 0;
   double close_values[];
   ArraySetAsSeries(close_values, true);
   if(CopyClose(_Symbol, _Period, 0, reg_period, close_values) >= reg_period)
     {
      ArrayReverse(close_values);
      Get7LevelSlopeInfo(close_values, reg_period, last_bar_weight, chart_max, chart_min, th_close_l1, th_close_l2, th_close_l3, result.close_slope, result.close_state, result.close_status_text, result.close_color);
     }
   double ema_values[];
   ArraySetAsSeries(ema_values, true);
   if(CopyBuffer(EmaHandle, 0, 0, reg_period, ema_values) >= reg_period)
     {
      ArrayReverse(ema_values);
      Get7LevelSlopeInfo(ema_values, reg_period, last_bar_weight, chart_max, chart_min, th_ema_l1, th_ema_l2, th_ema_l3, result.ema_slope, result.ema_state, result.ema_status_text, result.ema_color);
     }
   double distance_in_atr = (current_atr > 0) ? MathAbs(current_close - current_ema) / current_atr : 0;
   bool is_up_trend = (result.close_state > 0 || result.ema_state > 0);
   bool is_same_direction = (result.close_state * result.ema_state >= 0);
   bool is_strong_momentum = (MathAbs(result.close_state) >= 2 || MathAbs(result.ema_state) >= 2);
   if(MathAbs(result.close_state) >= 2 && MathAbs(result.ema_state) >= 2 && distance_in_atr > InpFomoThresholdAtr)
     {
      result.market_diagnosis_text = is_up_trend ? T.fomo_up : T.fomo_down;
      result.market_diagnosis_color = c_Fomo;
     }
   else
      if(MathAbs(result.close_state) >= 2 && MathAbs(result.ema_state) <= 1 && is_same_direction)
        {
         result.market_diagnosis_text = is_up_trend ? T.breakout_up : T.breakout_down;
         result.market_diagnosis_color = c_Breakout;
        }
      else
         if(is_same_direction && is_strong_momentum)
           {
            result.market_diagnosis_text = is_up_trend ? T.strong_trend_up : T.strong_trend_down;
            result.market_diagnosis_color = is_up_trend ? c_StrongTrend_Up : c_StrongTrend_Down;
           }
         else
            if(is_same_direction && (result.close_state != 0 || result.ema_state != 0))
              {
               result.market_diagnosis_text = is_up_trend ? T.has_trend_up : T.has_trend_down;
               result.market_diagnosis_color = is_up_trend ? c_HasTrend_Up : c_HasTrend_Down;
              }
            else
              {
               result.market_diagnosis_text = T.sideways;
               result.market_diagnosis_color = c_Sideway;
              }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void Get7LevelSlopeInfo(const double &data_array[], const int period, const double last_bar_weight, const double chart_max_price, const double chart_min_price, const double threshold_L1, const double threshold_L2, const double threshold_L3, double &viewport_slope, int &trend_state_code, string &trend_status, color &text_color)
  {
   double price_range = chart_max_price - chart_min_price;
   if(period <= 1 || price_range <= 0)
      return;
   double normalized_data[];
   ArrayResize(normalized_data, period);
   for(int i = 0; i < period; i++)
      normalized_data[i] = (data_array[i] - chart_min_price) / price_range;
   double sum_w = 0, sum_wx = 0, sum_wy = 0, sum_wxy = 0, sum_wx2 = 0;
   for(int i = 0; i < period; i++)
     {
      double weight = (i == period - 1) ? last_bar_weight : 1.0;
      double x = i;
      double y = normalized_data[i];
      sum_w += weight;
      sum_wx += weight * x;
      sum_wy += weight * y;
      sum_wxy += weight * x * y;
      sum_wx2 += weight * x * x;
     }
   double denominator = (sum_w * sum_wx2 - sum_wx * sum_wx);
   if(denominator == 0)
     {
      viewport_slope = 0;
      return;
     }
   viewport_slope = (sum_w * sum_wxy - sum_wx * sum_wy) / denominator;
   double abs_slope = MathAbs(viewport_slope);
   if(abs_slope < threshold_L1)
      trend_state_code = 0;
   else
      if(abs_slope < threshold_L2)
         trend_state_code = (viewport_slope > 0) ? 1 : -1;
      else
         if(abs_slope < threshold_L3)
            trend_state_code = (viewport_slope > 0) ? 2 : -2;
         else
            trend_state_code = (viewport_slope > 0) ? 3 : -3;
   switch(trend_state_code)
     {
      case 3:
         trend_status = T.level_p3;
         break;
      case 2:
         trend_status = T.level_p2;
         break;
      case 1:
         trend_status = T.level_p1;
         break;
      case 0:
         trend_status = T.level_0;
         break;
      case -1:
         trend_status = T.level_n1;
         break;
      case -2:
         trend_status = T.level_n2;
         break;
      case -3:
         trend_status = T.level_n3;
         break;
     }
   text_color = c_level_colors[trend_state_code + 3];
  }

//+------------------------------------------------------------------+
//| HÀM CHÍNH: KIỂM TRA CÁC "HỌ KỊCH BẢN"                            |
//+------------------------------------------------------------------+
//*
ENUM_SETUP_FAMILY CheckTradingSetups(int direction)
  {
   if(direction == 0)
      return SETUP_FAMILY_NONE;

   double DOpen = iOpen(_Symbol, PERIOD_H1, 0);
   double DClose = iClose(_Symbol, PERIOD_H1, 0);
   double DPreOpen = iOpen(_Symbol, PERIOD_H1, 1);
   double DPreClose = iClose(_Symbol, PERIOD_H1, 1);

   bool daily_ok = g_daily_percent > 70.0;
   if(daily_ok)
     {
      if(direction == 1 && DPreOpen < DPreClose && g_h1_pre_percent > 70.0 && DOpen < DClose && g_h1_percent > 70.0)  // Tín hiệu MUA
        {
         // Ưu tiên các kịch bản chất lượng cao nhất (pullback) trước
         if(Inp_EnableBuy_StrongTrendPullback && CheckBuy_StrongTrendPullback())
            return SETUP_FAMILY_BUY_STRONG_TREND_PULLBACK;
         if(Inp_EnableBuy_TrendMomentum && CheckBuy_TrendMomentum())
            return SETUP_FAMILY_BUY_TREND_MOMENTUM;
         if(Inp_EnableBuy_BreakoutConfirm && CheckBuy_BreakoutConfirmation())
            return SETUP_FAMILY_BUY_BREAKOUT_CONFIRMATION;
        }
      else
         if(direction == -1 && DPreOpen > DPreClose && g_h1_pre_percent > 70.0 && DOpen > DClose && g_h1_percent > 70.0)  // Tín hiệu BÁN
           {
            if(Inp_EnableSell_StrongTrendPullback && CheckSell_StrongTrendPullback())
               return SETUP_FAMILY_SELL_STRONG_TREND_PULLBACK;
            if(Inp_EnableSell_TrendMomentum && CheckSell_TrendMomentum())
               return SETUP_FAMILY_SELL_TREND_MOMENTUM;
            if(Inp_EnableSell_BreakoutConfirm && CheckSell_BreakoutConfirmation())
               return SETUP_FAMILY_SELL_BREAKOUT_CONFIRMATION;
           }
     }
// LogRejectedSignal(direction);
   return SETUP_FAMILY_NONE;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
ENUM_SETUP_FAMILY CheckCISDSetups(int direction)
  {
   if(direction == 0)
      return SETUP_FAMILY_NONE;

   double DOpen = iOpen(_Symbol, PERIOD_H1, 0);
   double DClose = iClose(_Symbol, PERIOD_H1, 0);
   double DPreOpen = iOpen(_Symbol, PERIOD_H1, 1);
   double DPreClose = iClose(_Symbol, PERIOD_H1, 1);

   bool daily_ok = g_daily_percent > 70.0;
   if(daily_ok)
     {
      if(direction == 1 && DPreOpen < DPreClose && g_h1_pre_percent > 70.0)  // Tín hiệu MUA
        {
         bool momentum_is_flow_up = (g_short_term.close_status_text == T.level_p1 || g_short_term.close_status_text == T.level_p2) &&
                                    (g_short_term.ema_status_text == T.level_p1 || g_short_term.ema_status_text == T.level_p2);
         if(momentum_is_flow_up)
            return SETUP_FAMILY_BUY_CISD;
        }
      else
         if(direction == -1 && DPreOpen > DPreClose && g_h1_pre_percent > 70.0)  // Tín hiệu BÁN
           {
            bool momentum_is_flow_down = (g_short_term.close_status_text == T.level_n1 || g_short_term.close_status_text == T.level_n2) &&
                                         (g_short_term.ema_status_text == T.level_n1 || g_short_term.ema_status_text == T.level_n2);
            if(momentum_is_flow_down)
               return SETUP_FAMILY_SELL_CISD;
           }
     }
// LogRejectedSignal(direction);
   return SETUP_FAMILY_NONE;
  }

//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
// ++                                                                         ++
// ++               PHẦN 3: HÀM KIỂM TRA TÍN HIỆU CHÍNH                       ++
// ++                                                                         ++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
ENUM_SETUP_FAMILY CheckCISDM30Setups(int direction)
  {
   if(direction == 0)
      return SETUP_FAMILY_NONE;

   DebugRejectedSignal(direction);

   if(g_daily_percent <= 70.0)
      return SETUP_FAMILY_NONE;

//--- Lấy dữ liệu nến cần thiết
   double H1Open = iOpen(_Symbol, PERIOD_H1, 0), H1Close = iClose(_Symbol, PERIOD_H1, 0), H1High = iHigh(_Symbol, PERIOD_H1, 0), H1Low = iLow(_Symbol, PERIOD_H1, 0);
   double H1PreOpen = iOpen(_Symbol, PERIOD_H1, 1), H1PreClose = iClose(_Symbol, PERIOD_H1, 1), H1PreHigh = iHigh(_Symbol, PERIOD_H1, 1), H1PreLow = iLow(_Symbol, PERIOD_H1, 1);
   double H1PrePreOpen = iOpen(_Symbol, PERIOD_H1, 2), H1PrePreClose = iClose(_Symbol, PERIOD_H1, 2), H1PrePreHigh = iHigh(_Symbol, PERIOD_H1, 2), H1PrePreLow = iLow(_Symbol, PERIOD_H1, 2);
   double M30Open = iOpen(_Symbol, PERIOD_M30, 0), M30Close = iClose(_Symbol, PERIOD_M30, 0), M30High = iHigh(_Symbol, PERIOD_M30, 0), M30Low = iLow(_Symbol, PERIOD_M30, 0);
   double M30PreOpen = iOpen(_Symbol, PERIOD_M30, 1), M30PreClose = iClose(_Symbol, PERIOD_M30, 1), M30PreHigh = iHigh(_Symbol, PERIOD_M30, 1), M30PreLow = iLow(_Symbol, PERIOD_M30, 1);
   double M15Open = iOpen(_Symbol, PERIOD_M15, 0), M15Close = iClose(_Symbol, PERIOD_M15, 0), M15High = iHigh(_Symbol, PERIOD_M15, 0), M15Low = iLow(_Symbol, PERIOD_M15, 0);
   double M15PreOpen = iOpen(_Symbol, PERIOD_M15, 1), M15PreClose = iClose(_Symbol, PERIOD_M15, 1);
   double M5Open = iOpen(_Symbol, PERIOD_M5, 0), M5Close = iClose(_Symbol, PERIOD_M5, 0);
   double M5PreOpen = iOpen(_Symbol, PERIOD_M5, 1), M5PreClose = iClose(_Symbol, PERIOD_M5, 1);
   double closeCISD = iClose(_Symbol, _Period, 1);

//--- NHÓM A: STATIC PATTERNS
   if(direction == 1)
     {
      if(M30Close > M30Open && M15Close > M15Open && M5Close > M5Open)
        {
         if(H1PrePreOpen < H1PrePreClose && g_h1_pre_pre_percent > 70.0 && H1PreOpen > H1PreClose && g_h1_pre_percent < 55.0 && H1PreHigh < H1PrePreHigh && H1PreLow > H1PrePreLow)
            return SETUP_FAMILY_BUY_CISD_CONSOLIDATION_H1;
         if(H1PreOpen < H1PreClose && g_h1_pre_percent > 70.0 && H1Open < H1Close && H1PreLow <= closeCISD && H1PreHigh >= closeCISD && g_h1_percent > 60.0 && g_h1_percent < 90.0)
            return SETUP_FAMILY_BUY_CISD_PULLBACK;
         // if(H1PreOpen < H1PreClose && g_h1_pre_percent > 70.0 && H1Open < H1Close && g_h1_percent > 60.0 && g_h1_percent < 90.0)
         //    return SETUP_FAMILY_BUY_CISD_FLOW_TREND;
        }
     }
   else
     {
      if(M30Close < M30Open && M15Close < M15Open && M5Close < M5Open)
        {
         if(H1PrePreOpen > H1PrePreClose && g_h1_pre_pre_percent > 70.0 && H1PreOpen < H1PreClose && g_h1_pre_percent < 55.0 && H1PreHigh < H1PrePreHigh && H1PreLow > H1PrePreLow)
            return SETUP_FAMILY_SELL_CISD_CONSOLIDATION_H1;
         if(H1PreOpen > H1PreClose && g_h1_pre_percent > 70.0 && H1Open > H1Close && H1PreLow <= closeCISD && H1PreHigh >= closeCISD && g_h1_percent > 60.0 && g_h1_percent < 90.0)
            return SETUP_FAMILY_SELL_CISD_PULLBACK;
         // if(H1PreOpen > H1PreClose && g_h1_pre_percent > 70.0 && H1Open > H1Close && g_h1_percent > 60.0 && g_h1_percent < 90.0)
         //    return SETUP_FAMILY_SELL_CISD_FLOW_TREND;
        }
     }

//--- NHÓM B: CONTEXTUAL COMPRESSION
   bool h1_context_buy = (H1PrePreOpen < H1PrePreClose && g_h1_pre_pre_percent > 70.0);
   bool h1_context_sell = (H1PrePreOpen > H1PrePreClose && g_h1_pre_pre_percent > 70.0);
   if((direction == 1 && h1_context_buy) || (direction == -1 && h1_context_sell))
     {
      double m15_h[4], m15_l[4], m15_o[4], m15_c[4];
      for(int i = 0; i < 4; i++)
        {
         m15_h[i] = iHigh(_Symbol, PERIOD_M15, i + 1);
         m15_l[i] = iLow(_Symbol, PERIOD_M15, i + 1);
         m15_o[i] = iOpen(_Symbol, PERIOD_M15, i + 1);
         m15_c[i] = iClose(_Symbol, PERIOD_M15, i + 1);
        }
      double h_m15 = MathMax(MathMax(m15_h[0], m15_h[1]), MathMax(m15_h[2], m15_h[3]));
      double l_m15 = MathMin(MathMin(m15_l[0], m15_l[1]), MathMin(m15_l[2], m15_l[3]));
      if(h_m15 < H1PrePreHigh && l_m15 > H1PrePreLow)
        {
         int up = 0, down = 0;
         bool strong_counter = false;
         for(int i = 0; i < 4; i++)
           {
            if(m15_c[i] > m15_o[i])
               up++;
            else
               down++;
            if((direction == 1 && m15_c[i] < m15_o[i] && g_m15_last4_percents[i] > 55.0) || (direction == -1 && m15_c[i] > m15_o[i] && g_m15_last4_percents[i] > 55.0))
               strong_counter = true;
           }
         if(!strong_counter)
           {
            if((direction == 1 && up >= 2 && down >= 1) || (direction == -1 && down >= 2 && up >= 1))
              {
               if((direction == 1 && M5Open < M5Close) || (direction == -1 && M5Open > M5Close))
                  return (direction == 1) ? SETUP_FAMILY_BUY_CISD_COMPRESSION_M15_FLAG : SETUP_FAMILY_SELL_CISD_COMPRESSION_M15_FLAG;
              }
            if(up + down == 4)
              {
               if((direction == 1 && M5Open < M5Close) || (direction == -1 && M5Open > M5Close))
                  return (direction == 1) ? SETUP_FAMILY_BUY_CISD_COMPRESSION_M15_QUIET : SETUP_FAMILY_SELL_CISD_COMPRESSION_M15_QUIET;
              }
           }
        }
     }

//--- NHÓM C: REAL-TIME ENTRIES
   bool h1_launchpad_buy = (H1PreOpen < H1PreClose && g_h1_pre_percent > 70.0);
   bool h1_launchpad_sell = (H1PreOpen > H1PreClose && g_h1_pre_percent > 70.0);
// Tính toán các mức hỗ trợ/kháng cự một lần
   double h1_pre_resistance_level = H1PreHigh - (H1PreHigh - H1PreLow) * 0.25; // Mức 75%
   double h1_pre_support_level = H1PreLow + (H1PreHigh - H1PreLow) * 0.25;     // Mức 25%

   if(direction == 1 && h1_launchpad_buy)
     {
      // Tín hiệu 1: Breakout sớm
      // if(M15Open < M15Close && M15High > H1PreHigh && M5Open < M5Close)
      //   return SETUP_FAMILY_BUY_CISD_RT_EARLY_BREAK;
      // Tín hiệu 2: Pullback về vùng hỗ trợ
      if(M30PreOpen > M30PreClose && M30PreLow > h1_pre_support_level && M30Open < M30Close && M15Open < M15Close && M5Open < M5Close)
         return SETUP_FAMILY_BUY_CISD_RT_PULLBACK_M30;
      // Tín hiệu 3: Tích lũy giữa giờ
      if((long)iTime(_Symbol, PERIOD_M15, 0) - (long)iTime(_Symbol, PERIOD_H1, 0) == 1800)
        {
         if(M15Open < M15Close && M15High > MathMax(iHigh(_Symbol, PERIOD_M15, 1), iHigh(_Symbol, PERIOD_M15, 2)) && M5Open < M5Close)
            return SETUP_FAMILY_BUY_CISD_RT_BUILDUP_M15;
        }
     }
   else
      if(direction == -1 && h1_launchpad_sell)
        {
         // Tín hiệu 1: Breakout sớm
         // if(M15Open > M15Close && M15Low < H1PreLow && M5Open > M5Close)
         //   return SETUP_FAMILY_SELL_CISD_RT_EARLY_BREAK;
         // Tín hiệu 2: Pullback về vùng kháng cự
         if(M30PreOpen < M30PreClose && M30PreHigh < h1_pre_resistance_level && M30Open > M30Close && M15Open > M15Close && M5Open > M5Close)
            return SETUP_FAMILY_SELL_CISD_RT_PULLBACK_M30;
         // Tín hiệu 3: Tích lũy giữa giờ
         if((long)iTime(_Symbol, PERIOD_M15, 0) - (long)iTime(_Symbol, PERIOD_H1, 0) == 1800)
           {
            if(M15Open > M15Close && M15Low < MathMin(iLow(_Symbol, PERIOD_M15, 1), iLow(_Symbol, PERIOD_M15, 2)) && M5Open > M5Close)
               return SETUP_FAMILY_SELL_CISD_RT_BUILDUP_M15;
           }
        }

// Nếu không có setup nào được tìm thấy, gọi hàm debug (tùy chọn)
   return SETUP_FAMILY_NONE;
  }

//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
// ++                                                                         ++
// ++               PHẦN 4: HÀM DEBUG (TÙY CHỌN SỬ DỤNG)                      ++
// ++                                                                         ++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
void DebugRejectedSignal(int direction)
  {
//--- Lấy dữ liệu nến cần thiết (chỉ lấy những gì cần cho debug)
   double H1Open = iOpen(_Symbol, PERIOD_H1, 0), H1Close = iClose(_Symbol, PERIOD_H1, 0), H1High = iHigh(_Symbol, PERIOD_H1, 0), H1Low = iLow(_Symbol, PERIOD_H1, 0);
   double H1PreOpen = iOpen(_Symbol, PERIOD_H1, 1), H1PreClose = iClose(_Symbol, PERIOD_H1, 1), H1PreHigh = iHigh(_Symbol, PERIOD_H1, 1), H1PreLow = iLow(_Symbol, PERIOD_H1, 1);
   double H1PrePreOpen = iOpen(_Symbol, PERIOD_H1, 2), H1PrePreClose = iClose(_Symbol, PERIOD_H1, 2), H1PrePreHigh = iHigh(_Symbol, PERIOD_H1, 2), H1PrePreLow = iLow(_Symbol, PERIOD_H1, 2);
   double M30Open = iOpen(_Symbol, PERIOD_M30, 0), M30Close = iClose(_Symbol, PERIOD_M30, 0);
   double M30PreOpen = iOpen(_Symbol, PERIOD_M30, 1), M30PreClose = iClose(_Symbol, PERIOD_M30, 1), M30PreHigh = iHigh(_Symbol, PERIOD_M30, 1), M30PreLow = iLow(_Symbol, PERIOD_M30, 1);
   double M15Open = iOpen(_Symbol, PERIOD_M15, 0), M15Close = iClose(_Symbol, PERIOD_M15, 0), M15High = iHigh(_Symbol, PERIOD_M15, 0), M15Low = iLow(_Symbol, PERIOD_M15, 0);
   double M5Open = iOpen(_Symbol, PERIOD_M5, 0), M5Close = iClose(_Symbol, PERIOD_M5, 0);
   double closeCISD = iClose(_Symbol, _Period, 1);

   PrintFormat("=== [DEBUG REJECTED SIGNAL | Direction: %d, Time: %s] ===", direction, TimeToString(TimeCurrent(), TIME_SECONDS));

// Điều kiện tiên quyết
   if(g_daily_percent <= 70.0)
     {
      PrintFormat("Rejected: Daily Percent too low (%.2f%% <= 70.0%%)", g_daily_percent);
      Print("=== [END DEBUG] ===");
      return;
     }

// --- CHECK LỆNH BUY ---
   if(direction == 1)
     {
      Print("--- Checking BUY Setups ---");

      // Điều kiện chung cho nhiều setup BUY
      bool isBullishFlow = (M30Close > M30Open && M15Close > M15Open && M5Close > M5Open);
      if(!isBullishFlow)
        {
         PrintFormat("Rejected: Basic flow is not bullish (M30:%s, M15:%s, M5:%s)",
                     M30Close > M30Open ? "UP" : "DOWN",
                     M15Close > M15Open ? "UP" : "DOWN",
                     M5Close > M5Open ? "UP" : "DOWN");
         Print("=== [END DEBUG] ===");
         return;
        }

      //--- A: STATIC PATTERNS ---
      Print("-- Checking A: Static Patterns --");
      // A1: CONSOLIDATION_H1
      if(!(H1PrePreOpen < H1PrePreClose))
        {
         Print("A1.Consolidation: H1[2] is not a bullish candle.");
         return;
        }
      if(!(g_h1_pre_pre_percent > 70.0))
        {
         PrintFormat("A1.Consolidation: H1[2] percent is too low (%.2f%% <= 70.0%%)", g_h1_pre_pre_percent);
         return;
        }
      if(!(H1PreOpen > H1PreClose))
        {
         Print("A1.Consolidation: H1[1] is not a bearish candle.");
         return;
        }
      if(!(g_h1_pre_percent < 55.0))
        {
         PrintFormat("A1.Consolidation: H1[1] percent is too high (%.2f%% >= 55.0%%)", g_h1_pre_percent);
         return;
        }
      if(!(H1PreHigh < H1PrePreHigh && H1PreLow > H1PrePreLow))
        {
         Print("A1.Consolidation: H1[1] is not an inside bar of H1[2].");
         return;
        }
      // A2: PULLBACK
      if(!(H1PreOpen < H1PreClose))
        {
         Print("A2.Pullback: H1[1] is not a bullish candle.");
         return;
        }
      if(!(g_h1_pre_percent > 70.0))
        {
         PrintFormat("A2.Pullback: H1[1] percent is too low (%.2f%% <= 70.0%%)", g_h1_pre_percent);
         return;
        }
      if(!(H1Open < H1Close))
        {
         Print("A2.Pullback: H1[0] is not a bullish candle.");
         return;
        }
      if(!(H1PreLow <= closeCISD && H1PreHigh >= closeCISD))
        {
         PrintFormat("A2.Pullback: CISD close (%.5f) is not inside H1[1] range [%.5f, %.5f].", closeCISD, H1PreLow, H1PreHigh);
         return;
        }
      if(!(g_h1_percent > 60.0 && g_h1_percent < 90.0))
        {
         PrintFormat("A2.Pullback: H1[0] percent is out of range (%.2f%%)", g_h1_percent);
         return;
        }

      //--- B: CONTEXTUAL COMPRESSION ---
      Print("-- Checking B: Contextual Compression --");
      bool h1_context_buy = (H1PrePreOpen < H1PrePreClose && g_h1_pre_pre_percent > 70.0);
      if(!h1_context_buy)
        {
         PrintFormat("B.Compression: H1[2] context is not valid for BUY (isUp:%s, %%:%.2f)", H1PrePreOpen < H1PrePreClose ? "true" : "false", g_h1_pre_pre_percent);
         return;
        }

      double m15_h[4], m15_l[4], m15_o[4], m15_c[4];
      for(int i = 0; i < 4; i++)
        {
         m15_h[i] = iHigh(_Symbol, PERIOD_M15, i + 1);
         m15_l[i] = iLow(_Symbol, PERIOD_M15, i + 1);
         m15_o[i] = iOpen(_Symbol, PERIOD_M15, i + 1);
         m15_c[i] = iClose(_Symbol, PERIOD_M15, i + 1);
        }
      double h_m15 = MathMax(MathMax(m15_h[0], m15_h[1]), MathMax(m15_h[2], m15_h[3]));
      double l_m15 = MathMin(MathMin(m15_l[0], m15_l[1]), MathMin(m15_l[2], m15_l[3]));

      if(!(h_m15 < H1PrePreHigh && l_m15 > H1PrePreLow))
        {
         Print("B.Compression: Last 4 M15 bars are not inside H1[2].");
         return;
        }

      int up = 0, down = 0;
      bool strong_counter = false;
      for(int i = 0; i < 4; i++)
        {
         if(m15_c[i] > m15_o[i])
            up++;
         else
            down++;
         if(m15_c[i] < m15_o[i] && g_m15_last4_percents[i] > 55.0)
            strong_counter = true;
        }
      if(strong_counter)
        {
         Print("B.Compression: Found a strong counter-trend M15 candle in the compression zone.");
         return;
        }
      if(!((up >= 2 && down >= 1) || (up + down == 4)))
        {
         PrintFormat("B.Compression: M15 candle count invalid for Flag/Quiet (Up:%d, Down:%d)", up, down);
         return;
        }
      if(!(M5Open < M5Close))
        {
         Print("B.Compression: Final M5 confirmation candle is not bullish.");
         return;
        }

      //--- C: REAL-TIME ENTRIES ---
      Print("-- Checking C: Real-Time Entries --");
      bool h1_launchpad_buy = (H1PreOpen < H1PreClose && g_h1_pre_percent > 70.0);
      if(!h1_launchpad_buy)
        {
         PrintFormat("C.Real-Time: H1[1] is not a valid BUY launchpad (isUp:%s, %%:%.2f)", H1PreOpen < H1PreClose ? "true" : "false", g_h1_pre_percent);
         return;
        }

      double h1_pre_support_level = H1PreLow + (H1PreHigh - H1PreLow) * 0.25; // Mức 25%

      // C1: PULLBACK_M30
      if(!(M30PreOpen > M30PreClose))
        {
         Print("C1.RT_Pullback: M30[1] is not a bearish candle.");
         return;
        }
      if(!(M30PreLow > h1_pre_support_level))
        {
         PrintFormat("C1.RT_Pullback: M30[1] low (%.5f) is not above support level (%.5f).", M30PreLow, h1_pre_support_level);
         return;
        }
      if(!(M30Open < M30Close && M15Open < M15Close && M5Open < M5Close))
        {
         Print("C1.RT_Pullback: Current flow is not bullish across M30, M15, M5.");
         return;
        }

      // C2: BUILDUP_M15
      long time_diff = (long)iTime(_Symbol, PERIOD_M15, 0) - (long)iTime(_Symbol, PERIOD_H1, 0);
      if(time_diff != 1800)
        {
         PrintFormat("C2.RT_Buildup: Not the 3rd M15 bar of the hour (time diff: %d s)", time_diff);
         return;
        }
      if(!(M15Open < M15Close))
        {
         Print("C2.RT_Buildup: M15[0] is not a bullish candle.");
         return;
        }
      if(!(M15High > MathMax(iHigh(_Symbol, PERIOD_M15, 1), iHigh(_Symbol, PERIOD_M15, 2))))
        {
         Print("C2.RT_Buildup: M15[0] did not break the high of the previous 2 M15 bars.");
         return;
        }
      if(!(M5Open < M5Close))
        {
         Print("C2.RT_Buildup: Final M5 confirmation candle is not bullish.");
         return;
        }
     }
// --- CHECK LỆNH SELL ---
   else
      if(direction == -1)
        {
         Print("--- Checking SELL Setups ---");

         // Điều kiện chung cho nhiều setup SELL
         bool isBearishFlow = (M30Close < M30Open && M15Close < M15Open && M5Close < M5Open);
         if(!isBearishFlow)
           {
            PrintFormat("Rejected: Basic flow is not bearish (M30:%s, M15:%s, M5:%s)",
                        M30Close < M30Open ? "DOWN" : "UP",
                        M15Close < M15Open ? "DOWN" : "UP",
                        M5Close < M5Open ? "DOWN" : "UP");
            Print("=== [END DEBUG] ===");
            return;
           }

         //--- A: STATIC PATTERNS ---
         Print("-- Checking A: Static Patterns --");
         // A1: CONSOLIDATION_H1
         if(!(H1PrePreOpen > H1PrePreClose))
           {
            Print("A1.Consolidation: H1[2] is not a bearish candle.");
            return;
           }
         if(!(g_h1_pre_pre_percent > 70.0))
           {
            PrintFormat("A1.Consolidation: H1[2] percent is too low (%.2f%% <= 70.0%%)", g_h1_pre_pre_percent);
            return;
           }
         if(!(H1PreOpen < H1PreClose))
           {
            Print("A1.Consolidation: H1[1] is not a bullish candle.");
            return;
           }
         if(!(g_h1_pre_percent < 55.0))
           {
            PrintFormat("A1.Consolidation: H1[1] percent is too high (%.2f%% >= 55.0%%)", g_h1_pre_percent);
            return;
           }
         if(!(H1PreHigh < H1PrePreHigh && H1PreLow > H1PrePreLow))
           {
            Print("A1.Consolidation: H1[1] is not an inside bar of H1[2].");
            return;
           }
         // A2: PULLBACK
         if(!(H1PreOpen > H1PreClose))
           {
            Print("A2.Pullback: H1[1] is not a bearish candle.");
            return;
           }
         if(!(g_h1_pre_percent > 70.0))
           {
            PrintFormat("A2.Pullback: H1[1] percent is too low (%.2f%% <= 70.0%%)", g_h1_pre_percent);
            return;
           }
         if(!(H1Open > H1Close))
           {
            Print("A2.Pullback: H1[0] is not a bearish candle.");
            return;
           }
         if(!(H1PreLow <= closeCISD && H1PreHigh >= closeCISD))
           {
            PrintFormat("A2.Pullback: CISD close (%.5f) is not inside H1[1] range [%.5f, %.5f].", closeCISD, H1PreLow, H1PreHigh);
            return;
           }
         if(!(g_h1_percent > 60.0 && g_h1_percent < 90.0))
           {
            PrintFormat("A2.Pullback: H1[0] percent is out of range (%.2f%%)", g_h1_percent);
            return;
           }

         //--- B: CONTEXTUAL COMPRESSION ---
         Print("-- Checking B: Contextual Compression --");
         bool h1_context_sell = (H1PrePreOpen > H1PrePreClose && g_h1_pre_pre_percent > 70.0);
         if(!h1_context_sell)
           {
            PrintFormat("B.Compression: H1[2] context is not valid for SELL (isDown:%s, %%:%.2f)", H1PrePreOpen > H1PrePreClose ? "true" : "false", g_h1_pre_pre_percent);
            return;
           }

         double m15_h[4], m15_l[4], m15_o[4], m15_c[4];
         for(int i = 0; i < 4; i++)
           {
            m15_h[i] = iHigh(_Symbol, PERIOD_M15, i + 1);
            m15_l[i] = iLow(_Symbol, PERIOD_M15, i + 1);
            m15_o[i] = iOpen(_Symbol, PERIOD_M15, i + 1);
            m15_c[i] = iClose(_Symbol, PERIOD_M15, i + 1);
           }
         double h_m15 = MathMax(MathMax(m15_h[0], m15_h[1]), MathMax(m15_h[2], m15_h[3]));
         double l_m15 = MathMin(MathMin(m15_l[0], m15_l[1]), MathMin(m15_l[2], m15_l[3]));

         if(!(h_m15 < H1PrePreHigh && l_m15 > H1PrePreLow))
           {
            Print("B.Compression: Last 4 M15 bars are not inside H1[2].");
            return;
           }

         int up = 0, down = 0;
         bool strong_counter = false;
         for(int i = 0; i < 4; i++)
           {
            if(m15_c[i] > m15_o[i])
               up++;
            else
               down++;
            if(m15_c[i] > m15_o[i] && g_m15_last4_percents[i] > 55.0)
               strong_counter = true;
           }
         if(strong_counter)
           {
            Print("B.Compression: Found a strong counter-trend M15 candle in the compression zone.");
            return;
           }
         if(!((down >= 2 && up >= 1) || (up + down == 4)))
           {
            PrintFormat("B.Compression: M15 candle count invalid for Flag/Quiet (Up:%d, Down:%d)", up, down);
            return;
           }
         if(!(M5Open > M5Close))
           {
            Print("B.Compression: Final M5 confirmation candle is not bearish.");
            return;
           }

         //--- C: REAL-TIME ENTRIES ---
         Print("-- Checking C: Real-Time Entries --");
         bool h1_launchpad_sell = (H1PreOpen > H1PreClose && g_h1_pre_percent > 70.0);
         if(!h1_launchpad_sell)
           {
            PrintFormat("C.Real-Time: H1[1] is not a valid SELL launchpad (isDown:%s, %%:%.2f)", H1PreOpen > H1PreClose ? "true" : "false", g_h1_pre_percent);
            return;
           }

         double h1_pre_resistance_level = H1PreHigh - (H1PreHigh - H1PreLow) * 0.25; // Mức 75%

         // C1: PULLBACK_M30
         if(!(M30PreOpen < M30PreClose))
           {
            Print("C1.RT_Pullback: M30[1] is not a bullish candle.");
            return;
           }
         if(!(M30PreHigh < h1_pre_resistance_level))
           {
            PrintFormat("C1.RT_Pullback: M30[1] high (%.5f) is not below resistance level (%.5f).", M30PreHigh, h1_pre_resistance_level);
            return;
           }
         if(!(M30Open > M30Close && M15Open > M15Close && M5Open > M5Close))
           {
            Print("C1.RT_Pullback: Current flow is not bearish across M30, M15, M5.");
            return;
           }

         // C2: BUILDUP_M15
         long time_diff = (long)iTime(_Symbol, PERIOD_M15, 0) - (long)iTime(_Symbol, PERIOD_H1, 0);
         if(time_diff != 1800)
           {
            PrintFormat("C2.RT_Buildup: Not the 3rd M15 bar of the hour (time diff: %d s)", time_diff);
            return;
           }
         if(!(M15Open > M15Close))
           {
            Print("C2.RT_Buildup: M15[0] is not a bearish candle.");
            return;
           }
         if(!(M15Low < MathMin(iLow(_Symbol, PERIOD_M15, 1), iLow(_Symbol, PERIOD_M15, 2))))
           {
            Print("C2.RT_Buildup: M15[0] did not break the low of the previous 2 M15 bars.");
            return;
           }
         if(!(M5Open > M5Close))
           {
            Print("C2.RT_Buildup: Final M5 confirmation candle is not bearish.");
            return;
           }
        }

// Nếu tất cả các điều kiện trên đều không bị từ chối, có thể có lỗi logic ở đâu đó
   Print("No specific setup condition failed, but no setup was returned. Check logic in CheckCISDM30Setups.");
   Print("=== [END DEBUG] ===");
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
ENUM_SETUP_FAMILY CheckBreakoutSetups(int direction)
  {
   double DOpen = iOpen(_Symbol, PERIOD_H1, 0);
   double DClose = iClose(_Symbol, PERIOD_H1, 0);
   double DPreOpen = iOpen(_Symbol, PERIOD_H1, 1);
   double DPreClose = iClose(_Symbol, PERIOD_H1, 1);

   bool daily_ok = g_daily_percent > 70.0;
   if(daily_ok)
     {
      if(direction == 1 && DPreOpen < DPreClose && g_h1_pre_percent > 70.0 && DOpen < DClose && g_h1_percent > 70.0)  // Tín hiệu MUA
         return CheckBuy_BreakoutRange();
      else
         if(direction == -1 && DPreOpen > DPreClose && g_h1_pre_percent > 70.0 && DOpen > DClose && g_h1_percent > 70.0)  // Tín hiệu BÁN
            return CheckSell_BreakoutRange();
     }
// LogRejectedSignal(direction);
   return SETUP_FAMILY_NONE;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void LogRejectedSignal(int direction)
  {
// if(InpEnableDebugLog)
     {
      string direction_text = (direction == 1) ? "BUY" : "SELL";
      PrintFormat("--- [Trade Check] %s Signal for %s REJECTED ---", direction_text, _Symbol);
      // Log chi tiết trạng thái hiện tại của các thành phần
      PrintFormat("  - Daily Strength: %.2f%%", g_daily_percent);
      PrintFormat("  - H1 Trend: '%s'", g_short_term.market_diagnosis_text);
      PrintFormat("  - H4 Trend: '%s'", g_long_term.market_diagnosis_text);
      PrintFormat("  - Price Slope: '%s'", g_short_term.close_status_text);
      PrintFormat("  - EMA Slope: '%s'", g_short_term.ema_status_text);
      Print("--------------------------------------------------");
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
ENUM_SETUP_FAMILY CheckBuy_BreakoutRange()
  {
   if(g_long_term.market_diagnosis_text == T.strong_trend_up || g_long_term.market_diagnosis_text == T.has_trend_up)
     {
      bool momentum_is_flow_up = (g_short_term.close_status_text == T.level_p1 || g_short_term.close_status_text == T.level_p2) &&
                                 (g_short_term.ema_status_text == T.level_p1 || g_short_term.ema_status_text == T.level_p2);
      if(momentum_is_flow_up)
         return SETUP_FAMILY_BUY_BREAKOUT_RANGE;

      bool momentum_is_early = (g_short_term.close_status_text == T.level_p1 || g_short_term.close_status_text == T.level_p2) &&
                               (g_short_term.ema_status_text == T.level_0);
      if(momentum_is_early)
         return SETUP_FAMILY_BUYLIMIT_BREAKOUT_RANGE;
     }
   return SETUP_FAMILY_NONE;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
ENUM_SETUP_FAMILY CheckSell_BreakoutRange()
  {
   if(g_long_term.market_diagnosis_text == T.strong_trend_down || g_long_term.market_diagnosis_text == T.has_trend_down)
     {
      bool momentum_is_flow_down = (g_short_term.close_status_text == T.level_n1 || g_short_term.close_status_text == T.level_n2) &&
                                   (g_short_term.ema_status_text == T.level_n1 || g_short_term.ema_status_text == T.level_n2);
      if(momentum_is_flow_down)
         return SETUP_FAMILY_SELL_BREAKOUT_RANGE;

      bool momentum_is_early = (g_short_term.close_status_text == T.level_n1 || g_short_term.close_status_text == T.level_n2) &&
                               (g_short_term.ema_status_text == T.level_0);
      if(momentum_is_early)
         return SETUP_FAMILY_SELLLIMIT_BREAKOUT_RANGE;
     }
   return SETUP_FAMILY_NONE;
  }
//+------------------------------------------------------------------+
//| BƯỚC 3: CÁC HÀM KIỂM TRA MODULE HÓA CHO TỪNG "HỌ KỊCH BẢN"       |
//+------------------------------------------------------------------+

// --- Các hàm kiểm tra cho Lệnh MUA ---

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CheckBuy_StrongTrendPullback()
  {
// LOGIC: Cả 2 khung TG đều có xu hướng RẤT MẠNH
   if(g_long_term.market_diagnosis_text == T.strong_trend_up)
     {
      // LOGIC: Chỉ vào lệnh khi động lượng MỚI BẮT ĐẦU (pullback/chững lại)
      // --- Lấy giá đóng của nến trước ---
      double ltf_cisd_price = iClose(_Symbol, _Period, 1);
      // --- Thử đọc EMA từ handle, nhưng nếu thất bại thì chỉ SKIP phần phụ thuộc EMA ---
      double EmaBuffer[];
      bool ema_ok = false;
      if(EmaHandle != INVALID_HANDLE)
        {
         ArrayResize(EmaBuffer, 2);
         ArraySetAsSeries(EmaBuffer, true); // quan trọng: đảo thứ tự về [0] là nến hiện tại
         int copied = CopyBuffer(EmaHandle, 0, 0, 2, EmaBuffer);
         if(copied >= 2)
            ema_ok = true;
        }
      // --- Nếu EMA hợp lệ, kiểm tra trường hợp momentum "sideway" (pullback/chững lại) ---
      if(ema_ok)
        {
         double ema_prev = EmaBuffer[1]; // EMA của nến trước
         bool momentum_is_sideway =
            g_short_term.close_status_text == T.level_0 &&
            (g_short_term.ema_status_text == T.level_0 || g_short_term.ema_status_text == T.level_p1) &&
            ltf_cisd_price > ema_prev;

         if(momentum_is_sideway)
            return true;
        }
      bool momentum_is_early = (g_short_term.close_status_text == T.level_p1 || g_short_term.close_status_text == T.level_p2) &&
                               (g_short_term.ema_status_text == T.level_0 || g_short_term.ema_status_text == T.level_p1);

      bool momentum_is_flow_up = (g_short_term.ema_status_text == T.level_p2) &&
                                 (g_short_term.close_status_text == T.level_0 || g_short_term.close_status_text == T.level_p1);

      return momentum_is_early || momentum_is_flow_up;
     }
   return false;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CheckBuy_TrendMomentum()
  {
// LOGIC: Cả 2 khung TG đều có xu hướng ĐÃ HÌNH THÀNH
   bool trend_is_established = (g_long_term.market_diagnosis_text == T.has_trend_up);
   if(!trend_is_established)
      return false;

// LOGIC: Chỉ vào lệnh khi động lượng đang TĂNG TỐC
   bool momentum_is_accelerating = (g_short_term.close_status_text == T.level_p1 || g_short_term.close_status_text == T.level_p2 || g_short_term.close_status_text == T.level_p3) &&
                                   (g_short_term.ema_status_text == T.level_p1 || g_short_term.ema_status_text == T.level_p2);

   bool momentum_is_pullback = (g_short_term.close_status_text == T.level_0) && (g_short_term.ema_status_text == T.level_p2 || g_short_term.ema_status_text == T.level_p3);

   return momentum_is_accelerating || momentum_is_pullback;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CheckBuy_BreakoutConfirmation()
  {
// LOGIC: H1 vừa phá vỡ, H4 đã có xu hướng ủng hộ
   if(g_long_term.market_diagnosis_text == T.sideways)
     {
      // LOGIC: Breakout cần được xác nhận bởi động lượng mạnh
      bool momentum_exists = (g_short_term.close_status_text == T.level_p3) && (g_short_term.ema_status_text == T.level_p3);
      return momentum_exists;
     }
   return false;
  }

// --- Các hàm kiểm tra cho Lệnh BÁN (tương tự nhưng ngược lại) ---

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CheckSell_StrongTrendPullback()
  {
   if(g_long_term.market_diagnosis_text == T.strong_trend_down)
     {
      // --- Lấy giá đóng của nến trước ---
      double ltf_cisd_price = iClose(_Symbol, _Period, 1);
      // --- Thử đọc EMA từ handle, nhưng nếu thất bại thì chỉ SKIP phần phụ thuộc EMA ---
      double EmaBuffer[];
      bool ema_ok = false;
      if(EmaHandle != INVALID_HANDLE)
        {
         ArrayResize(EmaBuffer, 2);
         ArraySetAsSeries(EmaBuffer, true); // quan trọng: đảo thứ tự về [0] là nến hiện tại
         int copied = CopyBuffer(EmaHandle, 0, 0, 2, EmaBuffer);
         if(copied >= 2)
            ema_ok = true;
        }
      // --- Nếu EMA hợp lệ, kiểm tra trường hợp momentum "sideway" (pullback/chững lại) ---
      if(ema_ok)
        {
         double ema_prev = EmaBuffer[1]; // EMA của nến trước
         bool momentum_is_sideway =
            g_short_term.close_status_text == T.level_0 &&
            (g_short_term.ema_status_text == T.level_0 || g_short_term.ema_status_text == T.level_n1) &&
            ltf_cisd_price < ema_prev;

         if(momentum_is_sideway)
            return true;
        }

      bool momentum_is_early = (g_short_term.close_status_text == T.level_n1 || g_short_term.close_status_text == T.level_n2) &&
                               (g_short_term.ema_status_text == T.level_0 || g_short_term.ema_status_text == T.level_n1);

      bool momentum_is_flow_down = (g_short_term.ema_status_text == T.level_n2) &&
                                   (g_short_term.close_status_text == T.level_0 || g_short_term.close_status_text == T.level_n1);

      return momentum_is_early || momentum_is_flow_down;
     }
   return false;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CheckSell_TrendMomentum()
  {
   bool trend_is_established = (g_long_term.market_diagnosis_text == T.has_trend_down);
   if(!trend_is_established)
      return false;

   bool momentum_is_accelerating = (g_short_term.close_status_text == T.level_n1 || g_short_term.close_status_text == T.level_n2 || g_short_term.close_status_text == T.level_n3) &&
                                   (g_short_term.ema_status_text == T.level_n1 || g_short_term.ema_status_text == T.level_n2 || g_short_term.ema_status_text == T.level_n3);

   bool momentum_is_pullback = (g_short_term.close_status_text == T.level_0) && (g_short_term.ema_status_text == T.level_n2 || g_short_term.ema_status_text == T.level_n3);

   return momentum_is_accelerating || momentum_is_pullback;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool CheckSell_BreakoutConfirmation()
  {
   if(g_long_term.market_diagnosis_text == T.sideways)
     {
      bool momentum_exists = (g_short_term.close_status_text == T.level_n3) && (g_short_term.ema_status_text == T.level_n3);
      return momentum_exists;
     }
   return false;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool isTradingTime()
  {
// 1. Khai báo biến cấu trúc MqlDateTime
   MqlDateTime currentTimeStruct;

// 2. Lấy thời gian hiện tại của server
   datetime serverTime = TimeCurrent();

// 3. Chuyển đổi datetime sang cấu trúc
   TimeToStruct(serverTime, currentTimeStruct);

// 4. Lấy giờ hiện tại trực tiếp từ cấu trúc
   int currentHour = currentTimeStruct.hour;

// Điều kiện kiểm tra giờ
   bool isTradingTime = (currentHour < 20) && (currentHour > 1);
   if(!isTradingTime)
     {
      string currentTimeStr = TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS);
      Print(currentTimeStr, ": Trading time from 2h to 21h");
     }
   return isTradingTime;
  }

//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
// ++                                                                         ++
// ++    HÀM LẤY TÊN SETUP NGẮN GỌN (PHIÊN BẢN ĐẦY ĐỦ VÀ CẬP NHẬT)            ++
// ++                                                                         ++
//+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
string GetSetupFamilyName(ENUM_SETUP_FAMILY setup_family)
  {
   switch(setup_family)
     {
      // --- Trường hợp không có setup ---
      case SETUP_FAMILY_NONE:
         return "None";

      // --- Các setup cũ, chung chung ---
      case SETUP_FAMILY_BUY_STRONG_TREND_PULLBACK:
      case SETUP_FAMILY_SELL_STRONG_TREND_PULLBACK:
         return "Pullback";

      case SETUP_FAMILY_BUY_TREND_MOMENTUM:
      case SETUP_FAMILY_SELL_TREND_MOMENTUM:
         return "Momentum";

      case SETUP_FAMILY_BUY_BREAKOUT_CONFIRMATION:
      case SETUP_FAMILY_SELL_BREAKOUT_CONFIRMATION:
         return "Breakout";

      case SETUP_FAMILY_BUY_BREAKOUT_RANGE:
      case SETUP_FAMILY_SELL_BREAKOUT_RANGE:
         return "Range";

      // *** BỔ SUNG CÁC TRƯỜNG HỢP CÒN THIẾU ***
      case SETUP_FAMILY_BUYLIMIT_BREAKOUT_RANGE:
      case SETUP_FAMILY_SELLLIMIT_BREAKOUT_RANGE:
         return "RangeLimit";

      case SETUP_FAMILY_BUY_CISD:
      case SETUP_FAMILY_SELL_CISD:
         return "CISD_Generic"; // Dùng tên này để phân biệt với các setup CISD cụ thể

      // --- NHÓM A: STATIC PATTERNS (CISD) ---
      case SETUP_FAMILY_BUY_CISD_PULLBACK:
      case SETUP_FAMILY_SELL_CISD_PULLBACK:
         return "CISD_Pullback"; // Giữ tên cũ cho nhất quán

      case SETUP_FAMILY_BUY_CISD_FLOW_TREND:
      case SETUP_FAMILY_SELL_CISD_FLOW_TREND:
         return "CISD_FlowTrend";

      case SETUP_FAMILY_BUY_CISD_CONSOLIDATION_H1:
      case SETUP_FAMILY_SELL_CISD_CONSOLIDATION_H1:
         return "CISD_Consol_H1";

      // --- NHÓM B: CONTEXTUAL COMPRESSION (CISD) ---
      case SETUP_FAMILY_BUY_CISD_COMPRESSION_M15_FLAG:
      case SETUP_FAMILY_SELL_CISD_COMPRESSION_M15_FLAG:
         return "CISD_Comp_Flag";

      case SETUP_FAMILY_BUY_CISD_COMPRESSION_M15_QUIET:
      case SETUP_FAMILY_SELL_CISD_COMPRESSION_M15_QUIET:
         return "CISD_Comp_Quiet";

      // --- NHÓM C: REAL-TIME ENTRIES (CISD) ---
      case SETUP_FAMILY_BUY_CISD_RT_EARLY_BREAK:
      case SETUP_FAMILY_SELL_CISD_RT_EARLY_BREAK:
         return "CISD_RT_Break";

      case SETUP_FAMILY_BUY_CISD_RT_PULLBACK_M30:
      case SETUP_FAMILY_SELL_CISD_RT_PULLBACK_M30:
         return "CISD_RT_Pullback";

      case SETUP_FAMILY_BUY_CISD_RT_BUILDUP_M15:
      case SETUP_FAMILY_SELL_CISD_RT_BUILDUP_M15:
         return "CISD_RT_Buildup";

      // --- Trường hợp mặc định ---
      default:
         return "Unknown";
     }
  }

//*/
//+------------------------------------------------------------------+
//| Tính toán Lot Size và tự động điều chỉnh SL nếu cần              |
//+------------------------------------------------------------------+
double CalculateLotSize(double riskAmount, double &slPrice, double entryPrice)
  {
   if(riskAmount <= 0)
      return 0.0;

// --- Lấy các thông số quan trọng của symbol ---
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0 || tick_size <= 0)
     {
      Print("Invalid tick value or tick size for symbol ", _Symbol);
      return 0.0;
     }

// --- BƯỚC 1: Xác định hướng của SL ban đầu (trên hay dưới entry) ---
   bool is_sl_below_entry = (slPrice < entryPrice);

// --- Tính toán khoảng cách SL và kiểm tra ---
   double sl_distance_price = MathAbs(entryPrice - slPrice);
   if(sl_distance_price < tick_size)
     {
      Print("Stop loss is too close to the entry price.");
      return 0.0;
     }

// --- Tính toán số tiền lỗ cho 1 lot ---
   double loss_for_1_lot = (sl_distance_price / tick_size) * tick_value;
   if(loss_for_1_lot <= 0)
     {
      Print("Cannot calculate lot size due to zero or negative risk per lot.");
      return 0.0;
     }

// --- Tính toán lot size lý thuyết ---
   double lot_size = riskAmount / loss_for_1_lot;

// --- Lấy các giới hạn lot size ---
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
// Áp dụng các giới hạn tùy chỉnh của bạn
   if(IsForexPair(_Symbol) || StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "USTEC") >= 0)
     {
      if(StringFind(_Symbol, "USTEC") >= 0)
         max_lot = max_lot_size;
      if(IsForexPair(_Symbol))
         max_lot = max_lot_size / 2;
      if(StringFind(_Symbol, "XAU") >= 0)
         max_lot = 0.3;
     }
   double step_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

// Chuẩn hóa lot size theo bước nhảy
   double normalized_lot_size = MathFloor(lot_size / step_lot) * step_lot;

// =================================================================================
// <<< PHẦN LOGIC MỚI: KIỂM TRA GIỚI HẠN VÀ TÍNH TOÁN LẠI SL NẾU CẦN >>>
// =================================================================================
   double final_lot_size = normalized_lot_size;

// Nếu lot size tính được vượt quá mức tối đa cho phép
   if(final_lot_size > max_lot)
     {
      PrintFormat("Lot size tính toán (%.2f) vượt quá max_lot (%.2f). Đang điều chỉnh SL.", final_lot_size, max_lot);

      // 1. Giới hạn lot size về mức tối đa
      final_lot_size = max_lot;

      // 2. Tính lại khoảng cách SL cần thiết để giữ nguyên riskAmount với lot size mới
      // Công thức đảo ngược: sl_distance = (riskAmount / lot_size) / (tick_value / tick_size)
      double new_sl_distance = (riskAmount / final_lot_size) * (tick_size / tick_value);

      // 3. Cập nhật lại giá slPrice dựa trên hướng SL ban đầu
      if(is_sl_below_entry)
        {
         // Nếu SL ban đầu ở dưới, SL mới cũng ở dưới
         slPrice = entryPrice - new_sl_distance;
        }
      else
        {
         // Nếu SL ban đầu ở trên, SL mới cũng ở trên
         slPrice = entryPrice + new_sl_distance;
        }

      // Chuẩn hóa giá SL mới theo số chữ số thập phân của symbol
      slPrice = NormalizeDouble(slPrice, _Digits);

      PrintFormat("SL đã được cập nhật thành: %.*f để phù hợp với rủi ro %.2f USD", _Digits, slPrice, riskAmount);
     }
// =================================================================================
// <<< KẾT THÚC PHẦN LOGIC MỚI >>>
// =================================================================================

// Kiểm tra lại với lot size tối thiểu
   if(final_lot_size < min_lot)
     {
      PrintFormat("Calculated lot size (%.8f) is less than the minimum allowed (%.8f).", final_lot_size, min_lot);
      return 0.0;
     }

// --- Kiểm tra Margin (sử dụng final_lot_size) ---
   double margin_required;
   if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, final_lot_size, SymbolInfoDouble(_Symbol, SYMBOL_ASK), margin_required))
     {
      Print("Failed to calculate margin. Error: ", GetLastError());
      return 0.0;
     }

   if(AccountInfoDouble(ACCOUNT_MARGIN_FREE) < margin_required)
     {
      Print("Not enough free margin. Required: ", DoubleToString(margin_required, 2), ", Available: ", DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2));
      return 0.0;
     }

   return final_lot_size;
  }

//==================================================================
// SECTION 6 & 7: DRAWING FUNCTIONS
//==================================================================
// Helper: tạo màu ARGB (a: 0..255, r,g,b: 0..255)
color ARGB(int a, int r, int g, int b)
  {
   return (color)(((uint)a << 24) | ((uint)r << 16) | ((uint)g << 8) | (uint)b);
  }

// Tính số dòng sẽ hiển thị trong panel (dùng cùng các flags InpShow...)
int CountPanelLines()
  {
   int lines = 2;
   if(InpShowH1CISD)
      lines = lines + numItemStatus - 1;
   if(InpShowH1Status)
      lines = lines + 5;
   if(InpShowDailyStatus)
      lines++;
   if(InpShowShortTermStatus)
      lines++;
   if(InpShowLongTermStatus)
      lines++;
   if(InpShowCloseDetails)
      lines++;
   if(InpShowEmaDetails)
      lines++;
   if(InpShowStochasticDetails)
      lines = lines + 4;
   return lines;
  }

// Vẽ / cập nhật nền panel (rectangle label) với alpha trong background color
void DrawSlopePanelBackground()
  {
   int lines = CountPanelLines();
   string bg_name = "SlopePanelBG";
   int padding_x = 6;
   int padding_y = 6;

// Kích thước ước lượng (tùy chỉnh cho vừa ý)
   int width = 230; // bạn có thể tính dựa trên font size & độ dài text nếu muốn
   int height = InpPanelLineSpacing * lines + padding_y * 2;
   if(height < 20)
      height = 20;

   if(ObjectFind(0, bg_name) < 0)
      ObjectCreate(0, bg_name, OBJ_RECTANGLE_LABEL, 0, 0, 0);

   ObjectSetInteger(0, bg_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bg_name, OBJPROP_XDISTANCE, InpPanelXDistance - padding_x);
   ObjectSetInteger(0, bg_name, OBJPROP_YDISTANCE, InpPanelYDistance - padding_y);
   ObjectSetInteger(0, bg_name, OBJPROP_XSIZE, width);
   ObjectSetInteger(0, bg_name, OBJPROP_YSIZE, height);

// Màu nền với alpha (0 = trong suốt, 255 = đặc). Thử a = 160..200 cho mờ vừa phải
   color bg = ARGB(160, 0, 0, 0); // nền đen mờ
   ObjectSetInteger(0, bg_name, OBJPROP_BGCOLOR, (int)bg);

// Không vẽ viền (hoặc đặt viền trong suốt)
   ObjectSetInteger(0, bg_name, OBJPROP_COLOR, (int)clrNONE);

// Đặt ở foreground (không ở background), và z-order thấp hơn label
   ObjectSetInteger(0, bg_name, OBJPROP_BACK, false); // false: vẽ ở phía trước chart elements
   ObjectSetInteger(0, bg_name, OBJPROP_ZORDER, 9998);

   ObjectSetInteger(0, bg_name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, bg_name, OBJPROP_SELECTED, false);

   if(g_managed_objects.Search(bg_name) < 0)
      g_managed_objects.Add(bg_name);
  }

//=== Vẽ nền mờ trung tâm ===//
void DrawChecklistPanelBackground(int lines)
  {
   if(!InpShowChecklistPanel)
      return;
   string bg_name = "ChecklistPanelBG";
   int padding_x = 6;
   int padding_y = 6;

// Ước lượng chiều rộng và chiều cao
   int width = 160;
   int height = 18 * lines + padding_y * 2;
   if(height < 20)
      height = 20;

// Lấy chiều rộng chart để căn giữa
   int chart_width = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS, 0);
   int x = (chart_width / 2) - (width / 2) - padding_x + 60; // Căn giữa

   if(ObjectFind(0, bg_name) < 0)
      ObjectCreate(0, bg_name, OBJ_RECTANGLE_LABEL, 0, 0, 0);

   ObjectSetInteger(0, bg_name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bg_name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, bg_name, OBJPROP_YDISTANCE, InpPanelYDistance - padding_y);
   ObjectSetInteger(0, bg_name, OBJPROP_XSIZE, width);
   ObjectSetInteger(0, bg_name, OBJPROP_YSIZE, height);

// Nền đen mờ
   color bg_color = ARGB(180, 0, 0, 0); // 180 = mờ vừa, nền đen
   ObjectSetInteger(0, bg_name, OBJPROP_BGCOLOR, (int)bg_color);

// Viền nhẹ
   color border_color = ARGB(220, 80, 80, 80); // xám nhạt
   ObjectSetInteger(0, bg_name, OBJPROP_COLOR, border_color);

// Vẽ dưới label nhưng vẫn nổi hơn chart
   ObjectSetInteger(0, bg_name, OBJPROP_BACK, false);
   ObjectSetInteger(0, bg_name, OBJPROP_ZORDER, 9997);

   ObjectSetInteger(0, bg_name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, bg_name, OBJPROP_SELECTED, false);

   if(g_managed_objects.Search(bg_name) < 0)
      g_managed_objects.Add(bg_name);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void UpdateChecklistPanel(int signal, double ltf_cisd_price)
  {
   if(!InpShowChecklistPanel)
      return;
   string panel_prefix = "OBJ_ID_CHECKLIST_";
   int panel_width = 160; // Ước lượng chiều rộng panel
   int chart_width = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS, 0);
   int x = (chart_width / 2) - (panel_width / 2) + 60; // canh giữa ngang
   int y = 30;                                         // cách mép trên 20px
   int line_space = 16;
   int font_size = 10;
   color up_color = clrLime;
   color down_color = clrRed;
   color neutral_color = clrSilver;
   ENUM_BASE_CORNER corner = CORNER_LEFT_UPPER;

   DrawChecklistPanelBackground(5);

//--- Dữ liệu Daily
   double d_open = iOpen(_Symbol, PERIOD_D1, 0);
   double d_close = iClose(_Symbol, PERIOD_D1, 0);
   bool daily_up = (d_close > d_open);

//--- Xác định hướng tín hiệu
   string signal_text = (signal == 1) ? "BUY" : (signal == -1) ? "SELL"
                        : "NEUTRAL";
   color signal_color = (signal == 1) ? up_color : (signal == -1) ? down_color
                        : neutral_color;

//--- Tiêu đề
   string title = StringFormat("Checklist (%s)", signal_text);
   CreateOrMoveLabel(panel_prefix + "TITLE", x, y, signal_color, font_size, title, corner);
   y += line_space + 5;

   string H1CISD_Status = "Flat";
   color H1CISD_Color = c_Sideway;

   if(g_h1_signalType == 1)
     {
      H1CISD_Status = "Up";
      H1CISD_Color = c_StrongTrend_Up;
     }
   else
      if(g_h1_signalType == -1)
        {
         H1CISD_Status = "Down";
         H1CISD_Color = c_StrongTrend_Down;
        }

   string text = StringFormat("H1 CISD: %s", H1CISD_Status);
   CreateOrMoveLabel(panel_prefix + "H1CISD", x, y, H1CISD_Color, font_size, text, corner);
   y += line_space;

//--- Checklist 1: Daily Trend
   string daily_status = daily_up ? "Up" : "Down";
   bool cond_daily = (g_h1_signalType == 1 && daily_up) || (g_h1_signalType == -1 && !daily_up);
   string daily_check = cond_daily ? "✅" : "❌";
   string text1 = StringFormat("%s Daily: %s", daily_check, daily_status);
   CreateOrMoveLabel(panel_prefix + "DAILY", x, y, cond_daily ? up_color : down_color, font_size, text1, corner);
   y += line_space;

//--- Checklist 2: H1 CISD so với D.Open
   bool cond_h1 = (g_h1_signalType == 1) ? (g_h1_breakoutPrice > d_open) : (g_h1_breakoutPrice < d_open);
   string h1_symbol = (g_h1_signalType == 1) ? ">" : "<";
   string text2 = StringFormat("%s H1 CISD %s D.Open", cond_h1 ? "✅" : "❌", h1_symbol);
   CreateOrMoveLabel(panel_prefix + "H1", x, y, cond_h1 ? up_color : down_color, font_size, text2, corner);
   y += line_space;

//--- Checklist 3: M5 CISD so với D.Open
   bool cond_m5 = (g_h1_signalType == 1) ? (ltf_cisd_price > d_open) : (ltf_cisd_price < d_open);
   string m5_symbol = (g_h1_signalType == 1) ? ">" : "<";
   string text3 = StringFormat("%s M5 CISD %s D.Open", cond_m5 ? "✅" : "❌", m5_symbol);
   CreateOrMoveLabel(panel_prefix + "M5", x, y, cond_m5 ? up_color : down_color, font_size, text3, corner);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CreateOrMoveTrendLine(string name, datetime t1, double p1, datetime t2, double p2, color clr, int width, ENUM_LINE_STYLE style, bool is_background = true)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_BACK, is_background);
   if(g_managed_objects.Search(name) < 0)
      g_managed_objects.Add(name);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CreateOrMoveLabel(string name, int x, int y, color clr, int font_size, string text, ENUM_BASE_CORNER corner = CORNER_LEFT_UPPER)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, x, y);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_CORNER, corner);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, font_size);
   ObjectSetString(0, name, OBJPROP_TEXT, text);

// 🔹 Thêm dòng này để label nổi lên trên tất cả
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_ZORDER, 9999);

// 🔹 Nếu bạn muốn label không bị chọn nhầm khi click chart:
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTED, false);

   if(g_managed_objects.Search(name) < 0)
      g_managed_objects.Add(name);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CreateOrMoveText(string name, datetime t, double p, color clr, int font_size, string text, ENUM_ANCHOR_POINT anchor, bool is_background = false)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
   else
      ObjectMove(0, name, 0, t, p);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, font_size);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, name, OBJPROP_BACK, is_background); // Thêm dòng này
   if(g_managed_objects.Search(name) < 0)
      g_managed_objects.Add(name);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CreateOrMoveRectangle(string name, datetime t1, double p1, datetime t2, double p2, color clr, int width, ENUM_LINE_STYLE style, bool fill, bool is_background = true)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_FILL, fill);
   ObjectSetInteger(0, name, OBJPROP_BACK, is_background);
   ObjectSetInteger(0, name, OBJPROP_ZORDER, 0);
   if(g_managed_objects.Search(name) < 0)
      g_managed_objects.Add(name);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void CreateOrMoveArrow(string name, datetime t, double p, int code, color clr, ENUM_ANCHOR_POINT anchor)
  {
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW, 0, t, p);
   else
      ObjectMove(0, name, 0, t, p);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_ZORDER, 0);
   if(InpLTFArrowStyle == ARROW_Dot)
      ObjectSetString(0, name, OBJPROP_FONT, "Wingdings");
   if(g_managed_objects.Search(name) < 0)
      g_managed_objects.Add(name);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawH1PrimaryLine(datetime startTime, datetime endTime, double priceLevel, int signalType)
  {
   string name = GenerateObjectName(OBJ_ID_H1_PRIMARY_LINE);
   color lineColor = (signalType == 1) ? InpH1BullColor : InpH1BearColor;
   CreateOrMoveTrendLine(name, startTime, priceLevel, endTime, priceLevel, lineColor, InpH1LineWidth, InpH1LineStyle);
   if(InpShowH1Label && StringLen(InpH1LineLabelText) > 0)
     {
      string labelName = GenerateObjectName(OBJ_ID_H1_PRIMARY_LABEL);
      CreateOrMoveText(labelName, startTime, priceLevel, lineColor, InpCISDFontSize - 1, InpH1LineLabelText, ANCHOR_RIGHT);
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawConfirmationLine(datetime t1, datetime t2, double price, string type, bool is_continuation)
  {
   string name = GenerateObjectName("ConfirmationLine", TimeToString(t2, TIME_DATE | TIME_SECONDS));
   color clr = (type == "Bullish") ? InpBullColor : InpBearColor;
   ENUM_LINE_STYLE style = is_continuation ? InpContinuationConfirmationStyle : InpInitialConfirmationStyle;
   CreateOrMoveTrendLine(name, t1, price, t2, price, clr, InpLTFLineWidth, style);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawConfirmationLabel(datetime t, double p, string type)
  {
   string name = GenerateObjectName("ConfirmationLabel", TimeToString(t, TIME_DATE | TIME_SECONDS));
   color clr = (type == "Bullish") ? InpBullColor : InpBearColor;
   bool above = (type == "Bearish");
   double price_offset = _Point * InpCISDFontSize * 2;
   double final_price = above ? p + price_offset : p - price_offset;
   ENUM_ANCHOR_POINT anchor = above ? ANCHOR_TOP : ANCHOR_BOTTOM;
   CreateOrMoveText(name, t, final_price, clr, InpCISDFontSize, "Confirmed", anchor);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawSignalArrow(datetime time, double price, int direction)
  {
   string name = GenerateObjectName("SignalArrow", TimeToString(time, TIME_DATE | TIME_SECONDS));
   int arrow_code;
   if(InpLTFArrowStyle == ARROW_Arrow)
     {
      arrow_code = (direction == 1) ? 241 : 242;
     }
   else
     {
      arrow_code = 159;
     }
   color arrow_color = (direction == 1) ? InpBullColor : InpBearColor;
   ENUM_ANCHOR_POINT anchor = (direction == 1) ? ANCHOR_TOP : ANCHOR_BOTTOM;
   CreateOrMoveArrow(name, time, price, arrow_code, arrow_color, anchor);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int numItemStatus = 0;
void UpdateSlopePanelDisplay()
  {
   int current_y = InpPanelYDistance;

   string profit = StringFormat("%.2f$ Max: %.2f$ Min: %.2f$", buy_total_profit + sell_total_profit, g_total_profit_max, g_total_profit_min);
   CreateOrMoveLabel(GenerateObjectName("OBJ_ID_PROFIT_MAX_MIN"), InpPanelXDistance, current_y, clrLime, InpPanelFontSize, profit);
   current_y += InpPanelLineSpacing;

   string pips = StringFormat("%.1f Max: %.1f Min: %.1f", g_total_pips_now, g_total_pips_max, g_total_pips_min);
   CreateOrMoveLabel(GenerateObjectName("OBJ_ID_PIPS_MAX_MIN"), InpPanelXDistance, current_y, clrRed, InpPanelFontSize, pips);
   current_y += InpPanelLineSpacing;

// ==================== KHỐI CISD ====================
   if(InpShowH1CISD)
     {
      // --- Dữ liệu cho từng khung thời gian ---
      // Chúng ta đưa các giá trị thay đổi vào mảng để lặp qua
      int signalTypes[] = {g_h1_signalType, g_m30_signalType, g_m15_signalType, g_m5_signalType};
      string tfNames[] = {"H1", "M30", "M15", "M5"};
      string objectIds[] = {OBJ_ID_SLOPE_PANEL_H1_CISD, OBJ_ID_SLOPE_PANEL_M30_CISD, OBJ_ID_SLOPE_PANEL_M15_CISD, OBJ_ID_SLOPE_PANEL_M5_CISD};
      int numTimeframes = ArraySize(signalTypes);

      // --- Vòng lặp để xử lý chung ---
      for(int i = 0; i < numTimeframes; i++)
        {
         string status = "Flat";
         color statusColor = c_Sideway;

         if(signalTypes[i] == 1)
           {
            status = "Up";
            statusColor = c_StrongTrend_Up;
           }
         else
            if(signalTypes[i] == -1)
              {
               status = "Down";
               statusColor = c_StrongTrend_Down;
              }

         string text;
         // Trường hợp đặc biệt cho H1 có hiển thị giá
         if(tfNames[i] == "H1")
           {
            text = StringFormat("%s CISD: %s @ %s %s", tfNames[i], status, g_h1_buy_signal_active ? "true" : "false", g_h1_sell_signal_active ? "true" : "false");
           }
         else
            if(tfNames[i] == "M30")
              {
               text = StringFormat("%s CISD: %s @ %s %s", tfNames[i], status, g_m30_buy_signal_active ? "true" : "false", g_m30_sell_signal_active ? "true" : "false");
              }
            else
              {
               text = StringFormat("%s CISD: %s", tfNames[i], status);
              }

         CreateOrMoveLabel(GenerateObjectName(objectIds[i]), InpPanelXDistance, current_y, statusColor, InpPanelFontSize, text);
         current_y += InpPanelLineSpacing;
        }
     }

// ==================== KHỐI STATUS NẾN ====================
   if(InpShowH1Status)
     {
      // --- Dữ liệu cho từng khung thời gian ---
      // string labels[] = { "H4 Pre", "H1 Pre", "M30 Pre", "M15 Pre", "H4", "H1", "M30", "M15", "M5" };
      // ENUM_TIMEFRAMES periods[] = { PERIOD_H4, PERIOD_H1, PERIOD_M30, PERIOD_M15, PERIOD_H4, PERIOD_H1, PERIOD_M30, PERIOD_M15, PERIOD_M5 };
      // double percentages[] = { g_h4_pre_percent, g_h1_pre_percent, g_m30_pre_percent, g_m15_pre_percent, g_h4_percent, g_h1_percent, g_m30_percent, g_m15_percent, g_m5_percent };
      // string objectIds[] = { OBJ_ID_SLOPE_PANEL_H4_Pre, OBJ_ID_SLOPE_PANEL_H1_Pre, OBJ_ID_SLOPE_PANEL_M30_Pre, OBJ_ID_SLOPE_PANEL_M15_Pre, OBJ_ID_SLOPE_PANEL_H4, OBJ_ID_SLOPE_PANEL_H1, OBJ_ID_SLOPE_PANEL_M30, OBJ_ID_SLOPE_PANEL_M15, OBJ_ID_SLOPE_PANEL_M5 };
      string labels[] = {"H1", "M30", "M15", "M5"};
      ENUM_TIMEFRAMES periods[] = {PERIOD_H1, PERIOD_M30, PERIOD_M15, PERIOD_M5};
      double percentages[] = {g_h4_pre_percent, g_h1_pre_percent, g_h1_percent, g_m30_percent, g_m15_percent, g_m5_percent};
      string objectIds[] = {OBJ_ID_SLOPE_PANEL_H1, OBJ_ID_SLOPE_PANEL_M30, OBJ_ID_SLOPE_PANEL_M15, OBJ_ID_SLOPE_PANEL_M5};
      int numItems = ArraySize(labels);
      numItemStatus = numItems;

      // --- Vòng lặp để xử lý chung ---
      for(int i = 0; i < numItems; i++)
        {
         // Xử lý trường hợp đặc biệt cho "H1 Pre" (lấy dữ liệu nến trước đó, shift=1)
         int shift = (StringFind(labels[i], "Pre") != -1) ? 1 : 0;

         double o = iOpen(_Symbol, periods[i], shift);
         double c = iClose(_Symbol, periods[i], shift);

         string status = "";
         color statusColor = c_Sideway;

         if(c > o)
           {
            status = "Up";
            statusColor = c_StrongTrend_Up;
           }
         else
            if(c < o)
              {
               status = "Down";
               statusColor = c_StrongTrend_Down;
              }

         string text = StringFormat("%s: %s (%.2f%%) - %s", labels[i], status, percentages[i], GetTimeRemainingForNewCandle(periods[i]));
         if(StringFind(labels[i], "Pre") != -1)
            text = StringFormat("%s: %s (%.2f%%)", labels[i], status, percentages[i]);
         CreateOrMoveLabel(GenerateObjectName(objectIds[i]), InpPanelXDistance, current_y, statusColor, InpPanelFontSize, text);
         current_y += InpPanelLineSpacing;
        }
     }

// ==================== CÁC KHỐI CÒN LẠI (giữ nguyên vì logic không lặp lại) ====================
   if(InpShowDailyStatus)
     {
      double DOpen = iOpen(_Symbol, PERIOD_D1, 0);
      double DClose = iClose(_Symbol, PERIOD_D1, 0);

      string DStatus = "Flat";
      color DColor = c_Sideway;

      if(DClose > DOpen)
        {
         DStatus = "Up";
         DColor = c_StrongTrend_Up;
        }
      else
         if(DClose < DOpen)
           {
            DStatus = "Down";
            DColor = c_StrongTrend_Down;
           }

      string text = StringFormat("D: %s (%.2f%%)", DStatus, g_daily_percent);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_DAILY), InpPanelXDistance, current_y, DColor, InpPanelFontSize, text);
      current_y += InpPanelLineSpacing;
     }

   if(InpShowShortTermStatus)
     {
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_SHORT), InpPanelXDistance, current_y, g_short_term.market_diagnosis_color, InpPanelFontSize, T.short_term + g_short_term.market_diagnosis_text);
      current_y += InpPanelLineSpacing;
     }

   if(InpShowLongTermStatus)
     {
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_LONG), InpPanelXDistance, current_y, g_long_term.market_diagnosis_color, InpPanelFontSize, T.long_term + g_long_term.market_diagnosis_text);
      current_y += InpPanelLineSpacing;
     }

   if(InpShowCloseDetails)
     {
      string text = StringFormat("%s %s (%.2f%%)", T.close, g_short_term.close_status_text, g_short_term.close_slope * 100);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_CLOSE), InpPanelXDistance, current_y, g_short_term.close_color, InpPanelFontSize, text);
      current_y += InpPanelLineSpacing;
     }

   if(InpShowEmaDetails)
     {
      string text = StringFormat("%s(%d): %s (%.2f%%)", T.ema, InpEmaPeriod, g_short_term.ema_status_text, g_short_term.ema_slope * 100);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_EMA), InpPanelXDistance, current_y, g_short_term.ema_color, InpPanelFontSize, text);
      current_y += InpPanelLineSpacing;
     }

   if(InpShowStochasticDetails)
     {
      // Sử dụng StringFormat với độ chính xác 4 chữ số thập phân để thấy rõ sự thay đổi
      string textD2 = StringFormat("D2 : K=%.2f, D=%.2f\n", k_d2, d_d2);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_STOCH_D2), InpPanelXDistance, current_y, clrGreen, InpPanelFontSize, textD2);
      current_y += InpPanelLineSpacing;

      string textD1 = StringFormat("D1 : K=%.2f, D=%.2f\n", k_d1, d_d1);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_STOCH_D1), InpPanelXDistance, current_y, clrRed, InpPanelFontSize, textD1);
      current_y += InpPanelLineSpacing;

      string textH4 = StringFormat("H4 : K=%.2f, D=%.2f\n", k_h4, d_h4);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_STOCH_4H), InpPanelXDistance, current_y, clrGreen, InpPanelFontSize, textH4);
      current_y += InpPanelLineSpacing;

      string textH1 = StringFormat("H1 : K=%.2f, D=%.2f\n", k_h1, d_h1);
      CreateOrMoveLabel(GenerateObjectName(OBJ_ID_SLOPE_PANEL_STOCH_1H), InpPanelXDistance, current_y, clrRed, InpPanelFontSize, textH1);
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawDailyOpenLine()
  {
   for(int i = 0; i < InpNumOfDaysToDraw; i++)
     {
      double dClosePrev = iClose(_Symbol, PERIOD_D1, i + 1);
      double dOpenToday = iOpen(_Symbol, PERIOD_D1, i);
      if(dOpenToday == 0)
         break;
      datetime time_start = iTime(_Symbol, PERIOD_D1, i);
      datetime time_end;
      if(i == 0)
        {
         time_end = time_start + PeriodSeconds(PERIOD_D1) - 1;
         time_end = MathMin(TimeCurrent() + PeriodSeconds(), time_end);
        }
      else
        {
         time_end = time_start + PeriodSeconds(PERIOD_D1) - 1;
        }
      string lineName = GenerateObjectName(OBJ_ID_DAILY_OPEN_LINE, (string)time_start);
      string rectName = GenerateObjectName(OBJ_ID_DAILY_GAP_RECT, (string)time_start);
      if(MathAbs(dClosePrev - dOpenToday) < _Point)
        {
         CreateOrMoveTrendLine(lineName, time_start, dClosePrev, time_end, dClosePrev, clrYellow, 1, STYLE_SOLID, false);
        }
      else
        {
         double p_high = MathMax(dClosePrev, dOpenToday);
         double p_low = MathMin(dClosePrev, dOpenToday);
         CreateOrMoveRectangle(rectName, time_start, p_high, time_end, p_low, clrYellow, 1, STYLE_SOLID, false, false);
        }
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawH4ClosesOnCurrentTimeframe()
  {
   if(!InpShowH4CloseLine)
      return;
   datetime today_start = iTime(_Symbol, PERIOD_D1, 0);
   int start_h4_bar = iBarShift(_Symbol, PERIOD_H4, today_start, true);
   if(start_h4_bar < 0)
      return;
   datetime chart_now = iTime(_Symbol, _Period, 0) + PeriodSeconds();
   for(int i = 0; i <= start_h4_bar; i++)
     {
      datetime h4_time = iTime(_Symbol, PERIOD_H4, i) + PeriodSeconds(PERIOD_H4) - 1;
      if(h4_time < today_start || h4_time > chart_now)
         continue;
      double h4_close = iClose(_Symbol, PERIOD_H4, i);
      int bar_shift = iBarShift(_Symbol, _Period, h4_time, true);
      if(bar_shift < 0)
         continue;
      datetime tf_time = iTime(_Symbol, _Period, bar_shift);
      string lineName = GenerateObjectName("H4Close", (string)h4_time);
      CreateOrMoveTrendLine(lineName, tf_time, h4_close, chart_now, h4_close, InpH4CloseLineColor, InpH4CloseLineWidth, InpH4CloseLineStyle);
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DrawSidewayRanges()
  {
   for(int i = 0; i < 3; i++)
     {
      if(g_st_ranges[i].isActive)
        {
         string name = GenerateObjectName("SidewayRange_Current", g_st_ranges[i].timeframeLabel);
         CreateOrMoveRectangle(name, g_st_ranges[i].rangeStartTime, g_st_ranges[i].high, TimeCurrent() + PeriodSeconds(), g_st_ranges[i].low, InpShortTermRectColor, 1, STYLE_DOT, false);
        }
     }

   for(int i = 0; i < g_historical_ranges.Total(); i++)
     {
      CObject *obj = g_historical_ranges.At(i);
      RangeInfo *range = (RangeInfo *)obj;
      if(CheckPointer(range) == POINTER_INVALID)
         continue;
      string name = GenerateObjectName("SidewayRange_Hist", range.timeframeLabel + (string)range.rangeStartTime);
      color rect_color = (range.breakoutDirection == "Trend_Changed") ? clrSlateGray : (range.breakoutDirection == "Bullish" ? clrDarkSeaGreen : clrIndianRed);
      CreateOrMoveRectangle(name, range.rangeStartTime, range.high, range.rangeEndTime, range.low, rect_color, 1, STYLE_DASH, false);
     }
  }

//==================================================================
// SECTION 8: NOTIFICATION & UTILITY FUNCTIONS
//==================================================================
void ResetRangeInfo(RangeInfo &range)
  {
   range.isActive = false;
   range.high = 0;
   range.low = 0;
   range.rangeStartTime = 0;
   range.rangeEndTime = 0;
   range.breakoutDirection = "None";
   range.breakoutPrice = 0;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void TriggerCISDAlerts(string message)
  {
   if(InpAlertPopup)
      Alert(message);
   if(InpAlertPush)
      SendNotification(message);
   if(InpAlertEmail)
      SendMail("CISD Signal: " + _Symbol, message);
   if(InpAlertSound)
      PlaySound(InpSoundFile);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string SanitizeHTML(string text)
  {
   string s = text;
   StringReplace(s, "&", "&amp;");
   StringReplace(s, "<", "&lt;");
   StringReplace(s, ">", "&gt;");
   return s;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void SendTelegramMessage(string message)
  {
   if(!InpEnableTelegram || StringLen(InpTelegramBotToken) < 10 || StringLen(InpTelegramChatID) < 1 || StringLen(message) < 1)
      return;
   string url = "https://api.telegram.org/bot" + InpTelegramBotToken + "/sendMessage";
   string headers = "Content-Type: application/json; charset=utf-8";
   string escaped_message = message;
   StringReplace(escaped_message, "\\", "\\\\");
   StringReplace(escaped_message, "\"", "\\\"");
   StringReplace(escaped_message, "\r", "");
   StringReplace(escaped_message, "\n", "\\n");
   string json_body = StringFormat("{\"chat_id\":\"%s\", \"text\":\"%s\", \"parse_mode\":\"HTML\"}", InpTelegramChatID, escaped_message);
   char post_data[];
   int size_with_null = StringToCharArray(json_body, post_data, 0, -1, CP_UTF8);
   if(size_with_null > 0)
      ArrayResize(post_data, size_with_null - 1);
   else
     {
      Print("Failed to convert JSON to char array for Telegram.");
      return;
     }
   char result_data[];
   string result_headers;
   ResetLastError();
   int res = WebRequest("POST", url, headers, 5000, post_data, result_data, result_headers);
   if(res == -1)
      Print("WebRequest FAILED! Error code = ", GetLastError(), ".");
   else
      if(res != 200)
        {
         Print("WebRequest to Telegram returned HTTP Status: ", res);
         Print("Server Response: ", CharArrayToString(result_data));
        }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void SendTelegramScreenshot(string caption)
  {
   if(!InpEnableTelegram || StringLen(InpTelegramBotToken) < 10 || StringLen(InpTelegramChatID) < 1)
      return;
   string file_name = "CISD_Signal_" + _Symbol + "_" + TimeToString(TimeCurrent(), "yyyy.MM.dd_HH-mm-ss") + ".png";
   if(!ChartScreenShot(0, file_name, InpScreenshotWidth, InpScreenshotHeight, ALIGN_RIGHT))
     {
      Print("Failed to create screenshot file: ", file_name);
      return;
     }
   Sleep(200);
   uchar file_data[];
   int file_handle = FileOpen(file_name, FILE_READ | FILE_BIN);
   if(file_handle == INVALID_HANDLE)
     {
      Print("Failed to open screenshot file: ", file_name, ". Error: ", GetLastError());
      FileDelete(file_name);
      return;
     }
   if(FileReadArray(file_handle, file_data) <= 0)
     {
      Print("Failed to read screenshot file data.");
      FileClose(file_handle);
      FileDelete(file_name);
      return;
     }
   FileClose(file_handle);
   string boundary = "----WebKitFormBoundary" + IntegerToString(GetTickCount());
   uchar post_data[];
   string text_part = "--" + boundary + "\r\n" + "Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n" + InpTelegramChatID + "\r\n" + "--" + boundary + "\r\n" + "Content-Disposition: form-data; name=\"caption\"\r\n\r\n" + caption + "\r\n" + "--" + boundary + "\r\n" + "Content-Disposition: form-data; name=\"parse_mode\"\r\n\r\n" + "HTML\r\n";
   string photo_header = "--" + boundary + "\r\n" + "Content-Disposition: form-data; name=\"photo\"; filename=\"" + file_name + "\"\r\n" + "Content-Type: image/png\r\n\r\n";
   string footer = "\r\n--" + boundary + "--\r\n";
   uchar text_bytes[], photo_header_bytes[], footer_bytes[];
   int text_len = StringToCharArray(text_part, text_bytes, 0, -1, CP_UTF8) - 1;
   int photo_header_len = StringToCharArray(photo_header, photo_header_bytes, 0, -1, CP_UTF8) - 1;
   int footer_len = StringToCharArray(footer, footer_bytes, 0, -1, CP_UTF8) - 1;
   int total_size = text_len + photo_header_len + (int)ArraySize(file_data) + footer_len;
   ArrayResize(post_data, total_size);
   int pos = 0;
   ArrayCopy(post_data, text_bytes, pos, 0, text_len);
   pos += text_len;
   ArrayCopy(post_data, photo_header_bytes, pos, 0, photo_header_len);
   pos += photo_header_len;
   ArrayCopy(post_data, file_data, pos, 0, (int)ArraySize(file_data));
   pos += (int)ArraySize(file_data);
   ArrayCopy(post_data, footer_bytes, pos, 0, footer_len);
   string url = "https://api.telegram.org/bot" + InpTelegramBotToken + "/sendPhoto";
   string headers = "Content-Type: multipart/form-data; boundary=" + boundary;
   char result_data[];
   string result_headers;
   ResetLastError();
   int res = WebRequest("POST", url, headers, 10000, post_data, result_data, result_headers);
   FileDelete(file_name);
   if(res == -1)
      Print("Screenshot WebRequest FAILED! Error code = ", GetLastError());
   else
      if(res != 200)
        {
         Print("Screenshot WebRequest returned HTTP Status: ", res);
         Print("Server Response: ", CharArrayToString(result_data));
        }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void SendTradeExecutionToTelegram(string prefix, string trade_type, double price, double sl, double tp, const TrendAnalysisResult &st, const TrendAnalysisResult &lt)
  {
   if(!InpEnableTelegram)
      return;
   string trade_icon = (trade_type == "BUY") ? "🟢" : "🔴";
   datetime adjusted_time = TimeCurrent() + (InpTimeOffsetHours * 3600);
   string execution_time = TimeToString(adjusted_time, TIME_MINUTES);
   string message = StringFormat("%s %s: %s %s @ %s\n", trade_icon, prefix, trade_type, _Symbol, execution_time);
   message += "-----------------------------------\n";
   message += StringFormat("Entry Price: %s\n", DoubleToString(price, _Digits));
   message += StringFormat("Stop Loss:   %s\n", DoubleToString(sl, _Digits));
   message += StringFormat("Take Profit: %s\n", DoubleToString(tp, _Digits));
   message += "-----------------------------------\nANALYSIS SNAPSHOT:\n";
   message += StringFormat("%s%s\n", T.short_term, st.market_diagnosis_text);
   message += StringFormat("%s%s\n", T.long_term, lt.market_diagnosis_text);
   message += "-----------------------------------\nStochastic:\n";
   message += StringFormat("D2 : K=%.2f, D=%.2f\n", k_d2, d_d2);
   message += StringFormat("D1 : K=%.2f, D=%.2f\n", k_d1, d_d1);
   message += StringFormat("H4 : K=%.2f, D=%.2f\n", k_h4, d_h4);
   message += StringFormat("H1 : K=%.2f, D=%.2f\n", k_h1, d_h1);
   message += "-----------------------------------\n";
   message += StringFormat("SLOPE DETAILS (%s):\n", StringSubstr(T.short_term, 0, StringLen(T.short_term) - 2));
   message += StringFormat(" > %s %s (%.2f%%)\n", T.close, st.close_status_text, st.close_slope * 100);
   message += StringFormat(" > %s(%d): %s (%.2f%%)\n", T.ema, InpEmaPeriod, st.ema_status_text, st.ema_slope * 100);
   if(InpSendScreenshotOnSignal)
      SendTelegramScreenshot(message);
   else
      SendTelegramMessage(message);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string FormatBreakoutAlert(string timeframe_label, string direction, double price, datetime breakout_time)
  {
   string direction_icon = (direction == "Bullish") ? "▲" : "▼";
   string formatted_price = DoubleToString(price, _Digits);
   datetime adjusted_time = breakout_time + (InpTimeOffsetHours * 3600);
   string execution_time = TimeToString(adjusted_time, TIME_MINUTES);
   return StringFormat("🔥 %s %s %s %s (%s)", _Symbol, timeframe_label, direction_icon, formatted_price, execution_time);
  }

//+------------------------------------------------------------------+
//| Structures for data transfer                                     |
//+------------------------------------------------------------------+
struct DailyBarInfo
  {
   string            status;
   string            emoji;
   double            percent;
  };

//+------------------------------------------------------------------+
//| Helper Functions for Message Formatting                          |
//+------------------------------------------------------------------+

//--- Lấy thông tin nến D1 (Today/Yesterday)
DailyBarInfo GetDailyBarContext(const int shift)
  {
   DailyBarInfo info;
   double o = iOpen(_Symbol, PERIOD_D1, shift);
   double h = iHigh(_Symbol, PERIOD_D1, shift);
   double l = iLow(_Symbol, PERIOD_D1, shift);
   double c = iClose(_Symbol, PERIOD_D1, shift);

   if(o <= 0 || h <= 0 || l <= 0)
     {
      info.status = "N/A";
      info.emoji = "❓";
      info.percent = 0.0;
      return info;
     }

   if(c > o)
     {
      info.status = "Up";
      info.emoji = "🟢";
      // Đối với today (shift=0), dùng global percent, ngược lại thì tính toán
      info.percent = (shift == 0) ? g_daily_percent : ((h != l) ? ((c - l) / (h - l)) * 100.0 : 100.0);
     }
   else
      if(c < o)
        {
         info.status = "Down";
         info.emoji = "🔴";
         info.percent = (shift == 0) ? g_daily_percent : ((h != l) ? ((h - c) / (h - l)) * 100.0 : 100.0);
        }
      else
        {
         info.status = "Flat";
         info.emoji = "⚪";
         info.percent = 50.0;
        }
   return info;
  }

//--- Định dạng thông tin trạng thái CISD
string FormatCISDContext(string tf_label, int signal_type, double price)
  {
   string state, emoji;
   if(signal_type == 1)
     {
      state = "Bullish";
      emoji = "🟢";
     }
   else
      if(signal_type == -1)
        {
         state = "Bearish";
         emoji = "🔴";
        }
      else
        {
         state = "Neutral";
         emoji = "⚪";
        }
   return StringFormat("%s CISD: %s %s %s", tf_label, DoubleToString(price, _Digits), emoji, state);
  }

//--- Thêm checklist cho Market Diagnosis (H1, H4)
void AppendMarketDiagnosisChecklist(string &message, int direction)
  {
// H1 Checklist
   CArrayString *h1_ideals = new CArrayString();
   if(direction == 1)
     {
      h1_ideals.Add(T.has_trend_up);
      h1_ideals.Add(T.strong_trend_up);
      h1_ideals.Add(T.fomo_up);
     }
   else
     {
      h1_ideals.Add(T.has_trend_down);
      h1_ideals.Add(T.strong_trend_down);
      h1_ideals.Add(T.fomo_down);
     }
   AppendChecklistItem(message, "H1", g_short_term.market_diagnosis_text, g_short_term.market_diagnosis_text, h1_ideals);
   delete h1_ideals;

// H4 Checklist
   CArrayString *h4_ideals = new CArrayString();
   if(direction == 1)
     {
      h4_ideals.Add(T.has_trend_up);
      h4_ideals.Add(T.strong_trend_up);
     }
   else
     {
      h4_ideals.Add(T.has_trend_down);
      h4_ideals.Add(T.strong_trend_down);
     }
// Trong hàm FormatLTFConfirmationMessage có thêm T.sideways, ta có thể thêm điều kiện để xử lý
// Tuy nhiên để đơn giản, ta tạm giữ logic chung nhất
   AppendChecklistItem(message, "H4", g_long_term.market_diagnosis_text, g_long_term.market_diagnosis_text, h4_ideals);
   delete h4_ideals;
  }

//--- Thêm checklist cho Price và EMA
void AppendPriceEMAChecklist(string &message, int direction)
  {
   CArrayString *ideal_states = new CArrayString();
   if(direction == 1)
     {
      ideal_states.Add(T.level_p1);
      ideal_states.Add(T.level_p2);
      ideal_states.Add(T.level_p3);
     }
   else
     {
      ideal_states.Add(T.level_n1);
      ideal_states.Add(T.level_n2);
      ideal_states.Add(T.level_n3);
     }

// Price
   string price_raw_state = g_short_term.close_status_text;
   string price_display_state = StringFormat("%s (%.2f%%)", price_raw_state, g_short_term.close_slope * 100);
   AppendChecklistItem(message, "Price", price_raw_state, price_display_state, ideal_states);

// EMA
   string ema_raw_state = g_short_term.ema_status_text;
   string ema_display_state = StringFormat("%s (%.2f%%)", ema_raw_state, g_short_term.ema_slope * 100);
   AppendChecklistItem(message, "EMA", ema_raw_state, ema_display_state, ideal_states);

   delete ideal_states;
  }

//--- Định dạng thông tin giao dịch (Entry, SL, TP)
string FormatTradeInfo(int direction, double entry_price, double stoploss, double rr_ratio)
  {
   string info = "-----------------------------------\nBACKTEST / OPTIMIZATION INFO:\n";
   long spread_points = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread_points == 0)
      spread_points = long((SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / g_point_value);
   double tp = 0;
   double buffer_in_price = InpStopLossBufferPips * g_point_per_pips * g_point_value;
   if(direction == 1)
     {
      tp = entry_price + (entry_price - stoploss) * rr_ratio;
      stoploss = stoploss - buffer_in_price;
     }
   else
      if(direction == -1)
        {
         stoploss = stoploss + spread_points * g_point_value + buffer_in_price;
         tp = entry_price - (stoploss - entry_price) * rr_ratio;
        }
   info += direction == 1 ? "BUY STOP" : "SELL STOP";
   info += StringFormat(": %s\n", DoubleToString(entry_price, _Digits));
   info += StringFormat("SL:    %s\n", DoubleToString(stoploss, _Digits));
   info += StringFormat("TP (RR %s): %s\n", DoubleToString(rr_ratio, 1), DoubleToString(tp, _Digits));
   return info;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string FormatTradeBreakoutInfo(int direction, double entry_price, double stoploss, double rr_ratio)
  {
   string info = "-----------------------------------\nBACKTEST / OPTIMIZATION INFO:\n";
   double tp = (direction == 1) ? entry_price + (entry_price - stoploss) * rr_ratio : entry_price - (stoploss - entry_price) * rr_ratio;
   info += StringFormat("Entry: %s\n", DoubleToString(entry_price, _Digits));
   info += StringFormat("SL:    %s\n", DoubleToString(stoploss, _Digits));
   info += StringFormat("TP (RR %s): %s\n", DoubleToString(rr_ratio, 1), DoubleToString(tp, _Digits));
   return info;
  }
//+------------------------------------------------------------------+
//| Hàm format message cho Breakout                                  |
//+------------------------------------------------------------------+
string FormatBreakoutMessage(string timeframe_label, int direction, double price, datetime breakout_time, double stoploss, double entry)
  {
// --- Phần thông tin cơ bản ---
   string direction_icon = (direction == 1) ? "▲" : "▼";
   string formatted_price = DoubleToString(price, _Digits);
   datetime adjusted_time = breakout_time + (InpTimeOffsetHours * 3600);
   string execution_time = TimeToString(adjusted_time, TIME_MINUTES);

   string message = StringFormat("🔥 BREAKOUT: %s %s %s %s (%s)\n", _Symbol, timeframe_label, direction_icon, formatted_price, execution_time);

// --- Ngữ cảnh ngày ---
   message += "-----------------------------------\nDAILY CONTEXT\n";
   DailyBarInfo today_info = GetDailyBarContext(0);
   message += StringFormat("Today: %s %s (%.2f%%)\n", today_info.emoji, today_info.status, today_info.percent);
   DailyBarInfo yesterday_info = GetDailyBarContext(1);
   message += StringFormat("Yesterday: %s %s (%.2f%%)\n", yesterday_info.emoji, yesterday_info.status, yesterday_info.percent);

// --- Ngữ cảnh tín hiệu ---
   message += "-----------------------------------\nSIGNAL CONTEXT\n";
   message += FormatCISDContext("H1", g_h1_signalType, g_h1_breakoutPrice) + "\n";
   if(g_st_ranges[RANGE_PRICE].isActive)
      message += StringFormat(" > H1 Range: %s - %s\n",
                              DoubleToString(g_st_ranges[RANGE_PRICE].low, _Digits),
                              DoubleToString(g_st_ranges[RANGE_PRICE].high, _Digits));

// --- Checklist ---
   message += "\nSetup Checklist:\n";
   AppendMarketDiagnosisChecklist(message, direction);
   AppendPriceEMAChecklist(message, direction);

// --- Thông tin trade ---
   message += FormatTradeBreakoutInfo(direction, entry, stoploss, InpRRRatio);

   return message;
  }

//+------------------------------------------------------------------+
//| Hàm format message cho LTF Confirmation                          |
//+------------------------------------------------------------------+
string FormatLTFConfirmationMessage(const SignalAnalysis &info)
  {
   if(info.signal == 0)
      return "";

// --- Phần thông tin cơ bản ---
   string signal_icon = (info.signal == 1) ? "🔵" : "🟠";
   datetime adjusted_time = info.signal_time + (InpTimeOffsetHours * 3600);
   string execution_time = TimeToString(adjusted_time, TIME_MINUTES);
   string ltf_timeframe_name = StringSubstr(EnumToString(_Period), 7);

   string message = StringFormat("%s SIGNAL ALERT: %s %s @ %s\n", signal_icon, _Symbol, info.signal_type, execution_time);

// --- Ngữ cảnh ngày (có thêm chi tiết) ---
   message += "-----------------------------------\nDAILY CONTEXT\n";
   DailyBarInfo today_info = GetDailyBarContext(0);
   message += StringFormat("Today: %s %s (%.2f%%)\n", today_info.emoji, today_info.status, today_info.percent);

   double DOpen = iOpen(_Symbol, PERIOD_D1, 0);
   double price_diff_points = (info.ltf_cisd_price - DOpen) / _Point;
   string open_diff_str = "";
   if(price_diff_points > 0.1)
      open_diff_str = StringFormat("(+%s points)", DoubleToString(price_diff_points, 1));
   else
      if(price_diff_points < -0.1)
         open_diff_str = StringFormat("(%s points)", DoubleToString(price_diff_points, 1));
   message += StringFormat("└ Open: %s %s\n", DoubleToString(DOpen, _Digits), open_diff_str);

   DailyBarInfo yesterday_info = GetDailyBarContext(1);
   message += StringFormat("Yesterday: %s %s (%.2f%%)\n", yesterday_info.emoji, yesterday_info.status, yesterday_info.percent);

// --- Ngữ cảnh tín hiệu (có thêm chi tiết) ---
   message += "-----------------------------------\nSIGNAL CONTEXT\n";
   if(info.is_h1_range_breakout)
      message += "💥 H1 Range Breakout!\n";
   message += FormatCISDContext("H1", g_h1_signalType, g_h1_breakoutPrice) + "\n";
   message += StringFormat("%s CISD: %s\n", ltf_timeframe_name, DoubleToString(info.ltf_cisd_price, _Digits));

// Các phần hiển thị range đặc thù cho hàm này
   if(g_short_term.market_diagnosis_text == T.sideways && g_st_ranges[RANGE_DIAGNOSIS].isActive)
      message += StringFormat(" > H1 Range: %s - %s\n", DoubleToString(g_st_ranges[RANGE_DIAGNOSIS].low, _Digits), DoubleToString(g_st_ranges[RANGE_DIAGNOSIS].high, _Digits));
   if(g_short_term.close_state == 0 && g_st_ranges[RANGE_PRICE].isActive)
      message += StringFormat(" > H1 Range: %s - %s\n", DoubleToString(g_st_ranges[RANGE_PRICE].low, _Digits), DoubleToString(g_st_ranges[RANGE_PRICE].high, _Digits));
   if(g_short_term.ema_state == 0 && g_st_ranges[RANGE_EMA].isActive)
      message += StringFormat(" > H1 Range: %s - %s\n", DoubleToString(g_st_ranges[RANGE_EMA].low, _Digits), DoubleToString(g_st_ranges[RANGE_EMA].high, _Digits));

   message += "-----------------------------------\nStochastic:\n";
   message += StringFormat("D2 : K=%.2f, D=%.2f\n", k_d2, d_d2);
   message += StringFormat("D1 : K=%.2f, D=%.2f\n", k_d1, d_d1);
   message += StringFormat("H4 : K=%.2f, D=%.2f\n", k_h4, d_h4);
   message += StringFormat("H1 : K=%.2f, D=%.2f\n", k_h1, d_h1);

// --- Checklist ---
   message += "\nSetup Checklist:\n";
   AppendMarketDiagnosisChecklist(message, info.signal); // Dùng info.signal thay cho direction
   AppendPriceEMAChecklist(message, info.signal);

// --- CISD Conditions (phần riêng của hàm này) ---
   message += "CISD Conditions:\n";
   string icon;
   bool isDUp = (iClose(_Symbol, PERIOD_D1, 0) > DOpen);
   bool isDDown = (iClose(_Symbol, PERIOD_D1, 0) < DOpen);
   string dailyBodyStatus = isDUp ? "Up" : (isDDown ? "Down" : "Flat");

   icon = info.is_daily_body_aligned ? "✅" : "❌";
   message += StringFormat(" %s Daily: %s\n", icon, dailyBodyStatus);
   icon = info.is_h1_cisd_aligned ? "✅" : "❌";
   message += StringFormat(" %s H1 CISD %s D.Open\n", icon, (info.signal == 1 ? ">" : "<"));
   icon = (info.signal == 1 ? g_m30_signalType == 1 : g_m30_signalType == -1) ? "✅" : "❌";
   message += StringFormat(" %s M30 CISD %s D.Open\n", icon, (info.signal == 1 ? ">" : "<"));
   icon = info.is_ltf_cisd_aligned ? "✅" : "❌";
   message += StringFormat(" %s %s CISD %s D.Open\n", icon, ltf_timeframe_name, (info.signal == 1 ? ">" : "<"));

// --- Thông tin trade ---
   message += FormatTradeInfo(info.signal, info.breakout_level, info.stoploss_level, InpRRRatio);

   return message;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void AppendChecklistItem(string &message, const string &label, const string &raw_state, const string &display_state, const CArrayString *ideal_states)
  {
// So sánh chuỗi trạng thái gốc (raw_state) với mảng
   string icon = IsStateInArray(raw_state, ideal_states) ? "✅" : "❌";

// Hiển thị chuỗi đã được định dạng (display_state)
   message += StringFormat(" %s %s: %s\n", icon, label, display_state);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
string FormatAccountDashboardMessage()
  {
// Luôn làm mới dữ liệu trước khi lấy thông tin
// RefreshRates();

   string message = "";

// Lấy thông tin tài khoản
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double profit = AccountInfoDouble(ACCOUNT_PROFIT);
   string accountCurrency = AccountInfoString(ACCOUNT_CURRENCY);
   string serverName = AccountInfoString(ACCOUNT_SERVER);
   string accountName = AccountInfoString(ACCOUNT_NAME);
   long accountNumber = AccountInfoInteger(ACCOUNT_LOGIN);

// Đếm vị thế và tổng hợp lợi nhuận theo từng symbol
   int totalPositions = PositionsTotal();

// --- Mảng để lưu trữ thông tin tổng hợp theo từng symbol ---
   string openSymbols[];
   double symbolProfits[];
   int symbolPositionTypes[]; // BỔ SUNG: Mảng để lưu loại lệnh (BUY/SELL)
// ------------------------------------------------------------------

   for(int i = totalPositions - 1; i >= 0; i--)
     {
      // Chọn vị thế để lấy thông tin
      if(PositionGetTicket(i))
        {
         string positionSymbol = PositionGetString(POSITION_SYMBOL);
         double positionProfit = PositionGetDouble(POSITION_PROFIT);
         int positionType = (int)PositionGetInteger(POSITION_TYPE); // BỔ SUNG: Lấy loại lệnh

         bool symbolFound = false;
         int symbolIndex = -1;

         // Tìm xem symbol này đã có trong danh sách chưa
         for(int j = 0; j < ArraySize(openSymbols); j++)
           {
            if(openSymbols[j] == positionSymbol)
              {
               symbolFound = true;
               symbolIndex = j;
               break;
              }
           }

         if(symbolFound)
           {
            // Nếu đã có, cộng dồn lợi nhuận (logic này vẫn hữu ích nếu bạn thay đổi chiến lược)
            symbolProfits[symbolIndex] += positionProfit;
           }
         else
           {
            // Nếu chưa có, thêm symbol mới và thông tin của nó vào các mảng
            int newSize = ArraySize(openSymbols) + 1;
            ArrayResize(openSymbols, newSize);
            ArrayResize(symbolProfits, newSize);
            ArrayResize(symbolPositionTypes, newSize); // BỔ SUNG: Resize mảng loại lệnh

            openSymbols[newSize - 1] = positionSymbol;
            symbolProfits[newSize - 1] = positionProfit;
            symbolPositionTypes[newSize - 1] = positionType; // BỔ SUNG: Lưu loại lệnh
           }
        }
     }

// --- Tạo chuỗi chi tiết lợi nhuận theo symbol ---
   string positionsDetail = "";
   if(totalPositions > 0)
     {
      positionsDetail += "------------------------------------\n" +
                         "🔎 Positions by Symbol:\n";
      for(int i = 0; i < ArraySize(openSymbols); i++)
        {
         string profitStr = DoubleToString(symbolProfits[i], 2);
         string emoji = (symbolProfits[i] >= 0) ? "🟢" : "🔴";

         // SỬA ĐỔI: Chuyển đổi loại lệnh từ int sang chuỗi "BUY" hoặc "SELL"
         string typeStr = (symbolPositionTypes[i] == POSITION_TYPE_BUY) ? "BUY" : "SELL";

         // SỬA ĐỔI: Thêm "(typeStr)" vào chuỗi định dạng
         positionsDetail += StringFormat("%s %s (%s): %s %s\n",
                                         emoji,
                                         openSymbols[i],
                                         typeStr, // Thêm vào đây
                                         profitStr,
                                         accountCurrency);
        }
     }
// ----------------------------------------------------------------

// Format a message (kết hợp tất cả thông tin lại)
   message = StringFormat("📊 Account Dashboard (%s - %s)\n", serverName, accountName) +
             "------------------------------------\n" +
             StringFormat("🆔 Account: %d\n", accountNumber) +
             StringFormat("💰 Equity: %s %s\n", DoubleToString(equity, 2), accountCurrency) +
             StringFormat("📈 Total P/L: %s %s\n", DoubleToString(profit, 2), accountCurrency) +
             positionsDetail; // Thêm chuỗi chi tiết vào cuối tin nhắn

   return message;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
bool IsStateInArray(const string &state_to_find, const CArrayString *array)
  {
   if(CheckPointer(array) == POINTER_INVALID)
      return false;
   for(int i = 0; i < array.Total(); i++)
     {
      if(array.At(i) == state_to_find)
        {
         return true;
        }
     }
   return false;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void InitializeTranslations(ENUM_LANGUAGE lang)
  {
   if(lang == VIETNAMESE)
     {
      T.short_term = "H1: ";
      T.long_term = "H4: ";
      T.close = "Price:";
      T.ema = "EMA";
      T.market = "THỊ TRƯỜNG: ";
      T.fomo_up = "FOMO TĂNG! (Cẩn trọng)";
      T.fomo_down = "FOMO GIẢM! (Cẩn trọng)";
      T.breakout_up = "BỨT PHÁ TĂNG";
      T.breakout_down = "BỨT PHÁ GIẢM";
      T.strong_trend_up = "Xu hướng tăng mạnh";
      T.strong_trend_down = "Xu hướng giảm mạnh";
      T.has_trend_up = "Xu hướng tăng";
      T.has_trend_down = "Xu hướng giảm";
      T.sideways = "Sideway / Giằng co";
      T.level_p3 = "Tăng mạnh";
      T.level_p2 = "Xác nhận tăng";
      T.level_p1 = "Bắt đầu tăng";
      T.level_0 = "Đi ngang";
      T.level_n1 = "Bắt đầu giảm";
      T.level_n2 = "Xác nhận giảm";
      T.level_n3 = "Giảm mạnh";
     }
   else
     {
      T.short_term = "H1: ";
      T.long_term = "H4: ";
      T.close = "Price:";
      T.ema = "EMA";
      T.market = "MARKET: ";
      T.fomo_up = "FOMO UP! (Caution)";
      T.fomo_down = "FOMO DOWN! (Caution)";
      T.breakout_up = "BREAKOUT UP";
      T.breakout_down = "BREAKOUT DOWN";
      T.strong_trend_up = "Strong Trend - Up";
      T.strong_trend_down = "Strong Trend - Down";
      T.has_trend_up = "Has Trend - Up";
      T.has_trend_down = "Has Trend - Down";
      T.sideways = "Sideways / Chop";
      T.level_p3 = "Accelerating Up";
      T.level_p2 = "Established Up";
      T.level_p1 = "Initiating Up";
      T.level_0 = "Neutral";
      T.level_n1 = "Initiating Down";
      T.level_n2 = "Established Down";
      T.level_n3 = "Accelerating Down";
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double GetHighestPrice(string symbol, ENUM_TIMEFRAMES timeframe, int period, int start_shift)
  {
   double high_buffer[];
   ArraySetAsSeries(high_buffer, true);
   if(CopyHigh(symbol, timeframe, start_shift, period, high_buffer) <= 0)
     {
      Print("Error: Could not copy High data for ", symbol, " on ", EnumToString(timeframe));
      return 0.0;
     }
   return high_buffer[ArrayMaximum(high_buffer)];
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
double GetLowestPrice(string symbol, ENUM_TIMEFRAMES timeframe, int period, int start_shift)
  {
   double low_buffer[];
   ArraySetAsSeries(low_buffer, true);
   if(CopyLow(symbol, timeframe, start_shift, period, low_buffer) <= 0)
     {
      Print("Error: Could not copy Low data for ", symbol, " on ", EnumToString(timeframe));
      return 0.0;
     }
   return low_buffer[ArrayMinimum(low_buffer)];
  }

// Struct đơn giản để lưu giá và vị trí, không cần lớp phức tạp
struct PricePoint
  {
   double            price;
   int               shift;
  };

//+------------------------------------------------------------------+
//| GetHighestPivotPrice - sửa: boundary đúng, xử lý plateau, fallback |
//+------------------------------------------------------------------+
double GetHighestPivotPrice(string symbol, ENUM_TIMEFRAMES timeframe, int count, int start_pos)
  {
   int end_pos = start_pos + count - 1;
// cần ít nhất 3 cây để có "within" (bỏ biên)
   if(count <= 2 || Bars(symbol, timeframe) <= end_pos)
      return 0;

   double highest = -DBL_MAX;

// Duyệt qua các nến trong vùng, bao gồm cả end_pos-1
   for(int shift = start_pos + 1; shift <= end_pos - 1; shift++)
     {
      double high = iHigh(symbol, timeframe, shift);
      double left = iHigh(symbol, timeframe, shift - 1);  // nến trước (trái)
      double right = iHigh(symbol, timeframe, shift + 1); // nến sau (phải)

      // chấp nhận plateau: >= thay vì >
      if(high >= left && high >= right)
        {
         // mở rộng plateau để xác định plateau edge
         int leftEdge = shift;
         int rightEdge = shift;
         // mở rộng về trái
         while(leftEdge - 1 >= start_pos + 1 && iHigh(symbol, timeframe, leftEdge - 1) == high)
            leftEdge--;
         // mở rộng về phải
         while(rightEdge + 1 <= end_pos - 1 && iHigh(symbol, timeframe, rightEdge + 1) == high)
            rightEdge++;

         // giá ngoài plateau
         double outsideLeft = (leftEdge - 1 >= start_pos) ? iHigh(symbol, timeframe, leftEdge - 1) : -DBL_MAX;
         double outsideRight = (rightEdge + 1 <= end_pos) ? iHigh(symbol, timeframe, rightEdge + 1) : -DBL_MAX;

         // plateau hợp lệ nếu hai bên ngoài thấp hơn plateau
         if(outsideLeft < high && outsideRight < high)
           {
            if(high > highest)
               highest = high;
           }
        }
     }

// Nếu không tìm được pivot hợp lệ -> fallback = highest bên trong vùng (không tính biên)
   if(highest == -DBL_MAX)
     {
      double maxInside = -DBL_MAX;
      for(int s = start_pos + 1; s <= end_pos - 1; s++)
        {
         double h = iHigh(symbol, timeframe, s);
         if(h > maxInside)
            maxInside = h;
        }
      if(maxInside != -DBL_MAX)
         highest = maxInside;
      else
        {
         // cực kỳ hiếm: fallback cuối cùng dùng iHighest (có thể trả về biên)
         int idx = iHighest(symbol, timeframe, MODE_HIGH, count, start_pos);
         highest = iHigh(symbol, timeframe, idx);
        }
     }

   return highest;
  }

//+------------------------------------------------------------------+
//| GetLowestPivotPrice - sửa tương ứng cho low                      |
//+------------------------------------------------------------------+
double GetLowestPivotPrice(string symbol, ENUM_TIMEFRAMES timeframe, int count, int start_pos)
  {
   int end_pos = start_pos + count - 1;
   if(count <= 2 || Bars(symbol, timeframe) <= end_pos)
      return 0;

   double lowest = DBL_MAX;

   for(int shift = start_pos + 1; shift <= end_pos - 1; shift++)
     {
      double low = iLow(symbol, timeframe, shift);
      double left = iLow(symbol, timeframe, shift - 1);  // nến trước (trái)
      double right = iLow(symbol, timeframe, shift + 1); // nến sau (phải)

      // chấp nhận plateau
      if(low <= left && low <= right)
        {
         int leftEdge = shift;
         int rightEdge = shift;
         while(leftEdge - 1 >= start_pos + 1 && iLow(symbol, timeframe, leftEdge - 1) == low)
            leftEdge--;
         while(rightEdge + 1 <= end_pos - 1 && iLow(symbol, timeframe, rightEdge + 1) == low)
            rightEdge++;

         double outsideLeft = (leftEdge - 1 >= start_pos) ? iLow(symbol, timeframe, leftEdge - 1) : DBL_MAX;
         double outsideRight = (rightEdge + 1 <= end_pos) ? iLow(symbol, timeframe, rightEdge + 1) : DBL_MAX;

         if(outsideLeft > low && outsideRight > low)
           {
            if(low < lowest)
               lowest = low;
           }
        }
     }

   if(lowest == DBL_MAX)
     {
      double minInside = DBL_MAX;
      for(int s = start_pos + 1; s <= end_pos - 1; s++)
        {
         double l = iLow(symbol, timeframe, s);
         if(l < minInside)
            minInside = l;
        }
      if(minInside != DBL_MAX)
         lowest = minInside;
      else
        {
         int idx = iLowest(symbol, timeframe, MODE_LOW, count, start_pos);
         lowest = iLow(symbol, timeframe, idx);
        }
     }

   return lowest;
  }

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void GetCustomDailyInfo(CustomCandleInfo &candle)
  {
   datetime startTime;
   double startPrice;
   if(InpDOpenOffsetHours == 0)
     {
      startTime = iTime(_Symbol, PERIOD_D1, 0);
      startPrice = iClose(_Symbol, PERIOD_D1, 1);
     }
   else
     {
      datetime targetTime = iTime(_Symbol, PERIOD_D1, 0) - (InpDOpenOffsetHours * 3600);
      int h1_shift = iBarShift(_Symbol, PERIOD_H1, targetTime, false);
      if(h1_shift < 0)
        {
         Print("DOpen Error: Not enough H1 data.");
         startTime = iTime(_Symbol, PERIOD_D1, 0);
         startPrice = iOpen(_Symbol, PERIOD_D1, 0);
        }
      else
        {
         startTime = iTime(_Symbol, PERIOD_H1, h1_shift);
         startPrice = iClose(_Symbol, PERIOD_H1, h1_shift);
        }
     }
   datetime endTime;
   double endPrice;
   if(InpDCloseOffsetHours == 0)
     {
      endTime = iTime(_Symbol, PERIOD_D1, -1) - 1;
      endPrice = iClose(_Symbol, _Period, 1);
     }
   else
     {
      datetime targetTime = (iTime(_Symbol, PERIOD_D1, -1) - 1) - (InpDCloseOffsetHours * 3600);
      int h1_shift = iBarShift(_Symbol, PERIOD_H1, targetTime, false);
      if(h1_shift < 0)
        {
         Print("DClose Error: Not enough H1 data.");
         endTime = iTime(_Symbol, PERIOD_D1, -1) - 1;
         endPrice = iClose(_Symbol, _Period, 1);
        }
      else
        {
         endTime = iTime(_Symbol, PERIOD_H1, h1_shift);
         endPrice = iClose(_Symbol, PERIOD_H1, h1_shift);
        }
     }
   endTime = MathMin(endTime, TimeCurrent());
   double highestHigh = 0;
   double lowestLow = DBL_MAX;
   int start_shift = iBarShift(_Symbol, PERIOD_H1, startTime, true);
   int end_shift = iBarShift(_Symbol, PERIOD_H1, endTime, true);
   if(start_shift >= 0 && end_shift >= 0)
     {
      int num_bars = start_shift - end_shift + 1;
      double h1_highs[], h1_lows[];
      if(CopyHigh(_Symbol, PERIOD_H1, end_shift, num_bars, h1_highs) > 0 && CopyLow(_Symbol, PERIOD_H1, end_shift, num_bars, h1_lows) > 0)
        {
         highestHigh = h1_highs[ArrayMaximum(h1_highs)];
         lowestLow = h1_lows[ArrayMinimum(h1_lows)];
        }
     }
   if(highestHigh == 0)
      highestHigh = MathMax(startPrice, endPrice);
   if(lowestLow == DBL_MAX)
      lowestLow = MathMin(startPrice, endPrice);
   candle.openTime = startTime;
   candle.open = startPrice;
   candle.high = highestHigh;
   candle.low = lowestLow;
   candle.close = endPrice;
  }

//+------------------------------------------------------------------+
//| Phân tích cấu trúc nến, phiên bản TỰ ĐỘNG HIỆU CHỈNH, an toàn và chính xác.|
//+------------------------------------------------------------------+
CandleAnalysisResult AnalyzeCandleStructure(ENUM_TIMEFRAMES primary_tf, ENUM_TIMEFRAMES secondary_tf, int primary_shift)
  {
   CandleAnalysisResult result;
   result.path = PATH_UNKNOWN;
   result.description = "N/A";

// --- Bước 1: Lấy dữ liệu nến LỚN dựa trên shift ---
   MqlRates primary_rates[];
   if(CopyRates(_Symbol, primary_tf, primary_shift, 1, primary_rates) < 1)
     {
      result.description = "Error: Cannot copy " + EnumToString(primary_tf) + " data at shift " + (string)primary_shift;
      return result;
     }

   double primaryOpen = primary_rates[0].open;
   double primaryHigh = primary_rates[0].high;
   double primaryLow = primary_rates[0].low;
   double primaryClose = primary_rates[0].close;
   datetime primaryStartTime = primary_rates[0].time;
   datetime primaryEndTime = primaryStartTime + PeriodSeconds(primary_tf) - 1;
   primaryEndTime = MathMin(primaryEndTime, TimeCurrent());

// --- Bước 2: Xác định đường đi của giá ---
   datetime time_of_high = 0, time_of_low = 0;
   int shift_end = iBarShift(_Symbol, secondary_tf, primaryStartTime, false);
   int shift_start = iBarShift(_Symbol, secondary_tf, primaryEndTime, false);

   if(shift_end < 0 || shift_start < 0)
     {
      result.description = "Error: Not enough " + EnumToString(secondary_tf) + " data.";
      return result;
     }

   for(int i = shift_end; i >= shift_start; i--)
     {
      if(iHigh(_Symbol, secondary_tf, i) >= primaryHigh && time_of_high == 0)
         time_of_high = iTime(_Symbol, secondary_tf, i);
      if(iLow(_Symbol, secondary_tf, i) <= primaryLow && time_of_low == 0)
         time_of_low = iTime(_Symbol, secondary_tf, i);
      if(time_of_high != 0 && time_of_low != 0)
         break;
     }

   if(time_of_high == 0 || time_of_low == 0)
     {
      result.description = "Analyzing...";
      return result;
     }

   if(time_of_high > time_of_low)
      result.path = PATH_OLHC;
   else
      if(time_of_low > time_of_high)
         result.path = PATH_OHLC;

// --- Bước 3: Xác định loại thân nến ---
   double body_size = MathAbs(primaryOpen - primaryClose);
   double total_range = primaryHigh - primaryLow;
   if(total_range > 0 && (body_size / total_range) < 0.1)
      result.body = BODY_DOJI;
   else
      if(primaryClose > primaryOpen)
         result.body = BODY_BULLISH;
      else
         result.body = BODY_BEARISH;

// --- Bước 4: Kết hợp và phân loại chi tiết ---
   string tf_name = StringSubstr(EnumToString(primary_tf), 7);
   const double shadow_threshold = 0.15; // Ngưỡng 15% để xác định nến Marubozu

   switch(result.path)
     {
      case PATH_OHLC: // Đỉnh được tạo trước
         if(result.body == BODY_BULLISH)
            result.description = StringFormat("%s Đảo chiều giảm thất bại (OHLC - Bullish)", tf_name);
         else
            if(result.body == BODY_BEARISH)
              {
               if(total_range > 0)
                 {
                  double upper_shadow_ratio = (primaryHigh - primaryOpen) / total_range;
                  double lower_shadow_ratio = (primaryClose - primaryLow) / total_range;
                  if(upper_shadow_ratio < shadow_threshold && lower_shadow_ratio < shadow_threshold)
                     result.description = StringFormat("%s Xu hướng giảm mạnh (OHLC - Marubozu-like)", tf_name);
                  else
                     result.description = StringFormat("%s Đảo chiều giảm điển hình (OHLC - Reversal)", tf_name);
                 }
               else
                  result.description = StringFormat("%s Đảo chiều giảm điển hình (OHLC - Reversal)", tf_name);
              }
            else // BODY_DOJI
               result.description = StringFormat("%s Thiếu quyết đoán sau khi giảm (OHLC - Doji)", tf_name);
         break;

      case PATH_OLHC: // Đáy được tạo trước
         if(result.body == BODY_BULLISH)
           {
            if(total_range > 0)
              {
               double lower_shadow_ratio = (primaryOpen - primaryLow) / total_range;
               double upper_shadow_ratio = (primaryHigh - primaryClose) / total_range;
               if(lower_shadow_ratio < shadow_threshold && upper_shadow_ratio < shadow_threshold)
                  result.description = StringFormat("%s Xu hướng tăng mạnh (OLHC - Marubozu-like)", tf_name);
               else
                  result.description = StringFormat("%s Đảo chiều tăng điển hình (OLHC - Reversal)", tf_name);
              }
            else
               result.description = StringFormat("%s Đảo chiều tăng điển hình (OLHC - Reversal)", tf_name);
           }
         else
            if(result.body == BODY_BEARISH)
               result.description = StringFormat("%s Đảo chiều tăng thất bại (OLHC - Bearish)", tf_name);
            else // BODY_DOJI
               result.description = StringFormat("%s Thiếu quyết đoán sau khi tăng (OLHC - Doji)", tf_name);
         break;

      default: // PATH_UNKNOWN
         if(result.body == BODY_BULLISH)
            result.description = StringFormat("%s Xu hướng tăng không rõ ràng", tf_name);
         else
            if(result.body == BODY_BEARISH)
               result.description = StringFormat("%s Xu hướng giảm không rõ ràng", tf_name);
            else
               result.description = StringFormat("%s Đi ngang không rõ ràng", tf_name);
         break;
     }

   return result;
  }
/*
CandleAnalysisResult AnalyzeCandleStructure(ENUM_TIMEFRAMES primary_tf, ENUM_TIMEFRAMES secondary_tf, int primary_shift)
  {
   CandleAnalysisResult result;
   result.path = PATH_UNKNOWN;
   result.body = BODY_UNKNOWN;
   result.description = "N/A";

// --- Bước 1: Lấy dữ liệu và xác định khoảng thời gian của nến LỚN ---
   MqlRates primary_rates[];
   if(CopyRates(_Symbol, primary_tf, primary_shift, 1, primary_rates) < 1)
     {
      result.description = "Error: Cannot copy " + EnumToString(primary_tf) + " data.";
      return result;
     }

   datetime primaryStartTime = primary_rates[0].time;
   datetime primaryEndTime = (primary_shift == 0) ? TimeCurrent() : primaryStartTime + PeriodSeconds(primary_tf);

   double primaryOpen = primary_rates[0].open;
   double primaryHigh = primary_rates[0].high;
   double primaryLow = primary_rates[0].low;
   double primaryClose = primary_rates[0].close;
   double total_range = primaryHigh - primaryLow;

// --- Bước 2: Tìm kiếm và TỰ ĐỘNG HIỆU CHỈNH phạm vi nến NHỎ ---
   int shift_end = iBarShift(_Symbol, secondary_tf, primaryStartTime, false);
   int shift_start = iBarShift(_Symbol, secondary_tf, primaryEndTime, false);

   if(primary_shift == 0 && shift_start < 0)
      shift_start = 0;

   if(shift_end < 0 || shift_start < 0)
     {
      result.description = "Error: Not enough " + EnumToString(secondary_tf) + " data in range.";
      return result;
     }

// LOGIC HIỆU CHỈNH: Nếu nến tìm thấy (shift_end) nằm TRƯỚC thời gian bắt đầu của nến lớn,
// chúng ta sẽ "tiến tới" (giảm chỉ số) để tìm nến đầu tiên nằm TRONG phạm vi.
   while(shift_end >= shift_start && iTime(_Symbol, secondary_tf, shift_end) < primaryStartTime)
     {
      shift_end--; // Tiến tới nến gần hơn (chỉ số nhỏ hơn)
     }

// Sau khi hiệu chỉnh, nếu shift_end đã vượt qua shift_start, có nghĩa là không có nến nào phù hợp
   if(shift_end < shift_start)
     {
      result.description = "Error: Could not find a matching " + EnumToString(secondary_tf) + " start bar.";
      return result;
     }

// --- Bước 3: Phân tích đường đi của giá ---
   datetime time_of_high = 0, time_of_low = 0;
   for(int i = shift_end; i >= shift_start; i--)
     {
      if(iHigh(_Symbol, secondary_tf, i) >= primaryHigh && time_of_high == 0)
         time_of_high = iTime(_Symbol, secondary_tf, i);
      if(iLow(_Symbol, secondary_tf, i) <= primaryLow && time_of_low == 0)
         time_of_low = iTime(_Symbol, secondary_tf, i);

      if(time_of_high != 0 && time_of_low != 0)
         break;
     }

   if(time_of_high == 0 || time_of_low == 0)
     {
      result.description = "Analyzing...";
      return result;
     }

   if(time_of_high > time_of_low)
      result.path = PATH_OLHC;
   else
      if(time_of_low > time_of_high)
         result.path = PATH_OHLC;

// --- Bước 4: Xác định loại thân nến ---
   double body_size = MathAbs(primaryOpen - primaryClose);
   if(total_range > 0 && (body_size / total_range) < 0.1)
      result.body = BODY_DOJI;
   else
      if(primaryClose > primaryOpen)
         result.body = BODY_BULLISH;
      else
         result.body = BODY_BEARISH;

// --- Bước 5: Kết hợp và tạo mô tả chi tiết ---
   string tf_name = StringSubstr(EnumToString(primary_tf), 7);
   const double shadow_threshold = 0.15;

   switch(result.path)
     {
      case PATH_OHLC: // Đỉnh được tạo trước
         if(result.body == BODY_BULLISH)
            result.description = StringFormat("%s Đảo chiều giảm thất bại", tf_name);
         else
            if(result.body == BODY_BEARISH)
              {
               if(total_range > 0 && (primaryHigh - primaryOpen) / total_range < shadow_threshold && (primaryClose - primaryLow) / total_range < shadow_threshold)
                  result.description = StringFormat("%s Xu hướng giảm mạnh", tf_name);
               else
                  result.description = StringFormat("%s Đảo chiều giảm điển hình", tf_name);
              }
            else
               result.description = StringFormat("%s Thiếu quyết đoán sau khi giảm", tf_name);
         break;

      case PATH_OLHC: // Đáy được tạo trước
         if(result.body == BODY_BULLISH)
           {
            if(total_range > 0 && (primaryOpen - primaryLow) / total_range < shadow_threshold && (primaryHigh - primaryClose) / total_range < shadow_threshold)
               result.description = StringFormat("%s Xu hướng tăng mạnh (OLHC - Marubozu-like)", tf_name);
            else
               result.description = StringFormat("%s Đảo chiều tăng điển hình (OLHC - Reversal)", tf_name);
           }
         else
            if(result.body == BODY_BEARISH)
               result.description = StringFormat("%s Đảo chiều tăng thất bại (OLHC - Bearish)", tf_name);
            else // BODY_DOJI
               result.description = StringFormat("%s Thiếu quyết đoán sau khi tăng (OLHC - Doji)", tf_name);
         break;

      default: // PATH_UNKNOWN
         if(result.body == BODY_BULLISH)
            result.description = StringFormat("%s Xu hướng tăng không rõ ràng", tf_name);
         else
            if(result.body == BODY_BEARISH)
               result.description = StringFormat("%s Xu hướng giảm không rõ ràng", tf_name);
            else
               result.description = StringFormat("%s Đi ngang không rõ ràng", tf_name);
         break;
     }

   return result;
  }
  //*/
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Tính toán và trả về thời gian còn lại cho đến nến mới            |
//| Input: timeframe (ví dụ: PERIOD_M5, PERIOD_H1)                  |
//| Output: Chuỗi văn bản có định dạng "phút:giây" (ví dụ: "145:20") |
//+------------------------------------------------------------------+
string GetTimeRemainingForNewCandle(ENUM_TIMEFRAMES timeframe)
  {
// 1. Lấy tổng số giây của một cây nến trong timeframe được chỉ định
   long period_total_seconds = PeriodSeconds(timeframe);

// Kiểm tra trường hợp timeframe không hợp lệ (ví dụ: timeframe tùy chỉnh)
   if(period_total_seconds <= 0)
     {
      return "N/A"; // Trả về "Not Available" nếu không tính được
     }

// 2. Lấy thời gian hiện tại của server (tính bằng giây)
   long current_server_time = TimeCurrent();

// 3. Tính toán thời điểm mở cửa của cây nến TIẾP THEO
// Đây là một công thức toán học hiệu quả sử dụng phép chia số nguyên
// (current_server_time / period_total_seconds) -> tìm ra chỉ số của nến hiện tại
// (+ 1) -> chuyển sang chỉ số của nến tiếp theo
// (* period_total_seconds) -> chuyển chỉ số trở lại thành thời gian (giây)
   long next_candle_open_time = ((current_server_time / period_total_seconds) + 1) * period_total_seconds;

// 4. Tính toán số giây còn lại
   long remaining_seconds = next_candle_open_time - current_server_time;

// 5. Chuyển đổi tổng số giây còn lại sang định dạng "phút:giây"
   long total_minutes_part = remaining_seconds / 60; // Lấy phần phút
   long seconds_part = remaining_seconds % 60;       // Lấy phần giây còn lại

// 6. Định dạng chuỗi kết quả
// StringFormat("%d:%02d", ...)
// %d -> in ra số phút
// %02d -> in ra số giây, nếu chỉ có 1 chữ số thì thêm số 0 ở đầu (ví dụ: 9 -> "09")
   string result_text = StringFormat("%d:%02d", total_minutes_part, seconds_part);

   return result_text;
  }
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| All other CHOCH and ZigZag helper functions                      |
//+------------------------------------------------------------------+
void CopyZigZagPointsArray(ZigZagPoint &dst[], const ZigZagPoint &src[])
  {
   int src_size = ArraySize(src);
   ArrayResize(dst, src_size);
   for(int i = 0; i < src_size; i++)
     {
      dst[i] = src[i];
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void UpdateChartObjects(const ZigZagPoint &points[], int nPoints)
  {
   int prev_nPoints = ArraySize(prev_points);
   int first_diff_idx = -1;
   int limit = MathMin(nPoints, prev_nPoints);
   for(int i = 0; i < limit; i++)
     {
      if(prev_points[i].time != points[i].time || prev_points[i].price != points[i].price || prev_points[i].isCHOCH != points[i].isCHOCH || prev_points[i].chochBreakoutTime != points[i].chochBreakoutTime)
        {
         first_diff_idx = i;
         break;
        }
     }
   if(first_diff_idx == -1 && nPoints != prev_nPoints)
     {
      first_diff_idx = limit;
     }
   if(first_diff_idx == -1)
      return;
// DeleteObjectsFromIndex(first_diff_idx, prev_nPoints);
   DrawZigZagObjects(points, nPoints, first_diff_idx);
   CopyZigZagPointsArray(prev_points, points);
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void DeleteObjectsFromIndex(int from_index, int total_old_points)
  {
   for(int i = from_index; i < total_old_points; i++)
     {
      string id = IntegerToString(i);
      ObjectDelete(0, "ZZ_Label_" + id);
      ObjectDelete(0, "ZZ_Line_" + id);
     }
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| [OPTIMIZED] Vẽ các đối tượng ZigZag sử dụng hàm helper            |
//+------------------------------------------------------------------+
void DrawZigZagObjects(const ZigZagPoint &points[], const int nPoints, int start_index = 0)
  {
   color clr_HH = clrRed, clr_HL = clrCyan, clr_LH = clrMagenta, clr_LL = clrAntiqueWhite;

   for(int i = start_index; i < nPoints; i++)
     {
      // --- Xác định màu sắc chung cho điểm ZigZag hiện tại ---
      color clr = clrWhite;
      if(points[i].type == "HH")
         clr = clr_HH;
      else
         if(points[i].type == "LH")
            clr = clr_LH;
         else
            if(points[i].type == "HL")
               clr = clr_HL;
            else
               if(points[i].type == "LL")
                  clr = clr_LL;

      // --- 1. Vẽ Nhãn (Labels) ---
      if(ZigZag_Label_Show)
        {
         string lblName = "ZZ_Label_" + IntegerToString(i);
         double label_price;
         ENUM_ANCHOR_POINT anchor_point;

         if(points[i].isHigh)
           {
            label_price = points[i].price + LabelOffsetPips * _Point;
            anchor_point = ANCHOR_LOWER;
           }
         else
           {
            label_price = points[i].price - LabelOffsetPips * _Point;
            anchor_point = ANCHOR_UPPER;
           }

         // Gọi hàm helper để vẽ Text, đặt ở lớp NỔI (foreground)
         CreateOrMoveText(lblName, points[i].time, label_price, clr, 8, points[i].type, anchor_point, false);
        }

      // --- 2. Vẽ Đường nối ZigZag ---
      if(ZigZag_Show && i < nPoints - 1)
        {
         string lineName = "ZZ_Line_" + IntegerToString(i);
         // Gọi hàm helper để vẽ TrendLine, đặt ở lớp NỀN (background)
         CreateOrMoveTrendLine(lineName, points[i].time, points[i].price, points[i + 1].time, points[i + 1].price, clr, 1, STYLE_SOLID, true);
        }

      // --- 3. Vẽ Đường CHOCH ---
      if(ZigZag_CHOCH_Show && points[i].isCHOCH && points[i].chochBreakoutTime > 0)
        {
         string lineName;
         color chColor = (points[i].chochType == "Up") ? clrYellow : clrOrange;

         if(points[i].chochType == "Up")
            lineName = "CHOCH_Line_Up_" + IntegerToString(i);
         else
            lineName = "CHOCH_Line_Down_" + IntegerToString(i);

         // Gọi hàm helper để vẽ TrendLine, đặt ở lớp NỀN (background)
         CreateOrMoveTrendLine(lineName, points[i].time, points[i].price, points[i].chochBreakoutTime, points[i].price, chColor, 1, STYLE_DOT, true);
        }
     }
  }

/*
void DrawZigZagObjects(const ZigZagPoint &points[], const int nPoints, int start_index = 0)
  {
   color clr_HH = clrRed, clr_HL = clrCyan, clr_LH = clrMagenta, clr_LL = clrAntiqueWhite;
   for(int i = start_index; i < nPoints; i++)
     {
      color clr = clrWhite;
      if(points[i].type == "HH")
         clr = clr_HH;
      else
         if(points[i].type == "LH")
            clr = clr_LH;
         else
            if(points[i].type == "HL")
               clr = clr_HL;
            else
               if(points[i].type == "LL")
                  clr = clr_LL;
      if(Show_Labels)
        {
         string lblName = "ZZ_Label_" + IntegerToString(i);
         string label_text = points[i].type;
         double label_price;
         ENUM_ANCHOR_POINT anchor_point;
         if(points[i].isHigh)
           {
            label_price = points[i].price + LabelOffsetPips * _Point;
            anchor_point = ANCHOR_LOWER;
           }
         else
           {
            label_price = points[i].price - LabelOffsetPips * _Point;
            anchor_point = ANCHOR_UPPER;
           }
         if(ObjectFind(0, lblName) < 0)
            ObjectCreate(0, lblName, OBJ_TEXT, 0, points[i].time, label_price);
         ObjectSetString(0, lblName, OBJPROP_TEXT, label_text);
         ObjectSetInteger(0, lblName, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lblName, OBJPROP_ANCHOR, anchor_point);
         ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, lblName, OBJPROP_ZORDER, 0);
        }
      if(i < nPoints - 1)
        {
         string lineName = "ZZ_Line_" + IntegerToString(i);
         if(ObjectFind(0, lineName) < 0)
            ObjectCreate(0, lineName, OBJ_TREND, 0, points[i].time, points[i].price, points[i + 1].time, points[i + 1].price);
         ObjectSetInteger(0, lineName, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, lineName, OBJPROP_ZORDER, 0);
        }
      if(points[i].isCHOCH)
        {
         string lineName;
         color chColor = (points[i].chochType == "Up") ? clrYellow : clrOrange;
         if(points[i].chochType == "Up")
            lineName = "CHOCH_Line_Up_" + IntegerToString(i);
         else
            lineName = "CHOCH_Line_Down_" + IntegerToString(i);
         if(points[i].chochBreakoutTime > 0)
           {
            if(ObjectFind(0, lineName) < 0)
               ObjectCreate(0, lineName, OBJ_TREND, 0, points[i].time, points[i].price, points[i].chochBreakoutTime, points[i].price);
            ObjectSetInteger(0, lineName, OBJPROP_COLOR, chColor);
            ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, lineName, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, lineName, OBJPROP_ZORDER, 0);
           }
        }
     }
  }
 // */
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
int ExtractRawZigZagPoints(ZigZagPoint &points[], const int bars)
  {
   ArrayResize(points, bars);
   int nPoints = 0;
   bool lastIsHigh = false, hasLast = false;
   for(int i = 1; i < bars; i++)
     {
      bool isHigh = (upBuffer[i] != EMPTY_VALUE);
      bool isLow  = (dnBuffer[i] != EMPTY_VALUE);
      datetime barTime = iTime(_Symbol, PERIOD_CURRENT, i);
      if(isHigh && !isLow)
        {
         points[nPoints].index = i;
         points[nPoints].price = upBuffer[i];
         points[nPoints].time = barTime;
         points[nPoints].isHigh = true;
         nPoints++;
         lastIsHigh = true;
         hasLast = true;
        }
      else
         if(!isHigh && isLow)
           {
            points[nPoints].index = i;
            points[nPoints].price = dnBuffer[i];
            points[nPoints].time = barTime;
            points[nPoints].isHigh = false;
            nPoints++;
            lastIsHigh = false;
            hasLast = true;
           }
         else
            if(isHigh && isLow)
              {
               if(!hasLast || lastIsHigh)
                 {
                  points[nPoints].index = i;
                  points[nPoints].price = dnBuffer[i];
                  points[nPoints].time = barTime;
                  points[nPoints].isHigh = false;
                  nPoints++;
                  lastIsHigh = false;
                  hasLast = true;
                  points[nPoints].index = i;
                  points[nPoints].price = upBuffer[i];
                  points[nPoints].time = barTime;
                  points[nPoints].isHigh = true;
                  nPoints++;
                  lastIsHigh = true;
                  hasLast = true;
                 }
               else
                 {
                  points[nPoints].index = i;
                  points[nPoints].price = upBuffer[i];
                  points[nPoints].time = barTime;
                  points[nPoints].isHigh = true;
                  nPoints++;
                  lastIsHigh = true;
                  hasLast = true;
                  points[nPoints].index = i;
                  points[nPoints].price = dnBuffer[i];
                  points[nPoints].time = barTime;
                  points[nPoints].isHigh = false;
                  nPoints++;
                  lastIsHigh = false;
                  hasLast = true;
                 }
              }
     }
   ArrayResize(points, nPoints);
   return nPoints;
  }
//+------------------------------------------------------------------+
//|                                                                  |
//+------------------------------------------------------------------+
void ProcessZigZag(ZigZagPoint &points[], const int nPoints, int start_processing_idx)
  {
   int start_labeling_idx = MathMax(0, start_processing_idx - 4);
   for(int i = start_labeling_idx; i < nPoints; i++)
     {
      if(points[i].isHigh)
        {
         int prevHighIdx = i + 2;
         if(prevHighIdx < nPoints && points[prevHighIdx].isHigh)
            points[i].type = (points[i].price > points[prevHighIdx].price) ? "HH" : "LH";
         else
            points[i].type = "HH";
        }
      else
        {
         int prevLowIdx = i + 2;
         if(prevLowIdx < nPoints && !points[prevLowIdx].isHigh)
            points[i].type = (points[i].price > points[prevLowIdx].price) ? "HL" : "LL";
         else
            points[i].type = "LL";
        }
      points[i].isCHOCH = false;
      points[i].chochConfirmingPointIndex = -1;
      points[i].chochZoneBasePointIndex = -1;
      points[i].chochBreakoutTime = 0;
     }
   int lastHH_idx = -1;
   int lastLL_idx = -1;
   for(int i = nPoints - 1; i >= 0; i--)
     {
      if(points[i].type == "LL")
        {
         if(lastHH_idx != -1)
           {
            if(i >= start_labeling_idx || lastHH_idx >= start_labeling_idx)
              {
               double hh_price_level = points[lastHH_idx].price;
               int start_bar = iBarShift(_Symbol, PERIOD_CURRENT, points[lastHH_idx].time);
               for(int k = start_bar - 1; k >= 0; k--)
                 {
                  if(iHigh(_Symbol, PERIOD_CURRENT, k) > hh_price_level && iClose(_Symbol, PERIOD_CURRENT, k) > iOpen(_Symbol, PERIOD_CURRENT, k))
                    {
                     datetime breakoutTime = iTime(_Symbol, PERIOD_CURRENT, k);
                     points[lastHH_idx].isCHOCH = true;
                     points[lastHH_idx].chochType = "Down";
                     points[lastHH_idx].chochBreakoutTime = breakoutTime;
                     points[lastHH_idx].chochConfirmingPointIndex = i;
                     int zoneBaseIdx = -1;
                     for(int m = 0; m < nPoints; m++)
                       {
                        if(points[m].type == "LL" && points[m].time < breakoutTime)
                          {
                           zoneBaseIdx = m;
                           break;
                          }
                       }
                     points[lastHH_idx].chochZoneBasePointIndex = zoneBaseIdx;
                     break;
                    }
                 }
              }
           }
         lastLL_idx = i;
        }
      else
         if(points[i].type == "HH")
           {
            if(lastLL_idx != -1)
              {
               if(i >= start_labeling_idx || lastLL_idx >= start_labeling_idx)
                 {
                  double ll_price_level = points[lastLL_idx].price;
                  int start_bar = iBarShift(_Symbol, PERIOD_CURRENT, points[lastLL_idx].time);
                  for(int k = start_bar - 1; k >= 0; k--)
                    {
                     if(iLow(_Symbol, PERIOD_CURRENT, k) < ll_price_level && iClose(_Symbol, PERIOD_CURRENT, k) < iOpen(_Symbol, PERIOD_CURRENT, k))
                       {
                        datetime breakoutTime = iTime(_Symbol, PERIOD_CURRENT, k);
                        points[lastLL_idx].isCHOCH = true;
                        points[lastLL_idx].chochType = "Up";
                        points[lastLL_idx].chochBreakoutTime = breakoutTime;
                        points[lastLL_idx].chochConfirmingPointIndex = i;
                        int zoneBaseIdx = -1;
                        for(int m = 0; m < nPoints; m++)
                          {
                           if(points[m].type == "HH" && points[m].time < breakoutTime)
                             {
                              zoneBaseIdx = m;
                              break;
                             }
                          }
                        points[lastLL_idx].chochZoneBasePointIndex = zoneBaseIdx;
                        break;
                       }
                    }
                 }
              }
            lastHH_idx = i;
           }
     }
  }