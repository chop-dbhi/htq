import json
from flask import Flask, request, abort, make_response, url_for
import htq


app = Flask('htq')


@app.route('/', methods=['post'])
def send():
    json = request.json

    if 'url' not in json:
        abort(422)

    url = json['url']
    method = json.get('method')
    data = json.get('data')
    headers = json.get('headers')
    timeout = json.get('timeout')

    req = htq.send(url=url,
                   method=method,
                   data=data,
                   headers=headers,
                   timeout=timeout)

    # Redirect to request endpoint
    resp = make_response('', 303)
    resp.headers['Location'] = url_for('get', uuid=req['uuid'],
                                       _external=True)
    return resp


@app.route('/<uuid>/', methods=['get'])
def get(uuid):
    req = htq.request(uuid)

    if req is None:
        abort(404)

    req['links'] = {
        'self': {
            'href': url_for('get', uuid=uuid, _external=True),
        }
    }

    # Add link to response if the request is complete
    if req['status'] in {htq.SUCCESS, htq.ERROR, htq.TIMEOUT}:
        req['links']['response'] = {
            'href': url_for('response', uuid=uuid,
                            _external=True)
        }

    resp = make_response(json.dumps(req), 200)
    resp.headers['Content-Type'] = 'application/json'

    return resp


@app.route('/<uuid>/', methods=['delete'])
def cancel(uuid):
    ok = htq.cancel(uuid)

    if not ok:
        abort(404)

    return '', 204


@app.route('/<uuid>/response/', methods=['get'])
def response(uuid):
    rp = htq.response(uuid)

    if not rp:
        abort(404)

    rp['links'] = {
        'self': {
            'href': url_for('response', uuid=uuid, _external=True),
        },
        'request': {
            'href': url_for('get', uuid=uuid, _external=True),
        }
    }

    resp = make_response(json.dumps(rp), 200)
    resp.headers['Content-Type'] = 'application/json'

    return resp


@app.route('/<uuid>/response/', methods=['delete'])
def purge(uuid):
    ok = htq.purge(uuid)

    if not ok:
        abort(404)

    return '', 204
