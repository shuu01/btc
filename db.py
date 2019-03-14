import aiosqlite

DB = 'btc.db'

async def init_db():

    async with aiosqlite.connect(DB) as db:
        await db.execute("create table if not exists history (id integer, exchange varchar(10), symbol varchar(10), side varchar(5), price float, quantity real, confirmed tinyint default 0, PRIMARY KEY (id, exchange));")
        await db.execute("create table if not exists orders (id integer, exchange varchar(10), symbol varchar(10), side varchar(5), price float, quantity real);")
        await db.execute("create table if not exists prices (exchange varchar(10), symbol varchar(10), price float);")
        await db.execute("create table if not exists total (date datetime, exchange varchar(10), total float);")
        await db.commit()

async def exec_select(command):

    async with aiosqlite.connect(DB) as db:
        async with db.execute(command) as cursor:
            values = await cursor.fetchall()
            return values

async def get_history():

    return await exec_select("select * from history;")

async def get_orders():

    return await exec_select("select * from orders;")

async def get_prices():

    return await exec_select("select * from prices;")

async def get_history_confirmed():

    return await exec_select("select * from history where confirmed < 1;")

async def set_history_confirmed(order_id, exchange):

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
        await db.execute('delete from prices where exchange = ?;', (name,))
        await db.commit()
        for symbol, price in prices.items():
            values = (name, symbol, price)
            await db.execute('insert into prices (exchange, symbol, price) values (?, ?, ?)', values)

        await db.commit()

async def set_orders(name, orders):

    if not orders:
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute('delete from orders where exchange = ?', (name,))
        await db.commit()
        for order in orders:
            values = (
                order.get('id'),
                name,
                order.get('symbol'),
                order.get('side'),
                order.get('quantity'),
                order.get('price'),
            )
            await db.execute('insert into orders (id, exchange, symbol, side, quantity, price) values (?, ?, ?, ?, ?, ?)', values)

        await db.commit()
