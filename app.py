import numpy as np
import uvicorn
from asyncpg import Connection, connect
from fastapi import FastAPI
from pypika import Query, Table
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

config = Config("env")
DATABASE_URL = config('DATABASE_URL')

app = FastAPI()
app.mount('/static', StaticFiles(directory='statics'), name='static')
templates = Jinja2Templates(directory='templates')


def xyt_to_feature(idx, x, y, temperature):
    return {
        'lat': y,
        'lng': x,
        'count': float(temperature)
    }


@app.get('/')
async def index(request: Request) -> templates.TemplateResponse:
    conn: Connection = app.state.connection
    table = Table('main')
    records = await conn.fetch(
        str((Query.from_(table).select(table.id)))
    )
    id_list = [val[0] for val in records]
    context = {
        "request": request,
        "id_list": id_list,
    }
    return templates.TemplateResponse("index.html", context)


@app.get('/records/{record_id}')
async def record_view(request: Request, record_id: int) -> templates.TemplateResponse:
    conn: Connection = app.state.connection
    table = Table('main')
    record = await conn.fetchrow(
        str((Query.from_(table).select(table.dat).where(table.id == record_id)))
    )
    context = {
        "request": request,
        "dat": record[0],
        "record_id": record_id,
    }
    return templates.TemplateResponse("record.html", context)


@app.get('/bigdict/{record_id}')
async def bigdict(record_id: int):
    conn: Connection = app.state.connection
    table = Table('main')
    record = await conn.fetchrow(
        str((Query.from_(table).select(table.val).where(table.id == record_id)))
    )
    matrix = record[0]
    matrix = matrix[1:-1]
    matrix = list(matrix.split(', '))
    xyt = []
    step = 2.5
    c = 0
    for i, y in enumerate(np.arange(90, -90, -step)):
        for j, x in enumerate(np.append(np.arange(0, 180, step), np.arange(-180, 0, step))):
            t = matrix[i + j + c]
            val = [x, y, t]
            xyt.append(val)
        c += 143
    bigdict = [xyt_to_feature(idx=i, x=val[0], y=val[1], temperature=val[2])
               for i, val in enumerate(xyt)]
    return JSONResponse(bigdict)


@app.route('/error')
async def error(request):
    raise RuntimeError("Oh no")


@app.exception_handler(404)
async def not_found(request, exc):
    template = "404.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=404)


@app.exception_handler(500)
async def server_error(request, exc):
    template = "500.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=500)


@app.on_event("startup")
async def app_init():
    app.state.connection = await connect(DATABASE_URL)


@app.on_event("shutdown")
async def app_stop():
    await app.state.connection.close()


if __name__ == "__main__":
    uvicorn.run("app:app", host='localhost', port=8000, reload=False)
