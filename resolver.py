from collections import deque

def trade(records: list[str], debug = False) -> tuple[int,int,int]:
    '''
    Resolves the records of a trading order book.

    Inputs trades in the form:
        [ stock_name [order size price [...]] ]

    For example
        [ APPL BUY 100 400 ]
        [ GOOG BUY 50 200 SELL 50 250 ]

    Records are assumed to be chronological, and whenever a match is input into the log,
    attempts are immediately made to resolve the order.
    '''
    # Write your code here
    order_book = OrderBook()

    for record in records:
        process_order(order_book, record)

    longExposure = order_book.get_position_value('long')
    shortExposure = order_book.get_position_value('short')

    if debug:
        print(order_book.positions['long'])
        print(order_book.positions['short'])
        print(order_book.market)

    return (order_book.profit, longExposure, shortExposure)

class OrderBook:
    def __init__(self):
        self.profit = 0

        # Positions : { stock : { price : quantity } }
        self.positions = {"long": {}, "short": {}}

        # Market : { stock : deque([ [ price, quantity, timestamp, is_internal ] ]) }
        self.market = {"offers": {}, "buys": {}, "sells": {}, "bids": {}}

        self._stock_list = set()
        self.timestamp = 0

    def get_position_value(self, position_type):
        total_value = 0
        for portfolio in self.positions[position_type].values():
            total_value += sum(int(price) * int(quantity) for price, quantity in portfolio.items())
        return total_value

    def process_order(self, stock_symbol, order_type, quantity, price):
        if stock_symbol not in self._stock_list:
            self._add_stock(stock_symbol)

        order_function = {
            'BUY': self.process_buy,
            'SELL': self.process_sell,
            'BID': self.process_bid,
            'OFFER': self.process_offer
        }.get(order_type)

        if order_function:
            order_function(stock_symbol, quantity, price)
        
        # increment timestamp to keep track of chronology
        self.timestamp += 1

    def process_buy(self, stock, quantity, price):
        sells = list(self.market["sells"].get(stock, deque()))
        offers = list(self.market["offers"].get(stock, deque()))

        # merge sells and offers to treat them as the same 'order type' on the market
        # as we have the is_internal flag, we can retrieve which 'bag' they're from later
        # for the profit calculations
        combined_orders = sorted(sells + offers, key=lambda x: (x[0], x[3], x[2]))  # Sort by price, is_internal, then timestamp

        while quantity > 0 and combined_orders:
            order_price, order_quantity, order_timestamp, is_internal = combined_orders[0]
            if order_price <= price:
                trade_quantity = min(quantity, order_quantity)

                # pretty sure there is some link between is_internal and the result
                # of this expression, it may better to rely on is_internal than generating
                # these short or long strings.
                # TODO
                position_type = "short" if [order_price, order_quantity, order_timestamp, is_internal] in sells else "long"
                self._remove_from_position(position_type, stock, order_price, trade_quantity)
                bag = 'sells' if position_type == 'short' else 'offers'

                # dont make profit if its an internal trade
                if not is_internal:
                    self.profit += (price - order_price) * trade_quantity

                self.market[bag][stock][0][1] -= trade_quantity
                if self.market[bag][stock][0][1] == 0:
                    self.market[bag][stock].popleft()

                quantity -= trade_quantity
                combined_orders.pop(0)
            else:
                break

        if quantity > 0:
            self._add_to_position("long", stock, price, quantity)
            self.market["buys"].setdefault(stock, deque()).append([price, quantity, self.timestamp, True])

    def process_sell(self, stock, quantity, price):
        buys = list(self.market["buys"].get(stock, deque()))
        bids = list(self.market["bids"].get(stock, deque()))
        combined_orders = sorted(buys + bids, key=lambda x: (-x[0], x[2]))

        while quantity > 0 and combined_orders:
            order_price, order_quantity, order_timestamp, is_internal = combined_orders[0]

            if order_price >= price:
                trade_quantity = min(quantity, order_quantity)
                position_type = "long" if [order_price, order_quantity, order_timestamp, is_internal] in buys else "short"
                bag = 'buys' if position_type == 'long' else 'bids'

                self._remove_from_position(position_type, stock, order_price, trade_quantity)

                if not is_internal:
                    self.profit += (order_price - price) * trade_quantity

                self.market[bag][stock][0][1] -= trade_quantity
                if self.market[bag][stock][0][1] == 0:
                    self.market[bag][stock].popleft()

                quantity -= trade_quantity
                combined_orders.pop(0)
            else:
                break

        if quantity > 0:
            self._add_to_position("short", stock, price, quantity)
            self.market["sells"].setdefault(stock, deque()).append([price, quantity, self.timestamp, True])


    def process_offer(self, stock, quantity, price):
        # merge buys to process bids chronologically
        buys = list(self.market["buys"].get(stock, deque()))
        bids = list(self.market["bids"].get(stock, deque()))
        combined_orders = sorted(buys + bids, key=lambda x: (-x[0], x[2]))

        while quantity > 0 and combined_orders:
            buy_price, buy_quantity, buy_timestamp, is_internal = combined_orders[0]
            if buy_price >= price:
                trade_quantity = min(quantity, buy_quantity)
                self._remove_from_position("long", stock, buy_price, trade_quantity)
                bag = 'buys' if is_internal else 'bids'
                
                if is_internal:
                    self.profit += (buy_price - price) * trade_quantity

                self.market[bag][stock][0][1] -= trade_quantity
                if self.market[bag][stock][0][1] == 0:
                    self.market[bag][stock].popleft()

                quantity -= trade_quantity
                combined_orders.pop(0)
            else:
                combined_orders.pop(0)

        if quantity > 0:
            self.market["offers"].setdefault(stock, deque()).append([price, quantity, self.timestamp, False])

    def process_bid(self, stock, quantity, price):
        sells = list(self.market["sells"].get(stock, deque()))
        offers = list(self.market['offers'].get(stock, deque()))
        combined_orders = sorted(sells + offers, key=lambda x: (-x[0], x[2]), reverse=True)

        while quantity > 0 and combined_orders:
            sell_price, sell_quantity, sell_timestamp, is_internal = combined_orders[0]
            if sell_price <= price:
                trade_quantity = min(quantity, sell_quantity)
                self._remove_from_position("short", stock, sell_price, trade_quantity)
                bag = 'sells' if is_internal else 'offers'
                
                if is_internal:
                    self.profit += (price - sell_price) * trade_quantity

                self.market[bag][stock][0][1] -= trade_quantity
                if self.market[bag][stock][0][1] == 0:
                    self.market[bag][stock].popleft()

                quantity -= trade_quantity
                combined_orders.pop(0)
            else:
                combined_orders.pop(0)

        if quantity > 0:
            self.market["bids"].setdefault(stock, deque()).append([price, quantity, self.timestamp, False])

    def _add_to_position(self, position_type, stock, price, quantity):
        position = self.positions[position_type]
        if stock not in position:
            position[stock] = {}
        position[stock][str(price)] = position[stock].get(str(price), 0) + quantity

    def _remove_from_position(self, position_type, stock, price, quantity):
        position = self.positions[position_type]
        if stock in position and str(price) in position[stock]:
            position[stock][str(price)] -= quantity
            if position[stock][str(price)] <= 0:
                del position[stock][str(price)]

    def _add_stock(self, stock):
        for key in self.positions:
            self.positions[key][stock] = {}
        for key in self.market:
            self.market[key][stock] = deque()
        self._stock_list.add(stock)

    @staticmethod
    def _sort_market(orders, reverse=False):
        return sorted(orders, key=lambda x: (x[0], x[2]), reverse=reverse)
    
def process_order(order_book : OrderBook, record):
    components = record.split()
    
    # stock is always the first element
    stock_symbol = components[0]
    
    # The order list starts from element 1 onwards.
    i = 1
    while i < len(components):
        # Handle the order in triples
        order_type = components[i]
        quantity = int(components[i + 1])
        price = int(components[i + 2])
        
        order_book.process_order(stock_symbol, order_type, quantity, price)
        
        # Move to the next triple, the while statement will catch out of range exceptions
        i += 3
    
def process_string_order(order_book : OrderBook, order_string):
    # Split the string by spaces as we know the stock symbol doesn't contain spaces
    parts = order_string.split()

    company = parts[0]
    action = parts[1]
    quantity = int(parts[2])
    price = int(parts[3])

    order_book.process_order(company, action, quantity, price)