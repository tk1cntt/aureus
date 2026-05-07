//+------------------------------------------------------------------+
//|                                                    UrlParser.mqh |
//|                                      Copyright 2024, OpenAlgo.in |
//|                                          https://www.openalgo.in |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, OpenAlgo.in"
#property link      "https://www.openalgo.in"



// Utility function to parse URLs
void ParseUrl(string url, string& host, string& path, int& port)
{
    string protocol = "http";
    int pos = StringFind(url, "://");
    if (pos != -1)
    {
        protocol = StringSubstr(url, 0, pos);
        url = StringSubstr(url, pos + 3);
    }

    pos = StringFind(url, "/");
    if (pos != -1)
    {
        host = StringSubstr(url, 0, pos);
        path = StringSubstr(url, pos);
    }
    else
    {
        host = url;
        path = "/";
    }

    pos = StringFind(host, ":");
    if (pos != -1)
    {
        string portStr = StringSubstr(host, pos + 1);
        // Directly casting to int after ensuring the value is within the valid port range
        long portLong = StringToInteger(portStr);
        if (portLong >= 0 && portLong <= 65535)
        {
            port = (int)portLong;
        }
        else
        {
            Print("Port number out of valid range. Using default port.");
            port = protocol == "https" ? 443 : 80;
        }
        
        host = StringSubstr(host, 0, pos);
    }
    else
    {
        port = protocol == "https" ? 443 : 80;
    }
}

