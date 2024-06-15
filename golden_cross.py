from config import ALPACA_CONFIG
from datetime import datetime, timedelta
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd



class Trend(Strategy):

    def initialize(self):
        self.tickers = ["JBI", "SPY", "AAPL"]  # Modify this list to include your desired tickers
        self.sleeptime = "1D"
        self.ema_short = 13  # 13-day EMA
        self.ema_long = 48  # 48-day EMA

    def on_trading_iteration(self):
        for symbol in self.tickers:
            # Fetch historical prices for each symbol with the appropriate window size
            bars = self.get_historical_prices(symbol, self.ema_long + 1, "day")
            data = bars.df

            # Calculate short-term (13-day) and long-term (48-day) EMAs
            data[f'{self.ema_short}-day'] = data['close'].rolling(self.ema_short).mean()
            data[f'{self.ema_long}-day'] = data['close'].rolling(self.ema_long).mean()

            # Determine buy and sell signals using the crossover logic
            data['Signal'] = np.where(
                np.logical_and(
                    data[f'{self.ema_short}-day'] > data[f'{self.ema_long}-day'],
                    data[f'{self.ema_short}-day'].shift(1) <= data[f'{self.ema_long}-day'].shift(1)
                ),
                "BUY",
                None
            )
            data['Signal'] = np.where(
                np.logical_and(
                    data[f'{self.ema_short}-day'] < data[f'{self.ema_long}-day'],
                    data[f'{self.ema_short}-day'].shift(1) >= data[f'{self.ema_long}-day'].shift(1)
                ),
                "SELL",
                data['Signal']
            )

            # Get the latest trading signal
            signal = data.iloc[-1]['Signal']
            quantity = 100

            # Execute trades based on the detected signal
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
    trade = True  # If true will trade
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
