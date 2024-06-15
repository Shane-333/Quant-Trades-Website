from config import ALPACA_CONFIG
from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd
import logging


def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(df, short_span=12, long_span=26, signal_span=9):
    short_ema = df['close'].ewm(span=short_span, adjust=False).mean()
    long_ema = df['close'].ewm(span=long_span, adjust=False).mean()

    macd = short_ema - long_ema
    signal = macd.ewm(span=signal_span, adjust=False).mean()
    histogram = macd - signal

    return macd, signal, histogram


class Trend(Strategy):

    def initialize(self):
        self.tickers = ["GME", "SPY", "AAPL"]  # Modify this list to include your desired tickers
        self.sleeptime = "1S"
        self.rsi_period = 14  # Adjust RSI period as necessary
        self.min_volume = 100000  # Minimum trading volume to filter

    def on_trading_iteration(self):
        for symbol in self.tickers:
            # Fetch historical data
            bars = self.get_historical_prices(symbol, 26 + self.rsi_period + 9, "day")
            data = bars.df

            # Calculate Exponential Moving Averages (EMA)
            data['9-day'] = data['close'].ewm(span=9, adjust=False).mean()
            data['21-day'] = data['close'].ewm(span=21, adjust=False).mean()

            # Calculate RSI
            data['RSI'] = calculate_rsi(data, self.rsi_period)

            # Calculate MACD
            data['MACD'], data['Signal Line'], data['MACD Histogram'] = calculate_macd(data)

            # Check volume condition
            last_volume = data.iloc[-1]['volume']
            if last_volume < self.min_volume:
                print(f"Skipping trade for {symbol} due to insufficient volume: {last_volume}")
                continue

            # Define buy and sell signals using EMAs, RSI, and MACD
            data['Signal'] = np.where(
                (data['9-day'] > data['21-day']) & 
                (data['RSI'] < 30) &  # Oversold, signal a buy
                (data['MACD'] > data['Signal Line']),  # MACD line crosses above signal line
                "BUY", None
            )

            data['Signal'] = np.where(
                (data['9-day'] < data['21-day']) & 
                (data['RSI'] > 70) &  # Overbought, signal a sell
                (data['MACD'] < data['Signal Line']),  # MACD line crosses below signal line
                "SELL", data['Signal']
            )

            signal = data.iloc[-1]['Signal']

            quantity = 200
            if signal == 'BUY':
                pos = self.get_position(symbol)
                if pos is not None:
                    self.sell_all(symbol=symbol)

                order = self.create_order(symbol, quantity, "buy")
                self.submit_order(order)

            elif signal == 'SELL':
                pos = self.get_position(symbol)
                if pos is not None:
                    self.sell_all(symbol=symbol)

                order = self.create_order(symbol, quantity, "sell")
                self.submit_order(order)


if __name__ == "__main__":
    trade = False  # If true will trade
    if trade:
        broker = Alpaca(ALPACA_CONFIG)
        strategy = Trend(broker=broker)
        bot = Trader()
        bot.add_strategy(strategy)
        bot.run_all()
    else:
        start = datetime(2022, 4, 15)
        end = datetime(2023, 4, 15)
        Trend.backtest(
            YahooDataBacktesting,
            start,
            end
        )
