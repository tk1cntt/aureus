//+------------------------------------------------------------------+
//|                                           AureusSocketLib.mqh     |
//|                          Aureus Project — TCP Socket Library       |
//|                          Native MQL5 TCP — No external DLLs       |
//+------------------------------------------------------------------+
#property copyright "Aureus Project"
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
//| AureusSocket — Manages TCP connection to Aureus Gateway           |
//+------------------------------------------------------------------+
class AureusSocket
{
private:
   int      m_socket;           // Socket handle
   string   m_host;             // Gateway host
   int      m_port;             // Gateway port
   bool     m_connected;        // Connection state
   datetime m_lastConnectAttempt;
   datetime m_lastSendTime;
   datetime m_disconnectedSince; // When connection was lost
   int      m_reconnectDelaySec; // Minimum delay between reconnect attempts
   int      m_connectTimeoutMs;  // Connection timeout
   int      m_sendTimeoutMs;     // Send timeout
   string   m_sendBuffer;       // Accumulated buffer for batch sends
   int      m_sendCount;        // Messages sent since connect

   bool     DoConnect();
   void     DoDisconnect();

public:
   // Constructor
   AureusSocket()
   {
      m_socket            = INVALID_HANDLE;
      m_host              = "localhost";
      m_port              = 5555;
      m_connected         = false;
      m_lastConnectAttempt= 0;
      m_lastSendTime      = 0;
      m_disconnectedSince = 0;
      m_reconnectDelaySec = 3;
      m_connectTimeoutMs  = 3000;
      m_sendTimeoutMs     = 1000;
      m_sendBuffer        = "";
      m_sendCount         = 0;
   }

   // Destructor
   ~AureusSocket()
   {
      Disconnect();
   }

   // Configuration
   void  SetHost(string host)            { m_host = host; }
   void  SetPort(int port)               { m_port = port; }
   void  SetReconnectDelay(int sec)      { m_reconnectDelaySec = sec; }
   void  SetConnectTimeout(int ms)       { m_connectTimeoutMs = ms; }
   void  SetSendTimeout(int ms)          { m_sendTimeoutMs = ms; }

   // State
   bool  IsConnected()           const   { return m_connected; }
   int   GetSendCount()          const   { return m_sendCount; }
   datetime DisconnectedSince()  const   { return m_disconnectedSince; }

   // Connection
   bool  Connect();
   void  Disconnect();
   bool  EnsureConnected();      // Auto-reconnect if needed

   // Sending
   bool  SendJSON(string json);  // Send single JSON line
   bool  SendBatch(string &batch[], int count); // Send multiple JSON lines

   // Receiving
   int   CheckReadable();
   string Receive();             // Receive available data as string
};

//+------------------------------------------------------------------+
//| Connect to gateway                                                |
//+------------------------------------------------------------------+
bool AureusSocket::DoConnect()
{
   if(m_socket != INVALID_HANDLE)
   {
      SocketClose(m_socket);
      m_socket = INVALID_HANDLE;
   }

   m_socket = SocketCreate();
   if(m_socket == INVALID_HANDLE)
   {
      // PrintFormat("[AureusSocket] SocketCreate failed: %d", GetLastError());
      return false;
   }

   // Set timeouts
   SocketTimeouts(m_socket, m_connectTimeoutMs, m_sendTimeoutMs);

   // Attempt connection
   if(!SocketConnect(m_socket, m_host, m_port, m_connectTimeoutMs))
   {
      int err = GetLastError();
      // PrintFormat("[AureusSocket] Connect to %s:%d failed: %d", m_host, m_port, err);
      SocketClose(m_socket);
      m_socket = INVALID_HANDLE;
      return false;
   }

   // PrintFormat("[AureusSocket] Connected to %s:%d", m_host, m_port);
   return true;
}

//+------------------------------------------------------------------+
//| Disconnect from gateway                                           |
//+------------------------------------------------------------------+
void AureusSocket::DoDisconnect()
{
   if(m_socket != INVALID_HANDLE)
   {
      SocketClose(m_socket);
      m_socket = INVALID_HANDLE;
   }
   m_connected = false;
}

//+------------------------------------------------------------------+
//| Public Connect                                                     |
//+------------------------------------------------------------------+
bool AureusSocket::Connect()
{
   m_lastConnectAttempt = TimeCurrent();

   if(DoConnect())
   {
      m_connected = true;
      m_sendCount = 0;

      // If we were disconnected, log the gap duration
      if(m_disconnectedSince > 0)
      {
         int gapSec = (int)(TimeCurrent() - m_disconnectedSince);
         PrintFormat("[AureusSocket] Reconnected after %d seconds gap", gapSec);
      }
      m_disconnectedSince = 0;
      return true;
   }

   if(m_disconnectedSince == 0)
      m_disconnectedSince = TimeCurrent();

   return false;
}

//+------------------------------------------------------------------+
//| Public Disconnect                                                  |
//+------------------------------------------------------------------+
void AureusSocket::Disconnect()
{
   DoDisconnect();
   PrintFormat("[AureusSocket] Disconnected");
}

//+------------------------------------------------------------------+
//| Ensure connected — auto-reconnect with delay                      |
//+------------------------------------------------------------------+
bool AureusSocket::EnsureConnected()
{
   if(m_connected)
      return true;

   // Rate-limit reconnect attempts
   if(TimeCurrent() - m_lastConnectAttempt < m_reconnectDelaySec)
      return false;

   return Connect();
}

//+------------------------------------------------------------------+
//| Send a single JSON string (appends \n delimiter)                  |
//+------------------------------------------------------------------+
bool AureusSocket::SendJSON(string json)
{
   if(!m_connected)
   {
      if(!EnsureConnected())
         return false;
   }

   string payload = json + "\n";
   uchar data[];
   int totalLen = StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);

   // StringToCharArray adds null terminator, totalLen-1 is the actual data
   if(totalLen <= 1)
      return false;

   int dataLen = totalLen - 1;
   int totalSent = 0;
   
   // Loop to ensure all data is sent (handles partial sends)
   while(totalSent < dataLen)
   {
      // Create a temporary array for the remaining data
      uchar chunk[];
      int remaining = dataLen - totalSent;
      ArrayCopy(chunk, data, 0, totalSent, remaining);
      
      int sent = SocketSend(m_socket, chunk, remaining);
      if(sent <= 0)
      {
         int err = GetLastError();
         // PrintFormat("[AureusSocket] Send failed at %d/%d: %d (err: %d)", totalSent, dataLen, sent, err);
         m_connected = false;
         if(m_disconnectedSince == 0)
            m_disconnectedSince = TimeCurrent();
         return false;
      }
      totalSent += sent;
   }

   m_lastSendTime = TimeCurrent();
   m_sendCount++;
   return true;
}

//+------------------------------------------------------------------+
//| Send batch of JSON strings                                        |
//+------------------------------------------------------------------+
bool AureusSocket::SendBatch(string &batch[], int count)
{
   if(!m_connected)
   {
      if(!EnsureConnected())
         return false;
   }

   // Build single payload with newline delimiters
   string payload = "";
   for(int i = 0; i < count; i++)
   {
      payload += batch[i] + "\n";
   }

   uchar data[];
   int totalLen = StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(totalLen <= 1)
      return false;

   int dataLen = totalLen - 1;
   int totalSent = 0;
   
   while(totalSent < dataLen)
   {
      uchar chunk[];
      int remaining = dataLen - totalSent;
      ArrayCopy(chunk, data, 0, totalSent, remaining);
      
      int sent = SocketSend(m_socket, chunk, remaining);
      if(sent <= 0)
      {
         int err = GetLastError();
         // PrintFormat("[AureusSocket] Batch send failed at %d/%d: %d (err: %d)", totalSent, dataLen, sent, err);
         m_connected = false;
         if(m_disconnectedSince == 0)
            m_disconnectedSince = TimeCurrent();
         return false;
      }
      totalSent += sent;
   }

   m_lastSendTime = TimeCurrent();
   m_sendCount += count;
   PrintFormat("[AureusSocket] Batch sent: %d messages", count);
   return true;
}

//+------------------------------------------------------------------+
//| Check if data is available or error occurred                     |
//+------------------------------------------------------------------+
int AureusSocket::CheckReadable()
{
   if(!m_connected || m_socket == INVALID_HANDLE) return -1;
   int res = (int)::SocketIsReadable(m_socket);
   if(res < 0)
   {
      int err = GetLastError();
      PrintFormat("[AureusSocket] IsReadable error: %d", err);
      m_connected = false;
      if(m_disconnectedSince == 0) m_disconnectedSince = TimeCurrent();
   }
   return res;
}

//+------------------------------------------------------------------+
//| Receive data from socket (Read exact pending size)                |
//+------------------------------------------------------------------+
string AureusSocket::Receive()
{
   int pending = CheckReadable();
   if(pending <= 0) return "";
   
   uchar data[];
   ArrayResize(data, pending); 
   
   // Read exactly what is available
   int received = ::SocketRead(m_socket, data, pending, 500); 
   
   if(received <= 0)
   {
      int err = GetLastError();
      if(err != 0 && err != 5270 && err != 5271) { 
         PrintFormat("[AureusSocket] Receive error: %d (requested: %d)", err, pending);
         m_connected = false;
         if(m_disconnectedSince == 0) m_disconnectedSince = TimeCurrent();
      }
      return "";
   }
   
   string result = CharArrayToString(data, 0, received, CP_UTF8);
   PrintFormat("[AureusSocket] RX (%d bytes): %s", received, result);
   
   if(StringFind(result, "REQUEST_BACKFILL") >= 0)
      PrintFormat("[AureusSocket] Found COMMAND in packet: %s", result);
      
   return result;
}
