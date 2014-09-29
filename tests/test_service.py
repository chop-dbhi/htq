import json
import unittest
import responses
import htq
from htq import service
from htq.db import get_redis_client
from requests.utils import parse_header_links as phl


url = 'http://localhost/'

client = get_redis_client()

app = service.app.test_client()


def parse_header_links(value):
    _links = phl(value)
    links = {}

    for l in _links:
        key = l.get('rel') or l.get('url')
        links[key] = l['url']

    return links


class TestCase(unittest.TestCase):
    def setUp(self):
        client.flushdb()

        responses.add(responses.GET,
                      url=url,
                      body='{"ok": 1}',
                      status=200,
                      content_type='application/json')

        responses.add(responses.DELETE,
                      url=url,
                      status=204)

        responses.add(responses.POST,
                      url=url,
                      status=201)

    @responses.activate
    def test_root(self):
        resp = app.get('/')
        self.assertIn('Link', resp.headers)

    @responses.activate
    def test_send(self):
        resp = app.post('/', data=json.dumps({
            'url': url,
        }), headers={'content-type': 'application/json'})

        # Redirect
        self.assertEqual(resp.status_code, 303)

        resp = app.get(resp.location)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('status', json.loads(resp.data.decode('utf8')))

    @responses.activate
    def test_status(self):
        resp = app.post('/', data=json.dumps({
            'url': url,
        }), headers={'content-type': 'application/json'})

        resp = app.get(resp.location + 'status/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data.decode('utf8')),
                         {'status': 'queued'})

    @responses.activate
    def test_response(self):
        resp = app.post('/', data=json.dumps({
            'url': url,
        }), headers={'content-type': 'application/json'})

        location = resp.location

        # Receive response..
        htq.receive(htq.pop())

        resp = app.get(location)

        self.assertIn('response', resp.headers['Link'])

        links = parse_header_links(resp.headers['Link'])
        response_url = links['response']

        resp = app.get(response_url)
        self.assertEqual(resp.status_code, 200)

        resp = app.delete(response_url)
        self.assertEqual(resp.status_code, 204)

        resp = app.delete(response_url)
        self.assertEqual(resp.status_code, 404)

    @responses.activate
    def test_cancel(self):
        resp = app.post('/', data=json.dumps({
            'url': url,
        }), headers={'content-type': 'application/json'})

        location = resp.location

        resp = app.delete(location)
        self.assertEqual(resp.status_code, 204)

        resp = app.get(location)
        data = json.loads(resp.data.decode('utf8'))
        self.assertEqual(data['status'], htq.CANCELED)
