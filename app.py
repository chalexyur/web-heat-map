import numpy as np
import uvicorn
from asyncpg import Connection, connect
from fastapi import FastAPI, Form
from pypika import Query, Table, Order
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import date
from typing import List

import buildpg

config = Config("env")
DATABASE_URL = config('DATABASE_URL')

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')


def xyt_to_feature(idx, x, y, temperature):
    return {
        'lat': y,
        'lng': x,
        'count': float(temperature)
    }


@app.get('/')
async def index(request: Request) -> templates.TemplateResponse:
    table_names = ['h500', 'merd', 'prec', 't850']
    context = {
        'request': request,
        'table_names': table_names
    }
    return templates.TemplateResponse("index.html", context)


@app.get('/tables/{table_name}')
async def table_view(request: Request, table_name: str) -> templates.TemplateResponse:
    conn: Connection = app.state.connection
    table = Table(table_name)
    records = await conn.fetch(
        str((Query.from_(table)
             .select(table.id))
            .orderby('id', order=Order.desc)
            .limit(10))
    )
    id_list = [val[0] for val in records]

    context = {
        'request': request,
        'table_name': table_name,
        'id_list': id_list,
    }
    return templates.TemplateResponse("table.html", context)


@app.get('/tables/{table_name}/records/{record_id}')
async def record_view(request: Request, table_name: str, record_id: int) -> templates.TemplateResponse:
    conn: Connection = app.state.connection
    table = Table(table_name)
    record = await conn.fetchrow(
        str((Query.from_(table).select(table.dat).where(table.id == record_id)))
    )
    context = {
        "request": request,
        'table_name': table_name,
        "record_id": record_id,
        "dat": record[0],
    }
    return templates.TemplateResponse("record.html", context)


@app.get('/tables/{table_name}/records/{record_id}/bigdict/')
async def bigdict(table_name: str, record_id: int):
    conn: Connection = app.state.connection
    table = Table(table_name)
    record = await conn.fetchrow(
        str((Query.from_(table)
             .select(table.val)
             .where(table.id == record_id)))
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


async def get_average_for_values(
        table_name: str,
        start_date: date,
        end_date: date
) -> List[float]:
    conn: Connection = app.state.connection
    query, args = buildpg.render(
        """
    SELECT
        avg(transponed_arrays.element :: numeric)
    FROM
        :table_name,
        LATERAL (
            SELECT
                val ->> length_series.idx element,
                length_series.idx idx
            FROM
                (
                    SELECT
                        generate_series(0, jsonb_array_length(val) - 1)
                ) length_series(idx)
        ) transponed_arrays
    WHERE
        :table_name.dat BETWEEN :start_date
        AND :end_date
    GROUP BY
        transponed_arrays.idx
    ORDER BY
        transponed_arrays.idx;
    """,
        table_name=buildpg.V(table_name),
        start_date=start_date,
        end_date=end_date,
    )
    calculated_values = await conn.fetch(query, *args)

    return [rec[0] for rec in calculated_values]


@app.post("/tables/{table_name}/calculate-position/")
async def calculation(
        *,
        table_name: str,
        start_date: date = Form(...),
        end_date: date = Form(...),
        request: Request) -> List[float]:
    positions = await get_average_for_values(table_name, start_date, end_date)

    return positions


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
