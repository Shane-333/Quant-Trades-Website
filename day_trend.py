from config import ALPACA_CONFIG
from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd
import logging
import talib

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OptionsTrend(Strategy):
    def initialize(self):
        self.symbols = ["NFLX"]  # List of underlying tickers
        self.sleeptime = "1S"
        self.contracts_per_trade = 1  # Total number of contracts per trade
        self.minimum_volume = 100000  # Minimum trading volume requirement
        self.ema_short = 9  # Adjustable short-term EMA (9 periods)
        self.ema_long = 21  # Adjustable long-term EMA (21 periods)
        self.ema_200 = 200  # Long-term EMA (200 periods)
        self.risk_reward_ratio = 2  # Example: 2:1 risk-reward ratio
        self.atr_multiplier = 1.5  # ATR multiplier for the stop-loss calculation
        self.expiry_date = "2024-05-31"  # Set the expiry date for options contracts
        self.strike_price_offset = 1  # Offset from the current price
        self.rsi_period = 14  # RSI period
        self.rsi_overbought = 70  # RSI overbought threshold
        self.rsi_oversold = 30  # RSI oversold threshold
        self.macd_short = 12  # MACD short-term EMA
        self.macd_long = 26  # MACD long-term EMA
        self.macd_signal = 9  # MACD signal line period
        self.trailing_stop = {}  # Dictionary to hold trailing stop prices

    def create_options_order(self, symbol, qty, side, strike_price, expiry_date, option_type):
        """Create an options order with the specified parameters."""
        try:
            logging.info(f"Creating {side.upper()} options order for {symbol}: Qty={qty}, "
                         f"Strike Price={strike_price}, Expiry Date={expiry_date}, Type={option_type}")

            order = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "market",
                "strike": str(strike_price),
                "expiry": expiry_date,
                "option_type": option_type
            }
            # Ensure this matches the broker's expected order format for options
            created_order = self.broker.api.submit_order(**order)
            return created_order
        except Exception as e:
            logging.error(f"Error creating options order for {symbol}: {e}")
            return None

    def calculate_macd(self, data):
        """Calculate MACD and signal lines."""
        macd_line = data['close'].ewm(span=self.macd_short, adjust=False).mean() - data['close'].ewm(span=self.macd_long, adjust=False).mean()
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        return macd_line, signal_line

    def calculate_rsi(self, data, period):
        """Calculate the Relative Strength Index (RSI)."""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, data, period=14):
        """Calculate the Average True Range (ATR) for a given dataset."""
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift(1))
        low_close = abs(data['low'] - data['close'].shift(1))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    def on_trading_iteration(self):
        for symbol in self.symbols:
            try:
                # Fetch historical prices and calculate EMAs
                bars = self.get_historical_prices(symbol, 200, "day")
                if bars.df.empty:
                    logging.info(f"No historical data found for {symbol}")
                    continue

                stock_data = bars.df
                stock_data[f'{self.ema_short}-day'] = stock_data['close'].ewm(span=self.ema_short, adjust=False).mean()
                stock_data[f'{self.ema_long}-day'] = stock_data['close'].ewm(span=self.ema_long, adjust=False).mean()
                stock_data[f'{self.ema_200}-day'] = stock_data['close'].ewm(span=self.ema_200, adjust=False).mean()
                stock_data['ATR'] = self.calculate_atr(stock_data)
                stock_data['RSI'] = self.calculate_rsi(stock_data, self.rsi_period)
                stock_data['MACD'], stock_data['Signal_Line'] = self.calculate_macd(stock_data)

                logging.info(f"{symbol} data for decision:\n{stock_data.tail()}")

                # Generate signals using EMAs, RSI, and MACD
                stock_data['Signal'] = np.where(
                    (stock_data[f'{self.ema_short}-day'] > stock_data[f'{self.ema_long}-day']) &
                    (stock_data[f'{self.ema_short}-day'].shift(1) <= stock_data[f'{self.ema_long}-day'].shift(1)) &
                    (stock_data[f'{self.ema_short}-day'] > stock_data[f'{self.ema_200}-day']) &
                    (stock_data[f'{self.ema_long}-day'] > stock_data[f'{self.ema_200}-day']) &
                    (stock_data['RSI'] < self.rsi_overbought) &
                    (stock_data['MACD'] > stock_data['Signal_Line']) &
                    (stock_data['volume'] >= self.minimum_volume),
                    "BUY_CALL",
                    stock_data['Signal']
                )

                stock_data['Signal'] = np.where(
                    (stock_data[f'{self.ema_short}-day'] < stock_data[f'{self.ema_long}-day']) &
                    (stock_data[f'{self.ema_short}-day'].shift(1) >= stock_data[f'{self.ema_long}-day'].shift(1)) &
                    (stock_data[f'{self.ema_short}-day'] < stock_data[f'{self.ema_200}-day']) &
                    (stock_data[f'{self.ema_long}-day'] < stock_data[f'{self.ema_200}-day']) &
                    (stock_data['RSI'] > self.rsi_oversold) &
                    (stock_data['MACD'] < stock_data['Signal_Line']) &
                    (stock_data['volume'] >= self.minimum_volume),
                    "BUY_PUT",
                    stock_data['Signal']
                )

                signal = stock_data.iloc[-1]['Signal']
                logging.info(f"{symbol}: Detected Signal = {signal}")

                if signal:
                    open_orders = self.broker.api.get_orders()
                    if any(o.symbol == symbol for o in open_orders):
                        logging.info(f"Skipping {symbol}, open orders found.")
                        continue

                    entry_price = stock_data.iloc[-1]['close']
                    atr = stock_data.iloc[-1]['ATR']
                    if signal == 'BUY_CALL':
                        strike_price = round(entry_price + self.strike_price_offset, 2)
                        option_type = "call"
                        stop_loss = entry_price * 0.90  # 10% stop loss for calls
                        self.trailing_stop[symbol] = stop_loss
                    elif signal == 'BUY_PUT':
                        strike_price = round(entry_price - self.strike_price_offset, 2)
                        option_type = "put"
                        stop_loss = entry_price * 1.10  # 10% stop loss for puts
                        self.trailing_stop[symbol] = stop_loss

                    # Log order details before submission
                    logging.info(f"Order Details - {symbol}: Strike={strike_price}, Expiry={self.expiry_date}, Type={option_type}, Stop Loss={stop_loss}")

                    # Create the options order
                    order = self.create_options_order(symbol, self.contracts_per_trade, 'buy', strike_price, self.expiry_date, option_type)
                    if order:
                        logging.info(f"{signal} options order submitted for {symbol} with strike at {strike_price} and expiry on {self.expiry_date}")

                # Check trailing stop condition
                if symbol in self.trailing_stop:
                    current_price = stock_data.iloc[-1]['close']
                    if signal == 'BUY_CALL' and current_price < self.trailing_stop[symbol]:
                        logging.info(f"Trailing stop hit for {symbol}, selling call option")
                        self.sell_all()
                        del self.trailing_stop[symbol]
                    elif signal == 'BUY_PUT' and current_price > self.trailing_stop[symbol]:
                        logging.info(f"Trailing stop hit for {symbol}, selling put option")
                        self.sell_all()
                        del self.trailing_stop[symbol]

            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")

if __name__ == "__main__":
    trade = True  # If true will trade
    if trade:
        broker = Alpaca(ALPACA_CONFIG)
        strategy = OptionsTrend(broker=broker)
        bot = Trader()
        bot.add_strategy(strategy)
        bot.run_all()
    else:
        start = datetime(2022, 4, 15)
        end = datetime(2023, 4, 15)
        OptionsTrend.backtest(
            YahooDataBacktesting,
            start,
            end
        )
