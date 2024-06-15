from config import ALPACA_CONFIG
from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd
import logging


class OpenRangeBreakout(Strategy):
    def initialize(self):
        self.tickers = ["GME", "MRNA"]  # List of tickers
        self.sleeptime = "1S"
        self.ema_short = 9  # 9-period EMA
        self.ema_long = 20  # 20-period EMA
        self.open_range_minutes = 30  # First 30 minutes for the opening range
        self.min_volume = 100000  # Minimum trading volume
        self.risk_reward_ratio = 2  # 2:1 risk-reward ratio

        # Initialize to keep track of opening ranges for each ticker
        self.open_range_breakout = {}

    def calculate_opening_range(self, symbol):
        """Calculate the opening range (high/low) for the specified symbol."""
        bars = self.get_historical_prices(symbol, self.open_range_minutes, "minute")
        if bars.df.empty:
            return None

        # Calculate the high and low of the opening range
        opening_range_high = bars.df['high'].max()
        opening_range_low = bars.df['low'].min()

        return opening_range_high, opening_range_low

    def on_trading_iteration(self):
        for symbol in self.tickers:
            # Fetch daily data
            bars = self.get_historical_prices(symbol, 22, "day")
            data = bars.df

            # Calculate EMAs
            data[f'{self.ema_short}-day'] = data['close'].ewm(span=self.ema_short, adjust=False).mean()
            data[f'{self.ema_long}-day'] = data['close'].ewm(span=self.ema_long, adjust=False).mean()

            # Check volume condition
            last_volume = data.iloc[-1]['volume']
            if last_volume < self.min_volume:
                print(f"Skipping trade for {symbol} due to insufficient volume: {last_volume}")
                continue

            # Determine the opening range if not already done for the day
            if symbol not in self.open_range_breakout:
                opening_range = self.calculate_opening_range(symbol)
                if opening_range:
                    self.open_range_breakout[symbol] = opening_range
                else:
                    logging.info(f"Unable to calculate opening range for {symbol}")
                    continue

            opening_range_high, opening_range_low = self.open_range_breakout[symbol]
            latest_price = data.iloc[-1]['close']
            short_ema = data.iloc[-1][f'{self.ema_short}-day']
            long_ema = data.iloc[-1][f'{self.ema_long}-day']

            # Determine the breakout signal
            if latest_price > opening_range_high and short_ema > long_ema:
                signal = 'BUY'
            elif latest_price < opening_range_low and short_ema < long_ema:
                signal = 'SELL'
            else:
                signal = None

            # Log the detected signal
            logging.info(f"{symbol}: Detected Signal = {signal}")

            # Execute the detected signal
            quantity = 100  # Adjust this value as needed
            if signal == 'BUY':
                pos = self.get_position(symbol)
                if pos is not None:
                    self.sell_all()

                order = self.create_order(symbol, quantity, "buy")
                self.submit_order(order)

            elif signal == 'SELL':
                pos = self.get_position(symbol)
                if pos is not None:
                    self.sell_all()

                order = self.create_order(symbol, quantity, "sell")
                self.submit_order(order)


if __name__ == "__main__":
    trade = True  # If true, will trade
    if trade:
        broker = Alpaca(ALPACA_CONFIG)
        strategy = OpenRangeBreakout(broker=broker)
        bot = Trader()
        bot.add_strategy(strategy)
        bot.run_all()
    else:
        start = datetime(2022, 4, 15)
        end = datetime(2023, 4, 15)
        OpenRangeBreakout.backtest(
            YahooDataBacktesting,
            start,
            end
        )
