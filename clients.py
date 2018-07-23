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

from aiohttp import BasicAuth, ClientSession, request
import logging
from time import time
import hmac
import asyncio

class Ccex(object):

    def __init__(
            self,
            url="https://c-cex.com",
            api_url="https://c-cex.com/t",
            login=None,
            password=None,
            timeout=5,
            loop=None,
        ):

        self.url = url
        self.api_url = api_url
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)

        if not loop:
            loop = asyncio.get_event_loop()

        self.loop = loop

        headers = {'User-Agent': 'CCEX_API_WRAPPER'}
        self.session = ClientSession(loop=self.loop, headers=headers)
        self.timeout = timeout

    async def get_response(
            self,
            url,
            params={},
            headers=None,
            auth=None,
        ):

        params.update({
            'apikey': self.public_key,
            'nonce': int(time()),
        })

        req = request(
            method='GET',
            url=url,
            params=params,
            headers=headers,
        )

        if auth:
            signature = hmac.new(
                self.secret.encode('utf-8'),
                req.url.encode('utf-8'),
                'sha512',
            ).hexdigest()

            req.headers['apisign'] = signature

        res = await self.session.send(req, timeout=self.timeout)
        res = await res.json()

    async def close(self):

        self.session.close()

    def __getattr__(self, attr, *args, **kwargs):
        self.logger.info(attr, args, kwargs)

    async def get_balance(self):

        ''' Return non-zero balance '''

        balances = await self.get_response(
            "%s/api.html" % (self.api_url),
            params={'a': 'getbalances'},
            auth=True
        )

        ret = {}

        if balances:

            for balance in balances:
                currency = balance['Currency']
                if float(balance['Available']) > 0 or float(balance['Balance']) > 0:
                    ret[currency] = {'available': balance['Available'], 'reserved': balance['Balance']}

        return ret

    async def get_orders(self, pair=None):

        ''' Return active orders '''

        orders = await self.get_response(
            "%s/api.html" % (self.api_url),
            params={'a': 'getopenorders', 'market': pair},
            auth=True
        )

        ret = []

        if orders:

            for x in orders:
                order = {}
                order['symbol'] = x['Exchange']
                order['side'] = 'buy' if x['OrderType'] == 'LIMIT_BUY' else 'sell'
                order['quantity'] = x['Quantity']
                order['price'] = "{:.9f}".format(x['Limit']).rstrip('0')
                order['id'] = x['OrderUuid']
                ret.append(order)

        return ret

    async def get_history(self, pair=None, count=20):

        ''' Return order history '''

        trade = self.get_response(
            "%s/api.html" % (self.api_url),
            params={'a': 'getorderhistory', 'market': pair, 'count': count},
            auth=True,
        )

        ret = []

        if trade:
           for x in trade:
                order = {}
                order['symbol'] = x['Exchange']
                order['side'] = 'buy' if x['OrderType'] == 'LIMIT_BUY' else 'sell'
                order['quantity'] = x['Quantity']
                order['price'] = x['Price']
                order['id'] = x['OrderUuid']
                #order['status'] = 'filled'
                ret.append(order)

        return ret

    async def get_prices(self, symbols):

        ''' Return prices '''

        ret = {}
        prices = await self.get_request("%s/prices.json" % (self.api_url))

        if prices:

            for symbol in symbols:

                price = prices.get(symbol.lower(), {}).get('lastprice')

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

    def __getattr__(self, attr, *args, **kwargs):

        self.logger.error("method %s(%s, %s) doesn't exist" % (attr, args, kwargs))

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

        futures = [
            asyncio.ensure_future(self.get_balance()),
            asyncio.ensure_future(self.get_orders()),
            asyncio.ensure_future(self.get_history()),
            asyncio.ensure_future(self.get_prices()),
        ]

        done, pending = await asyncio.wait(futures)

        data = {}

        for future in done:
            data.update(future.result())

        total = self.calculate_total_balance(balance=data.get('balance'), prices=data.get('prices'))

        data['total'] = total

        if callback:
            callback(data)
        else:
            return data

    async def get_response(self, url=None, params={}):

        ''' Get response '''
        try:
            resp = await self.session.get(url, params=params, timeout=self.timeout)
        except Exception as e:
            self.logger.error(e)
            return
        else:
            jresp = await resp.json()
            resp.close()

        if 'error' in jresp:
            self.logger.error(jresp)
        else:
            return jresp

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

            return {'balance': ret}

    async def get_orders(self):

        ''' Return active orders for exchange '''

        self.logger.info('get orders')

        url = "%s/order" % self.api_url

        orders = await self.get_response(url)

        if orders:
            return {'orders': orders}

    async def get_history(self, limit=20):

        ''' Return filled orders for exchange '''

        self.logger.info('get history')

        url = "%s/history/order" % self.api_url
        params={'sort': 'desc', 'limit': limit}

        history_trades = await self.get_response(url=url, params=params)

        if history_trades:
            return {'history': history_trades}

    async def get_prices(self):

        ''' Return prices '''

        self.logger.info('get prices')

        url = "%s/public/ticker/" % self.api_url

        tickers = await self.get_response(url)

        prices = {}

        for ticker in tickers:

            last = ticker.get('last')
            symbol = ticker.get('symbol')
            if symbol and last:
                prices[symbol] = last

        if prices:
            return {'prices': prices}

    def calculate_total_balance(self, balance=None, prices=None, base='BTC'):

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

        return "{:.9f}".format(total)
