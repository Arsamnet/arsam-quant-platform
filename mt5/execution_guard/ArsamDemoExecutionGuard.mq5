#property copyright "Arsam Quant Platform"
#property strict
#property description "Guarded FIBOGroup DEMO execution boundary. LIVE accounts are always rejected."

input bool   EnableDemoExecution = false;
input string LocalApiBaseUrl = "http://127.0.0.1:8000";
input string ExecutionToken = "";
input string NodeId = "local-demo-node";
input long   MagicNumber = 5050001;
input int    PollIntervalSeconds = 2;
input int    HttpTimeoutMilliseconds = 2000;
input int    MaximumFutureSkewSeconds = 2;
input int    MaximumDeviationPoints = 10;

const string EXPECTED_COMPANY = "FIBO Group, Ltd";
const string EXPECTED_SERVER = "FIBOGroup-MT5 Server";
const string EXPECTED_CURRENCY = "USD";
const long   EXPECTED_LEVERAGE = 100;
const long   REVIEWED_MAGIC_NUMBER = 5050001;
const int    REVIEWED_FUTURE_SKEW_SECONDS = 2;
const int    REVIEWED_DEVIATION_POINTS = 10;
const double HARD_MAX_VOLUME = 0.01;
const int    HARD_MAX_OPEN_POSITIONS = 1;
const string JOURNAL_NAME = "ArsamQuant\\demo-execution-v050.csv";

bool g_busy = false;
bool g_reconciliation_blocked = false;

struct ExecutionWork
  {
   string execution_id;
   string intent_id;
   string request_id;
   string node_id;
   datetime created_at;
   datetime expires_at;
   string symbol;
   string side;
   string order_type;
   double volume;
   double requested_price;
   double stop_loss;
   double take_profit;
   double maximum_spread;
   string risk_fingerprint;
   string request_fingerprint;
   string nonce;
  };

struct JournalRecord
  {
   ExecutionWork work;
   string state;
   string marker;
  };

string IsoTime(const datetime value)
  {
   MqlDateTime parts;
   TimeToStruct(value,parts);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",
                       parts.year,parts.mon,parts.day,parts.hour,parts.min,parts.sec);
  }

datetime ParseIsoTime(string value)
  {
   int fractional=StringFind(value,".");
   if(fractional>=0)
      value=StringSubstr(value,0,fractional);
   StringReplace(value,"T"," ");
   StringReplace(value,"Z","");
   StringReplace(value,"-",".");
   return StringToTime(value);
  }

string JsonEscape(string value)
  {
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r","\\r");
   StringReplace(value,"\n","\\n");
   return value;
  }

bool JsonString(const string json,const string key,string &value)
  {
   string marker="\""+key+"\"";
   int position=StringFind(json,marker);
   if(position<0)
      return false;
   position=StringFind(json,":",position+StringLen(marker));
   if(position<0)
      return false;
   position++;
   while(position<StringLen(json) && StringGetCharacter(json,position)<=32)
      position++;
   if(StringSubstr(json,position,4)=="null")
     {
      value="";
      return true;
     }
   if(StringSubstr(json,position,1)!="\"")
      return false;
   position++;
   int finish=position;
   while(finish<StringLen(json))
     {
      if(StringSubstr(json,finish,1)=="\"" &&
         (finish==position || StringSubstr(json,finish-1,1)!="\\"))
         break;
      finish++;
     }
   if(finish>=StringLen(json))
      return false;
   value=StringSubstr(json,position,finish-position);
   return true;
  }

bool ParseWork(const string json,ExecutionWork &work,string &reason)
  {
   string schema_version,created_text,expires_text,volume_text,price_text;
   string sl_text,tp_text,spread_text;
   if(!JsonString(json,"schema_version",schema_version) || schema_version!="1.0" ||
      !JsonString(json,"execution_id",work.execution_id) ||
      !JsonString(json,"intent_id",work.intent_id) ||
      !JsonString(json,"request_id",work.request_id) ||
      !JsonString(json,"node_id",work.node_id) ||
      !JsonString(json,"created_at",created_text) ||
      !JsonString(json,"expires_at",expires_text) ||
      !JsonString(json,"symbol",work.symbol) ||
      !JsonString(json,"side",work.side) ||
      !JsonString(json,"order_type",work.order_type) ||
      !JsonString(json,"volume",volume_text) ||
      !JsonString(json,"requested_price",price_text) ||
      !JsonString(json,"stop_loss",sl_text) ||
      !JsonString(json,"take_profit",tp_text) ||
      !JsonString(json,"maximum_spread",spread_text) ||
      !JsonString(json,"risk_fingerprint",work.risk_fingerprint) ||
      !JsonString(json,"request_fingerprint",work.request_fingerprint) ||
      !JsonString(json,"nonce",work.nonce))
     {
      reason="malformed_execution_intent";
      return false;
     }
   work.created_at=ParseIsoTime(created_text);
   work.expires_at=ParseIsoTime(expires_text);
   work.volume=StringToDouble(volume_text);
   work.requested_price=StringToDouble(price_text);
   work.stop_loss=StringToDouble(sl_text);
   work.take_profit=StringToDouble(tp_text);
   work.maximum_spread=StringToDouble(spread_text);
   if(work.execution_id=="" || work.intent_id=="" || work.request_id=="" ||
      work.risk_fingerprint=="" || work.request_fingerprint=="" || work.nonce=="")
     {
      reason="missing_execution_identity";
      return false;
     }
   return true;
  }

bool AllowedSymbol(const string symbol)
  {
   return symbol=="EURUSD" || symbol=="GBPUSD" || symbol=="USDJPY";
  }

string CorrelationMarker(const string execution_id)
  {
   string compact=execution_id;
   StringReplace(compact,"-","");
   return "A5-"+StringSubstr(compact,0,24);
  }

bool JournalContains(const string execution_id,const string intent_id,
                     const string nonce,const string fingerprint)
  {
   int handle=FileOpen(JOURNAL_NAME,FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE)
      return false;
   bool duplicate=false;
   while(!FileIsEnding(handle))
     {
      string row_execution=FileReadString(handle);
      string row_intent=FileReadString(handle);
      string row_nonce=FileReadString(handle);
      string row_fingerprint=FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      FileReadString(handle);
      if(row_execution==execution_id || row_intent==intent_id ||
         row_nonce==nonce || row_fingerprint==fingerprint)
        {
         duplicate=true;
         break;
        }
     }
   FileClose(handle);
   return duplicate;
  }

bool AppendJournal(const ExecutionWork &work,const string state,const string marker)
  {
   int handle=FileOpen(JOURNAL_NAME,FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE)
     {
      Print("DEMO EXECUTION BLOCKED: journal unavailable, error=",GetLastError());
      return false;
     }
   FileSeek(handle,0,SEEK_END);
   uint written=FileWrite(handle,work.execution_id,work.intent_id,work.nonce,
                          work.request_fingerprint,state,marker,work.symbol,work.side,
                          DoubleToString(work.volume,8),DoubleToString(work.requested_price,10),
                          DoubleToString(work.stop_loss,10),DoubleToString(work.take_profit,10),
                          IsoTime(TimeGMT()));
   FileFlush(handle);
   FileClose(handle);
   return written>0;
  }

bool BrokerMarkerExists(const string marker,ulong &order_id,ulong &deal_id,
                        double &filled_volume,double &executed_price)
  {
   order_id=0;
   deal_id=0;
   filled_volume=0.0;
   executed_price=0.0;
   for(int index=PositionsTotal()-1;index>=0;index--)
     {
      ulong ticket=PositionGetTicket(index);
      if(ticket==0 || (long)PositionGetInteger(POSITION_MAGIC)!=MagicNumber)
         continue;
      string comment=PositionGetString(POSITION_COMMENT);
      if(StringFind(comment,marker)>=0)
        {
         order_id=(ulong)PositionGetInteger(POSITION_TICKET);
         filled_volume=PositionGetDouble(POSITION_VOLUME);
         executed_price=PositionGetDouble(POSITION_PRICE_OPEN);
         return true;
        }
     }
   for(int index=OrdersTotal()-1;index>=0;index--)
     {
      ulong ticket=OrderGetTicket(index);
      if(ticket==0 || (long)OrderGetInteger(ORDER_MAGIC)!=MagicNumber)
         continue;
      string comment=OrderGetString(ORDER_COMMENT);
      if(StringFind(comment,marker)>=0)
        {
         order_id=ticket;
         filled_volume=OrderGetDouble(ORDER_VOLUME_INITIAL)-OrderGetDouble(ORDER_VOLUME_CURRENT);
         executed_price=OrderGetDouble(ORDER_PRICE_OPEN);
         return true;
        }
     }
   if(!HistorySelect(0,TimeCurrent()))
      return false;
   for(int index=HistoryDealsTotal()-1;index>=0;index--)
     {
      ulong ticket=HistoryDealGetTicket(index);
      if(ticket==0 || (long)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=MagicNumber)
         continue;
      string comment=HistoryDealGetString(ticket,DEAL_COMMENT);
      if(StringFind(comment,marker)>=0)
        {
         deal_id=ticket;
         order_id=(ulong)HistoryDealGetInteger(ticket,DEAL_ORDER);
         filled_volume=HistoryDealGetDouble(ticket,DEAL_VOLUME);
         executed_price=HistoryDealGetDouble(ticket,DEAL_PRICE);
         return true;
        }
     }
   for(int index=HistoryOrdersTotal()-1;index>=0;index--)
     {
      ulong ticket=HistoryOrderGetTicket(index);
      if(ticket==0 || (long)HistoryOrderGetInteger(ticket,ORDER_MAGIC)!=MagicNumber)
         continue;
      string comment=HistoryOrderGetString(ticket,ORDER_COMMENT);
      if(StringFind(comment,marker)>=0)
        {
         order_id=ticket;
         filled_volume=HistoryOrderGetDouble(ticket,ORDER_VOLUME_INITIAL)-
                       HistoryOrderGetDouble(ticket,ORDER_VOLUME_CURRENT);
         executed_price=HistoryOrderGetDouble(ticket,ORDER_PRICE_OPEN);
         return true;
        }
     }
   return false;
  }

int ArsamPositionCount()
  {
   int count=0;
   for(int index=PositionsTotal()-1;index>=0;index--)
     {
      ulong ticket=PositionGetTicket(index);
      if(ticket>0 && (long)PositionGetInteger(POSITION_MAGIC)==MagicNumber)
         count++;
     }
   return count;
  }

bool ValidLoopbackBaseUrl(const string value)
  {
   const string prefix="http://127.0.0.1:";
   if(StringFind(value,prefix)!=0)
      return false;
   string port_text=StringSubstr(value,StringLen(prefix));
   int length=StringLen(port_text);
   if(length<1 || length>5)
      return false;
   for(int index=0;index<length;index++)
     {
      ushort character=StringGetCharacter(port_text,index);
      if(character<48 || character>57)
         return false;
     }
   long port=StringToInteger(port_text);
   return port>=1 && port<=65535 && IntegerToString((int)port)==port_text;
  }

bool ValidateFixedEnvironment(string &reason)
  {
   if(!EnableDemoExecution)
     {
      reason="ea_kill_switch_disabled";
      return false;
     }
   if(MagicNumber!=REVIEWED_MAGIC_NUMBER)
     {
      reason="magic_number_mismatch";
      return false;
     }
   if(!ValidLoopbackBaseUrl(LocalApiBaseUrl) || StringLen(ExecutionToken)<32 || NodeId=="")
     {
      reason="local_transport_not_safely_configured";
      return false;
     }
   if(MaximumFutureSkewSeconds!=REVIEWED_FUTURE_SKEW_SECONDS ||
      MaximumDeviationPoints!=REVIEWED_DEVIATION_POINTS)
     {
      reason="reviewed_timing_or_deviation_policy_mismatch";
      return false;
     }
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      reason="terminal_disconnected";
      return false;
     }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
      !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
     {
      reason="terminal_or_account_trading_not_allowed";
      return false;
     }
   if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO)
     {
      reason="account_is_not_demo";
      return false;
     }
   if(AccountInfoString(ACCOUNT_COMPANY)!=EXPECTED_COMPANY)
     {
      reason="broker_company_mismatch";
      return false;
     }
   if(AccountInfoString(ACCOUNT_SERVER)!=EXPECTED_SERVER)
     {
      reason="broker_server_mismatch";
      return false;
     }
   if(AccountInfoString(ACCOUNT_CURRENCY)!=EXPECTED_CURRENCY)
     {
      reason="account_currency_mismatch";
      return false;
     }
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=
      ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      reason="account_is_not_retail_hedging";
      return false;
     }
   if(AccountInfoInteger(ACCOUNT_LEVERAGE)!=EXPECTED_LEVERAGE)
     {
      reason="account_leverage_mismatch";
      return false;
     }
   return true;
  }

bool Aligned(const double value,const double quantum)
  {
   if(quantum<=0.0)
      return false;
   double normalized=MathRound(value/quantum)*quantum;
   return MathAbs(value-normalized)<=quantum*0.000001;
  }

bool ValidateStopsForTick(const ExecutionWork &work,const MqlTick &tick,string &reason)
  {
   double trigger_price=(work.side=="buy" ? tick.bid : tick.ask);
   if((work.side=="buy" && (work.stop_loss>=trigger_price ||
                             work.take_profit<=trigger_price)) ||
      (work.side=="sell" && (work.stop_loss<=trigger_price ||
                              work.take_profit>=trigger_price)))
     {
      reason="sl_tp_trigger_side_direction_invalid";
      return false;
     }
   long stops_level=SymbolInfoInteger(work.symbol,SYMBOL_TRADE_STOPS_LEVEL);
   long freeze_level=SymbolInfoInteger(work.symbol,SYMBOL_TRADE_FREEZE_LEVEL);
   double minimum_distance=(double)MathMax(stops_level,freeze_level)*
                           SymbolInfoDouble(work.symbol,SYMBOL_POINT);
   if(MathAbs(trigger_price-work.stop_loss)<minimum_distance ||
      MathAbs(work.take_profit-trigger_price)<minimum_distance)
     {
      reason="broker_trigger_side_stops_or_freeze_level_violated";
      return false;
     }
   return true;
  }

bool ValidateWork(const ExecutionWork &work,MqlTick &tick,string &reason)
  {
   datetime now=TimeGMT();
   if(work.node_id!=NodeId || work.order_type!="market")
     {
      reason="node_or_order_type_not_allowed";
      return false;
     }
   if(!AllowedSymbol(work.symbol) || (work.side!="buy" && work.side!="sell"))
     {
      reason="symbol_or_side_not_allowed";
      return false;
     }
   double reviewed_max_spread=(work.symbol=="USDJPY" ? 0.050 : 0.00050);
   if(work.maximum_spread<=0.0 || work.maximum_spread>reviewed_max_spread)
     {
      reason="intent_spread_policy_exceeds_reviewed_limit";
      return false;
     }
   if(work.created_at<=0 || work.expires_at<=0 || now>=work.expires_at ||
      work.created_at>now+MaximumFutureSkewSeconds)
     {
      reason="execution_intent_expired_or_future";
      return false;
     }
   if(StringLen(work.nonce)<16 || JournalContains(work.execution_id,work.intent_id,
                                                  work.nonce,work.request_fingerprint))
     {
      reason="duplicate_execution_identity";
      return false;
     }
   if(!SymbolSelect(work.symbol,true) ||
      (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(work.symbol,SYMBOL_TRADE_MODE)!=SYMBOL_TRADE_MODE_FULL)
     {
      reason="symbol_not_trade_enabled";
      return false;
     }
   double volume_min=SymbolInfoDouble(work.symbol,SYMBOL_VOLUME_MIN);
   double volume_max=SymbolInfoDouble(work.symbol,SYMBOL_VOLUME_MAX);
   double volume_step=SymbolInfoDouble(work.symbol,SYMBOL_VOLUME_STEP);
   if(work.volume<=0.0 || work.volume>HARD_MAX_VOLUME || work.volume<volume_min ||
      work.volume>volume_max || !Aligned(work.volume-volume_min,volume_step))
     {
      reason="volume_outside_reviewed_grid";
      return false;
     }
   if(work.stop_loss<=0.0 || work.take_profit<=0.0)
     {
      reason="broker_side_sl_tp_required";
      return false;
     }
   double tick_size=SymbolInfoDouble(work.symbol,SYMBOL_TRADE_TICK_SIZE);
   if(work.requested_price<=0.0 || !Aligned(work.requested_price,tick_size) ||
      !Aligned(work.stop_loss,tick_size) || !Aligned(work.take_profit,tick_size))
     {
      reason="sl_tp_tick_alignment_invalid";
      return false;
     }
   if(!SymbolInfoTick(work.symbol,tick))
     {
      reason="current_tick_unavailable";
      return false;
     }
   double spread=tick.ask-tick.bid;
   if(work.maximum_spread<=0.0 || spread<0.0 || spread>work.maximum_spread)
     {
      reason="spread_limit_exceeded";
      return false;
     }
   if(!ValidateStopsForTick(work,tick,reason))
      return false;
   if(ArsamPositionCount()>=HARD_MAX_OPEN_POSITIONS)
     {
      reason="arsam_position_limit_reached";
      return false;
     }
   return true;
  }

ENUM_ORDER_TYPE_FILLING FillingMode(const string symbol)
  {
   long allowed=SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE);
   if((allowed & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_FOK;
  }

bool HttpRequest(const string method,const string path,const string body,int &status_code,string &response)
  {
   string headers="X-FX-Execution-Token: "+ExecutionToken+"\r\n";
   if(body!="")
      headers+="Content-Type: application/json\r\n";
   char request_data[];
   char response_data[];
   if(body!="")
     {
      int size=StringToCharArray(body,request_data,0,WHOLE_ARRAY,CP_UTF8);
      if(size>0)
         ArrayResize(request_data,size-1);
     }
   string response_headers;
   ResetLastError();
   status_code=WebRequest(method,LocalApiBaseUrl+path,headers,HttpTimeoutMilliseconds,
                          request_data,response_data,response_headers);
   if(status_code<0)
     {
      Print("DEMO transport failed closed, error=",GetLastError());
      response="";
      return false;
     }
   response=CharArrayToString(response_data,0,-1,CP_UTF8);
   return true;
  }

bool ReportResult(const ExecutionWork &work,const string status,const uint retcode,
                  const string description,const ulong order_id,const ulong deal_id,
                  const double filled_volume,const double executed_price,
                  const string reconciliation,const string reason,const string endpoint)
  {
   int digits=(int)SymbolInfoInteger(work.symbol,SYMBOL_DIGITS);
   string body="{";
   body+="\"schema_version\":\"1.0\",";
   body+="\"execution_id\":\""+JsonEscape(work.execution_id)+"\",";
   body+="\"intent_id\":\""+JsonEscape(work.intent_id)+"\",";
   body+="\"status\":\""+status+"\",";
   body+="\"broker_retcode\":"+IntegerToString((int)retcode)+",";
   body+="\"broker_retcode_description\":\""+JsonEscape(description)+"\",";
   body+="\"broker_order_id\":"+StringFormat("%I64u",order_id)+",";
   body+="\"broker_deal_id\":"+StringFormat("%I64u",deal_id)+",";
   body+="\"requested_volume\":\""+DoubleToString(work.volume,2)+"\",";
   body+="\"filled_volume\":\""+DoubleToString(filled_volume,2)+"\",";
   body+="\"requested_price\":\""+DoubleToString(work.requested_price,digits)+"\",";
   body+="\"executed_price\":\""+DoubleToString(executed_price,digits)+"\",";
   body+="\"stop_loss\":\""+DoubleToString(work.stop_loss,digits)+"\",";
   body+="\"take_profit\":\""+DoubleToString(work.take_profit,digits)+"\",";
   body+="\"submitted_at\":\""+IsoTime(TimeGMT())+"\",";
   body+="\"executed_at\":\""+IsoTime(TimeGMT())+"\",";
   body+="\"reported_at\":\""+IsoTime(TimeGMT())+"\",";
   body+="\"symbol\":\""+work.symbol+"\",";
   body+="\"side\":\""+work.side+"\",";
   body+="\"reconciliation_status\":\""+reconciliation+"\",";
   body+="\"reason\":\""+JsonEscape(reason)+"\"}";
   int status_code;
   string response;
   if(!HttpRequest("POST",endpoint,body,status_code,response) || status_code<200 || status_code>=300)
     {
      Print("DEMO result report failed closed for execution_id=",work.execution_id,
            ", http_status=",status_code);
      return false;
     }
   return true;
  }

int FindJournalRecord(JournalRecord &records[],const string execution_id)
  {
   for(int index=0;index<ArraySize(records);index++)
      if(records[index].work.execution_id==execution_id)
         return index;
   return -1;
  }

bool LoadLatestJournal(JournalRecord &records[])
  {
   ArrayResize(records,0);
   int handle=FileOpen(JOURNAL_NAME,FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE)
      return !FileIsExist(JOURNAL_NAME,FILE_COMMON);
   while(!FileIsEnding(handle))
     {
      JournalRecord item;
      item.work.execution_id=FileReadString(handle);
      item.work.intent_id=FileReadString(handle);
      item.work.nonce=FileReadString(handle);
      item.work.request_fingerprint=FileReadString(handle);
      item.state=FileReadString(handle);
      item.marker=FileReadString(handle);
      item.work.symbol=FileReadString(handle);
      item.work.side=FileReadString(handle);
      item.work.volume=StringToDouble(FileReadString(handle));
      item.work.requested_price=StringToDouble(FileReadString(handle));
      item.work.stop_loss=StringToDouble(FileReadString(handle));
      item.work.take_profit=StringToDouble(FileReadString(handle));
      FileReadString(handle);
      if(item.work.execution_id=="")
         continue;
      if(item.work.intent_id=="" || item.work.nonce=="" || item.work.request_fingerprint=="" ||
         item.marker=="" || item.work.symbol=="" || item.work.side=="" ||
         item.work.volume<=0.0 || item.work.requested_price<=0.0 ||
         item.work.stop_loss<=0.0 || item.work.take_profit<=0.0)
        {
         FileClose(handle);
         return false;
        }
      int existing=FindJournalRecord(records,item.work.execution_id);
      if(existing<0)
        {
         int size=ArraySize(records);
         ArrayResize(records,size+1);
         records[size]=item;
        }
      else
         records[existing]=item;
     }
   FileClose(handle);
   return true;
  }

bool StartupReconcile()
  {
   JournalRecord records[];
   if(!LoadLatestJournal(records))
      return false;
   for(int index=0;index<ArraySize(records);index++)
     {
      string state=records[index].state;
      if(state=="rejected_unreported")
        {
         if(!ReportResult(records[index].work,"rejected",0,
                          "recovered pre-submission rejection",0,0,0.0,0.0,
                          "failed","pre-submission rejection recovered after restart",
                          "/v1/demo-execution/result"))
            return false;
         AppendJournal(records[index].work,"rejected",records[index].marker);
         continue;
        }
      if(state!="claimed" && state!="submitted" && state!="unknown" &&
         state!="filled" && state!="partially_filled")
         continue;
      ulong order_id,deal_id;
      double filled_volume,executed_price;
      if(BrokerMarkerExists(records[index].marker,order_id,deal_id,
                            filled_volume,executed_price))
        {
         if(filled_volume<=0.0 || executed_price<=0.0)
           {
            ReportResult(records[index].work,"submitted",0,
                         "matching broker order requires further reconciliation",
                         order_id,deal_id,0.0,0.0,"pending",
                         "broker order found without a confirmed fill",
                         "/v1/demo-execution/reconcile");
            AppendJournal(records[index].work,"submitted",records[index].marker);
            return false;
           }
         if(!ReportResult(records[index].work,"position_confirmed",0,
                          "startup broker identity reconciled",order_id,deal_id,
                          filled_volume,executed_price,
                          "confirmed","restart reconciliation confirmed broker identity",
                          "/v1/demo-execution/reconcile"))
            return false;
         AppendJournal(records[index].work,"position_confirmed",records[index].marker);
        }
      else
        {
         ReportResult(records[index].work,"unknown",0,"startup reconciliation uncertain",
                      0,0,0.0,0.0,"unknown","broker identity not provable after restart",
                      "/v1/demo-execution/reconcile");
         Print("DEMO EXECUTION BLOCKED: unresolved restart identity=",
               records[index].work.execution_id);
         return false;
        }
     }
   return true;
  }

void RejectBeforeSubmission(const ExecutionWork &work,const string reason)
  {
   string marker=CorrelationMarker(work.execution_id);
   AppendJournal(work,"rejected_unreported",marker);
   if(ReportResult(work,"rejected",0,"pre-submission guard rejection",0,0,0.0,0.0,
                   "failed",reason,"/v1/demo-execution/result"))
      AppendJournal(work,"rejected",marker);
   else
      g_reconciliation_blocked=true;
   Print("DEMO execution rejected: ",reason,", execution_id=",work.execution_id);
  }

void ExecuteGuarded(ExecutionWork &work)
  {
   string reason;
   MqlTick tick;
   if(!ValidateFixedEnvironment(reason) || !ValidateWork(work,tick,reason))
     {
      RejectBeforeSubmission(work,reason);
      return;
     }
   string marker=CorrelationMarker(work.execution_id);
   ulong prior_order,prior_deal;
   double prior_volume,prior_price;
   if(BrokerMarkerExists(marker,prior_order,prior_deal,prior_volume,prior_price))
     {
      if(prior_volume<=0.0 || prior_price<=0.0)
        {
         AppendJournal(work,"unknown",marker);
         g_reconciliation_blocked=true;
         ReportResult(work,"unknown",0,"existing broker order is not a confirmed fill",
                      prior_order,prior_deal,0.0,0.0,"unknown",
                      "duplicate submission blocked pending reconciliation",
                      "/v1/demo-execution/reconcile");
         return;
        }
      if(ReportResult(work,"position_confirmed",0,"existing broker identity reconciled",
                      prior_order,prior_deal,prior_volume,prior_price,"confirmed",
                      "duplicate broker submission suppressed","/v1/demo-execution/reconcile"))
         AppendJournal(work,"position_confirmed",marker);
      else
        {
         AppendJournal(work,"unknown",marker);
         g_reconciliation_blocked=true;
        }
      return;
     }
   if(!AppendJournal(work,"claimed",marker))
     {
      RejectBeforeSubmission(work,"durable_journal_unavailable");
      return;
     }

   MqlTradeRequest request={};
   MqlTradeCheckResult check={};
   MqlTradeResult result={};
   request.action=TRADE_ACTION_DEAL;
   request.magic=(ulong)MagicNumber;
   request.symbol=work.symbol;
   request.volume=work.volume;
   request.type=(work.side=="buy" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   request.price=(work.side=="buy" ? tick.ask : tick.bid);
   request.sl=work.stop_loss;
   request.tp=work.take_profit;
   request.deviation=(ulong)MaximumDeviationPoints;
   request.type_filling=FillingMode(work.symbol);
   request.type_time=ORDER_TIME_GTC;
   request.comment=marker;

   double required_margin=0.0;
   if(!OrderCalcMargin(request.type,request.symbol,request.volume,request.price,required_margin) ||
      required_margin<=0.0 || required_margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      RejectBeforeSubmission(work,"margin_preflight_failed");
      return;
     }
   ResetLastError();
   ZeroMemory(check);

   bool check_ok=OrderCheck(request,check);
   int check_error=GetLastError();

   if(!check_ok || check_error!=0 || check.retcode!=0)
     {
      RejectBeforeSubmission(
         work,
         "order_check_failed_local_"+
         IntegerToString(check_error)+
         "_retcode_"+
         IntegerToString((int)check.retcode)+
         "_"+
         check.comment
      );
      return;
     }
   MqlTick final_tick;
   if(!ValidateFixedEnvironment(reason) || TimeGMT()>=work.expires_at ||
      ArsamPositionCount()>=HARD_MAX_OPEN_POSITIONS ||
      !SymbolInfoTick(work.symbol,final_tick) || final_tick.ask-final_tick.bid>work.maximum_spread)
     {
      RejectBeforeSubmission(work,"final_pre_send_guard_failed");
      return;
     }
   if(!ValidateStopsForTick(work,final_tick,reason))
     {
      RejectBeforeSubmission(work,"final_pre_send_"+reason);
      return;
     }
   request.price=(work.side=="buy" ? final_tick.ask : final_tick.bid);
   ResetLastError();
   ZeroMemory(check);

   bool final_check_ok=OrderCheck(request,check);
   int final_check_error=GetLastError();

   if(!final_check_ok || final_check_error!=0 || check.retcode!=0)
     {
      RejectBeforeSubmission(
         work,
         "final_order_check_failed_local_"+
         IntegerToString(final_check_error)+
         "_retcode_"+
         IntegerToString((int)check.retcode)+
         "_"+
         check.comment
      );
      return;
     }
   if(!AppendJournal(work,"submitted",marker))
     {
      g_reconciliation_blocked=true;
      Print("DEMO execution blocked before broker submission: journal transition failed");
      return;
     }

   bool sent=OrderSend(request,result);
   ulong reconciled_order,reconciled_deal;
   double reconciled_volume,reconciled_price;
   bool broker_identity_found=BrokerMarkerExists(marker,reconciled_order,reconciled_deal,
                                                  reconciled_volume,reconciled_price);
   if(sent && (result.retcode==TRADE_RETCODE_DONE || result.retcode==TRADE_RETCODE_DONE_PARTIAL) &&
      broker_identity_found && (result.volume>0.0 || reconciled_volume>0.0))
     {
      string final_status=(result.retcode==TRADE_RETCODE_DONE_PARTIAL ?
                           "partially_filled" : "position_confirmed");
      string reconciliation=(final_status=="position_confirmed" ? "confirmed" : "pending");
      if(ReportResult(work,final_status,result.retcode,result.comment,
                      (result.order>0 ? result.order : reconciled_order),
                      (result.deal>0 ? result.deal : reconciled_deal),
                      (result.volume>0.0 ? result.volume : reconciled_volume),
                      (result.price>0.0 ? result.price : reconciled_price),
                      reconciliation,"broker response captured","/v1/demo-execution/result"))
         AppendJournal(work,final_status,marker);
      else
        {
         AppendJournal(work,"filled",marker);
         g_reconciliation_blocked=true;
        }
      return;
     }

   AppendJournal(work,"unknown",marker);
   g_reconciliation_blocked=true;
   ReportResult(work,"unknown",result.retcode,result.comment,result.order,result.deal,
                result.volume,result.price,"unknown",
                "submission outcome requires manual reconciliation",
                "/v1/demo-execution/result");
   Print("DEMO execution state UNKNOWN; no retry permitted, execution_id=",work.execution_id);
  }

void PollOnce()
  {
   if(g_busy || g_reconciliation_blocked || !EnableDemoExecution)
      return;
   g_busy=true;
   int status_code;
   string response;
   if(HttpRequest("GET","/v1/demo-execution/next","",status_code,response))
     {
      if(status_code==200)
        {
         ExecutionWork work;
         string reason;
         if(ParseWork(response,work,reason))
            ExecuteGuarded(work);
         else
            Print("DEMO malformed work rejected before execution: ",reason);
        }
      else if(status_code==409)
        {
         g_reconciliation_blocked=true;
         Print("DEMO EXECUTION BLOCKED: Python reports reconciliation required");
        }
      else if(status_code!=204)
         Print("DEMO polling failed closed, http_status=",status_code);
     }
   g_busy=false;
  }

int OnInit()
  {
   string reason;
   if(!EnableDemoExecution)
     {
      Comment("ARSAM v0.5.0 — DEMO EXECUTION DISABLED");
      Print("DEMO EXECUTION DISABLED");
     }
   else if(!ValidateFixedEnvironment(reason))
     {
      Comment("ARSAM v0.5.0 — DEMO EXECUTION BLOCKED: ",reason);
      Print("DEMO EXECUTION BLOCKED: ",reason);
      return INIT_FAILED;
     }
   else
     {
      if(!StartupReconcile())
        {
         g_reconciliation_blocked=true;
         Comment("ARSAM v0.5.0 — DEMO EXECUTION BLOCKED: RECONCILIATION REQUIRED");
         Print("DEMO EXECUTION BLOCKED: RECONCILIATION REQUIRED");
        }
      else
        {
         Comment("ARSAM v0.5.0 — DEMO EXECUTION ARMED\nLIVE MODE FORBIDDEN");
         Print("DEMO EXECUTION ARMED; LIVE MODE FORBIDDEN");
        }
     }
   if(PollIntervalSeconds<1 || HttpTimeoutMilliseconds<250 ||
      MaximumFutureSkewSeconds<0 || MaximumDeviationPoints<0)
      return INIT_PARAMETERS_INCORRECT;
   EventSetTimer(PollIntervalSeconds);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

void OnTimer()
  {
   PollOnce();
  }
