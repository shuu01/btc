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
from yarl import URL
import uuid

class Ccex(object):

    def __init__(
        self,
        url="https://c-cex.com",
        api_url="https://c-cex.com/t",
        login=None,
        password=None,
        timeout=5,
        loop=None,
        log=None,
    ):

        self.url = url
        self.api_url = api_url
        self.login = login
        self.password = password
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        if log:
            self.logger.setLevel(log)

        if not loop:
            loop = asyncio.get_event_loop()

        self.loop = loop

        self.session = ClientSession(loop=self.loop)
        self.timeout = timeout

    async def get_response(
        self,
        method='GET',
        url=None,
        params={},
        headers={},
        auth=None,
    ):

        params.update({
            'apikey': self.login,
            'nonce': int(time()),
        })

        url = URL(url).with_query(params)

        if auth:
            signature = hmac.new(
                key=self.password.encode(),
                msg=str(url).encode(),
                digestmod='sha512',
            ).hexdigest()

            headers['apisign'] = signature

        try:
            resp = await self.session.request(method, str(url), headers=headers, timeout=self.timeout)
        except Exception as e:
            self.logger.error('request error')
            self.logger.error(e)
            return

        try:
            jresp = await resp.json(content_type=None)
            resp.close()
        except Exception as e:
            self.logger.error(resp)
            self.logger.error(e)
            return

        if not jresp:
            return

        if url.path.endswith('json'):
            return jresp

        if jresp.get('success'):
            return jresp.get('result')
        else:
            self.logger.error(jresp.get('message'))

    async def close(self):

        await self.session.close()

    def __getattr__(self, attr, *args, **kwargs):

        self.logger.error("method {}({}, {}) doesn't exist".format(attr, args, kwargs))

    async def get_data(self, callback=None):

        '''data = {
            'balance': dict,
            'orders': list,
            'history': list,
            'prices': dict,
            'total': str,
        }'''

        futures = (
            asyncio.ensure_future(self.get_balance()),
            asyncio.ensure_future(self.get_orders()),
            asyncio.ensure_future(self.get_history()),
            asyncio.ensure_future(self.get_prices()),
        )

        results = await asyncio.gather(*futures)

        data = {}

        data['balance'] = results[0]
        data['orders'] = results[1]
        data['history'] = results[2]
        data['prices'] = results[3]

        total = self.calculate_total_balance(balance=data.get('balance'), prices=data.get('prices'))

        data['total'] = total

        if callback:
            callback(data)
        else:
            return data

    async def get_balance(self):

        ''' Return non-zero balance '''

        ret = {}

        balances = await self.get_response(
            url="{}/api.html".format(self.api_url),
            params={'a': 'getbalances'},
            auth=True
        )

        if balances:
            for balance in balances:
                currency = balance['Currency'].lower()
                if float(balance['Available']) > 0 or float(balance['Balance']) > 0:
                    ret[currency] = {'available': balance['Available'], 'reserved': balance['Balance']}

        return ret

    async def get_orders(self):

        ''' Return active orders '''

        ret = {}

        orders = await self.get_response(
            url="{}/api.html".format(self.api_url),
            params={'a': 'getopenorders'},
            auth=True
        )

        if orders:
            for x in orders:
                order = {}
                order['symbol'] = x['Exchange'].lower()
                order['side'] = 'buy' if x['OrderType'] == 'LIMIT_BUY' else 'sell'
                order['quantity'] = "{:.2f}".format(x['Quantity'])
                order['price'] = "{:.9f}".format(x['Limit']).rstrip('0')
                order_id = x['OrderUuid']
                order['id'] = order_id
                ret[order_id] = order

        return ret

    async def get_history(self, count=20):

        ''' Return order history '''

        ret = []

        trade = await self.get_response(
            url="{}/api.html".format(self.api_url),
            params={'a': 'getorderhistory', 'count': count},
            auth=True,
        )

        if trade:
            for x in trade:
                order = {}
                order['symbol'] = x['Exchange'].lower()
                order['quantity'] = "{:.2f}".format(x['Quantity'])
                order['price'] = "{:.9f}".format(x['PricePerUnit']).rstrip('0')
                order['id'] = x['OrderUuid']
                order['side'] = 'buy'
                if x['OrderType'] == 'LIMIT_BUY':
                    order['side'] = 'buy'
                    order['quantity'] = "{:.2f}".format(x['Quantity']/x['PricePerUnit'])
                else:
                    order['side'] = 'sell'
                if x['QuantityRemaining'] == 0:
                    order['status'] = 'filled'
                else:
                    order['status'] = 'other'
                order['updatedAt'] = x['TimeStamp']
                ret.append(order)

        return ret

    async def get_prices(self):

        ''' Return prices '''

        ret = {}

        prices = await self.get_response(url="{}/prices.json".format(self.api_url))

        if prices:
            for symbol, values in prices.items():
                price = values.get('lastprice')
                if price:
                    ret[symbol] = "{:.9f}".format(price).rstrip('0')

        return ret

    def calculate_total_balance(self, balance, prices, base='BTC'):

        ''' Calculate total balance in base currency '''

        total = 0

        if prices and balance:

            for currency, values in balance.items():

                available = float(values['available'])
                reserved = float(values['reserved'])

                if currency == base:
                    last = 1
                    available = 0
                else:
                    pair = currency + '-' + base
                    last = float(prices.get(pair, 0))

                total += (available + reserved)*last

        return total

class HitBTC(object):

    ''' Connect to exchange, get some stuff '''

    def __init__(
        self,
        url="https://hitbtc.com",
        api_url="https://api.hitbtc.com",
        login=None,
        password=None,
        timeout=5,
        loop=None,
        log=None,
    ):

        self.url = url
        self.api_url = api_url + "/api/2"
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        if log:
            self.logger.setLevel(log)

        if not loop:
            loop = asyncio.get_event_loop()

        self.loop = loop

        auth = BasicAuth(login=login, password=password)

        try:
            self.session = ClientSession(loop=self.loop, auth=auth)
        except Exception as e:
            print(e)

        self.timeout = timeout

    def __getattr__(self, attr, *args, **kwargs):

        self.logger.error("method {}({}, {}) doesn't exist".format(attr, args, kwargs))

    async def close(self):

        await self.session.close()

    async def get_data(self, callback=None):

        '''data = {
            'balance': dict,
            'orders': list,
            'history': list,
            'prices': dict,
            'total': str,
        }'''

        futures = (
            asyncio.ensure_future(self.get_balance()),
            asyncio.ensure_future(self.get_orders()),
            asyncio.ensure_future(self.get_history()),
            asyncio.ensure_future(self.get_prices()),
        )

        results = await asyncio.gather(*futures)

        data = {}

        data['balance'] = results[0]
        data['orders'] = results[1]
        data['history'] = results[2]
        data['prices'] = results[3]

        total = self.calculate_total_balance(balance=data.get('balance'), prices=data.get('prices'))

        data['total'] = total

        if callback:
            callback(data)
        else:
            return data

    async def get_response(
        self,
        method='GET',
        url=None,
        params={},
    ):

        ''' Get response '''

        try:
            resp = await self.session.request(method, url, params=params, timeout=self.timeout)
        except Exception as e:
            self.logger.error(e)
            return

        try:
            jresp = await resp.json(content_type=None)
            resp.close()
        except Exception as e:
            self.logger.error(e)
            return

        if 'error' in jresp:
            self.logger.error(jresp)
        else:
            return jresp

    async def get_balance(self):

        ''' Return currency list with positive available or reserved balance '''

        self.logger.info('get balance')

        url = "{}/trading/balance".format(self.api_url)

        balances = await self.get_response(url=url)

        ret = {}

        if balances:
            for balance in balances:
                currency = balance['currency'].lower()

                if float(balance['available']) > 0 or float(balance['reserved']) > 0:
                    ret[currency] = balance

        return ret

    async def get_orders(self):

        ''' Return active orders for exchange '''

        self.logger.info('get orders')

        url = "{}/order".format(self.api_url)

        orders = await self.get_response(url=url)
        ret = {}

        if orders:
            for order in orders:
                order_id = order['id']
                order['symbol'] = order['symbol'].lower()
                ret[order_id] = order

        return ret

    async def get_order(self, order_id):

        ''' Return order by order id '''

        self.logger.info('get order {}'.format(order_id))

        url = "{}/order/{}".format(self.api_url, order_id)

        order = await self.get_response(url=url)
        order['symbol'] = order['symbol'].lower()

        return order

    async def get_history(self, limit=20):

        ''' Return filled orders for exchange '''

        self.logger.info('get history')

        url = "{}/history/order".format(self.api_url)
        params={'sort': 'desc', 'limit': limit}

        history_trades = await self.get_response(url=url, params=params)

        if history_trades:
            for order in history_trades:
                order['symbol'] = order['symbol'].lower()
            return history_trades
        else:
            return []

    async def get_prices(self):

        ''' Return prices '''

        self.logger.info('get prices')

        url = "{}/public/ticker/".format(self.api_url)

        tickers = await self.get_response(url=url)

        prices = {}

        if tickers:

            for ticker in tickers:
                last = ticker.get('last')
                symbol = ticker.get('symbol').lower()

                if symbol and last:
                    prices[symbol] = last

        return prices

    async def new_order(self, symbol, side, quantity, price):

        self.logger.info('place new order in {}'.format(symbol))

        order_id = uuid.uuid4().hex

        params = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
        }

        url = "{}/order/{}".format(self.api_url, order_id)

        response = await self.get_response(method='PUT', url=url, params=params)

        return response

    def calculate_total_balance(self, balance=None, prices=None, base='BTC'):

        ''' Calculate total balance in base currency '''

        self.logger.info('set total balance in {}'.format(base))

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

        return "{:.9f}".format(total)
