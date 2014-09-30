import time
import json
from flask import Flask, abort, make_response, url_for, request as http_request
import htq


def build_link_header(links):
    """Builds a Link header according to RFC 5988.

    The format is a dict where the keys are the URI with the value being
    a dict of link parameters:

        {
            '/page=3': {
                'rel': 'next',
            },
            '/page=1': {
                'rel': 'prev',
            },
            ...
        }

    See https://tools.ietf.org/html/rfc5988#section-6.2.2 for registered
    link relation types.
    """
    _links = []

    for uri, params in links.items():
        link = ['<' + uri + '>']

        for key, value in params.items():
            link.append(key + '="' + str(value) + '"')

        _links.append('; '.join(link))

    return ', '.join(_links)


app = Flask('htq')


@app.route('/', methods=['get'])
def queue():
    reqs = []

    for req in htq.queued():
        req['links'] = {
            'self': url_for('request', uuid=req['uuid'], _external=True),
            'status': url_for('status', uuid=req['uuid'], _external=True),
            'response': url_for('response', uuid=req['uuid'], _external=True),
        }
        reqs.append(req)

    resp = make_response(json.dumps(reqs), 200)
    resp.headers['Link'] = build_link_header({
        url_for('queue', _external=True): {
            'rel': 'self',
        }
    })

    return resp


@app.route('/', methods=['post'])
def send():
    json = http_request.json

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
    resp.headers['Location'] = url_for('request', uuid=req['uuid'],
                                       _external=True)
    return resp


@app.route('/<uuid>/', methods=['get'])
def request(uuid):
    req = htq.request(uuid)

    if req is None:
        abort(404)

    resp = make_response(json.dumps(req), 200)
    resp.headers['Content-Type'] = 'application/json'
    resp.headers['Link'] = build_link_header({
        url_for('request', uuid=uuid, _external=True): {
            'rel': 'self',
        },
        url_for('status', uuid=uuid, _external=True): {
            'rel': 'status',
        },
        url_for('response', uuid=uuid, _external=True): {
            'rel': 'response',
        }
    })

    return resp


@app.route('/<uuid>/status/', methods=['get'])
def status(uuid):
    "Returns the status of the request."
    status = htq.status(uuid)

    if not status:
        abort(404)

    resp = make_response(json.dumps({'status': status}), 200)
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
    status = htq.status(uuid)

    if not status:
        abort(404)

    # Block until ready
    while True:
        # Poll status until it is complete
        if status not in {htq.QUEUED, htq.PENDING}:
            break

        time.sleep(0.1)
        status = htq.status(uuid)

    rp = htq.response(uuid) or {}

    resp = make_response(json.dumps(rp), 200)
    resp.headers['Content-Type'] = 'application/json'
    resp.headers['Link'] = build_link_header({
        url_for('response', uuid=uuid, _external=True): {
            'rel': 'self',
        },
        url_for('request', uuid=uuid, _external=True): {
            'rel': 'request',
        },
    })

    return resp


@app.route('/<uuid>/response/', methods=['delete'])
def purge(uuid):
    ok = htq.purge(uuid)

    if not ok:
        abort(404)

    return '', 204
