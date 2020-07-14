import aiosqlite

DB = 'btc.db'

async def init_db():

    async with aiosqlite.connect(DB) as db:
        await db.execute("create table if not exists history (id integer, exchange varchar(10), symbol varchar(10), side varchar(5), price float, quantity real, confirmed tinyint default 0, PRIMARY KEY (id, exchange));")
        await db.execute("create table if not exists orders (id integer, exchange varchar(10), symbol varchar(10), side varchar(5), price float, quantity real, PRIMARY KEY (id, exchange));")
        await db.execute("create table if not exists prices (exchange varchar(10), symbol varchar(10), price float, PRIMARY KEY (exchange, symbol));")
        await db.execute("create table if not exists total (date datetime, exchange varchar(10), total float);")
        await db.commit()

async def clear_db():

    async with aiosqlite.connect(DB) as db:
        await db.execute("delete from orders;")
        await db.execute("delete from prices;")
        await db.commit()

async def exec_select(command, values=None):

    async with aiosqlite.connect(DB) as db:
        async with db.execute(command, values) as cursor:
            values = await cursor.fetchall()
            return values

async def get_history():

    return await exec_select("select * from history;")

async def get_orders(exchange=None):

    '''
    {
        exchange1: [
            {   id: order_id,
                symbol: dogebtc,
                side: sell,
                quantity: 1000,
                price: 0.000000035
            },
            {   id: order_id2,
                symbol: ltcbtc,
                ...
            },
        ],
        exchange2: [
            {   id: order_id3,
                symbol: ethbtc,
                ...
            },
        ]
    }
    '''
    if exchange:
        command = "select id, exchange, symbol, side, quantity, price from orders where exchange=?;"
    else:
        command = "select id, exchange, symbol, side, quantity, price from orders;"

    values = {}
    for row in await exec_select(command, (exchange,)):
        #exchange = row[1]
        order_id = str(row[0])
        val = {
            'id': row[0],
            'exchange': exchange,
            'symbol': row[2],
            'side': row[3],
            'quantity': row[4],
            'price': "{:.9f}".format(row[5]),
        }
        #values.setdefault(exchange, []).append(val)
        values[order_id] = val

    return values

async def get_prices():

    '''
    {
        exchange1: {
            dogebtc: price,
            ethbtc: price1,
            ltcbtc: price2,
            ...
        },
        exchange2: {
            dogebtc: price,
            ethbtc: price1,
            ltcbtc: price2,
            ...
        }
    }
    '''

    values = {}
    for row in await exec_select("select exchange, symbol, price from prices;"):
        values.setdefault(row[0], {})[row[1]] = "{:.9f}".format(row[2])

    return values

async def get_history_confirmed():

    return await exec_select("select * from history where confirmed < 1;")

async def set_history_confirmed(order_id, exchange):

    async with aiosqlite.connect(DB) as db:
        await db.execute('update history set confirmed = 1 where id = ? and exchange = ?;', (order_id, exchange))
        await db.commit()

async def set_total(name, total):

    async with aiosqlite.connect(DB) as db:
        values = (name, total)
        await db.execute('insert into total (exchange, total, date) values (?, ?, NOW())', values)
        await db.commit()

async def set_history(name, orders):

    async with aiosqlite.connect(DB) as db:
        for order in orders:
            if order.get('id') and order['status'] == 'filled':
                values = (
                    order['id'],
                    name,
                    order['symbol'],
                    order['side'],
                    float(order['price']),
                    order['quantity'],
                    0,
                )
                await db.execute('insert or ignore into history (id, exchange, symbol, side, price, quantity, confirmed) values (?, ?, ?, ?, ?, ?, ?);', values)

        await db.commit()

async def set_prices(name, prices):

    if not prices:
        return

    async with aiosqlite.connect(DB) as db:
        for symbol, price in prices.items():
            values = (name, symbol, price)
            await db.execute('insert or replace into prices (exchange, symbol, price) values (?, ?, ?)', values)

        await db.commit()

async def set_orders(exchange, orders):

    if not orders:
        return

    async with aiosqlite.connect(DB) as db:
        db_orders = await get_orders(exchange)

    orders_to_add = set(orders) - set(db_orders)
    orders_to_remove = set(db_orders) - set(orders)

    for order_id in orders_to_add:
        order = orders[order_id]
        values = (
            order.get('id'),
            exchange,
            order.get('symbol'),
            order.get('side'),
            order.get('quantity'),
            order.get('price'),
        )
        async with aiosqlite.connect(DB) as db:
            await db.execute('insert or replace into orders (id, exchange, symbol, side, quantity, price) values (?, ?, ?, ?, ?, ?)', values)
            await db.commit()

    for order_id in orders_to_remove:
        order = db_orders[order_id]
        values = (
            order.get('id'),
            exchange,
        )
        async with aiosqlite.connect(DB) as db:
            await db.execute('delete from orders where id=? and exchange=?', values)
            await db.commit()
