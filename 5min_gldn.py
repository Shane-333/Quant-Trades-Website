from config import ALPACA_CONFIG
from datetime import datetime
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd
import logging
import talib
import alpaca_trade_api as tradeapi

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Trend(Strategy):
    def initialize(self):
        self.symbols = ["GME", "MRNA"]  # List of tickers
        self.start = "2022-01-01"
        self.sleeptime = "5S"
        self.shares_per_trade = 100  # Total number of shares per trade
        self.minimum_volume = 100000  # Minimum trading volume requirement
        self.ema_short = 13  # Adjustable short-term EMA (13 periods)
        self.ema_long = 48  # Adjustable long-term EMA (48 periods)
        self.risk_reward_ratio = 2  # Example: 2:1 risk-reward ratio
        self.atr_multiplier = 1.5  # ATR multiplier for the stop-loss calculation
        self.timeframe = tradeapi.TimeFrame(15, tradeapi.TimeFrameUnit.Minute)  # Use 15-minute data for bars
        self.rsi_period = 14  # RSI period
        self.macd_short = 12  # MACD short-term EMA
        self.macd_long = 26  # MACD long-term EMA
        self.macd_signal = 9  # MACD signal line

    def create_bracket_order(self, symbol, qty, side, take_profit_price, stop_loss_price):
        """Create a bracket order with stop loss and take profit, handle errors."""
        try:
            logging.info(f"Creating {side.upper()} bracket order for {symbol}: Qty={qty}, "
                         f"TP={take_profit_price}, SL={stop_loss_price}")

            order = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "market",
                "time_in_force": "day",
                "order_class": "bracket",
                "take_profit": {"limit_price": str(take_profit_price)},
                "stop_loss": {"stop_price": str(stop_loss_price)}
            }
            created_order = self.broker.api.submit_order(**order)
            return created_order
        except Exception as e:
            logging.error(f"Error creating order for {symbol}: {e}")
            return None

    def calculate_atr(self, high, low, close, period=14):
        """Calculate the Average True Range (ATR) using talib."""
        return talib.ATR(high, low, close, timeperiod=period)

    def calculate_rsi(self, close, period=14):
        """Calculate the Relative Strength Index (RSI) using talib."""
        return talib.RSI(close, timeperiod=period)

    def calculate_macd(self, close, fastperiod=12, slowperiod=26, signalperiod=9):
        """Calculate MACD and Signal Line using talib."""
        macd, macdsignal, macdhist = talib.MACD(close, fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)
        return macd, macdsignal

    def on_trading_iteration(self):
        for symbol in self.symbols:
            try:
                # Fetch 15-minute bar data
                bars = self.broker.api.get_bars(
                    symbol=symbol,
                    timeframe=self.timeframe,
                    start=datetime.strptime(self.start, "%Y-%m-%d"),
                    end=datetime.now()
                )

                if bars.empty:
                    logging.info(f"No historical data found for {symbol}")
                    continue

                # Convert the bar data to a DataFrame
                stock_data = bars.df
                stock_data.set_index('timestamp', inplace=True)

                # Apply EMAs over the aggregated 5-minute data
                stock_data[f'{self.ema_short}-period'] = stock_data['close'].ewm(span=self.ema_short, adjust=False).mean()
                stock_data[f'{self.ema_long}-period'] = stock_data['close'].ewm(span=self.ema_long, adjust=False).mean()
                
                # Calculate technical indicators using talib
                stock_data['ATR'] = self.calculate_atr(stock_data['high'], stock_data['low'], stock_data['close'])
                stock_data['RSI'] = self.calculate_rsi(stock_data['close'])
                stock_data['MACD'], stock_data['Signal_Line'] = self.calculate_macd(stock_data['close'])

                # Print out the data used for decision-making
                logging.info(f"{symbol} data for decision:\n{stock_data.tail()}")

                # Generate signals using EMAs
                stock_data['Signal'] = np.where(
                    (stock_data[f'{self.ema_short}-period'] > stock_data[f'{self.ema_long}-period']) &
                    (stock_data[f'{self.ema_short}-period'].shift(1) <= stock_data[f'{self.ema_long}-period'].shift(1)) &
                    (stock_data['volume'] >= self.minimum_volume),
                    "BUY",
                    None
                )

                stock_data['Signal'] = np.where(
                    (stock_data[f'{self.ema_short}-period'] < stock_data[f'{self.ema_long}-period']) &
                    (stock_data[f'{self.ema_short}-period'].shift(1) >= stock_data[f'{self.ema_long}-period'].shift(1)) &
                    (stock_data['volume'] >= self.minimum_volume),
                    "SELL",
                    stock_data['Signal']
                )

                signal = stock_data.iloc[-1]['Signal']
                logging.info(f"{symbol}: Detected Signal = {signal}")

                if signal:
                    open_orders = self.broker.api.get_orders()
                    if any(o.symbol == symbol for o in open_orders):
                        logging.info(f"Skipping {symbol}, open orders found.")
                        continue  # Skip if there are open orders for this symbol

                    entry_price = stock_data.iloc[-1]['close']
                    atr_value = stock_data.iloc[-1]['ATR']
                    if signal == 'BUY':
                        stop_loss_price = round(entry_price - (self.atr_multiplier * atr_value), 2)
                        take_profit_price = round(entry_price + (self.atr_multiplier * atr_value * self.risk_reward_ratio), 2)
                    elif signal == 'SELL':
                        stop_loss_price = round(entry_price + (self.atr_multiplier * atr_value), 2)
                        take_profit_price = round(entry_price - (self.atr_multiplier * atr_value * self.risk_reward_ratio), 2)

                    # Log order details before submission
                    logging.info(f"Order Details - {symbol}: TP at {take_profit_price}, SL at {stop_loss_price}")

                    order = self.create_bracket_order(symbol, self.shares_per_trade, signal.lower(), take_profit_price, stop_loss_price)
                    if order:
                        logging.info(f"{signal} order submitted for {symbol} with TP at {take_profit_price} and SL at {stop_loss_price}")
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")

if __name__ == "__main__":
    broker = Alpaca(ALPACA_CONFIG)
    strategy = Trend(broker=broker)
    bot = Trader()
    bot.add_strategy(strategy)
    bot.run_all()
