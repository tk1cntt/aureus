//+------------------------------------------------------------------+
//|                                                   CommonDefs.mqh |
//|                                      Copyright 2024, OpenAlgo.in |
//|                                          https://www.openalgo.in |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, OpenAlgo.in"
#property link      "https://www.openalgo.in"


// Define enums for Exchange
enum Exchanges {
    NSE,
    NFO,
    CDS,
    BSE,
    BFO,
    BCD,
    MCX,
    NCDEX
};

// Define enums for Product Type
enum ProductTypes {
    CNC,
    NRML,
    MIS
};

// Define enums for Price Type
enum PriceTypes {
    MARKET,
    LIMIT,
    SL,
    SLM
};