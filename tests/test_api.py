import unittest
import responses
import htq
from htq.api import get_redis_client


url = 'http://localhost/'

client = get_redis_client()


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

        self.assertEqual(req['status'], 'success')
        self.assertEqual(resp['code'], 200)
        self.assertEqual(resp['data'], '{"ok": 1}')
        self.assertEqual(resp['headers'], {
            'Content-Type': 'application/json',
        })

    @responses.activate
    def test_post(self):
        htq.send(url, 'post', data='{"foo": 1}', headers={
            'Content-Type': 'application/json',
        })

        uuid = htq.pop()
        resp = htq.receive(uuid)

        self.assertEqual(resp['status'], 'success')

    def test_error(self):
        htq.send('http://localhost:9999')

        uuid = htq.pop()

        resp = htq.receive(uuid)
        req = htq.request(uuid)

        self.assertEqual(resp['status'], 'error')
        self.assertEqual(req['status'], 'error')

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
        self.assertEqual(req['status'], 'canceled')
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
        self.assertEqual(req['status'], 'canceled')
        self.assertIsNone(resp)

    @responses.activate
    def test_purge(self):
        htq.send(url)
        uuid = htq.pop()

        htq.receive(uuid)
        htq.purge(uuid)

        resp = htq.response(uuid)
        self.assertIsNone(resp)
