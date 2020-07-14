from aiohttp import web
import db
from config import config
import aiohttp_jinja2
from jinja2 import FileSystemLoader

routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
    result = {}
    prices = await db.get_prices()
    for exchange in config.get('exchanges').values():
        name = exchange.get('name')
        result[name] = []
        orders = await db.get_orders(name)
        for order in orders.values():
            order['cur_price'] = prices[name][order['symbol']]
            result[name].append(order)
    context = {'orders': result, 'prices': prices}
    response = aiohttp_jinja2.render_template("index.html", request, context)
    return response

async def web_app():

    app = web.Application()
    app.add_routes(routes)

    aiohttp_jinja2.setup(app, loader=FileSystemLoader(''))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
