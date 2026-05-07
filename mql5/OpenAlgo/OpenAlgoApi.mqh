//+------------------------------------------------------------------+
//|                                                  OpenAlgoAPI.mqh |
//|                                      Copyright 2024, OpenAlgo.in |
//|                                          https://www.openalgo.in |
//+------------------------------------------------------------------+

#include <Trade/Trade.mqh>
#include "WinINet.mqh"
#include "CommonDefs.mqh"
#include "UrlParser.mqh"
#include "ErrorHandler.mqh"

#property copyright "Copyright 2024, OpenAlgo.in"
#property link      "https://www.openalgo.in"


// Function to place orders 

void PlaceOrder(string actionParam, int quantityParam, string apiUrlParam, string apiKeyParam, string strategyParam, string symbolParam, Exchanges exchangeParam, ProductTypes productParam, PriceTypes priceTypeParam, double priceParam=0, double triggerPriceParam=0, int disclosedQuantityParam=0)
{
    WininetRequest req;
    WininetResponse res;

    string host, path;
    int port;
    ParseUrl(apiUrlParam, host, path, port);
    
    // Convert enums to strings for exchange, product, and price type
    string exchangeStr, productTypeStr, priceTypeStr;
    
    switch(exchangeParam) {
        case NSE: exchangeStr = "NSE"; break;
        case NFO: exchangeStr = "NFO"; break;
        case CDS: exchangeStr = "CDS"; break;
        case BSE: exchangeStr = "BSE"; break;
        case BFO: exchangeStr = "BFO"; break;
        case BCD: exchangeStr = "BCD"; break;
        case MCX: exchangeStr = "MCX"; break;
        case NCDEX: exchangeStr = "NCDEX"; break;
        // You can add more cases here if you have additional exchanges.
    }

    switch(productParam) {
        case CNC: productTypeStr = "CNC"; break;
        case NRML: productTypeStr = "NRML"; break;
        case MIS: productTypeStr = "MIS"; break;
        // Additional products as needed...
    }

    switch(priceTypeParam) {
        case MARKET: priceTypeStr = "MARKET"; break;
        case LIMIT: priceTypeStr = "LIMIT"; break;
        case SL: priceTypeStr = "SL"; break;
        case SLM: priceTypeStr = "SL-M"; break;
        // Add additional price types if your system requires them.
    }

    req.method = "POST";
    req.host = host;
    req.path = path + "/api/v1/placeorder";
    req.port = port;
    req.headers = "Content-Type: application/json; charset=UTF-8\r\n";

   
    string postData = StringFormat("{\"apikey\":\"%s\",\"strategy\":\"%s\",\"symbol\":\"%s\",\"action\":\"%s\",\"exchange\":\"%s\",\"pricetype\":\"%s\",\"product\":\"%s\",\"quantity\":%d",
                            apiKeyParam, strategyParam, symbolParam, actionParam, exchangeStr, priceTypeStr, productTypeStr, quantityParam);
    
    if (priceParam > 0) {
        postData += StringFormat(",\"price\":%g", priceParam);
    }
    if (triggerPriceParam > 0) {
        postData += StringFormat(",\"trigger_price\":%g", triggerPriceParam);
    }
    if (disclosedQuantityParam > 0) {
        postData += StringFormat(",\"disclosed_quantity\":%d", disclosedQuantityParam);
    }

    postData += "}";
    
    StringReplace(postData, "'", "\"");
    req.data_str = postData;

    // Enhanced logging per D-04, D-08
    LogRequest("PlaceOrder", req);

    // Use retry wrapper (ERR-01)
    if (WebReqWithRetry(req, res, "PlaceOrder")) {
        // Success - log response (D-05)
        LogResponse("PlaceOrder", res);
        Print("[OpenAlgo] PlaceOrder: Order placed successfully");
    } else {
        // Failed - distinguish error type (D-14)
        if (res.status <= 0) {
            LogNetworkError("PlaceOrder", "Request failed");
        } else {
            LogApiError("PlaceOrder", res.status, res.GetDataStr());
        }
    }
}

// Function to place smart orders by analyzing the current open position
// The order is matched to the Position Size given in the position book
// Buy/Sell orders will be adjusted according to the Position Size

void PlaceSmartOrder(string actionParam, int quantityParam, int positionSizeParam, string apiUrlParam, string apiKeyParam, string strategyParam, string symbolParam, Exchanges exchangeParam, ProductTypes productParam, PriceTypes priceTypeParam, double priceParam=0, double triggerPriceParam=0, int disclosedQuantityParam=0)
{
    WininetRequest req;
    WininetResponse res;

    string host, path;
    int port;
    ParseUrl(apiUrlParam, host, path, port);
    
    // Convert enums to strings for exchange, product, and price type
    string exchangeStr, productTypeStr, priceTypeStr;
    
    switch(exchangeParam) {
        case NSE: exchangeStr = "NSE"; break;
        case NFO: exchangeStr = "NFO"; break;
        case CDS: exchangeStr = "CDS"; break;
        case BSE: exchangeStr = "BSE"; break;
        case BFO: exchangeStr = "BFO"; break;
        case BCD: exchangeStr = "BCD"; break;
        case MCX: exchangeStr = "MCX"; break;
        case NCDEX: exchangeStr = "NCDEX"; break;
        // Additional exchanges can be added here as needed.
    }

    switch(productParam) {
        case CNC: productTypeStr = "CNC"; break;
        case NRML: productTypeStr = "NRML"; break;
        case MIS: productTypeStr = "MIS"; break;
        // Additional products can be added here as needed.
    }

    switch(priceTypeParam) {
        case MARKET: priceTypeStr = "MARKET"; break;
        case LIMIT: priceTypeStr = "LIMIT"; break;
        case SL: priceTypeStr = "SL"; break;
        case SLM: priceTypeStr = "SL-M"; break;
        // Additional price types can be added here if needed.
    }

    req.method = "POST";
    req.host = host;
    req.path = path + "/api/v1/placesmartorder";
    req.port = port;
    req.headers = "Content-Type: application/json; charset=UTF-8\r\n";

    string postData = StringFormat("{\"apikey\":\"%s\",\"strategy\":\"%s\",\"symbol\":\"%s\",\"action\":\"%s\",\"exchange\":\"%s\",\"pricetype\":\"%s\",\"product\":\"%s\",\"quantity\":%d,\"position_size\":%d",
                            apiKeyParam, strategyParam, symbolParam, actionParam, exchangeStr, priceTypeStr, productTypeStr, quantityParam, positionSizeParam);

    // Including the optional parameters in the request if they are specified
    if (priceParam > 0) {
        postData += StringFormat(",\"price\":%g", priceParam);
    }
    if (triggerPriceParam > 0) {
        postData += StringFormat(",\"trigger_price\":%g", triggerPriceParam);
    }
    if (disclosedQuantityParam > 0) {
        postData += StringFormat(",\"disclosed_quantity\":%d", disclosedQuantityParam);
    }

    postData += "}";
    
    StringReplace(postData, "'", "\"");
    req.data_str = postData;

    // Enhanced logging per D-04, D-08
    LogRequest("PlaceSmartOrder", req);

    // Use retry wrapper (ERR-01)
    if (WebReqWithRetry(req, res, "PlaceSmartOrder")) {
        // Success - log response (D-05)
        LogResponse("PlaceSmartOrder", res);
        Print("[OpenAlgo] PlaceSmartOrder: Order placed successfully");
    } else {
        // Failed - distinguish error type (D-14)
        if (res.status <= 0) {
            LogNetworkError("PlaceSmartOrder", "Request failed");
        } else {
            LogApiError("PlaceSmartOrder", res.status, res.GetDataStr());
        }
    }
}

// Function to modify an existing order

void ModifyOrder(string orderidParam, string actionParam, int quantityParam, double priceParam, string apiUrlParam, string apiKeyParam, string strategyParam, string symbolParam, Exchanges exchangeParam, ProductTypes productParam, PriceTypes priceTypeParam, int disclosedQuantityParam=0, double triggerPriceParam=0)
{
    WininetRequest req;
    WininetResponse res;

    string host, path;
    int port;
    ParseUrl(apiUrlParam, host, path, port);
    
    // Convert enums to strings for exchange, product, and price type
    string exchangeStr, productTypeStr, priceTypeStr;
    
    switch(exchangeParam) {
        case NSE: exchangeStr = "NSE"; break;
        case NFO: exchangeStr = "NFO"; break;
        case CDS: exchangeStr = "CDS"; break;
        case BSE: exchangeStr = "BSE"; break;
        case BFO: exchangeStr = "BFO"; break;
        case BCD: exchangeStr = "BCD"; break;
        case MCX: exchangeStr = "MCX"; break;
        case NCDEX: exchangeStr = "NCDEX"; break;
        // Additional exchanges can be added here as needed.
    }

    switch(productParam) {
        case CNC: productTypeStr = "CNC"; break;
        case NRML: productTypeStr = "NRML"; break;
        case MIS: productTypeStr = "MIS"; break;
        // Additional products can be added here as needed.
    }

    switch(priceTypeParam) {
        case LIMIT: priceTypeStr = "LIMIT"; break;
        case MARKET: priceTypeStr = "MARKET"; break;
        // Additional price types can be added here if needed.
    }

    req.method = "POST";
    req.host = host;
    req.path = path + "/api/v1/modifyorder";
    req.port = port;
    req.headers = "Content-Type: application/json; charset=UTF-8\r\n";

    // Prepare JSON data for HTTP POST request
    string postData = StringFormat("{\"apikey\":\"%s\",\"strategy\":\"%s\",\"symbol\":\"%s\",\"action\":\"%s\",\"exchange\":\"%s\",\"orderid\":\"%s\",\"product\":\"%s\",\"pricetype\":\"%s\",\"price\":\"%g\",\"quantity\":\"%d\",\"disclosed_quantity\":\"%d\",\"trigger_price\":\"%g\"}",
                            apiKeyParam, strategyParam, symbolParam, actionParam, exchangeStr, orderidParam, productTypeStr, priceTypeStr, priceParam, quantityParam, disclosedQuantityParam, triggerPriceParam);

    StringReplace(postData, "'", "\"");
    req.data_str = postData;

    // Enhanced logging per D-04, D-08
    LogRequest("ModifyOrder", req);

    // Use retry wrapper (ERR-01)
    if (WebReqWithRetry(req, res, "ModifyOrder")) {
        // Success - log response (D-05)
        LogResponse("ModifyOrder", res);
        Print("[OpenAlgo] ModifyOrder: Order modified successfully");
    } else {
        // Failed - distinguish error type (D-14)
        if (res.status <= 0) {
            LogNetworkError("ModifyOrder", "Request failed");
        } else {
            LogApiError("ModifyOrder", res.status, res.GetDataStr());
        }
    }
}


// Function to cancel an existing order
void CancelOrder(string orderidParam, string apiUrlParam, string apiKeyParam, string strategyParam)
{
    WininetRequest req;
    WininetResponse res;

    string host, path;
    int port;
    ParseUrl(apiUrlParam, host, path, port);
    
    req.method = "POST";
    req.host = host;
    req.path = path + "/api/v1/cancelorder";
    req.port = port;
    req.headers = "Content-Type: application/json; charset=UTF-8\r\n";

    // Prepare JSON data for HTTP POST request
    string postData = StringFormat("{\"apikey\":\"%s\",\"strategy\":\"%s\",\"orderid\":\"%s\"}",
                                   apiKeyParam, strategyParam, orderidParam);

    StringReplace(postData, "'", "\"");
    req.data_str = postData;

    // Enhanced logging per D-04, D-08
    LogRequest("CancelOrder", req);

    // Use retry wrapper (ERR-01)
    if (WebReqWithRetry(req, res, "CancelOrder")) {
        // Success - log response (D-05)
        LogResponse("CancelOrder", res);
        Print("[OpenAlgo] CancelOrder: Order cancelled successfully");
    } else {
        // Failed - distinguish error type (D-14)
        if (res.status <= 0) {
            LogNetworkError("CancelOrder", "Request failed");
        } else {
            LogApiError("CancelOrder", res.status, res.GetDataStr());
        }
    }
}


// Function to close all open positions for a strategy
void ClosePosition(string apiUrlParam, string apiKeyParam, string strategyParam)
{
    WininetRequest req;
    WininetResponse res;

    string host, path;
    int port;
    ParseUrl(apiUrlParam, host, path, port);
    
    req.method = "POST";
    req.host = host;
    req.path = path + "/api/v1/closeposition";
    req.port = port;
    req.headers = "Content-Type: application/json; charset=UTF-8\r\n";

    // Prepare JSON data for HTTP POST request
    string postData = StringFormat("{\"apikey\":\"%s\",\"strategy\":\"%s\"}",
                                   apiKeyParam, strategyParam);

    StringReplace(postData, "'", "\"");
    req.data_str = postData;

    // Enhanced logging per D-04, D-08
    LogRequest("ClosePosition", req);

    // Use retry wrapper (ERR-01)
    if (WebReqWithRetry(req, res, "ClosePosition")) {
        // Success - log response (D-05)
        LogResponse("ClosePosition", res);
        Print("[OpenAlgo] ClosePosition: Position closed successfully");
    } else {
        // Failed - distinguish error type (D-14)
        if (res.status <= 0) {
            LogNetworkError("ClosePosition", "Request failed");
        } else {
            LogApiError("ClosePosition", res.status, res.GetDataStr());
        }
    }
}

// Function to cancel all orders for a strategy
void CancelAllOrders(string apiUrlParam, string apiKeyParam, string strategyParam)
{
    WininetRequest req;
    WininetResponse res;

    string host, path;
    int port;
    ParseUrl(apiUrlParam, host, path, port);
    
    req.method = "POST";
    req.host = host;
    req.path = path + "/api/v1/cancelallorder";
    req.port = port;
    req.headers = "Content-Type: application/json; charset=UTF-8\r\n";

    // Prepare JSON data for HTTP POST request
    string postData = StringFormat("{\"apikey\":\"%s\",\"strategy\":\"%s\"}",
                                   apiKeyParam, strategyParam);

    StringReplace(postData, "'", "\"");
    req.data_str = postData;

    // Enhanced logging per D-04, D-08
    LogRequest("CancelAllOrders", req);

    // Use retry wrapper (ERR-01)
    if (WebReqWithRetry(req, res, "CancelAllOrders")) {
        // Success - log response (D-05)
        LogResponse("CancelAllOrders", res);
        Print("[OpenAlgo] CancelAllOrders: All orders cancelled successfully");
    } else {
        // Failed - distinguish error type (D-14)
        if (res.status <= 0) {
            LogNetworkError("CancelAllOrders", "Request failed");
        } else {
            LogApiError("CancelAllOrders", res.status, res.GetDataStr());
        }
    }
}


