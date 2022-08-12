# coding=utf-8
import ccxt
import datetime
import time
import json

COLOR_RESET = "\033[0;0m"
COLOR_GREEN = "\033[0;32m"
COLOR_RED = "\033[1;31m"
COLOR_BLUE = "\033[1;34m"
COLOR_WHITE = "\033[1;37m"
LOGFILE = ""

# amount is the amount of token, not the amount of usd
config = json.dumps({
    "apiKey": "",
    "secret": "",
    "sub_account": "",
    "symbol": "",
    "grid_number": ,
    "lower_price": ,
    "upper_price": ,
    "amount": ,
    'stoploss': ,
    'side': ''})

config = json.loads(config)

exchange = ccxt.ftx({
    'verbose': False,
    'apiKey': config["apiKey"],
    'secret': config["secret"],
    'enableRateLimit': True,
    'headers': {
        'FTX-SUBACCOUNT': config["sub_account"],
    },
})

exchange_markets = exchange.load_markets()


class Oreder_Info:
    def __init__(self):
        self.done = False
        self.side = None
        self.id = 0


class Grid_trader:
    order_list = []

    def __init__(self, exchange, symbol, grid_number=0, lower_price=0.0, upper_price=0.0, amount=0, stop=0, side='long'):
        self.symbol = symbol
        self.exchange = exchange
        self.order_min_inteval = 0.1
        self.grid_number = grid_number
        self.upper_price = upper_price
        self.lower_price = lower_price
        self.totalamount = float(amount)
        self.inteval_profit = (self.upper_price - self.lower_price) / self.grid_number
        self.stop = stop
        self.side = side
        self.amount = 0

        pass

    def place_order_init(self):
        # start cal level and place grid oreder
        for i in range(self.grid_number + 1):  # n+1 lines make n grid
            price = self.lower_price + i * self.inteval_profit
            bid_price, ask_price = self.send_request("get_bid_ask_price")
            order = Oreder_Info()
            if price < ask_price:
                order.id = self.send_request("place_order", "buy", price)
                log("place buy order id = " + str(order.id) + " in " + str(price))
            else:
                order.id = self.send_request("place_order", "sell", price)
                log("place sell order id = " + str(order.id) + " in " + str(price))
            self.order_list.append(order)

    def form_initial_balance(self):
        current_price  =self.exchange.fetch_ticker(self.symbol)['ask']
        if self.side == 'long':
            self.amount = self.totalamount / ((self.upper_price - current_price)/(self.upper_price - self.lower_price)+1) / self.grid_number
            self.exchange.createMarketBuyOrder(self.symbol, (self.upper_price - current_price)/(self.upper_price - self.lower_price)*self.grid_number*self.amount)
        elif self.side == 'short':
            self.amount = self.totalamount / ((current_price - self.lower_price)/(self.upper_price - self.lower_price)+1) /self.grid_number
            self.exchange.createMarketSellOrder(self.symbol, (current_price - self.lower_price) / (self.upper_price - self.lower_price) * self.grid_number * self.amount)
        else:
            pass

    def loop_job(self):
        for order in self.order_list:
            order_info = self.send_request("get_order", order.id)
            side = order_info["side"]
            if order_info["status"] == "closed":
                new_order_price = 0.0
                old_order_id = order_info["id"]
                bid_price, ask_price = self.send_request("get_bid_ask_price")
                msg = side + " order id : " + str(old_order_id) + " : " + str(order_info["price"]) + " completed , put "
                if side == "buy":
                    new_order_price = float(order_info["price"]) + self.inteval_profit
                    order.id = self.send_request("place_order", "sell", new_order_price)
                    msg = msg + "sell"
                    log(msg)
                else:
                    new_order_price = float(order_info["price"]) - self.inteval_profit
                    order.id = self.send_request("place_order", "buy", new_order_price)
                    msg = msg + "buy"
                msg = msg + " order id : " + str(order.id) + " : " + str(new_order_price)
                log(msg)

    def check_liquidation(self):
        (pnl, amount, direction) = self.send_request('get_pnl')
        liquidation = pnl < - self.stop
        if liquidation:
            self.exchange.cancelAllOrders(self.symbol)
            if direction == 'buy':
                self.exchange.createMarketSellOrder(self.symbol, amount)
                log('stoploss')
                exit()
            else:
                self.exchange.createMarketBuyOrder(self.symbol, -float(amount))
                log('stoploss')
                exit()

    def send_request(self, task, input1=None, input2=None):
        tries = 3
        for i in range(tries):
            try:
                if task == "get_bid_ask_price":
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    return ticker["bid"], ticker["ask"]

                elif task == "get_order":
                    return self.exchange.fetchOrder(input1)["info"]

                elif task == "place_order":
                    side = input1
                    price = input2
                    orderid = 0
                    if side == "buy":
                        orderid = self.exchange.create_limit_buy_order(self.symbol, self.amount, price)["info"]["id"]
                    else:
                        orderid = self.exchange.create_limit_sell_order(self.symbol, self.amount, price)["info"]["id"]
                    return orderid

                elif task == 'get_pnl':
                    symbols = [self.symbol]
                    data = self.exchange.fetchPositions(symbols=symbols)[0]
                    pnl = float(data['info']['recentPnl'])
                    balance = self.exchange.fetchBalance()['total']['USD']
                    amount = data['info']['netSize']
                    pnl_percentage = pnl / balance
                    direction = data['info']['side']
                    return pnl_percentage, amount, direction

                else:
                    return None
            except ccxt.NetworkError as e:
                if i < tries - 1:  # i is zero indexed
                    log("NetworkError , try last " + str(i) + "chances" + str(e))
                    time.sleep(0.5)
                    continue
                else:
                    log(str(e))
                    raise
            except ccxt.ExchangeError as e:
                if i < tries - 1:  # i is zero indexed
                    log(str(e))
                    time.sleep(0.5)
                    continue
                else:
                    log(str(e))
                    raise
            break


def log(msg):
    timestamp = datetime.datetime.now().strftime("%b %d %Y %H:%M:%S ")
    s = "[%s] %s:%s %s" % (timestamp, COLOR_WHITE, COLOR_RESET, msg)
    print(s)


main_job = Grid_trader(exchange, config["symbol"], config["grid_number"], config["lower_price"], config["upper_price"],
                       config["amount"], config['stoploss'], config['side'])

main_job.form_initial_balance()
main_job.place_order_init()

while True:
    print("Loop in :", datetime.datetime.now())
    main_job.check_liquidation()
    main_job.loop_job()
    time.sleep(0.5)
