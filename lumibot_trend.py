#9/21 Bot
from config import ALPACA_CONFIG
from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import numpy as np
import pandas as pd


class Trend(Strategy):

    def initialize(self):
        self.signals = {}
        self.start = "2022-01-01"
        self.sleeptime = "10S"
        self.tickers = ["AMC", "PG", "AAPL"]  # Add more tickers as needed
        self.ready_to_buy = {symbol: False for symbol in self.tickers}

    def on_trading_iteration(self):
        for symbol in self.tickers:
            # Fetch historical prices for each symbol with the appropriate window size
            bars = self.get_historical_prices(symbol, 22, "day")
            data = bars.df

            # Calculate short-term (9-day) and long-term (21-day) EMAs
            data['9-day'] = data['close'].ewm(span=9, adjust=False).mean()
            data['21-day'] = data['close'].ewm(span=21, adjust=False).mean()

            # Determine buy and sell signals using the 9/21 crossover logic
            data['Signal'] = np.where(
                np.logical_and(
                    data['9-day'] > data['21-day'],
                    data['9-day'].shift(1) <= data['21-day'].shift(1)
                ),
                "BUY",
                None
            )
            data['Signal'] = np.where(
                np.logical_and(
                    data['9-day'] < data['21-day'],
                    data['9-day'].shift(1) >= data['21-day'].shift(1)
                ),
                "SELL",
                data['Signal']
            )

            # Get the latest trading signal for the current symbol
            self.signals[symbol] = data.iloc[-1]['Signal']

            quantity = 100

            # Execute trades based on the detected signal
            if self.signals[symbol] == 'BUY':
                # Check if the second candle after the crossover is bullish
                if self.ready_to_buy[symbol]:
                    last_candle = data.iloc[-1]
                    if last_candle['close'] > last_candle['open']:
                        pos = self.get_position(symbol)
                        if pos is not None:
                            self.sell_all()

                        # Set stop loss at 2% below the buy price
                        stop_loss_price = last_candle['close'] * 0.98
                        # Set take profit at 2 times the stop loss distance above the buy price
                        take_profit_price = last_candle['close'] + 2 * (last_candle['close'] - stop_loss_price)

                        order = self.create_order(symbol, quantity, "buy", stop_price=stop_loss_price, take_profit=take_profit_price)
                        self.submit_order(order)
                    self.ready_to_buy[symbol] = False
                else:
                    self.ready_to_buy[symbol] = True

            elif self.signals[symbol] == 'SELL':
                pos = self.get_position(symbol)
                if pos is not None:
                    self.sell_all()

                order = self.create_order(symbol, quantity, "sell")
                self.submit_order(order)

            # Reset ready_to_buy if no BUY signal on the latest iteration
            if self.signals[symbol] != 'BUY':
                self.ready_to_buy[symbol] = False

    def create_order(self, symbol, quantity, side, stop_price=None, take_profit=None):
        order = {
            "symbol": symbol,
            "qty": quantity,
            "side": side,
            "type": "market",  # Change to "limit" or "stop" as per your requirement
            "time_in_force": "gtc"  # Good till canceled
        }
        if stop_price and take_profit:
            order["stop_loss"] = {
                "stop_price": stop_price
            }
            order["take_profit"] = {
                "price": take_profit
            }
        return order


if __name__ == "__main__":
    trade = True  # If true, will trade
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
