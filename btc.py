#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  btc.py
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

# stuff
import requests
from clients import HitBTC, Ccex
import sys
import json
import sqlite3
import webbrowser
from os import path
from datetime import datetime

# gtk stuff
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk as gdk
from gi.repository import Gtk as gtk
from gi.repository import GObject as gobject

# plot stuff
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from matplotlib.backends.backend_gtk3cairo import FigureCanvasGTK3Cairo as FigureCanvas
from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3 as NavigationToolbar

#_cfg = '~/.config/btc/btc.cfg'
_cfg = 'btc.cfg'
_db = '~/.config/btc/btc.db'

TELEGRAM_URL = ''
CHAT_ID = ''

class App(object):

    def __init__(self, clients, database, errors=None):

        refresh = 5

        self.statusicon = gtk.StatusIcon()
        # icon theme
        self.icon_theme = gtk.IconTheme.get_default()

        # connect event to statusicon
        self.statusicon.connect("button-press-event", self.on_click)

        self.set_menu()

        if errors:
            # load icon from icon theme
            pixbuf = self.icon_theme.load_icon(self.get_icon_name('red'), 48, 0)
            # set status icon
            self.statusicon.set_from_pixbuf(pixbuf)
            # set status tooltip
            self.statusicon.set_tooltip_text(errors)

            return None
        # set api client for every exchange in config
        #self.set_clients()

        self.clients = clients

        self.conn = sqlite3.connect(database, detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.conn.cursor()

        self.tooltip = []
        self.history = {}

        self.order_window = gtk.Window()
        self.order_window.set_default_size(600, 400)

        # execute update every 'refresh' seconds
        self.timer = gobject.timeout_add(refresh*1000, self.update)

        #self.save_total_balance()

    def set_history(self, client):
        ''' Set filled orders for exchange '''

        table = client.name.lower() + '_history'

        #self.cursor.execute("drop table %s" % table)

        self.cursor.execute("select 1 from sqlite_master where type='table' and name = ?", (table,))
        table_exists = self.cursor.fetchone()

        if not table_exists:
            self.cursor.execute("create table %s (id integer primary key, symbol varchar(10), side varchar(5), price float, quantity real, confirmed tinyint default 0);" % (table))

        history = client.history

        if history:

            if table_exists:

                values = [(order['id'], order['symbol'], order['side'], float(order['price']), order['quantity'], 0) for order in history if order.get('id') and order['status'] == 'filled']

            else:

                values = [(order['id'], order['symbol'], order['side'], float(order['price']), order['quantity'], 1) for order in history if order['status'] == 'filled']

            self.cursor.executemany('insert or ignore into ' + table + ' (id, symbol, side, price, quantity, confirmed) values (?, ?, ?, ?, ?, ?)', values)

        self.cursor.execute('delete from %s where id not in (select id from %s order by id desc limit 100)' % (table, table))

        self.conn.commit()

        self.cursor.execute('select * from %s where confirmed < 1' % table)

        history = {}

        for line in self.cursor.fetchall():

            order_id = line[0]

            history[order_id] = {'symbol': line[1], 'side': line[2], 'price': "{:.9f}".format(line[3]).rstrip('0'), 'quantity': line[4]}

        return history

    def save_total_balance(self):

        for client in self.clients:

            table = client.name + '_total'
            self.cursor.execute("create table if not exists %s (id integer primary key autoincrement, time timestamp default current_timestamp, balance real)" % (table))

            total = client.total
            if total > 0:
                self.cursor.execute("insert into %s (balance) values(%s)" % (table, total))

        self.conn.commit()

    def close(self, widget=None, data=None):

        for client in self.clients:

            client.stop()

        self.conn.close()

        gtk.main_quit()

    def show_settings(self, widget=None, data=None):

        window = gtk.Window()
        vbox = gtk.VBox(False, 10)
        hbox = gtk.HBox(False, 10)

        label = gtk.Label("labeltext")
        hbox.pack_start(label, expand=True, fill=True, padding=0)
        label.show()

        entry = gtk.Entry()
        hbox.pack_start(entry, expand=True, fill=True, padding=0)
        entry.show()

        hbox.show()

        vbox.pack_start(hbox, expand=True, fill=True, padding=0)
        vbox.show()

        window.set_position(gtk.WindowPosition.MOUSE)
        window.add(vbox)
        window.show()

    def show_total_balance(self, widget=None, data=None):

        window = gtk.Window()
        window.set_default_size(600, 400)
        vbox = gtk.VBox(False, 10)
        window.add(vbox)

        fig = Figure(figsize=(5,5), dpi=100)
        ax = fig.add_subplot(111)

        x = []
        y = []

        exchange = "hitbtc"
        self.cursor.execute('select id, datetime(time, "localtime"), balance from %s_total' % exchange)
        #self.cursor.execute('select * from %s_total' % exchange)
        for line in self.cursor.fetchall():
            x.append(datetime.strptime(line[1], '%Y-%m-%d %H:%M:%S'))
            y.append(line[2])

        ax.plot(x, y, color='green', marker='o')
        ax.grid(True)
        ax.set_title('')
        hfmt = DateFormatter('%Y-%m-%d %H:%M:%S')
        ax.xaxis.set_major_formatter(hfmt)
        fig.autofmt_xdate()

        canvas = FigureCanvas(fig)
        canvas.set_size_request(400, 500)
        vbox.pack_start(canvas, True, True, 0)
        toolbar = NavigationToolbar(canvas, window)
        vbox.pack_start(toolbar, False, False, 0)

        #hbox = gtk.HBox(False, 10)

        window.show_all()

    def set_menu(self):

        menu = gtk.Menu()

        item_total_balance = gtk.MenuItem("Balance")
        item_settings = gtk.MenuItem("Settings")
        item_exit = gtk.MenuItem("Exit")

        # Append the menu items
        menu.append(item_total_balance)
        menu.append(item_settings)
        menu.append(item_exit)

        # Add callbacks
        item_total_balance.connect("activate", self.show_total_balance, "BTC")
        item_exit.connect("activate", self.close, "Close")
        item_settings.connect("activate", self.show_settings, "Show")

        # Show the menu items
        item_total_balance.show()
        item_settings.show()
        item_exit.show()

        # Popup the menu
        self.menu = menu

    def set_orders(self):

        window = self.order_window
        for ch in window.get_children():
            window.remove(ch)

        vbox = gtk.VBox(False, 10)

        for client in self.clients:

            name = client.name
            url = client.url
            orders = client.orders
            history = self.history.get(name)
            prices = client.prices
            total = "{:.9f}".format(client.total)
            table = name + '_history'

            line = name + ": " + str(total)
            label = gtk.Label(line)
            label.set_markup("<a href=\"%s\" title=\"%s\">%s</a>" % (url, url, line))
            #box = gtk.EventBox()
            #box.add(label)
            #label.set_events(gdk.EventMask.BUTTON_PRESS_MASK)
            #box.connect("button-press-event", self.open_url, url)
            vbox.pack_start(label, expand=True, fill=True, padding=0)
            label.show()
            #box.show()

            if orders:

                for order in orders:

                    symbol = order['symbol']
                    cur_price = prices.get(symbol)
                    side = order['side']
                    quantity = order['quantity']
                    price = order['price']
                    #order_id = order['id']

                    line = "%s %s: %s for %s (%s)" % (symbol, side, quantity, price, cur_price)
                    label = gtk.Label(line)
                    color = gdk.RGBA()
                    if side == 'sell':
                        color.parse('#AA3300')
                    if side == 'buy':
                        color.parse('#0066AA')
                    color.to_string()
                    label.override_color(gtk.StateFlags.NORMAL, color)
                    #label.set_name(order_id)
                    vbox.pack_start(label, expand=True, fill=True, padding=0)
                    label.show()

            if history:

                for order_id, order in history.items():

                    symbol = order['symbol']
                    cur_price = prices.get(symbol)
                    side = order['side']
                    quantity = order['quantity']
                    price = order['price']
                    #"{:.9f}".format(price)

                    line = "%s %s: %s for %s (%s)" % (symbol, side, quantity, price, cur_price)
                    label = gtk.Label(line)
                    #menu_item.set_image(gtk.Image().new_from_stock(gtk.STOCK_APPLY, gtk.IconSize.LARGE_TOOLBAR))
                    #menu_item.set_always_show_image(True)
                    color = gdk.color_parse("green")
                    label.modify_fg(gtk.StateFlags.NORMAL, color)
                    label.set_has_window(True)
                    label.set_events(gdk.EventMask.BUTTON_PRESS_MASK)
                    label.connect("button-press-event", self.confirm_order, {'table': table, 'id': order_id, 'exchange': name})
                    vbox.pack_start(label, expand=True, fill=True, padding=0)
                    label.show()

        window.add(vbox)
        vbox.show()

    @staticmethod
    def position(menu, x, y, icon):

        return gtk.StatusIcon.position_menu(menu, x, y, icon)

    def menu_left(self, event_button, event_time, data=None):

        isVisible = self.order_window.get_property("visible")
        if (isVisible):
            self.order_window.hide()
        else:
            self.order_window.set_position(gtk.WindowPosition.MOUSE)
            self.order_window.show()

    def menu_right(self, event_button, event_time, data=None):

        self.menu.popup(None, None, None, self.statusicon, event_button, event_time)

    @staticmethod
    def open_url(widget, button, url):

        webbrowser.open_new_tab(url)

    def confirm_order(self, widget, button=None, data=None):

        self.order_window.remove(widget)

        self.cursor.execute("update %s set confirmed = 1 where id = %s" % (data['table'], data['id']))

        del self.history[data['exchange']][data['id']]

        self.save_total_balance()

        return True

    def on_click(self, icon, event):

        btn = event.button
        #print(event.get_root_coords())

        time = gtk.get_current_event_time() # required by the popup

        if btn == 1: # left click
            self.menu_left(btn, time)
        if btn == 3: # right click
            self.menu_right(btn, time)

    def get_icon_name(self, color=None, overlay=False):

        if color == 'red':
            return "btc-red"

        if color == 'green':
            if overlay:
                return "btc-green-at"
            else:
                return "btc-green"

        if overlay:
            return "btc-gray-at"
        else:
            return "btc-gray"

    def update(self):

        #print("update")

        color = 'gray'

        for client in self.clients:

            symbols = []

            for order in client.orders:
                symbols.append(order.get('symbol'))

            for order in client.history:
                symbols.append(order.get('symbol'))

            history = self.set_history(client)
            history_cl = self.history.get(client.name, {})

            if history:

                color = 'green'

                for order_id in history:

                    order = history_cl.get(order_id)

                    if not order:
                        history_cl[order_id] = history[order_id]
                        order = history_cl.get(order_id)

                    if order.get('send'):
                        continue

                    order['send'] = 1

                    line = "%s: %s %s %s for %s" % (
                        client.name,
                        order['symbol'],
                        order['side'],
                        order['quantity'],
                        order['price'],
                    )

                    telegram_send_message(line)

            client.update(prices=set(symbols))

            self.history[client.name] = history_cl

            #self.set_total_balance(exchange, 'BTC')

        pixbuf = self.icon_theme.load_icon(self.get_icon_name(color), 48, 0)
        self.statusicon.set_from_pixbuf(pixbuf)
        self.statusicon.set_tooltip_text("\n".join(self.tooltip))
        self.set_orders()

        # True for timeout function
        return True

    def main(self):

        gtk.main()


def create_client(exchange):

    if not exchange.get('enabled'):
        return

    url = exchange.get('url')
    public_key = exchange.get('public_key')
    secret = exchange.get('secret')
    api_url = exchange.get('api')
    name = exchange.get('name')
    refresh = exchange.get('refresh', 15)
    timeout = exchange.get('timeout', 5)

    if not (public_key and secret and api_url and name):
        return

    try:
        client = globals()[name](url, api_url, public_key, secret, timeout)
    except Exception as e:
        print(name + str(e))
        return

    return client

def telegram_send_message(text):

    proxies = {'https': "socks5h://localhost:9050"} #tor

    url = TELEGRAM_URL
    chat_id = CHAT_ID

    if url and chat_id:
        try:
            params = {'chat_id': chat_id, 'text': text}
            response = requests.post(url + 'sendMessage', data=params, proxies=proxies)
            return response
        except Exception as e:
            print(e)

def main(args):

    config = {}
    errors = None

    config_path = path.expanduser(_cfg)
    with open(config_path) as json_data_file:
        try:
            config = json.load(json_data_file)
        except Exception as e:
            errors = str(e)

    token = config['telegram']['token']

    global CHAT_ID
    CHAT_ID = config['telegram']['chat_id']
    global TELEGRAM_URL
    TELEGRAM_URL = "https://api.telegram.org/bot%s/" % token

    clients = []

    for exchange in config['exchanges'].values():

        client = create_client(exchange)

        if client:

            #print(client.get_symbols())
            client.update(orders=True, history=True, balance=True, total='BTC')
            client.run(exchange['refresh'])
            clients.append(client)

    app = App(clients, path.expanduser(_db), errors)

    app.main()

if __name__ == '__main__':

    sys.exit(main(sys.argv))
