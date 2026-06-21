import json
import os
import datetime
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import pandas_ta as ta
from statsmodels.nonparametric.kernel_regression import KernelReg

TRADE_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trades_history.json')


def save_trade_to_file(trade_record):
    """ذخیره معامله در فایل JSON"""
def save_trade_to_file(trade_record):
    try:
        existing = []
        # بررسی وجود فایل و اینکه حجم آن بزرگتر از صفر بایت باشد
        if os.path.exists(TRADE_LOG_PATH) and os.path.getsize(TRADE_LOG_PATH) > 0:
            with open(TRADE_LOG_PATH, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                
        existing.append(trade_record)
        with open(TRADE_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"خطا در نوشتن فایل: {e}")


def total_positons():
    """تعداد پوزیشن‌های باز"""
    return mt5.positions_total()


def balance():
    """موجودی حساب"""
    account_info = mt5.account_info()
    return account_info.balance if account_info else 0.0


def profit():
    """سود/زیان کل پوزیشن‌ها"""
    positions = mt5.positions_get()
    return sum(position._asdict()['profit'] for position in (positions or []))


def kandel(timeframe='30m', limit=10, symbol='BTCUSD.'):
    """دریافت داده‌های کندل"""
    tf_mapping = {
        '1m': mt5.TIMEFRAME_M1, '3m': mt5.TIMEFRAME_M3, '5m': mt5.TIMEFRAME_M5,
        '15m': mt5.TIMEFRAME_M15, '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1,
        '4h': mt5.TIMEFRAME_H4, '1d': mt5.TIMEFRAME_D1, '1w': mt5.TIMEFRAME_W1
    }
    time = tf_mapping.get(timeframe)

    candles = mt5.copy_rates_from_pos(symbol, time, 0, limit)
    if candles is None or len(candles) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def rsi(timeframe='15m', symbol='BTCUSD.'):
    """محاسبه شاخص RSI"""
    lengths = {"1h": 10, "4h": 8, "1d": 10, "1w": 10, "30m": 10, "15m": 15, "5m": 14, "3m": 14, "1m": 14}
    length = lengths.get(timeframe, 14)

    df = kandel(timeframe, limit=50, symbol=symbol)
    if df.empty:
        return 0

    rsi_series = df.ta.rsi(length=length)
    return rsi_series.iloc[-1] if not rsi_series.dropna().empty else 0


def averagen(timeframe, symbol='BTCUSD.', number=1):
    """میانگین قیمت بستن"""
    df = kandel(timeframe, limit=number, symbol=symbol)
    if df.empty:
        return 0
    return df['close'].mean()


def ema(timeframe, window, symbol):
    """میانگین متحرک نمایی (آخرین مقدار)"""
    df = kandel(timeframe, limit=window * 2, symbol=symbol)
    if df.empty:
        return 0
    df['ema'] = df['close'].ewm(span=window).mean()
    return df['ema'].iloc[-1]


def ema_all(timeframe, window, symbol):
    """تمام مقادیر میانگین متحرک نمایی"""
    df = kandel(timeframe, limit=window * 10, symbol=symbol)
    if df.empty:
        return []
    df['ema'] = df['close'].ewm(span=window).mean()
    return df['ema'].tolist()


def bollinger_Band(timeframe, symbol):
    """باندهای بولینگر (پایین، بالا، وسط)"""
    df = kandel(timeframe, limit=100, symbol=symbol)
    if df.empty:
        return 0, 0, 0

    bbands = df.ta.bbands(length=20, std=2)
    if bbands is None or bbands.empty:
        return 0, 0, 0

    lb_col = [col for col in bbands.columns if col.startswith('BBL_')][0]
    ub_col = [col for col in bbands.columns if col.startswith('BBU_')][0]
    mid_col = [col for col in bbands.columns if col.startswith('BBM_')][0]

    lb = bbands[lb_col].iloc[-1]
    ub = bbands[ub_col].iloc[-1]
    sma = bbands[mid_col].iloc[-1]
    return lb, ub, sma


def ATR(timeframe, symbol, window=14):
    """دامنه واقعی متوسط (ATR)"""
    df = kandel(timeframe, limit=200, symbol=symbol)
    if df.empty:
        return 0
    atr_series = df.ta.atr(length=window)
    return atr_series.iloc[-1] if not atr_series.dropna().empty else 0


def qty(myBalance):
    """تعیین حجم معامله بر اساس موجودی"""
    if myBalance < 300:
        return 0.01
    elif myBalance <= 499:
        return 0.02
    elif myBalance <= 999:
        return 0.03
    elif myBalance <= 1499:
        return 0.04
    elif myBalance <= 1999:
        return 0.05
    elif myBalance <= 2499:
        return 0.06
    elif myBalance <= 2999:
        return 0.07
    elif myBalance <= 3999:
        return 0.08
    elif myBalance <= 5000:
        return 0.09
    else:
        return 0.1


def create_order(symbol, lot, order_type, price, sl=0, tp=0, comment="ربات معامله‌گر"):
    """ایجاد سفارش معامله"""
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": float(sl),
        "tp": float(tp),
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    order = mt5.order_send(request)
    if order is None or order.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"خطا: کد برگشت {order.retcode if order else 'نامشخص'}")
        return None

    print(f"{comment} اجرا شد.")
    return order


def close_order(symbol, lot, order_type, price, ticket):
    """بستن سفارش باز"""
    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    for filling_mode in filling_modes:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "بستن معامله",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            break


def close_all_positions():
    """بستن تمام پوزیشن‌ها"""
    positions = mt5.positions_get()
    if not positions:
        return

    for position in positions:
        pos_dict = position._asdict()
        symbol = pos_dict['symbol']
        ticket = pos_dict['ticket']
        lot = pos_dict['volume']

        if pos_dict['type'] == mt5.ORDER_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        close_order(symbol, lot, order_type, price, ticket)


def close_half_positions():
    """بستن نیمی از پوزیشن‌ها"""
    positions = mt5.positions_get()
    if not positions:
        return

    half_count = len(positions) // 2
    for i, position in enumerate(positions):
        if i >= half_count:
            break

        pos_dict = position._asdict()
        symbol = pos_dict['symbol']
        ticket = pos_dict['ticket']
        lot = pos_dict['volume']

        if pos_dict['type'] == mt5.ORDER_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        close_order(symbol, lot, order_type, price, ticket)


def modify_position(ticket, new_stop_loss, new_take_profite):
    """تغییر سطح حد ضرر و حد سود"""
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return False

    position = position[0]
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": float(new_stop_loss),
        "tp": float(new_take_profite),
        "symbol": position.symbol,
        "type": position.type,
        "volume": position.volume,
    }
    return mt5.order_send(request)


def whatKandel(timeframe='30m', candle=-1, symbol='BTCUSD.'):
    """تعیین نوع شمع (صعودی یا نزولی)"""
    df = kandel(timeframe, limit=abs(candle) + 5, symbol=symbol)
    if df.empty:
        return None
    res = df.iloc[candle]
    return 'نزولی' if res['open'] > res['close'] else 'صعودی'


def body(timeframe, candel, symbol='BTCUSD.'):
    """اندازه بدنه شمع"""
    df = kandel(timeframe, limit=abs(candel) + 5, symbol=symbol)
    if df.empty:
        return 0
    res = df.iloc[candel]
    return abs(res['open'] - res['close'])


def check_time(start_hour, end_hour):
    """بررسی ساعت معاملات (سشن‌های جهانی)"""
    current_time = datetime.datetime.now(datetime.UTC).time()
    if start_hour > end_hour:
        return current_time.hour >= start_hour or current_time.hour <= end_hour
    return start_hour <= current_time.hour <= end_hour


def hemayat(symbol):
    """پیدا کردن سطح حمایت (پایین‌ترین مقاومت زیر قیمت)"""
    kandeld = kandel('1d', 5, symbol)
    kandelw = kandel('1w', 5, symbol)
    kande4h = kandel('4h', 5, symbol)
    kande1h = kandel('1h', 5, symbol)

    if any(df.empty for df in [kandeld, kandelw, kande4h, kande1h]):
        return False

    lines = [
        kandeld.iloc[-2]['high'], kandeld.iloc[-2]['low'],
        kandelw.iloc[-1]['high'], kandelw.iloc[-1]['low'],
        kandelw.iloc[-2]['high'], kandelw.iloc[-2]['low'],
        kande4h.iloc[-2]['high'], kande4h.iloc[-2]['low'],
        kande1h.iloc[-2]['high'], kande1h.iloc[-2]['low']
    ]

    price = mt5.symbol_info_tick(symbol).ask
    valid_lines = [i for i in lines if i < price]
    return max(valid_lines) if valid_lines else False


def moghavemat(symbol):
    """پیدا کردن سطح مقاومت (بالاترین حمایت بالای قیمت)"""
    kandeld = kandel('1d', 5, symbol)
    kandelw = kandel('1w', 5, symbol)
    kande4h = kandel('4h', 5, symbol)
    kande1h = kandel('1h', 5, symbol)

    if any(df.empty for df in [kandeld, kandelw, kande4h, kande1h]):
        return False

    lines = [
        kandeld.iloc[-2]['high'], kandeld.iloc[-2]['low'],
        kandelw.iloc[-1]['high'], kandelw.iloc[-1]['low'],
        kandelw.iloc[-2]['high'], kandelw.iloc[-2]['low'],
        kande4h.iloc[-2]['high'], kande4h.iloc[-2]['low'],
        kande1h.iloc[-2]['high'], kande1h.iloc[-2]['low']
    ]

    price = mt5.symbol_info_tick(symbol).ask
    valid_lines = [i for i in lines if i > price]
    return min(valid_lines) if valid_lines else False


def kijun_sen(symbol, timeframe, num):
    """محاسبه Kijun-sen (میانه اصلی ایچیموکو)"""
    df = kandel(timeframe=timeframe, limit=num, symbol=symbol)
    if df.empty:
        return 0
    mini = df['low'].min()
    maxi = df['high'].max()
    return (maxi + mini) / 2


def Nadayara_Watson(timeframe, symbol, current_candle_index, backcandles, bw=7):
    """رگرسیون Nadaraya-Watson"""
    df = kandel(timeframe, 200 * 20, symbol=symbol)
    if df.empty:
        return None, None, None

    df = df[df["high"] != df["low"]].copy()
    df["EMA_slow"] = ta.ema(df["close"], length=50)
    df["EMA_fast"] = ta.ema(df["close"], length=40)
    df['ATR'] = ta.atr(df["high"], df["low"], df["close"], length=7)
    df.reset_index(inplace=True, drop=True)

    start_index = max(current_candle_index + backcandles, 0)
    dfsample = df[start_index:current_candle_index + 1].copy()
    dfsample.reset_index(drop=True, inplace=True)

    X = dfsample.index.to_numpy()
    model = KernelReg(endog=dfsample['close'].to_numpy(), exog=X, var_type='c', reg_type='lc', bw=[bw])
    fitted_values, _ = model.fit()

    residuals = dfsample['close'] - fitted_values
    std_dev = 2.0 * np.std(residuals)

    middle = fitted_values[:-1]
    upper = middle + std_dev
    lower = middle - std_dev

    return middle, upper, lower


tokyo = check_time(0, 9)
londen = check_time(7, 16)
new_york = check_time(12, 21)
sydney = check_time(22, 5)


def has_open_position(symbol, strategy):
    """بررسی وجود پوزیشن باز برای یک استراتژی"""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return False
    for pos in positions:
        if pos.comment == strategy:
            return True
    return False


def execute_trade(symbol, lot, order_type, price, sl, tp, strategy):
    """اجرای معامله (واقعی یا پیپر)"""
    if has_open_trade_for_strategy(strategy):
        print(f"استراتژی {strategy} از قبل معامله باز دارد")
        return None
    
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
        real_trade = cfg["real_trading"]
    except:
        real_trade = False

    if real_trade:
        return create_order(
            symbol,
            lot,
            order_type,
            price,
            sl,
            tp,
            strategy
        )
    else:
        trade_side = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
        trade_record = {
            "id": str(datetime.datetime.now().timestamp()),
            "symbol": symbol,
            "side": trade_side,
            "volume": lot,
            "entry_price": price,
            "sl": sl,
            "tp": tp,
            "profit": 0,
            "account_type": "تمرین",
            "strategy": strategy,
            "status": "open",
            "timestamp": datetime.datetime.now().isoformat()
        }
        save_trade_to_file(trade_record)
        return trade_record


def cross_kijun_sen(symbol, timeframe):
    """عبور قیمت از Kijun-sen"""
    kandels = kandel(timeframe, 5, symbol)

    mid_prev = (max(kandels[-2]["open"], kandels[-2]["close"]) - min(kandels[-2]["open"], kandels[-2]["close"])) / 2 + min((kandels[-2]["open"], kandels[-2]["close"]))
    mid_curr = (max(kandels[-1]["open"], kandels[-1]["close"]) - min(kandels[-1]["open"], kandels[-1]["close"])) / 2 + min((kandels[-1]["open"], kandels[-1]["close"]))
    kijun = kijun_sen_befor(symbol, timeframe)

    if mid_prev < kijun < mid_curr:
        return "صعودی"
    elif mid_prev > kijun > mid_curr:
        return "نزولی"
    else:
        return False


def cross_sen_4_befor(symbol, timeframe):
    """عبور Senkou Span"""
    kandels1 = kandel(timeframe=timeframe, limit=31, symbol=symbol)
    high = []
    low = []
    i = -3
    for n in range(26):
        high.append(kandels1[i]['high'])
        low.append(kandels1[i]['low'])
        i -= 1
    minis = min(low)
    maxis = max(high)
    sen = (maxis + minis) / 2
    
    highB = []
    lowB = []
    i = -5
    for n in range(26):
        highB.append(kandels1[i]['high'])
        lowB.append(kandels1[i]['low'])
        i -= 1
    minisb = min(lowB)
    maxisb = max(highB)
    senb = (maxisb + minisb) / 2

    kandels2 = kandel(timeframe=timeframe, limit=16, symbol=symbol)
    high2 = []
    low2 = []
    i = -3
    for n in range(9):
        high2.append(kandels2[i]['high'])
        low2.append(kandels2[i]['low'])
        i -= 1
    minik = min(low2)
    maxik = max(high2)
    ken = (maxik + minik) / 2

    highB2 = []
    lowB2 = []
    i = -5
    for n in range(9):
        highB2.append(kandels2[i]['high'])
        lowB2.append(kandels2[i]['low'])
        i -= 1
    minikb = min(lowB2)
    maxikb = max(highB2)
    kenb = (maxikb + minikb) / 2

    if kenb < senb and ken > sen:
        return 0
    if kenb > senb and ken < sen:
        return 1


def kijun_sen_befor(symbol, timeframe, num=26):
    """محاسبه Kijun-sen شمع قبلی"""
    x = num + 2
    kandels = kandel(timeframe=timeframe, limit=x, symbol=symbol)
    high = []
    low = []
    i = -3
    for n in range(num):
        high.append(kandels[i]['high'])
        low.append(kandels[i]['low'])
        i -= 1
    mini = min(low)
    maxi = max(high)
    sen = (maxi + mini) / 2
    return sen


def Senkou_Span_A(symbol, timeframe):
    """محاسبه Senkou Span A"""
    spanA = (kijun_sen(symbol, timeframe, 9) + kijun_sen(symbol, timeframe, 26)) / 2
    return spanA


def Senkou_Span_B(symbol, timeframe):
    """محاسبه Senkou Span B"""
    return kijun_sen(symbol, timeframe, 52)


def ema_cross(symbol, timeframe, ema1, ema2):
    """تشخیص عبور دو EMA"""
    ema1_arr = ema_all(timeframe, ema1, symbol)
    ema2_arr = ema_all(timeframe, ema2, symbol)
    
    if ema1_arr[-2] < ema2_arr[-2] and ema1_arr[-1] > ema2_arr[-1]:
        return "صعودی"
    elif ema1_arr[-2] > ema2_arr[-2] and ema1_arr[-1] < ema2_arr[-1]:
        return "نزولی"
    else:
        return False


def has_open_trade_for_strategy(strategy_name):
    """بررسی وجود معامله باز برای استراتژی"""
    try:
        with open(TRADE_LOG_PATH, "r", encoding="utf-8") as f:
            trades = json.load(f)

        for trade in trades:
            if trade.get("strategy") == strategy_name and trade.get("status") == "open":
                return True

        return False
    except:
        return False