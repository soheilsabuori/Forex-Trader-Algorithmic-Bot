import sys
import os
import json
import datetime
import MetaTrader5 as mt5
import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import subprocess

pg.setConfigOptions(antialias=True)


class CandlestickItem(pg.GraphicsObject):
    """رسم کندل ها معاملات"""
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.picture = QtGui.QPicture()
        self.generatePicture()

    def generatePicture(self):
        if not self.data or len(self.data) == 0:
            return
        p = QtGui.QPainter(self.picture)

        w = 40
        if len(self.data) > 1:
            w = (self.data[1][0] - self.data[0][0]) * 0.7

        for t, open_p, high, low, close in self.data:
            p.setPen(pg.mkPen('#7f8c8d', width=1))
            p.drawLine(QtCore.QPointF(t, low), QtCore.QPointF(t, high))

            if open_p > close:
                p.setBrush(pg.mkBrush('#e74c3c'))
                p.setPen(pg.mkPen('#e74c3c', width=1))
            else:
                p.setBrush(pg.mkBrush('#2ecc71'))
                p.setPen(pg.mkPen('#2ecc71', width=1))

            p.drawRect(QtCore.QRectF(t - w/2, open_p, w, close - open_p))
        p.end()

    def paint(self, painter, *args):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        rect = self.picture.boundingRect()
        if rect.isNull():
            return QtCore.QRectF()
        return QtCore.QRectF(rect)


class TradingApp(QtWidgets.QMainWindow):
    """نرم‌افزار اصلی داشبورد معاملات"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bot Dashboard")
        self.resize(1100, 750)

        self.symbol = "BTCUSD"
        self.file_path = "trades_history.json"

        self.bot_process = None
        self.start_bot()

        if not mt5.initialize():
            print("خطا در اتصال به متاتریدر ۵")
            sys.exit(1)

        if not mt5.symbol_select(self.symbol, True):
            print(f"نماد {self.symbol} در متاتریدر یافت نشد")
            sys.exit(1)

        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        main_widget.setStyleSheet("background-color: #1e1e1e;")

        self.header_label = QtWidgets.QLabel("در حال دریافت اطلاعات بازار...")
        self.header_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0; padding: 5px;")

        self.signal_label = QtWidgets.QLabel("آخرین سیگنال: -")
        self.signal_label.setStyleSheet("font-size: 12px; color: #f1c40f; padding: 5px;")
        self.real_trade_checkbox = QtWidgets.QCheckBox("معامله واقعی در MT5")
        self.real_trade_checkbox.setStyleSheet("font-size:12px;color:#2ecc71;")
        self.real_trade_checkbox.stateChanged.connect(self.toggle_real_trading)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addWidget(self.real_trade_checkbox)
        header_layout.addWidget(self.header_label, stretch=1)
        header_layout.addWidget(self.signal_label)
        main_layout.addLayout(header_layout)

        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        top_splitter.setStyleSheet("QSplitter::handle { background-color: #444; }")

        indicator_panel = QtWidgets.QWidget()
        indicator_panel.setMaximumWidth(180)
        indicator_panel.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
        indicator_layout = QtWidgets.QVBoxLayout(indicator_panel)
        indicator_layout.setContentsMargins(8, 8, 8, 8)

        indicator_title = QtWidgets.QLabel("اندیکاتورها")
        indicator_title.setStyleSheet("font-weight: bold; color: #f1c40f; margin-bottom: 6px;")
        indicator_layout.addWidget(indicator_title)

        self.indicator_checkboxes = {}
        for label in ["EMA 9", "EMA 20", "EMA 50", "Bollinger Bands"]:
            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setStyleSheet("color: #e0e0e0;")
            checkbox.stateChanged.connect(self.toggle_indicator)
            indicator_layout.addWidget(checkbox)
            self.indicator_checkboxes[label] = checkbox

        self.indicator_value_label = QtWidgets.QLabel("اندیکاتورهای فعال: -")
        self.indicator_value_label.setStyleSheet("color: #b0d8ff; padding-top: 10px;")
        indicator_layout.addWidget(self.indicator_value_label)
        indicator_layout.addStretch()
        top_splitter.addWidget(indicator_panel)


        indicator_panel.setMaximumWidth(180)
        top_splitter.setSizes([180, 800])
        top_splitter.setStretchFactor(0, 0)
        top_splitter.setStretchFactor(1, 1)

        chart_panel = QtWidgets.QWidget()
        chart_layout = QtWidgets.QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_widget = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        self.graph_widget.setBackground('#2d2d2d')
        self.graph_widget.showGrid(x=True, y=True, alpha=0.25)
        self.graph_widget.setLabel('right', 'قیمت')
        self.graph_widget.setLabel('bottom', 'زمان')
        self.graph_widget.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.graph_widget.scene().sigMouseClicked.connect(self.handle_chart_click)
        chart_layout.addWidget(self.graph_widget)
        top_splitter.addWidget(chart_panel)

        main_layout.addWidget(top_splitter, stretch=3)

        self.ask_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#e74c3c', width=1.5, style=QtCore.Qt.PenStyle.DashLine))
        self.bid_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#2980b9', width=1.5, style=QtCore.Qt.PenStyle.DashLine))
        self.graph_widget.addItem(self.ask_line)
        self.graph_widget.addItem(self.bid_line)
        
        self.candlestick_plot = None
        self.indicator_lines = {}
        self.current_candles = None
        self.trade_marker_items = []
        self.has_initialized_chart = False
        self.footer_container = QtWidgets.QWidget()
        footer_container_layout = QtWidgets.QVBoxLayout(self.footer_container)
        footer_container_layout.setContentsMargins(0, 0, 0, 0)
        footer_container_layout.setSpacing(0)

        self.footer_tabs = QtWidgets.QTabWidget()
        self.footer_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2a2a2a; background-color: #1e1e1e; } "
            "QTabBar::tab { background: #2a2a2a; color: #e0e0e0; padding: 6px 12px; margin-right: 1px; } "
            "QTabBar::tab:selected { background: #1e1e1e; color: #f1c40f; font-weight: bold; }"
        )

        open_panel = QtWidgets.QWidget()
        open_layout = QtWidgets.QVBoxLayout(open_panel)
        open_layout.setContentsMargins(0, 0, 0, 0)
        self.open_trades_table = QtWidgets.QTableWidget()
        self.open_trades_table.setColumnCount(10)
        self.open_trades_table.setHorizontalHeaderLabels([
            'شناسه', 'نماد', 'نوع معامله', 'حجم', 'قیمت ورود',
            'حد ضرر (SL)', 'حد سود (TP)', 'سود/زیان ($)',
            'نوع حساب', 'استراتژی'
        ])
        self.open_trades_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.open_trades_table.setStyleSheet("QTableWidget { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #444; } QHeaderView::section { background-color: #1a1a1a; color: #e0e0e0; font-weight: bold; border: 1px solid #444; } QTableWidget::item { border: 1px solid #444; }")
        open_layout.addWidget(self.open_trades_table)
        self.footer_tabs.addTab(open_panel, "معاملات باز")

        history_panel = QtWidgets.QWidget()
        history_layout = QtWidgets.QVBoxLayout(history_panel)
        history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(11)
        self.history_table.setHorizontalHeaderLabels([
            'شناسه', 'نماد', 'نوع معامله', 'حجم', 'قیمت ورود',
            'قیمت بستن', 'حد ضرر (SL)', 'حد سود (TP)',
            'سود/زیان ($)', 'نوع حساب', 'استراتژی'
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.history_table.setStyleSheet("QTableWidget { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #444; } QHeaderView::section { background-color: #1a1a1a; color: #e0e0e0; font-weight: bold; border: 1px solid #444; } QTableWidget::item { border: 1px solid #444; }")
        history_layout.addWidget(self.history_table)
        self.footer_tabs.addTab(history_panel, "تاریخچه")

        footer_container_layout.addWidget(self.footer_tabs)
        main_layout.addWidget(self.footer_container, stretch=2)
        self.footer_tabs.currentChanged.connect(self.update_footer_table_visibility)

        self.open_trades_table.setVisible(True)
        self.history_table.setVisible(False)
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.footer_container)  
        main_splitter.setSizes([500, 200])
        main_splitter.setStretchFactor(0, 1)  
        main_splitter.setStretchFactor(1, 0)  
        main_layout.addWidget(main_splitter)

        self.trades_list = []
        self.load_trades_from_file()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_app)
        self.timer.start(1000)

    def load_trades_from_file(self):
        """بارگذاری معاملات از فایل"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.trades_list = json.load(f)
            except Exception:
                self.trades_list = []
        else:
            self.trades_list = []

        for trade in self.trades_list:
            trade.setdefault('status', 'open')
            trade.setdefault('close_price', None)
            trade.setdefault('close_time', None)
            trade.setdefault('strategy', '')
            trade.setdefault('account_type', 'Virtual (App)')
            trade.setdefault('profit', 0.0)

        self.refresh_table_gui()

    # def save_new_trade(self, trade_id, symbol, side, volume, price, sl, tp, account_type, strategy=""):
    #     """ثبت معامله جدید"""
    #     new_trade = {
    #         "id": str(trade_id),
    #         "symbol": symbol,
    #         "side": side,
    #         "volume": float(volume),
    #         "entry_price": float(price),
    #         "sl": float(sl),
    #         "tp": float(tp),
    #         "profit": 0.0,
    #         "account_type": account_type,
    #         "strategy": strategy,
    #         "status": "open",
    #         "close_price": None,
    #         "close_time": None,
    #         "timestamp": datetime.datetime.now().isoformat(timespec='seconds')
    #     }
    #     self.trades_list.append(new_trade)
    #     self.save_to_disk()
    #     self.refresh_table_gui()

    def save_to_disk(self):
        """ذخیره معاملات روی فایل"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.trades_list, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"خطا در نوشتن فایل: {e}")

    def refresh_table_gui(self):
        """به‌روزرسانی نمایش جداول"""
        self.open_trades_table.setRowCount(0)
        self.history_table.setRowCount(0)

        open_rows = 0
        history_rows = 0
        for trade in self.trades_list:
            if trade.get('status') == 'closed':
                self.history_table.insertRow(history_rows)
                self.history_table.setItem(history_rows, 0, QtWidgets.QTableWidgetItem(str(trade.get('id', ''))))
                self.history_table.setItem(history_rows, 1, QtWidgets.QTableWidgetItem(str(trade.get('symbol', ''))))
                self.history_table.setItem(history_rows, 2, QtWidgets.QTableWidgetItem(str(trade.get('side', ''))))
                self.history_table.setItem(history_rows, 3, QtWidgets.QTableWidgetItem(str(trade.get('volume', ''))))
                self.history_table.setItem(history_rows, 4, QtWidgets.QTableWidgetItem(str(trade.get('entry_price', ''))))
                self.history_table.setItem(history_rows, 5, QtWidgets.QTableWidgetItem(str(trade.get('close_price', ''))))
                self.history_table.setItem(history_rows, 6, QtWidgets.QTableWidgetItem(str(trade.get('sl', ''))))
                self.history_table.setItem(history_rows, 7, QtWidgets.QTableWidgetItem(str(trade.get('tp', ''))))
                
                profit_val = trade.get('profit', 0)
                p_item = QtWidgets.QTableWidgetItem(f"{profit_val:.2f}")
                p_item.setForeground(QtGui.QBrush(QtGui.QColor('#2ecc71' if profit_val >= 0 else '#e74c3c')))
                self.history_table.setItem(history_rows, 8, p_item)
                self.history_table.setItem(history_rows, 9, QtWidgets.QTableWidgetItem(str(trade.get('account_type', ''))))
                self.history_table.setItem(history_rows, 10, QtWidgets.QTableWidgetItem(str(trade.get('strategy', ''))))
                history_rows += 1
            else:
                self.open_trades_table.insertRow(open_rows)
                self.open_trades_table.setItem(open_rows, 0, QtWidgets.QTableWidgetItem(str(trade.get('id', ''))))
                self.open_trades_table.setItem(open_rows, 1, QtWidgets.QTableWidgetItem(str(trade.get('symbol', ''))))
                self.open_trades_table.setItem(open_rows, 2, QtWidgets.QTableWidgetItem(str(trade.get('side', ''))))
                self.open_trades_table.setItem(open_rows, 3, QtWidgets.QTableWidgetItem(str(trade.get('volume', ''))))
                self.open_trades_table.setItem(open_rows, 4, QtWidgets.QTableWidgetItem(str(trade.get('entry_price', ''))))
                self.open_trades_table.setItem(open_rows, 5, QtWidgets.QTableWidgetItem(str(trade.get('sl', ''))))
                self.open_trades_table.setItem(open_rows, 6, QtWidgets.QTableWidgetItem(str(trade.get('tp', ''))))

                profit_val = trade.get('profit', 0)
                profit_item = QtWidgets.QTableWidgetItem(f"{profit_val:.2f}")
                profit_item.setForeground(QtGui.QBrush(QtGui.QColor('#2ecc71' if profit_val >= 0 else '#e74c3c')))
                self.open_trades_table.setItem(open_rows, 7, profit_item)
                self.open_trades_table.setItem(open_rows, 8, QtWidgets.QTableWidgetItem(str(trade.get('account_type', ''))))
                self.open_trades_table.setItem(open_rows, 9, QtWidgets.QTableWidgetItem(str(trade.get('strategy', ''))))
                open_rows += 1

    def update_app(self):
        """به‌روزرسانی اطلاعات قیمت و نمودار"""
        self.load_trades_from_file()
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.header_label.setText(f"خطا: عدم دریافت دیتای زنده برای {self.symbol}")
            return

        self.header_label.setText(f"نماد: {self.symbol}  |  قیمت خرید (Ask): {tick.ask:.2f}  |  قیمت فروش (Bid): {tick.bid:.2f}")
        self.ask_line.setValue(tick.ask)
        self.bid_line.setValue(tick.bid)

        candles = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, 1000)
        if candles is not None and len(candles) > 0:
            self.current_candles = candles
            formatted_data = [(c['time'], c['open'], c['high'], c['low'], c['close']) for c in candles]
            if self.candlestick_plot is not None:
                self.graph_widget.removeItem(self.candlestick_plot)
            self.candlestick_plot = CandlestickItem(formatted_data)
            self.graph_widget.addItem(self.candlestick_plot)
            if not self.has_initialized_chart:
                self.graph_widget.autoRange()
                self.has_initialized_chart = True

        disk_update_required = False
        for trade in self.trades_list:
            if trade.get('symbol') != self.symbol or trade.get('status') == 'closed':
                continue
            
            current_price = tick.bid if trade.get('side') == 'BUY' else tick.ask
            multiplier = 1 if trade.get('side') == 'BUY' else -1
            trade['profit'] = (current_price - trade.get('entry_price', 0)) * float(trade.get('volume', 0)) * multiplier * 100
            if trade.get('side') == 'BUY':
                if (trade.get('tp', 0) > 0 and current_price >= trade.get('tp')) or (trade.get('sl', 0) > 0 and current_price <= trade.get('sl')):
                    trade['status'] = 'closed'
                    trade['close_price'] = current_price
                    trade['close_time'] = datetime.datetime.now().isoformat(timespec='seconds')
                    disk_update_required = True
            else:
                if (trade.get('sl', 0) > 0 and current_price >= trade.get('sl')) or (trade.get('tp', 0) > 0 and current_price <= trade.get('tp')):
                    trade['status'] = 'closed'
                    trade['close_price'] = current_price
                    trade['close_time'] = datetime.datetime.now().isoformat(timespec='seconds')
                    disk_update_required = True

        if disk_update_required:
            self.save_to_disk()

        self.update_indicator_overlays()
        self.update_trade_markers()

        if self.trades_list:
            latest_trade = self.trades_list[-1]
            strategy = latest_trade.get('strategy', '-')
            side = latest_trade.get('side', '-')
            self.signal_label.setText(f"آخرین سیگنال: {side} | استراتژی: {strategy}")
        else:
            self.signal_label.setText("آخرین سیگنال: -")

        
        self.refresh_table_gui()

    def update_footer_table_visibility(self, index):
        """تغییر تب فوتر"""
        if index == 0:
            self.open_trades_table.setVisible(True)
            self.history_table.setVisible(False)
        elif index == 1:
            self.open_trades_table.setVisible(False)
            self.history_table.setVisible(True)



    def toggle_indicator(self, state):
        self.update_indicator_overlays()

    def handle_chart_click(self, event):
        if event.double() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.reset_zoom()

    def reset_zoom(self):
        if self.current_candles is not None and len(self.current_candles) > 0:
            self.graph_widget.autoRange()
    
    def save_config(self):
        with open("config.json", "w") as f:
            json.dump(
                {
                    "real_trading": self.real_trading
                },
                f
            )

    def toggle_real_trading(self):
        self.real_trading = self.real_trade_checkbox.isChecked()
        self.save_config()

    def update_indicator_overlays(self):
        for item in list(self.indicator_lines.values()):
            try:
                self.graph_widget.removeItem(item)
            except Exception:
                pass
        self.indicator_lines.clear()

        if self.current_candles is None or len(self.current_candles) == 0:
            return

        times = [c['time'] for c in self.current_candles]
        closes = [c['close'] for c in self.current_candles]
        df = pd.DataFrame({'time': times, 'close': closes})
        if self.indicator_checkboxes.get('EMA 9').isChecked():
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            curve = pg.PlotCurveItem(df['time'].tolist(), df['ema9'].tolist(), pen=pg.mkPen('#f39c12', width=1.5))
            self.graph_widget.addItem(curve)
            self.indicator_lines['EMA 9'] = curve

        if self.indicator_checkboxes.get('EMA 20').isChecked():
            df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
            curve = pg.PlotCurveItem(df['time'].tolist(), df['ema20'].tolist(), pen=pg.mkPen('#9b59b6', width=1.2))
            self.graph_widget.addItem(curve)
            self.indicator_lines['EMA 20'] = curve

        if self.indicator_checkboxes.get('EMA 50').isChecked():
            df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
            curve = pg.PlotCurveItem(df['time'].tolist(), df['ema50'].tolist(), pen=pg.mkPen('#1abc9c', width=1.2))
            self.graph_widget.addItem(curve)
            self.indicator_lines['EMA 50'] = curve

        if self.indicator_checkboxes.get('Bollinger Bands').isChecked():
            period = 20
            df['bb_mid'] = df['close'].rolling(window=period).mean()
            df['bb_std'] = df['close'].rolling(window=period).std()
            df['bb_upper'] = df['bb_mid'] + (2 * df['bb_std'])
            df['bb_lower'] = df['bb_mid'] - (2 * df['bb_std'])
            df_clean = df.dropna(subset=['bb_mid', 'bb_upper', 'bb_lower'])
            if not df_clean.empty:
                mid_curve = pg.PlotCurveItem(df_clean['time'].tolist(), df_clean['bb_mid'].tolist(), pen=pg.mkPen('#5dade2', width=1, style=QtCore.Qt.PenStyle.DashLine))
                upper_curve = pg.PlotCurveItem(df_clean['time'].tolist(), df_clean['bb_upper'].tolist(), pen=pg.mkPen('#e67e22', width=1.2))
                lower_curve = pg.PlotCurveItem(df_clean['time'].tolist(), df_clean['bb_lower'].tolist(), pen=pg.mkPen('#e67e22', width=1.2))
                self.graph_widget.addItem(mid_curve)
                self.graph_widget.addItem(upper_curve)
                self.graph_widget.addItem(lower_curve)
                self.indicator_lines['BB_mid'] = mid_curve
                self.indicator_lines['BB_upper'] = upper_curve
                self.indicator_lines['BB_lower'] = lower_curve

        active_indicators = [name for name, cb in self.indicator_checkboxes.items() if cb.isChecked()]
        if active_indicators:
            self.indicator_value_label.setText("اندیکاتورهای فعال: " + ", ".join(active_indicators))
        else:
            self.indicator_value_label.setText("اندیکاتورهای فعال: -")

    def update_trade_markers(self):
        for item in self.trade_marker_items:
            try:
                self.graph_widget.removeItem(item)
            except Exception:
                pass
        self.trade_marker_items.clear()

        if self.current_candles is None or len(self.current_candles) == 0:
            return

        x_anchor = self.current_candles[-1]['time']
        for trade in self.trades_list:
            if trade.get('symbol') != self.symbol or trade.get('status') != 'open':
                continue
            value = trade.get('entry_price', 0)
            color = '#2ecc71' if trade.get('side') == 'BUY' else '#e74c3c'
            line = pg.InfiniteLine(value, angle=0, movable=False, pen=pg.mkPen(color, width=1.2, style=QtCore.Qt.PenStyle.DashLine))
            text = pg.TextItem(f"{trade.get('side', '')} {trade.get('strategy', '')}", color=color)
            text.setPos(x_anchor, value)
            self.graph_widget.addItem(line)
            self.graph_widget.addItem(text)
            self.trade_marker_items.extend([line, text])

    def closeEvent(self, event):
        mt5.shutdown()
        event.accept()
    
    def start_bot(self):
        try:
            self.bot_process = subprocess.Popen(
                ["python", "BOT.py"]
            )
            print("Bot Started")
        except Exception as e:
            print("Bot Start Error:", e)

    def check_trade_file_updates(self):

        try:

            with open("trades_history.json", "r", encoding="utf-8") as f:
                trades = json.load(f)

            current_count = len(trades)

            if current_count != len(self.trades_list):
                self.refresh_table_gui()

        except Exception as e:
            print(e)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = TradingApp()
    window.show()


    sys.exit(app.exec())