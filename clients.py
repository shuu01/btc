#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  clients.py
#
#  Copyright 2018  <shuu01@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

from aiohttp import BasicAuth, ClientSession
import logging
from time import time
import hmac
import asyncio

class Ccex(object):

    def __init__(self, url, api_url, public_key, secret, timeout=5):

        self.url = url
        self.api_url = api_url
        self.public_key = public_key
        self.secret = secret
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'CCEX_API_WRAPPER'})
        self.timeout = timeout
        self.name = self.__class__.__name__

        self.to_update = {}
        self.is_running = False

        self.balance = {}
        self.orders = []
        self.history = []
        self.prices = {}
        self.total = 0

    def threaded(function):

        def wrapper(*args, **kwargs):

            thread = Thread(target=function, args=args, kwargs=kwargs)
            thread.start()
            return thread

        return wrapper

    def request(self, url, params={}, headers=None, auth=None):

        params.update({'apikey': self.public_key, 'nonce': int(time())})

        req = requests.Request(
                method='GET',
                url=url,
                params=params,
                headers=headers,
                )

        prep_req = req.prepare()

        if auth:
            signature = hmac.new(
            self.secret.encode('utf-8'),
            prep_req.url.encode('utf-8'),
            'sha512',
            ).hexdigest()

            prep_req.headers['apisign'] = signature

        try:
            res = self.session.send(prep_req, timeout=self.timeout)
            return res.json()
        except Exception as e:
            print(e)

    def _run(self):

        self.is_running = False

        self.run(self.interval)

        if self.to_update.get('balance'):
            self.set_balance()

        if self.to_update.get('orders'):
            self.set_orders()

        if self.to_update.get('history'):
            self.set_history()

        if self.to_update.get('prices'):
            self.set_prices(self.to_update.get('prices', []))

        if self.to_update.get('total'):
            base = self.to_update.get('total')
            self.set_total_balance(base)

    def run(self, interval):

        self.interval = interval

        if not self.is_running:
            self.timer = Timer(self.interval, self._run)
            self.timer.start()
            self.is_running = True

    def stop(self):

        self.timer.cancel()

    def update(self, **kwargs):

        self.to_update.update(kwargs)

    def get_names(self):
        ''' Get names for symbols '''
        return self.request("%s/coinnames.json" % (self.api_url))

    def get_prices(self):
        ''' Get prices for pairs'''
        return self.request("%s/prices.json" % (self.api_url))

    def get_pairs(self):
        ''' Get available pairs '''
        res = self.request("%s/pairs.json" % (self.api_url))
        if res:
            return res.get('pairs')

    def get_ticker(self, pair):
        ''' Get ticker for pair '''
        res = self.request("%s/%s.json" % (self.api_url, pair))
        if res:
            return res#.get('ticker')

    def get_balances(self):
        ''' Retrieve all balances from account '''
        res = self.request("%s/api.html" % (self.api_url), params={'a': 'getbalances'}, auth=True)
        if res:
            return res.get('result')

    def get_balance(self, symbol):
        ''' Get balance for symbol '''
        res = self.request("%s/api.html" % (self.api_url), params={'a': 'getbalance', 'currency': symbol}, auth=True)
        if res:
            return res.get('result')

    def get_active_orders(self, pair=None):
        ''' Get active orders '''
        res = self.request("%s/api.html" % (self.api_url), params={'a': 'getopenorders', 'market': pair}, auth=True)
        if res:
            return res.get('result')

    def get_order_history(self, pair=None, count=None):

        res = self.request("%s/api.html" % (self.api_url), params={'a': 'getorderhistory', 'market': pair, 'count': count}, auth=True)
        if res:
            return res.get('result')

    def get_mytrades(self, pair):

        res = self.request("%s/api.html" % (self.api_url), params={'a': 'mytrades', 'marketid': pair}, auth=True)
        if res:
            return res.get('return')

    def __getattr__(self, attr, *args, **kwargs):
        print(attr, args, kwargs)

    @threaded
    def set_balance(self):

        balances = self.get_balances()

        if balances:

            for balance in balances:
                currency = balance['Currency']
                if float(balance['Available']) > 0 or float(balance['Balance']) > 0:
                    self.balance[currency] = {'available': balance['Available'], 'reserved': balance['Balance']}

    @threaded
    def set_orders(self):

        orders = self.get_active_orders()

        if orders:
            self.orders = []
            for x in orders:
                order = {}
                order['symbol'] = x['Exchange']
                order['side'] = 'buy' if x['OrderType'] == 'LIMIT_BUY' else 'sell'
                order['quantity'] = x['Quantity']
                order['price'] = "{:.9f}".format(x['Limit']).rstrip('0')
                order['id'] = x['OrderUuid']
                self.orders.append(order)

    @threaded
    def set_history(self, base='BTC'):

        if not self.balance:
            return

        history = []
        for symbol in self.balance:
            pair = symbol + '-' + base
            if symbol != base:
                trade = self.get_mytrades(symbol+'-'+base)
                if trade:
                    for x in trade:
                        order = {}
                        order['symbol'] = x['marketid']
                        order['side'] = x['tradetype'].lower()
                        order['quantity'] = x['quantity']
                        order['price'] = x['tradeprice']
                        order['id'] = x['order_id']
                        order['status'] = 'filled'
                        history.append(order)

        self.history = history

    @threaded
    def set_prices(self, symbols):

        prices = self.get_prices()
        if prices:

            for symbol in symbols:
                price = prices.get(symbol.lower(), {}).get('lastprice')
                if price:
                    self.prices[symbol] = "{:.9f}".format(price).rstrip('0')

    @threaded
    def set_total_balance(self, base):
        ''' Calculate total balance in base currency '''

        total = 0

        if self.prices and self.balance:

            for currency, values in self.balance.items():

                available = float(values['available'])
                reserved = float(values['reserved'])

                if currency == base:
                    last = 1
                    available = 0
                else:
                    pair = currency + '-' + base
                    last = float(self.prices.get(pair, 0))

                total += (available + reserved)*last

        self.total = total

class HitBTC(object):

    ''' Connect to exchange, get some stuff, put stuff into variables. '''

    def __init__(
            self,
            url="https://hitbtc.com",
            api_url="https://api.hitbtc.com",
            login=None,
            password=None,
            timeout=5,
            loop=None,
        ):

        self.url = url
        self.api_url = api_url + "/api/2"
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)

        if not loop:
            loop = asyncio.get_event_loop()

        self.loop = loop

        auth = BasicAuth(login=login, password=password)
        self.session = ClientSession(loop=self.loop, auth=auth)
        self.timeout = timeout

        self.is_running = False

        self.balance = {}
        self.orders = []
        self.history = []
        self.prices = {}
        self.total = 0

    def __getattr__(self, attr, *args, **kwargs):

        self.logger.error("method %s(%s, %s) doesn't exist" % (attr, args, kwargs))

    async def _run(self, interval, callback):

        while True:

            balance = await self.get_balance()
            orders = await self.get_orders()
            history = await self.get_history()
            prices = await self.get_prices()

            total = self.calculate_total_balance(balance, prices)

            ret = {
                'balance': balance,
                'orders': orders,
                'history': history,
                'prices': prices,
                'total': total,
            }

            if callback:
                callback(ret)

            await asyncio.sleep(interval)

    def run(self, interval=15, callback=None):

        if not self.is_running:
            self.is_running = True
            self.loop.run_until_complete(self._run(interval, callback))

    def stop(self):

        if self.is_running:
            self.loop.close()
            self.is_running = False

    async def get_response(self, url=None, params={}):

        ''' Get response '''

        resp = await self.session.get(url, params=params, timeout=self.timeout)
        resp = await resp.json()

        if 'error' in resp:
            self.logger.error(resp)
        else:
            return resp

    async def get_balance(self):

        ''' Return currency list with positive available or reserved balance '''

        self.logger.info('get balance')

        url = "%s/trading/balance" % self.api_url

        balances = await self.get_response(url=url)

        if balances:
            ret = {}
            for balance in balances:
                currency = balance['currency']
                if float(balance['available']) > 0 or float(balance['reserved']) > 0:
                    ret[currency] = balance

        return ret

    async def get_orders(self):

        ''' Return active orders for exchange '''

        self.logger.info('get orders')

        url = "%s/order" % self.api_url

        orders = await self.get_response(url)

        if orders:
            return orders

    async def get_history(self, limit=20):

        ''' Return filled orders for exchange '''

        self.logger.info('get history')

        url = "%s/history/order" % self.api_url
        params={'sort': 'desc', 'limit': limit}

        history_trades = await self.get_response(url=url, params=params)

        if history_trades:

            return history_trades

    async def get_prices(self):

        ''' Return prices for every symbol in symbols '''

        self.logger.info('get prices')

        url = "%s/public/ticker/" % self.api_url

        tickers = await self.get_response(url)

        prices = {}

        for ticker in tickers:

            last = ticker.get('last')
            symbol = ticker.get('symbol')
            if symbol and last:
                prices[symbol] = last

        return prices

    def calculate_total_balance(self, balance, prices, base='BTC'):

        ''' Calculate total balance in base currency '''

        self.logger.info('set total balance in %s' % base)

        total = 0

        if prices and balance:

            for currency, values in balance.items():

                available = float(values['available'])
                reserved = float(values['reserved'])

                if currency == base:
                    last = 1
                else:
                    last = float(prices.get(currency+base, 0))

                total += (available + reserved)*last

        return total
