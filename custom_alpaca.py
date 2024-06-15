from config import ALPACA_CONFIG
from lumibot.brokers import Alpaca as LumibotAlpaca
from alpaca_trade_api import REST

class CustomAlpaca(LumibotAlpaca):
    def __init__(self, config):
        super().__init__(config)
        self.api = REST(
            self._config['API_KEY'], 
            self._config['API_SECRET'], 
            base_url=self._config['PAPER']
        )

    def get_account(self):
        return self.api.get_account()

    def get_positions(self):
        # Use the correct method to fetch all positions
        return self.api.list_positions()

    # Replace get_orders with list_orders
    def get_orders(self):
        # Use the correct method provided by the Alpaca API
        return self.api.list_orders()