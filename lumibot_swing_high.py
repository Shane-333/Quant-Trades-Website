from config import ALPACA_CONFIG
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy
from lumibot.traders import Trader
import logging
import pandas as pd


# Configure logging to write to a file
logging.basicConfig(filename="trading_bot.log", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SwingHigh(Strategy):
    def initialize(self):
        self.sleeptime = "10S"
        self.symbols = ["JBI", "AMC", "SOUN", "MARA"]
        self.period_high = 13
        self.period_low = 48
        self.ema_200_period = 200
        self.high_data = {symbol: [] for symbol in self.symbols}
        self.low_data = {symbol: [] for symbol in self.symbols}
        self.ema_200 = {symbol: [] for symbol in self.symbols}
        self.ema_13 = {symbol: [] for symbol in self.symbols}
        self.ema_48 = {symbol: [] for symbol in self.symbols}
        self.ready_to_buy = {symbol: False for symbol in self.symbols}

    def calculate_ema(self, prices, period):
        if len(prices) < period:
            return None
        prices_series = pd.Series(prices)
        return prices_series.ewm(span=period, adjust=False).mean().iloc[-1]

    def on_trading_iteration(self):
        for symbol in self.symbols:
            try:
                # Fetch the historical prices with a daily timeframe
                bars = self.get_historical_prices(symbol, 200, "day")
                if bars.df.empty:
                    continue
                
                stock_data = bars.df
                last_price = stock_data['close'].iloc[-1]
                self.high_data[symbol] = stock_data['high'].tolist()
                self.low_data[symbol] = stock_data['low'].tolist()
                
                # Update the 200-day EMA
                new_ema_200 = self.calculate_ema(stock_data['close'].tolist(), self.ema_200_period)
                self.ema_200[symbol].append(new_ema_200)
                if len(self.ema_200[symbol]) > self.ema_200_period:
                    self.ema_200[symbol].pop(0)

                # Update the 13-period EMA
                new_ema_13 = self.calculate_ema(stock_data['close'].tolist(), self.period_high)
                self.ema_13[symbol].append(new_ema_13)
                if len(self.ema_13[symbol]) > self.period_high:
                    self.ema_13[symbol].pop(0)

                # Update the 48-period EMA
                new_ema_48 = self.calculate_ema(stock_data['close'].tolist(), self.period_low)
                self.ema_48[symbol].append(new_ema_48)
                if len(self.ema_48[symbol]) > self.period_low:
                    self.ema_48[symbol].pop(0)

                # Check if 13 EMA crossed above 48 EMA and both are above 200 EMA
                if (len(self.ema_200[symbol]) == self.ema_200_period and 
                    len(self.ema_13[symbol]) == self.period_high and 
                    len(self.ema_48[symbol]) == self.period_low):

                    if (self.ema_13[symbol][-1] > self.ema_48[symbol][-1] and
                        self.ema_13[symbol][-2] <= self.ema_48[symbol][-2] and
                        self.ema_13[symbol][-1] > self.ema_200[symbol][-1] and
                        self.ema_48[symbol][-1] > self.ema_200[symbol][-1]):

                        if not self.get_position(symbol):
                            if self.ready_to_buy[symbol]:
                                # Buy on second confirmation candle
                                stop_loss_price = last_price * 0.90
                                take_profit_price = last_price + 2 * (last_price - stop_loss_price)
                                self.log_message(f"{symbol}: Confirming buy at price: {last_price}, SL: {stop_loss_price}, TP: {take_profit_price}")
                                order = {
                                    'symbol': symbol,
                                    'qty': 1,
                                    'side': 'buy',
                                    'type': 'limit',
                                    'time_in_force': 'day',
                                    'stop_price': stop_loss_price,
                                    'limit_price': take_profit_price
                                }
                                self.submit_order(order)
                                self.ready_to_buy[symbol] = False
                            else:
                                # First candle confirmation
                                self.ready_to_buy[symbol] = True
                    else:
                        self.ready_to_buy[symbol] = False

                # Sell condition
                if self.get_position(symbol) and last_price < min(self.low_data[symbol]):
                    self.log_message(f"{symbol}: Selling at price: {last_price}")
                    self.sell_all(symbol=symbol)
            except Exception as e:
                self.log_message(f"Error processing {symbol}: {str(e)}")

    def before_market_closes(self):
        for symbol in self.symbols:
            if self.get_position(symbol):
                self.sell_all(symbol=symbol)

if __name__ == "__main__":
    broker = Alpaca(ALPACA_CONFIG)
    strategy = SwingHigh(broker=broker)
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()
