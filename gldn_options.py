from config import ALPACA_CONFIG
from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OptionsTrend(Strategy):
    def initialize(self):
        self.symbols = ["NOW"]  # List of underlying tickers
        self.sleeptime = "1S"
        self.contracts_per_trade = 1  # Total number of contracts per trade
        self.minimum_volume = 100000  # Minimum trading volume requirement
        self.ema_short = 13  # Adjustable short-term EMA (13 periods)
        self.ema_long = 48  # Adjustable long-term EMA (48 periods)
        self.ema_200 = 200  # Long-term EMA (200 periods)
        self.atr_multiplier = 1.5  # ATR multiplier for the stop-loss calculation
        self.expiry_date = "2024-05-31"  # Set the expiry date for options contracts
        self.strike_price_offset = 1  # Offset from the current price
        self.rsi_period = 14  # RSI period
        self.rsi_overbought = 70  # RSI overbought threshold
        self.rsi_oversold = 30  # RSI oversold threshold
        self.macd_short = 12  # MACD short-term EMA
        self.macd_long = 26  # MACD long-term EMA
        self.macd_signal = 9  # MACD signal line period
        self.stop_loss = {}  # Dictionary to hold stop loss prices
        self.take_profit = {}  # Dictionary to hold take profit prices

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
                    np.where(
                        (stock_data[f'{self.ema_short}-day'] < stock_data[f'{self.ema_long}-day']) &
                        (stock_data[f'{self.ema_short}-day'].shift(1) >= stock_data[f'{self.ema_long}-day'].shift(1)) &
                        (stock_data[f'{self.ema_short}-day'] < stock_data[f'{self.ema_200}-day']) &
                        (stock_data[f'{self.ema_long}-day'] < stock_data[f'{self.ema_200}-day']) &
                        (stock_data['RSI'] > self.rsi_oversold) &
                        (stock_data['MACD'] < stock_data['Signal_Line']) &
                        (stock_data['volume'] >= self.minimum_volume),
                        "BUY_PUT",
                        "HOLD"
                    )
                )

                stock_data['Confirm'] = stock_data['Signal'].shift(1)
                signal = stock_data.iloc[-1]['Signal']
                confirm = stock_data.iloc[-1]['Confirm']

                logging.info(f"{symbol}: Detected Signal = {signal}, Confirmed Signal = {confirm}")

                if confirm in ["BUY_CALL", "BUY_PUT"]:
                    open_orders = self.broker.api.get_orders()
                    if any(o.symbol == symbol for o in open_orders):
                        logging.info(f"Skipping {symbol}, open orders found.")
                        continue

                    entry_price = stock_data.iloc[-1]['close']
                    atr = stock_data.iloc[-1]['ATR']
                    if confirm == 'BUY_CALL':
                        strike_price = round(entry_price + self.strike_price_offset, 2)
                        option_type = "call"
                        stop_loss = entry_price * 0.90  # 10% stop loss for calls
                        take_profit = entry_price + 2 * (entry_price - stop_loss)  # 2:1 risk-to-reward ratio
                    elif confirm == 'BUY_PUT':
                        strike_price = round(entry_price - self.strike_price_offset, 2)
                        option_type = "put"
                        stop_loss = entry_price * 1.10  # 10% stop loss for puts
                        take_profit = entry_price - 2 * (stop_loss - entry_price)  # 2:1 risk-to-reward ratio

                    self.stop_loss[symbol] = stop_loss
                    self.take_profit[symbol] = take_profit

                    # Log order details before submission
                    logging.info(f"Order Details - {symbol}: Strike={strike_price}, Expiry={self.expiry_date}, Type={option_type}, Stop Loss={stop_loss}, Take Profit={take_profit}")

                    # Create the options order
                    order = self.create_options_order(symbol, self.contracts_per_trade, 'buy', strike_price, self.expiry_date, option_type)
                    if order:
                        logging.info(f"{confirm} options order submitted for {symbol} with strike at {strike_price} and expiry on {self.expiry_date}")

                # Check stop loss and take profit conditions
                if symbol in self.stop_loss and symbol in self.take_profit:
                    current_price = stock_data.iloc[-1]['close']
                    if confirm == 'BUY_CALL':
                        if current_price <= self.stop_loss[symbol]:
                            logging.info(f"Stop loss hit for {symbol}, selling call option")
                            self.sell_all()
                            del self.stop_loss[symbol]
                            del self.take_profit[symbol]
                        elif current_price >= self.take_profit[symbol]:
                            logging.info(f"Take profit hit for {symbol}, selling call option")
                            self.sell_all()
                            del self.stop_loss[symbol]
                            del self.take_profit[symbol]
                    elif confirm == 'BUY_PUT':
                        if current_price >= self.stop_loss[symbol]:
                            logging.info(f"Stop loss hit for {symbol}, selling put option")
                            self.sell_all()
                            del self.stop_loss[symbol]
                            del self.take_profit[symbol]
                        elif current_price <= self.take_profit[symbol]:
                            logging.info(f"Take profit hit for {symbol}, selling put option")
                            self.sell_all()
                            del self.stop_loss[symbol]
                            del self.take_profit[symbol]

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
