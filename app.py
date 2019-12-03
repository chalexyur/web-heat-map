import json

import numpy as np
import uvicorn
from sqlalchemy import create_engine, MetaData, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from starlette.applications import Starlette
from starlette.config import Config
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.endpoints import HTTPEndpoint

Base = declarative_base()

meta = MetaData()

templates = Jinja2Templates(directory='templates')

app = Starlette(debug=True)
app.mount('/static', StaticFiles(directory='statics'), name='static')
config = Config("env")

DATABASE_URL = config('DATABASE_URL')
engine = create_engine(DATABASE_URL, echo=False)


def xyt_to_feature(idx, x, y, temperature):
    # coordinates = [x, y]
    # return {
    #     'type': 'Feature',
    #     'properties': {
    #         'id': idx,
    #
    #         'temperature': float(temperature)/100,
    #     },
    #     'geometry':{
    #         'type': 'Point',
    #         'coordinates': coordinates
    #     }
    # }
    return {
        'lat': y,
        'lng': x,
        'count': float(temperature)
    }


class Record(Base):
    __tablename__ = 'main'
    id = Column(Integer, primary_key=True)
    dat = Column(String)
    datprop = Column(String)
    val = Column(String)


@app.route('/')
async def homepage(request):
    conn = engine.connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    q = session.query(Record).with_entities(Record.id).limit(10)

    template = "index.html"
    context = {"request": request,
               "records": [id[0] for id in q]
               }
    conn.close()
    return templates.TemplateResponse(template, context)


@app.route('/records/{record_id}')
async def record_view(request):
    conn = engine.connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    record_id = request.path_params['record_id']
    q = session.query(Record).with_entities(Record.dat).filter(Record.id == record_id)
    dat = q.first()[0]
    template = "record.html"
    context = {"request": request,
               "dat": dat,
               "record_id": record_id,
               }
    conn.close()
    return templates.TemplateResponse(template, context)


@app.route('/bigdict/{record_id}')
class BigDict(HTTPEndpoint):
    async def get(self, request):
        record_id = request.path_params['record_id']
        conn = engine.connect()
        Session = sessionmaker(bind=engine)
        session = Session()
        q = session.query(Record).with_entities(Record.dat, Record.val).filter(Record.id == record_id)
        dat, matrix = q.first()
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
        conn.close()
        return JSONResponse(bigdict)


@app.route('/error')
async def error(request):
    """
    An example error. Switch the `debug` setting to see either tracebacks or 500 pages.
    """
    raise RuntimeError("Oh no")


@app.exception_handler(404)
async def not_found(request, exc):
    """
    Return an HTTP 404 page.
    """
    template = "404.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=404)


@app.exception_handler(500)
async def server_error(request, exc):
    """
    Return an HTTP 500 page.
    """
    template = "500.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=500)


if __name__ == "__main__":
    uvicorn.run("app:app", host='localhost', port=8000, reload=False)
