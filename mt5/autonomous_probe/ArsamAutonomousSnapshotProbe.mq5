#property strict

// Read-only continuous snapshot exporter for v0.6 autonomous DEMO orchestration.
// This EA contains no order, position, or pending-order mutation path.

input string RequestedSymbols = "EURUSD,GBPUSD,USDJPY";
input string OutputFile = "arsam_autonomous_snapshot_1_0.json";
input ENUM_TIMEFRAMES DecisionTimeframe = PERIOD_M15;
input int RefreshSeconds = 1;

string JsonEscape(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\\", "\\\\");
   StringReplace(escaped, "\"", "\\\"");
   StringReplace(escaped, "\r", "\\r");
   StringReplace(escaped, "\n", "\\n");
   StringReplace(escaped, "\t", "\\t");
   return "\"" + escaped + "\"";
}

string BoolJson(const bool value)
{
   return value ? "true" : "false";
}

string DecimalJson(const double value, const int digits)
{
   return JsonEscape(DoubleToString(value, digits));
}

string UtcIso(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   return StringFormat(
      "%04d-%02d-%02dT%02d:%02d:%02dZ",
      parts.year,
      parts.mon,
      parts.day,
      parts.hour,
      parts.min,
      parts.sec
   );
}

datetime ServerToUtc(const datetime server_time)
{
   const long offset_seconds = (long)TimeTradeServer() - (long)TimeGMT();
   return (datetime)((long)server_time - offset_seconds);
}

bool CalculateDailyRealizedPnl(double &value)
{
   const datetime now = TimeTradeServer();
   if(now <= 0)
      return false;

   MqlDateTime parts;
   TimeToStruct(now, parts);
   parts.hour = 0;
   parts.min = 0;
   parts.sec = 0;
   const datetime start = StructToTime(parts);

   ResetLastError();
   if(!HistorySelect(start, now))
      return false;

   value = 0.0;
   const int total = HistoryDealsTotal();
   for(int index = 0; index < total; index++)
   {
      const ulong ticket = HistoryDealGetTicket(index);
      if(ticket == 0)
         continue;

      const ENUM_DEAL_TYPE deal_type =
         (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(deal_type != DEAL_TYPE_BUY && deal_type != DEAL_TYPE_SELL)
         continue;

      value += HistoryDealGetDouble(ticket, DEAL_PROFIT);
      value += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      value += HistoryDealGetDouble(ticket, DEAL_SWAP);
      value += HistoryDealGetDouble(ticket, DEAL_FEE);
   }
   return true;
}

string BuildSymbolJson(const string symbol)
{
   MqlTick tick;
   ResetLastError();
   if(!SymbolInfoTick(symbol, tick))
      return "";

   const datetime server_now = TimeTradeServer();
   if(server_now <= 0 || tick.time <= 0)
      return "";

   const long tick_age = (long)server_now - (long)tick.time;
   if(tick_age < 0)
      return "";

   const double previous_close = iClose(symbol, PERIOD_D1, 1);
   const datetime bar_time = iTime(symbol, DecisionTimeframe, 0);
   if(previous_close <= 0.0 || bar_time <= 0 || tick.bid <= 0.0 || tick.ask < tick.bid)
      return "";

   const string profit_currency = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
   const int symbol_digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(symbol_digits < 0)
      return "";

   string json = "{";
   json += "\"name\":" + JsonEscape(symbol) + ",";
   json += "\"base_currency\":" + JsonEscape(SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE)) + ",";
   // For reviewed FX pairs, MT5 profit currency is the quote currency.
   json += "\"quote_currency\":" + JsonEscape(profit_currency) + ",";
   json += "\"bid\":" + DecimalJson(tick.bid, symbol_digits) + ",";
   json += "\"ask\":" + DecimalJson(tick.ask, symbol_digits) + ",";
   json += "\"previous_close\":" + DecimalJson(previous_close, symbol_digits) + ",";
   json += "\"observed_at\":" + JsonEscape(UtcIso(ServerToUtc(tick.time))) + ",";
   json += "\"decision_bar_time\":" + JsonEscape(UtcIso(ServerToUtc(bar_time))) + ",";
   json += "\"tick_age_seconds\":" + IntegerToString((int)tick_age) + ",";
   json += "\"trade_mode_code\":" +
      IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE));
   return json + "}";
}

bool WriteSnapshot()
{
   if(RefreshSeconds < 1)
      return false;

   string requested[];
   const int requested_count = StringSplit(
      RequestedSymbols,
      (ushort)StringGetCharacter(",", 0),
      requested
   );
   if(requested_count <= 0)
      return false;

   double daily_realized_pnl = 0.0;
   if(!CalculateDailyRealizedPnl(daily_realized_pnl))
   {
      Print("Autonomous snapshot blocked: daily realized P/L unavailable. Error: ", GetLastError());
      return false;
   }

   string symbols_json = "[";
   int observed_count = 0;
   for(int index = 0; index < requested_count; index++)
   {
      string symbol = requested[index];
      StringTrimLeft(symbol);
      StringTrimRight(symbol);
      StringToUpper(symbol);
      if(symbol == "" || !SymbolSelect(symbol, true))
      {
         Print("Autonomous snapshot blocked: symbol unavailable: ", symbol);
         return false;
      }

      const string symbol_json = BuildSymbolJson(symbol);
      if(symbol_json == "")
      {
         Print("Autonomous snapshot blocked: incomplete market state for ", symbol);
         return false;
      }

      if(observed_count > 0)
         symbols_json += ",";
      symbols_json += symbol_json;
      observed_count++;
   }
   symbols_json += "]";

   if(observed_count != requested_count)
      return false;

   const string acquired_at = UtcIso(TimeGMT());
   const int account_currency_digits = (int)AccountInfoInteger(ACCOUNT_CURRENCY_DIGITS);
   if(account_currency_digits < 0)
      return false;

   string json = "{";
   json += "\"schema_version\":\"1.0\",";
   json += "\"mode\":\"autonomous_demo_snapshot\",";
   json += "\"source_type\":\"mql5_autonomous_probe\",";
   json += "\"acquired_at\":" + JsonEscape(acquired_at) + ",";
   json += "\"broker\":{";
   json += "\"company\":" + JsonEscape(TerminalInfoString(TERMINAL_COMPANY)) + ",";
   json += "\"server\":" + JsonEscape(AccountInfoString(ACCOUNT_SERVER)) + "},";
   json += "\"terminal\":{";
   json += "\"connected\":" + BoolJson((bool)TerminalInfoInteger(TERMINAL_CONNECTED)) + "},";
   json += "\"account\":{";
   json += "\"currency\":" + JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)) + ",";
   json += "\"trade_mode_code\":" +
      IntegerToString((int)AccountInfoInteger(ACCOUNT_TRADE_MODE)) + ",";
   json += "\"leverage\":" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LEVERAGE)) + ",";
   json += "\"margin_mode_code\":" +
      IntegerToString((int)AccountInfoInteger(ACCOUNT_MARGIN_MODE)) + ",";
   json += "\"trade_allowed\":" +
      BoolJson((bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) + ",";
   json += "\"automated_trading_allowed\":" +
      BoolJson((bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) + ",";
   json += "\"balance\":" + DecimalJson(AccountInfoDouble(ACCOUNT_BALANCE), account_currency_digits) + ",";
   json += "\"equity\":" + DecimalJson(AccountInfoDouble(ACCOUNT_EQUITY), account_currency_digits) + ",";
   json += "\"daily_realized_pnl\":" + DecimalJson(daily_realized_pnl, account_currency_digits) + ",";
   json += "\"open_position_count\":" + IntegerToString(PositionsTotal());
   json += "},";
   json += "\"symbols\":" + symbols_json;
   json += "}";

   const int handle = FileOpen(OutputFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(handle == INVALID_HANDLE)
   {
      Print("Autonomous snapshot export failed. Error: ", GetLastError());
      return false;
   }
   FileWriteString(handle, json);
   FileFlush(handle);
   FileClose(handle);
   return true;
}

int OnInit()
{
   if(RefreshSeconds < 1)
   {
      Print("Autonomous snapshot probe requires RefreshSeconds >= 1.");
      return INIT_PARAMETERS_INCORRECT;
   }
   EventSetTimer(RefreshSeconds);
   if(!WriteSnapshot())
      Print("Initial autonomous snapshot was not produced; no trading decision is authorized.");
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   WriteSnapshot();
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}
