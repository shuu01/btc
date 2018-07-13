#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  hitbtc.py
#
#  Copyright 2018  <pi@rpi3>
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

import requests
import json
#from requests.auth import HTTPDigestAuth
from time import time
import hmac
#from threading import Thread, Timer, Event

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

    def __init__(self, url, api_url, public_key, secret, timeout=5):

        self.url = url
        self.api_url = api_url + "/api/2"
        self.session = requests.session()
        self.session.auth = (public_key, secret)
        self.timeout = timeout
        self.name = self.__class__.__name__

        self.to_update = {}
        self.is_running = False

        self.balance = {}
        self.orders = []
        self.history = []
        self.prices = {}
        self.total = 0

    def __getattr__(self, attr, *args, **kwargs):

        print(attr, args, kwargs)

    def exception(function):

        def wrapper(*args, **kwargs):

            try:
                ret = function(*args, **kwargs)
                if 'error' in ret:
                    print(ret)
                    return
                return ret
            except requests.exceptions.RequestException as e:
                print(e)

        return wrapper

    def threaded(function):

        def wrapper(*args, **kwargs):

            thread = Thread(target=function, args=args, kwargs=kwargs)
            thread.start()
            return thread

        return wrapper

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

    @exception
    def get_symbol(self, symbol_code):
        """ Get symbol """
        return self.session.get("%s/public/symbol/%s" % (self.api_url, symbol_code), timeout=self.timeout).json()

    @exception
    def get_symbols(self):
        """ Get symbols """
        return self.session.get("%s/public/symbol" % (self.api_url), timeout=self.timeout).json()

    @exception
    def get_account_balance(self):
        """ Get main balance """
        return self.session.get("%s/account/balance" % self.api_url, timeout=self.timeout).json()

    @exception
    def get_trading_balance(self):
        """ Get trading balance """
        return self.session.get("%s/trading/balance" % self.api_url, timeout=self.timeout).json()

    @exception
    def get_ticker(self, symbol_code):
        """ Get ticker """
        return self.session.get("%s/public/ticker/%s" % (self.api_url, symbol_code), timeout=self.timeout).json()

    @exception
    def get_tickers(self):
        """ Get ticker """
        return self.session.get("%s/public/ticker/" % self.api_url).json()

    @exception
    def get_active_orders(self):
        """ Get active orders """
        return self.session.get("%s/order" % self.api_url, timeout=self.timeout).json()

    @exception
    def get_history_trades(self):
        """ Get history trades """
        return self.session.get("%s/history/order" % self.api_url, timeout=self.timeout, params={'sort': 'desc', 'limit': 20}).json()

    @threaded
    def set_balance(self):
        ''' Set currency list with positive available or reserved balance '''

        balances = self.get_trading_balance()

        if balances:
            self.balance = {}
            for balance in balances:
                currency = balance['currency']
                if float(balance['available']) > 0 or float(balance['reserved']) > 0:
                    self.balance[currency] = balance

    @threaded
    def set_orders(self):
        ''' Set active orders for exchange '''

        orders = self.get_active_orders()

        if orders:
            self.orders = orders

    @threaded
    def set_history(self):
        ''' Set filled orders for exchange '''

        history_trades = self.get_history_trades()

        if history_trades:

            self.history = history_trades

    @threaded
    def set_prices(self, symbols):
        ''' Set prices for every symbol in symbols '''

        tickers = []

        for symbol in symbols:

            tickers.append(self.get_ticker(symbol))

        if tickers:

            for ticker in tickers:

                last = ticker.get('last')
                symbol = ticker.get('symbol')
                if symbol and last:
                    self.prices[symbol] = last

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
                else:
                    last = float(self.prices.get(currency+base, 0))

                total += (available + reserved)*last

        self.total = total
