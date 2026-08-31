#property strict
#property script_show_inputs

// Read-only metadata/calculation exporter for schema 1.0.
// This script contains no order, position, or pending-order mutation path.

input string RequestedSymbols = "EURUSD,GBPUSD,USDJPY";
input string OutputFile = "arsam_mt5_metadata_1_0.json";
input double CalibrationVolume = 0.01;

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

string DecimalJson(const double value)
{
   return JsonEscape(DoubleToString(value, 16));
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

string BuildSymbolJson(const string symbol, const string observed_at)
{
   const string profit_currency = SymbolInfoString(symbol, SYMBOL_CURRENCY_PROFIT);
   string json = "{";
   json += "\"name\":" + JsonEscape(symbol) + ",";
   json += "\"base_currency\":" + JsonEscape(SymbolInfoString(symbol, SYMBOL_CURRENCY_BASE)) + ",";
   // MT5 exposes profit currency rather than a separate quote field. For FX this is the quote.
   json += "\"quote_currency\":" + JsonEscape(profit_currency) + ",";
   json += "\"profit_currency\":" + JsonEscape(profit_currency) + ",";
   json += "\"margin_currency\":" + JsonEscape(SymbolInfoString(symbol, SYMBOL_CURRENCY_MARGIN)) + ",";
   json += "\"digits\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)) + ",";
   json += "\"point\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_POINT)) + ",";
   json += "\"tick_size\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE)) + ",";
   json += "\"tick_value\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE)) + ",";
   json += "\"tick_value_profit\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT)) + ",";
   json += "\"tick_value_loss\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS)) + ",";
   json += "\"contract_size\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE)) + ",";
   json += "\"volume_min\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN)) + ",";
   json += "\"volume_max\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX)) + ",";
   json += "\"volume_step\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP)) + ",";
   json += "\"volume_limit\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_VOLUME_LIMIT)) + ",";
   json += "\"bid\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_BID)) + ",";
   json += "\"ask\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_ASK)) + ",";
   json += "\"reported_spread_points\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_SPREAD)) + ",";
   json += "\"spread_is_floating\":" + BoolJson((bool)SymbolInfoInteger(symbol, SYMBOL_SPREAD_FLOAT)) + ",";
   json += "\"trade_mode_code\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE)) + ",";
   json += "\"order_mode_mask\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_ORDER_MODE)) + ",";
   json += "\"filling_mode_mask\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE)) + ",";
   json += "\"expiration_mode_mask\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_EXPIRATION_MODE)) + ",";
   json += "\"stop_level_points\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL)) + ",";
   json += "\"freeze_level_points\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL)) + ",";
   json += "\"calculation_mode_code\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_TRADE_CALC_MODE)) + ",";
   json += "\"swap_mode_code\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_SWAP_MODE)) + ",";
   json += "\"swap_long\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_SWAP_LONG)) + ",";
   json += "\"swap_short\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_SWAP_SHORT)) + ",";
   json += "\"rollover_day\":" + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_SWAP_ROLLOVER3DAYS)) + ",";
   json += "\"margin_initial\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_MARGIN_INITIAL)) + ",";
   json += "\"margin_maintenance\":" + DecimalJson(SymbolInfoDouble(symbol, SYMBOL_MARGIN_MAINTENANCE)) + ",";
   json += "\"observed_at\":" + JsonEscape(observed_at);
   return json + "}";
}

string BuildProfitCase(
   const string symbol,
   const ENUM_ORDER_TYPE side,
   const double open_price,
   const double close_price,
   const string observed_at
)
{
   double calculated = 0.0;
   ResetLastError();
   const bool success = OrderCalcProfit(
      side,
      symbol,
      CalibrationVolume,
      open_price,
      close_price,
      calculated
   );
   const int error_code = success ? 0 : GetLastError();
   string json = "{";
   json += "\"symbol\":" + JsonEscape(symbol) + ",";
   json += "\"side\":" + JsonEscape(side == ORDER_TYPE_BUY ? "buy" : "sell") + ",";
   json += "\"volume\":" + DecimalJson(CalibrationVolume) + ",";
   json += "\"open_price\":" + DecimalJson(open_price) + ",";
   json += "\"close_price\":" + DecimalJson(close_price) + ",";
   json += "\"calculated_profit\":" + (success ? DecimalJson(calculated) : "null") + ",";
   json += "\"success\":" + BoolJson(success) + ",";
   json += "\"error_code\":" + IntegerToString(error_code) + ",";
   json += "\"observed_at\":" + JsonEscape(observed_at);
   return json + "}";
}

string BuildMarginCase(
   const string symbol,
   const ENUM_ORDER_TYPE side,
   const double price,
   const string observed_at
)
{
   double calculated = 0.0;
   ResetLastError();
   const bool success = OrderCalcMargin(side, symbol, CalibrationVolume, price, calculated);
   const int error_code = success ? 0 : GetLastError();
   string json = "{";
   json += "\"symbol\":" + JsonEscape(symbol) + ",";
   json += "\"side\":" + JsonEscape(side == ORDER_TYPE_BUY ? "buy" : "sell") + ",";
   json += "\"volume\":" + DecimalJson(CalibrationVolume) + ",";
   json += "\"price\":" + DecimalJson(price) + ",";
   json += "\"calculated_margin\":" + (success ? DecimalJson(calculated) : "null") + ",";
   json += "\"success\":" + BoolJson(success) + ",";
   json += "\"error_code\":" + IntegerToString(error_code) + ",";
   json += "\"observed_at\":" + JsonEscape(observed_at);
   return json + "}";
}

void OnStart()
{
   if(CalibrationVolume <= 0.0)
   {
      Print("Read-only metadata probe rejected non-positive calibration volume.");
      return;
   }

   string requested[];
   const int requested_count = StringSplit(
      RequestedSymbols,
      (ushort)StringGetCharacter(",", 0),
      requested
   );
   if(requested_count <= 0)
   {
      Print("Read-only metadata probe requires at least one symbol.");
      return;
   }

   const string acquired_at = UtcIso(TimeGMT());
   string requested_json = "[";
   string symbols_json = "[";
   string profits_json = "[";
   string margins_json = "[";
   int observed_count = 0;
   int calculation_count = 0;

   for(int index = 0; index < requested_count; index++)
   {
      string symbol = requested[index];
      StringTrimLeft(symbol);
      StringTrimRight(symbol);
      StringToUpper(symbol);
      if(index > 0)
         requested_json += ",";
      requested_json += JsonEscape(symbol);

      if(symbol == "" || !SymbolSelect(symbol, true))
         continue;

      const string observed_at = UtcIso(TimeGMT());
      if(observed_count > 0)
         symbols_json += ",";
      symbols_json += BuildSymbolJson(symbol, observed_at);
      observed_count++;

      const double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      const double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
      const double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(tick_size > 0.0 && ask > 0.0 && bid > tick_size)
      {
         if(calculation_count > 0)
         {
            profits_json += ",";
            margins_json += ",";
         }
         profits_json += BuildProfitCase(
            symbol,
            ORDER_TYPE_BUY,
            ask,
            ask + tick_size,
            observed_at
         );
         profits_json += "," + BuildProfitCase(
            symbol,
            ORDER_TYPE_SELL,
            bid,
            bid - tick_size,
            observed_at
         );
         margins_json += BuildMarginCase(symbol, ORDER_TYPE_BUY, ask, observed_at);
         calculation_count++;
      }
   }

   requested_json += "]";
   symbols_json += "]";
   profits_json += "]";
   margins_json += "]";

   string json = "{";
   json += "\"schema_version\":\"1.0\",";
   json += "\"mode\":\"read_only_metadata_probe\",";
   json += "\"source_type\":\"mql5_metadata_probe\",";
   json += "\"acquired_at\":" + JsonEscape(acquired_at) + ",";
   json += "\"broker\":{";
   json += "\"company\":" + JsonEscape(TerminalInfoString(TERMINAL_COMPANY)) + ",";
   json += "\"server\":" + JsonEscape(AccountInfoString(ACCOUNT_SERVER)) + "},";
   json += "\"terminal\":{";
   json += "\"name\":" + JsonEscape(TerminalInfoString(TERMINAL_NAME)) + ",";
   json += "\"build\":" + IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD)) + ",";
   json += "\"version\":null,";
   json += "\"connected\":" + BoolJson((bool)TerminalInfoInteger(TERMINAL_CONNECTED)) + ",";
   json += "\"server_time_raw\":" + JsonEscape(TimeToString(TimeTradeServer(), TIME_DATE | TIME_SECONDS)) + ",";
   json += "\"server_utc_offset_minutes\":null},";
   json += "\"account\":{";
   json += "\"currency\":" + JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)) + ",";
   json += "\"trade_mode_code\":" + IntegerToString((int)AccountInfoInteger(ACCOUNT_TRADE_MODE)) + ",";
   json += "\"leverage\":" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LEVERAGE)) + ",";
   json += "\"margin_mode_code\":" + IntegerToString((int)AccountInfoInteger(ACCOUNT_MARGIN_MODE)) + ",";
   json += "\"trade_allowed\":" + BoolJson((bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) + ",";
   json += "\"automated_trading_allowed\":" + BoolJson((bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) + ",";
   json += "\"account_id_hash\":null},";
   json += "\"requested_symbols\":" + requested_json + ",";
   json += "\"symbols\":" + symbols_json + ",";
   json += "\"profit_calculations\":" + profits_json + ",";
   json += "\"margin_calculations\":" + margins_json;
   json += "}";

   const int handle = FileOpen(OutputFile, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(handle == INVALID_HANDLE)
   {
      Print("Read-only metadata export failed. Error: ", GetLastError());
      return;
   }
   FileWriteString(handle, json);
   FileClose(handle);
   Print("Read-only metadata export complete: ", OutputFile);
}
