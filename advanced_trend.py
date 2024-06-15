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
import alpaca_trade_api as tradeapi


# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Trend(Strategy):
    def initialize(self):
        self.symbols = ["SIX", "HPQ", "TQQQ"]  # List of tickers
        self.start = "2022-01-01"
        self.sleeptime = "1S"
        self.shares_per_trade = 100  # Total number of shares per trade
        self.minimum_volume = 100000  # Minimum trading volume requirement
        self.ema_short = 9  # Adjustable short-term EMA
        self.ema_long = 21  # Adjustable long-term EMA
        self.risk_reward_ratio = 2  # Example: 2:1 risk-reward ratio
        self.atr_multiplier = 1.5  # ATR multiplier for the stop-loss calculation
        self.rsi_period = 14  # RSI period
        self.rsi_threshold_oversold = 30  # RSI oversold threshold
        self.rsi_threshold_overbought = 70  # RSI overbought threshold
        self.macd_short = 12  # MACD short-term EMA
        self.macd_long = 26  # MACD long-term EMA
        self.macd_signal = 9  # MACD signal line

    def create_bracket_order(self, symbol, qty, side, take_profit_price, stop_loss_price):
        """Create a bracket order with stop loss and take profit."""
        try:
            logging.info(f"Creating {side.upper()} bracket order for {symbol}: Qty={qty}, "
                         f"TP={take_profit_price}, SL={stop_loss_price}")

            order = self.create_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type='market',
                time_in_force='day',
                order_class='bracket',
                take_profit={'limit_price': str(take_profit_price)},
                stop_loss={'stop_price': str(stop_loss_price)}
            )
            return order

        except Exception as e:
            logging.error(f"Error creating bracket order for {symbol}: {e}")
            return None

    def calculate_rsi(self, data):
        """Calculate the Relative Strength Index (RSI) using talib."""
        rsi = talib.RSI(data['close'], timeperiod=self.rsi_period)
        return rsi

    def calculate_macd(self, data):
        """Calculate MACD and Signal Line using talib."""
        macd, macdsignal, _ = talib.MACD(data['close'], fastperiod=self.macd_short, slowperiod=self.macd_long, signalperiod=self.macd_signal)
        return macd, macdsignal

    def calculate_atr(self, data):
        """Calculate the Average True Range (ATR) using talib."""
        atr = talib.ATR(data['high'], data['low'], data['close'], timeperiod=14)  # Standard ATR period is 14
        return atr

    def on_trading_iteration(self):
        for symbol in self.symbols:
            try:
                # Fetch historical data with the specified timeframe
                bars = self.get_historical_prices(symbol, 200, "day")
                if bars.df.empty:
                    logging.info(f"No historical data found for {symbol}")
                    continue
                
                stock_data = bars.df
                stock_data[f'{self.ema_short}-day'] = stock_data['close'].ewm(span=self.ema_short, adjust=False).mean()
                stock_data[f'{self.ema_long}-day'] = stock_data['close'].ewm(span=self.ema_long, adjust=False).mean()

                # Calculate RSI
                stock_data['RSI'] = self.calculate_rsi(stock_data)

                # Calculate MACD
                stock_data['MACD'], stock_data['Signal_Line'] = self.calculate_macd(stock_data)

                # Calculate ATR
                stock_data['ATR'] = self.calculate_atr(stock_data)

                # Log the latest data and indicators
                logging.info(f"Latest data for {symbol}:\n{stock_data.tail()}")

                # Generate signals using RSI and MACD
                stock_data['Signal'] = np.where(
                    (stock_data['RSI'] < self.rsi_threshold_oversold) &
                    (stock_data['MACD'] > stock_data['Signal_Line']) &
                    (stock_data[f'{self.ema_short}-day'] > stock_data[f'{self.ema_long}-day']) &
                    (stock_data['volume'] >= self.minimum_volume),
                    "BUY",
                    None
                )

                stock_data['Signal'] = np.where(
                    (stock_data['RSI'] > self.rsi_threshold_overbought) &
                    (stock_data['MACD'] < stock_data['Signal_Line']) &
                    (stock_data[f'{self.ema_short}-day'] < stock_data[f'{self.ema_long}-day']) &
                    (stock_data['volume'] >= self.minimum_volume),
                    "SELL",
                    stock_data['Signal']
                )

                signal = stock_data.iloc[-1]['Signal']
                logging.info(f"{symbol}: Detected Signal = {signal}")

                if signal:
                    open_orders = self.broker.api.get_orders(status='open')
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

                    logging.info(f"Order Details - {symbol}: TP at {take_profit_price}, SL at {stop_loss_price}")

                    order = self.create_bracket_order(symbol, self.shares_per_trade, signal.lower(), take_profit_price, stop_loss_price)
                    if order:
                        try:
                            self.submit_order(order)
                            logging.info(f"{signal} order submitted for {symbol} with TP at {take_profit_price} and SL at {stop_loss_price}")
                        except Exception as e:
                            logging.error(f"Error submitting order for {symbol}: {e}")
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")


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
