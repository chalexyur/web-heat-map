import numpy as np
import pandas as pd
import databases
from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from starlette.config import Config
import uvicorn
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from geojson import Point, Feature, FeatureCollection, dump
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import json

Base = declarative_base()

meta = MetaData()

templates = Jinja2Templates(directory='templates')

app = Starlette(debug=True)
app.mount('/static', StaticFiles(directory='statics'), name='static')
config = Config(".env")

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
    q = session.query(Record).with_entities(Record.dat, Record.val).filter(Record.id == record_id)
    dat, matrix = q.first()
    matrix = matrix[1:-1]
    matrix = list(matrix.split(', '))
    # for idx, val in enumerate(bigdata):
    #     print(idx, val)
    xyt = []
    step = 2.5
    c = 0
    for i, y in enumerate(np.arange(90, -90, -step)):
        for j, x in enumerate(np.append(np.arange(0, 180, step), np.arange(-180, 0, step))):
            t = matrix[i + j + c]
            val = [x, y, t]
            xyt.append(val)
        c += 143

    dict_xyt = {i: xyt[i] for i in range(0, len(xyt))}

    # df = pd.DataFrame(xyt)
    # df.to_csv('xyt.csv', index=False, header=['x', 'y', 't'])

    # feature_collection = FeatureCollection([xyt_to_feature(idx=i, x=val[0], y=val[1], temperature=val[2])
    #                                         for i, val in enumerate(xyt)
    #                                         ])
    # with open('statics/js/data.geojson', 'w') as f:
    #     dump(feature_collection, f)

    with open('statics/js/bigdata.json', 'w') as f:
        json.dump([xyt_to_feature(idx=i, x=val[0], y=val[1], temperature=val[2])
                   for i, val in enumerate(xyt)
                   ], f)
    template = "record.html"
    context = {"request": request,
               "dat": dat,
               }
    conn.close()
    return templates.TemplateResponse(template, context)


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
    uvicorn.run("app:app", host='0.0.0.0', port=8000, reload=True)
