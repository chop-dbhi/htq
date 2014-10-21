import unittest
import responses
import htq
from htq.db import get_redis_client


url = 'http://localhost/'

client = get_redis_client()


class TestCase(unittest.TestCase):
    def setUp(self):
        htq.flush()

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
    def test_send_receive(self):
        # Send (queue) a request
        htq.send(url)
        self.assertEqual(htq.size(), 1)

        # Pop off UUID for receiving
        uuid = htq.pop()
        self.assertEqual(htq.size(), 0)

        # Actually send request/get response
        htq.receive(uuid)

        # Check states
        req = htq.request(uuid)
        resp = htq.response(uuid)

        self.assertEqual(req['status'], htq.SUCCESS)
        self.assertEqual(resp['code'], 200)
        self.assertEqual(resp['data'], '{"ok": 1}')
        self.assertEqual(resp['headers'], {
            'Content-Type': 'application/json',
        })

    @responses.activate
    def test_status(self):
        htq.send(url)
        uuid = htq.pop()
        self.assertEqual(htq.status(uuid), htq.QUEUED)

    @responses.activate
    def test_post(self):
        htq.send(url, 'post', data='{"foo": 1}', headers={
            'Content-Type': 'application/json',
        })

        uuid = htq.pop()
        resp = htq.receive(uuid)

        self.assertEqual(resp['status'], htq.SUCCESS)

    def test_error(self):
        htq.send('http://localhost:9999')

        uuid = htq.pop()

        resp = htq.receive(uuid)
        req = htq.request(uuid)

        self.assertEqual(resp['status'], htq.ERROR)
        self.assertEqual(req['status'], htq.ERROR)

    @responses.activate
    def test_cancel_queued(self):
        htq.send(url)
        uuid = htq.pop()

        # Cancel while queued
        htq.cancel(uuid)

        # Receive has not effect
        htq.receive(uuid)

        req = htq.request(uuid)
        resp = htq.response(uuid)
        self.assertEqual(req['status'], htq.CANCELED)
        self.assertIsNone(resp)

    @responses.activate
    def test_cancel_complete(self):
        htq.send(url)
        uuid = htq.pop()

        htq.receive(uuid)

        # Cancel will change the state and delete the response
        htq.cancel(uuid)

        req = htq.request(uuid)
        resp = htq.response(uuid)
        self.assertEqual(req['status'], htq.CANCELED)
        self.assertIsNone(resp)

    @responses.activate
    def test_purge(self):
        htq.send(url)
        uuid = htq.pop()

        htq.receive(uuid)
        htq.purge(uuid)

        resp = htq.response(uuid)
        self.assertIsNone(resp)

    @responses.activate
    def test_id(self):
        htq.send(url, data='v1', id='foo')
        htq.send(url, data='v2', id='foo')

        # First request is canceled
        uuid = htq.pop()
        req1 = htq.request(uuid)
        self.assertEqual(req1['status'], htq.CANCELED)

        # Second is queued
        uuid = htq.pop()
        req2 = htq.request(uuid)
        self.assertEqual(req2['status'], htq.QUEUED)
