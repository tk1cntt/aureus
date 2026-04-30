#property link          "https://www.earnforex.com/metatrader-scripts/close-all-orders/"
#property version       "1.03"
#property copyright     "EarnForex.com - 2020-2025"
#property description   "A script to close all positions."
#property description   ""
#property description   "WARNING: There is no guarantee that this script will work as intended. Use at your own risk."
#property description   ""
#property description   "Find more on www.EarnForex.com"
#property icon          "\\Files\\EF-Icon-64x64px.ico"
#property script_show_inputs

#include <Trade/Trade.mqh>
CTrade *Trade;

enum ENUM_ORDER_TYPES
{
    ALL_ORDERS = 1, // ALL POSITIONS
    ONLY_BUY = 2,   // BUY ONLY
    ONLY_SELL = 3   // SELL ONLY
};

enum ENUM_SORT_ORDERS
{
    SORT_ORDERS_NO, // No sorting (the fastest method)
    SORT_ORDERS_ABS_PROFIT_ASC, // Smaller profit/loss first
    SORT_ORDERS_ABS_PROFIT_DESC, // Larger profit/loss first
    SORT_ORDERS_PROFIT_ASC, // From biggest loss to biggest profit
    SORT_ORDERS_PROFIT_DESC // From biggest profit to biggest loss
};

input bool OnlyCurrentSymbol = false; // Close only instrument in the chart
input ENUM_ORDER_TYPES PositionTypeFilter = ALL_ORDERS; // Type of positions to close
input bool OnlyInProfit = false;      // Close only positions in profit
input bool OnlyInLoss = false;        // Close only positions in loss
input bool OnlyMagicNumber = false;   // Close only positions matching the magic number
input int MagicNumber = 0;            // Matching magic number
input bool OnlyWithComment = false;   // Close only positions with the following comment
input string MatchingComment = "";    // Matching comment
input int Slippage = 2;               // Slippage
input int Delay = 0;                  // Delay to wait between closing attempts (in milliseconds)
input int Retries = 10;               // How many times to try closing each position
input ENUM_SORT_ORDERS Sort = SORT_ORDERS_NO; // Sort positions for closing?
input int ClosePercentage = 100;      // Close percentage
input bool AsyncMode = false;         // Close trades are closed in async mode?
input double MinProfitCurrency = 0;   // Minimum profit in currency units
input double MinLossCurrency = 0;     // Minimum loss in currency units
input int MinProfitPoints = 0;        // Minimum profit in points
input int MinLossPoints = 0;          // Minimum loss in points

// Global variables:
double PositionsByProfit[][2]; // To sort positions by floating profit (if necessary).

void OnStart()
{
    Trade = new CTrade;
    Trade.SetAsyncMode(AsyncMode);
    int total = PositionsTotal();
    // Log the total number of positions.
    Print("Total positions found: ", total);
    int cnt = 0; // Number of positions found during filtering.

    // Start a loop to scan all the positions.
    // The loop starts from the last, otherwise it could skip positions.
    for (int i = total - 1; i >= 0; i--)
    {
        // If the position cannot be selected throw and log an error.
        if (PositionGetSymbol(i) == "")
        {
            Print("ERROR - Unable to select the position - ", GetLastError());
            break;
        }

        // Check if the position matches the filter and if not skip the position and move to the next.
        if ((PositionTypeFilter == ONLY_SELL) && (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)) continue; // Don't act if the position is a Buy, and it was selected to only close Sell positions.
        if ((PositionTypeFilter == ONLY_BUY) && (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)) continue; // Don't act if the position is a Sell, and it was selected to only close Buy positions.
        if ((OnlyCurrentSymbol) && (PositionGetString(POSITION_SYMBOL) != Symbol())) continue;
        if ((OnlyInProfit) && (PositionGetDouble(POSITION_PROFIT) <= 0)) continue;
        if ((OnlyInLoss) && (PositionGetDouble(POSITION_PROFIT) >= 0)) continue;
        if ((OnlyMagicNumber) && (PositionGetInteger(POSITION_MAGIC) != MagicNumber)) continue;
        if ((OnlyWithComment) && (StringCompare(PositionGetString(POSITION_COMMENT), MatchingComment) != 0)) continue;

        // Profit/loss filters.
        if (MinProfitCurrency > 0 && PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP) + CaclulateCommission() < MinProfitCurrency) continue;
        if (MinLossCurrency > 0 && PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP) + CaclulateCommission() > -MinLossCurrency) continue;
        if (MinProfitPoints > 0)
        {
            if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY && PositionGetDouble(POSITION_PRICE_CURRENT) - PositionGetDouble(POSITION_PRICE_OPEN) < MinProfitPoints * SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_POINT)) continue;
            if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL && PositionGetDouble(POSITION_PRICE_OPEN) - PositionGetDouble(POSITION_PRICE_CURRENT) < MinProfitPoints * SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_POINT)) continue;
        }
        if (MinLossPoints > 0)
        {
            if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY && PositionGetDouble(POSITION_PRICE_OPEN) - PositionGetDouble(POSITION_PRICE_CURRENT) < MinLossPoints * SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_POINT)) continue;
            if (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL && PositionGetDouble(POSITION_PRICE_CURRENT) - PositionGetDouble(POSITION_PRICE_OPEN) < MinLossPoints * SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_POINT)) continue;
        }

        if (Sort != SORT_ORDERS_NO)
        {
            cnt++;
            
            ArrayResize(PositionsByProfit, cnt, 100); // Reserve extra physical memory to increase the resizing speed.

            double profit = PositionGetDouble(POSITION_PROFIT);
            if ((Sort == SORT_ORDERS_ABS_PROFIT_ASC) || (Sort == SORT_ORDERS_ABS_PROFIT_DESC))
            {
                profit = MathAbs(profit);
            }

            PositionsByProfit[cnt - 1][0] = profit;
            PositionsByProfit[cnt - 1][1] = (double)PositionGetInteger(POSITION_TICKET);
        }
        else
        {
            CloseOrder();
        }
    }

    if (Sort != SORT_ORDERS_NO) // If some sorting is required, the script hasn't closed anything yet.
    {
        ArraySort(PositionsByProfit); // Default sorting is in ascending order. Descending will be handled by processing the last elements first.
        // It's time to actually close the orders based on the collected info.
        total = ArrayRange(PositionsByProfit, 0);
        for (int i = 0; i < total; i++)
        {
            if ((Sort == SORT_ORDERS_ABS_PROFIT_ASC) || (Sort == SORT_ORDERS_PROFIT_ASC)) CloseOrder((ulong)PositionsByProfit[i][1]);
            else if ((Sort == SORT_ORDERS_ABS_PROFIT_DESC) || (Sort == SORT_ORDERS_PROFIT_DESC)) CloseOrder((ulong)PositionsByProfit[total - i - 1][1]);
        }
    }

    total = OrdersTotal();
    Print("Total pending orders found: ", total);
    for (int i = total - 1; i >= 0; i--)
    {
        ulong ticket = OrderGetTicket(i);
        if (ticket == 0)
        {
            Print("ERROR - Unable to select the pending order - ", GetLastError());
            break;
        }

        ENUM_ORDER_TYPE order_type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
        if ((PositionTypeFilter == ONLY_SELL) && (order_type != ORDER_TYPE_SELL_LIMIT) && (order_type != ORDER_TYPE_SELL_STOP) && (order_type != ORDER_TYPE_SELL_STOP_LIMIT)) continue;
        if ((PositionTypeFilter == ONLY_BUY) && (order_type != ORDER_TYPE_BUY_LIMIT) && (order_type != ORDER_TYPE_BUY_STOP) && (order_type != ORDER_TYPE_BUY_STOP_LIMIT)) continue;
        if ((OnlyCurrentSymbol) && (OrderGetString(ORDER_SYMBOL) != Symbol())) continue;
        if ((OnlyMagicNumber) && (OrderGetInteger(ORDER_MAGIC) != MagicNumber)) continue;
        if ((OnlyWithComment) && (StringCompare(OrderGetString(ORDER_COMMENT), MatchingComment) != 0)) continue;

        DeletePendingOrder(ticket);
    }

    delete Trade;
}

void DeletePendingOrder(ulong ticket)
{
    for (int try = 0; try < Retries; try++)
    {
        bool result = Trade.OrderDelete(ticket);

        if (!result) Print("ERROR - Unable to delete the pending order - ", ticket, " - Error ", GetLastError());

        Sleep(Delay);

        if (result) break;
    }
}

void CloseOrder(ulong ticket = 0)
{
    if (ticket != 0) // Otherwise, already selected.
    {
        if (!PositionSelectByTicket(ticket))
        {
            Print("ERROR - Unable to select the position by ticket. Ticket: ", ticket, ", Error: ", GetLastError());
            return;
        }
    }

    double CloseVolume = PositionGetDouble(POSITION_VOLUME);
    if (ClosePercentage < 100)
    {
        CloseVolume = (CloseVolume * ClosePercentage) / 100.0;
        double vol_min = SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_VOLUME_MIN);
        double vol_step = SymbolInfoDouble(PositionGetString(POSITION_SYMBOL), SYMBOL_VOLUME_STEP);

        if (CloseVolume < vol_min) CloseVolume = vol_min;
        else
        {
            double steps = 0;
            if (vol_step != 0) steps = CloseVolume / vol_step;
            if (MathFloor(steps) < steps)
            {
                CloseVolume = MathFloor(steps) * vol_step; // Close the smallest part of the volume possible.
            }
        }
    }

    // Try to close the trade in a cycle to overcome temporary failures.
    for (int try = 0; try < Retries; try++)
    {
        bool result = Trade.PositionClosePartial(PositionGetInteger(POSITION_TICKET), CloseVolume, Slippage);

        // If there was an error, log it.
        if (!result) Print("ERROR - Unable to close the position - ", PositionGetInteger(POSITION_TICKET), " - Error ", GetLastError());

        Sleep(Delay);

        if (result) break; // Finished with this position.
    }
}

// Assumes that the position is already selected.
double CaclulateCommission()
{
    // Retrieving the position's commission involves going through its deals:
    HistorySelectByPosition(PositionGetInteger(POSITION_IDENTIFIER));
    double comm = 0;
    for (int i = HistoryDealsTotal() - 1; i >= 0; i--)
    {
        ulong deal_ticket = HistoryDealGetTicket(i);
        if (deal_ticket > 0)
        {
            comm += HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION); // In netting mode, multiple deals are possible.
        }
    }
    return comm;
}                    
//+------------------------------------------------------------------+