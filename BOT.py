import os
import datetime
from time import sleep
import MetaTrader5 as mt5
from module.My_Library import *

if not mt5.initialize():
    print("خطا در اتصال به متاتریدر")
    quit()

lot = 0.01
symbol = "BTCUSD"

strategy = [
    "EMA",
    "GoldenCross",
    "DeathCross",
    "rsi",
    "Cross_kenken_and_kijun",
    "EMA5M",
    "distanse ema",
    "Bollinger Band",
    "Nadayara Watson",
    "VWAP + Bollinger bands",
]

print("ربات اجرا می‌شود...")

while True:
    positions = mt5.positions_get(symbol=symbol)
    active_trades = {st: not has_open_position(symbol, st) for st in strategy}

    if positions:
        for position in positions:
            pos_dict = position._asdict()
            comment = pos_dict.get('comment', '')
            STG_state = active_trades.get(comment, False)

            price_ask = mt5.symbol_info_tick(symbol).ask
            price_bid = mt5.symbol_info_tick(symbol).bid

            # خروج استراتژی: distanse ema
            if comment == "distanse ema" and not STG_state:
                ema_1m_9 = ema_all("1m", 9, symbol)
                if ema_1m_9:
                    target_ema = round(ema_1m_9[-1], 2)
                    if pos_dict["type"] == mt5.ORDER_TYPE_BUY and price_ask >= target_ema:
                        close_order(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, pos_dict["ticket"])
                    elif pos_dict["type"] == mt5.ORDER_TYPE_SELL and price_ask <= target_ema:
                        close_order(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, pos_dict["ticket"])

            # خروج استراتژی: Cross ema 10
            if comment == "Cross ema 10" and not STG_state:
                ema_1m_10 = ema_all("1m", 10, symbol)
                if ema_1m_10:
                    target_ema = round(ema_1m_10[-1], 2)
                    if pos_dict["type"] == mt5.ORDER_TYPE_BUY and price_ask <= target_ema:
                        close_order(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, pos_dict["ticket"])
                    elif pos_dict["type"] == mt5.ORDER_TYPE_SELL and price_ask >= target_ema:
                        close_order(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, pos_dict["ticket"])

            # خروج استراتژی: Bollinger Band
            if comment == "Bollinger Band" and not STG_state:
                lb, ub, sma = bollinger_Band("15m", symbol)
                if lb != 0:
                    if pos_dict["type"] == mt5.ORDER_TYPE_BUY and price_ask >= round(ub, 2):
                        close_order(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, pos_dict["ticket"])
                    elif pos_dict["type"] == mt5.ORDER_TYPE_SELL and price_ask <= round(lb, 2):
                        close_order(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, pos_dict["ticket"])

            # خروج استراتژی: Nadayara Watson
            if comment == "Nadayara Watson" and not STG_state:
                middle, upper, lower = Nadayara_Watson("15m", symbol, -1, -20)
                if upper is not None:
                    if pos_dict["type"] == mt5.ORDER_TYPE_BUY and price_ask >= round(upper[-1], 2):
                        close_order(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, pos_dict["ticket"])
                    elif pos_dict["type"] == mt5.ORDER_TYPE_SELL and price_ask <= round(lower[-1], 2):
                        close_order(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, pos_dict["ticket"])

    times = ["1m", "5m", "15m", "30m", "1h"]
    for time in times:
        price_ask = mt5.symbol_info_tick(symbol).ask
        price_bid = mt5.symbol_info_tick(symbol).bid

        kandels = kandel(time, 30, symbol)
        if kandels.empty:
            continue

        ema9_arr = ema_all(time, 9, symbol)
        ema20_arr = ema_all(time, 20, symbol)
        ema50_arr = ema_all(time, 50, symbol)

        if active_trades["distanse ema"] and time == "1m" and len(ema9_arr) >= 20 and len(ema20_arr) >= 20 and len(ema50_arr) >= 20:
            distance = []
            idx = -1
            for j in range(20):
                v_max = max(ema9_arr[idx], ema20_arr[idx], ema50_arr[idx])
                v_min = min(ema9_arr[idx], ema20_arr[idx], ema50_arr[idx])
                distance.append(v_max - v_min)
                idx -= 1

            max_dist = max(distance)
            current_dist_minus_1 = max(ema9_arr[-2], ema20_arr[-2], ema50_arr[-2]) - min(ema9_arr[-2], ema20_arr[-2],
                                                                                         ema50_arr[-2])
            current_ema50 = ema(time, 50, symbol)
            current_ema9 = round(ema9_arr[-1], 2)

            if current_dist_minus_1 == max_dist and price_ask < current_ema50 and not (current_ema9 < price_ask < round(current_ema50, 2)) and max_dist >= 1.5 and current_ema9 - price_ask > 0.25:
                sl = price_ask - 1.5
                tp = price_ask + 2.5
                execute_trade(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, sl, tp, "distanse ema")

            elif current_dist_minus_1 == max_dist and price_ask > current_ema50 and not (round(current_ema50, 2) < price_ask < current_ema9) and max_dist >= 1.5 and price_bid - current_ema9 > 0.25:
                sl = price_ask - 1.5
                tp = price_ask + 2.5
                execute_trade(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, sl, tp, "distanse ema")

        if active_trades["EMA"] and time == "1m":
            cross_dir = ema_cross(symbol, time, 9, 20) if 'ema_cross' in globals() else None
            current_ema100 = ema(time, 100, symbol)

            if cross_dir == 'down to up' and price_ask < current_ema100:
                max_ema = max(ema9_arr[-1], ema20_arr[-1])
                if round(ema(time, 50, symbol) - max_ema, 2) >= 1:
                    sl = kandels.iloc[-2]['low']
                    if price_ask - sl <= price_ask - price_bid:
                        sl -= 0.5
                    tp = price_ask + (price_ask - sl)
                    execute_trade(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, sl, tp, 'EMA')

            elif cross_dir == 'up to down' and price_ask > current_ema100:
                min_ema = min(ema9_arr[-1], ema20_arr[-1])
                if round(min_ema - ema(time, 50, symbol), 2) >= 1:
                    sl = kandels.iloc[-2]['high']
                    if sl - price_bid <= price_ask - price_bid:
                        sl += 0.5
                    tp = price_bid - (sl - price_bid)
                    execute_trade(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, sl, tp, 'EMA')

        if positions:
            for pos in positions:
                pos_dict = pos._asdict()
                if pos_dict["comment"] == "EMA":
                    # Buy Risk Free
                    if pos_dict["type"] == mt5.ORDER_TYPE_BUY:
                        if ((pos_dict["price_open"] - pos_dict["sl"]) * 0.5) <= (price_ask - pos_dict["price_open"]):
                            modify_position(pos_dict["ticket"], pos_dict["price_open"], pos_dict["tp"])
                    # Sell Risk Free
                    elif pos_dict["type"] == mt5.ORDER_TYPE_SELL:
                        if ((pos_dict["sl"] - pos_dict["price_open"]) * 0.5) <= (pos_dict["price_open"] - price_ask):
                            modify_position(pos_dict["ticket"], pos_dict["price_open"], pos_dict["tp"])

        if active_trades["EMA5M"] and time == "5m":
            cross_dir = ema_cross(symbol, time, 9, 15) if 'ema_cross' in globals() else None
            if cross_dir == 'down to up':
                sl = price_bid - 2
                tp = price_ask + (price_ask - sl)
                execute_trade(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, sl, tp, 'EMA5M')
            elif cross_dir == 'up to down':
                sl = price_bid + 2
                tp = price_bid - (sl - price_bid)
                execute_trade(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, sl, tp, 'EMA5M')

        if time == "15m":
            cross_dir = ema_cross(symbol, "15m", 50, 200) if 'ema_cross' in globals() else None
            is_market_active = check_time(7, 16) or check_time(12, 21)

            if active_trades["GoldenCross"] and cross_dir == "down to up" and whatKandel("15m", -2,
                                                                                         symbol) == "long" and is_market_active:
                sl = kandels.iloc[-2]['low']
                tp = price_ask + (price_ask - sl)
                execute_trade(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, sl, tp, "GoldenCross")

            if active_trades["DeathCross"] and cross_dir == "up to down" and whatKandel("15m", -2,
                                                                                        symbol) == "short" and is_market_active:
                sl = kandels.iloc[-2]['high']
                tp = price_ask - (sl - price_ask)
                execute_trade(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, sl, tp, "DeathCross")

        if time == "15m":
            lb, ub, sma = bollinger_Band(time, symbol)
            if lb != 0:
                if active_trades["Bollinger Band"] and lb > kandels.iloc[-2]["close"] and not (lb > kandels.iloc[-3]["close"]):
                    sl = price_ask - 100
                    tp = price_ask + 100
                    execute_trade(symbol, lot, mt5.ORDER_TYPE_BUY, price_ask, sl, tp, "Bollinger Band")
                elif active_trades["Bollinger Band"] and lb < kandels.iloc[-2]["close"] and not (lb < kandels.iloc[-3]["close"]):
                    sl = price_ask + 100
                    tp = price_ask - 100
                    execute_trade(symbol, lot, mt5.ORDER_TYPE_SELL, price_bid, sl, tp, "Bollinger Band")

            if positions:
                for pos in positions:
                    pos_dict = pos._asdict()
                    if pos_dict["comment"] == "Bollinger Band":
                        if pos_dict["type"] == mt5.ORDER_TYPE_BUY and price_ask >= sma:
                            modify_position(pos_dict["ticket"], sma, pos_dict["tp"])
                        elif pos_dict["type"] == mt5.ORDER_TYPE_SELL and price_ask <= sma:
                            modify_position(pos_dict["ticket"], sma, pos_dict["tp"])

    sleep(1)