#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  test.py
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

from clients import HitBTC, Ccex
import asyncio
import logging
from os import path
import json
import aiohttp
from aiosocks.connector import ProxyConnector, ProxyClientRequest
import aiosqlite
import db
from web import web_app

logging.basicConfig()
#DB = 'btc.db'
CFG = 'btc.cfg'

config = {}
config_path = path.expanduser(CFG)

with open(config_path) as json_data_file:
    try:
        config = json.load(json_data_file)
    except Exception as e:
        print(e)

async def telegram_send_message(text):

    url = "https://api.telegram.org/bot{}/".format(config.get('telegram').get('token'))
    chat_id = config.get('telegram').get('chat_id')

    conn = ProxyConnector()

    proxy = "socks5://localhost:9050"

    if url and chat_id:
        try:
            params = {'chat_id': chat_id, 'text': text}
            async with aiohttp.ClientSession(connector=conn, request_class=ProxyClientRequest) as session:
                async with session.get(url + 'sendMessage', proxy=proxy, params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            print(e)

def create_client(exchange, loop):

    url = exchange.get('url')
    public_key = exchange.get('public_key')
    secret = exchange.get('secret')
    api_url = exchange.get('api')
    name = exchange.get('name')
    timeout = exchange.get('timeout', 5)

    if not (public_key and secret):
        return

    try:
        client = globals()[name](url=url, api_url=api_url, login=public_key, password=secret, timeout=timeout, loop=loop)
    except Exception as e:
        print(name + str(e))
        return

    return client

async def load_to_db(name, data):

    await db.set_prices(name, data.get('prices'))
    await db.set_orders(name, data.get('orders'))
    await db.set_history(name, data.get('history'))
    #db.set_total(name, data.get('total'))

async def check_history():

    for row in await db.get_history_confirmed():
        message = "{}: {} {} {} for {:.9f}".format(
            row[1], #exchange
            row[2], #symbol
            row[3], #side
            row[5], #quantity
            row[4], #price
        )
        response = await telegram_send_message(message)
        if response and response.get('ok'):
            await db.set_history_confirmed(row[0], row[1])

def show(name, data):

    print("{}: {}".format(name, data.get('total')))
    print("orders:")
    for order in data.get('orders'):
        symbol = order.get('symbol')
        side = order.get('side')
        quantity = order.get('quantity')
        price = order.get('price')
        cur_price = data.get('prices').get(symbol)
        print("{:9} {:4} {:5} for {:11} ({})".format(symbol, side, quantity, price, cur_price))

    print("-------")
    print("filled:")
    for order in data.get('history'):
        symbol = order.get('symbol')
        side = order.get('side')
        quantity = order.get('quantity')
        price = order.get('price')
        status = order.get('status')
        date = order.get('updatedAt').split('.')[0].replace('T', ' ')
        if status == "filled":
            print("{} {:9} {:4} {:5} for {:11}".format(date, symbol, side, quantity, price))
    print()

async def update(clients):

    for client in clients:
        data = await client.get_data()
        await load_to_db(client.name, data)

    await check_history()

async def periodic_update(clients, period):

    while True:
        await update(clients)
        await asyncio.sleep(period)

async def main(loop):

    await db.init_db()

    clients = []
    for exchange in config.get('exchanges').values():
        if exchange.get('enabled'):
            client = create_client(exchange, loop)
            clients.append(client)

    await web_app()
    await periodic_update(clients, 5)

    # try:
        # await future
    # except Exception as e:
        # for client in clients:
            # await client.close()
        # loop.close()

    return 0

if __name__ == '__main__':

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
