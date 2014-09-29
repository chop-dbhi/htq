import json
import time
import redis
import requests
import logging
from uuid import uuid4
from .db import get_redis_client


__all__ = (
    'send',
    'receive',
    'queued',
    'request',
    'status',
    'response',
    'pop',
    'push',
    'cancel',
    'purge',
    'size',
    'logger',
    'SUCCESS',
    'QUEUED',
    'CANCELED',
    'PENDING',
    'TIMEOUT',
    'ERROR',
)


# Default request timeout
DEFAULT_TIMEOUT = 60

# The requests send queue
REQ_SEND_QUEUE = 'htq:send'

# Key prefix of a hash that stores the requests
REQ_PREFIX = 'htq:requests:'

# Key prefix of a hash that stores the responses
RESP_PREFIX = 'htq:responses:'


QUEUED = 'queued'
CANCELED = 'canceled'
PENDING = 'pending'
SUCCESS = 'success'
TIMEOUT = 'timeout'
ERROR = 'error'


logger = logging.getLogger('htq')


def _timestamp():
    return int(time.time() * 1000)


def _encode_request(r):
    r = r.copy()

    if 'headers' in r:
        r['headers'] = json.dumps(r['headers'])

    # Remove empty data so it is not stringified as 'None'
    if 'data' in r and r['data'] is None:
        r.pop('data')

    return r


def _decode_request(r):
    if not r:
        return

    if 'data' not in r:
        r['data'] = None

    r['timeout'] = int(r['timeout'])
    r['time'] = int(r['time'])
    r['headers'] = json.loads(r['headers'])

    return r


def _encode_response(r):
    r = r.copy()

    if 'headers' in r:
        r['headers'] = json.dumps(r['headers'])

    return r


def _decode_response(r):
    if not r:
        return

    r['time'] = int(r['time'])

    if r['status'] == SUCCESS:
        r['code'] = int(r['code'])
        r['elapsed'] = float(r['elapsed'])
        r['headers'] = json.loads(r['headers'])

    return r


def send(url, method=None, data=None, headers=None, timeout=None):
    "Enqueues an HTTP request."
    client = get_redis_client()

    if not method:
        if data is None:
            method = 'get'
        else:
            method = 'post'

    uuid = str(uuid4())

    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    if not headers:
        headers = {}

    req = {
        'uuid': uuid,
        'status': QUEUED,
        'time': _timestamp(),
        'url': url,
        'method': method,
        'data': data,
        'headers': headers,
        'timeout': timeout,
    }

    with client.pipeline() as p:
        p.multi()
        p.lpush(REQ_SEND_QUEUE, uuid)
        p.hmset(REQ_PREFIX + uuid, _encode_request(req))
        p.execute()

    logger.debug('[{}] queued request'.format(uuid))

    return req


def pop():
    "Pops the next request UUID off the queue for processing."
    client = get_redis_client()

    return client.brpop(REQ_SEND_QUEUE)[1]


def push(uuid):
    """Pushes a UUID into the queue.

    This provides a means to recover the queue in case of an error
    downstream.
    """
    client = get_redis_client()

    client.lpush(REQ_SEND_QUEUE, uuid)


def queued():
    "Returns all queued requests."
    client = get_redis_client()

    stop = client.llen(REQ_SEND_QUEUE)

    reqs = []

    # Get the full range
    for uuid in client.lrange(REQ_SEND_QUEUE, 0, stop):
        reqs.append(_decode_request(client.hgetall(REQ_PREFIX + uuid)))

    return reqs


def size():
    "Returns the size of the request queue."
    client = get_redis_client()

    return client.llen(REQ_SEND_QUEUE)


def request(uuid):
    "Get a request by UUID."
    client = get_redis_client()

    req = client.hgetall(REQ_PREFIX + uuid)

    return _decode_request(req)


def status(uuid):
    "Get the request status by UUID."
    client = get_redis_client()

    return client.hget(REQ_PREFIX + uuid, 'status')


def cancel(uuid):
    """Cancels a request.

    This will mark the status as 'canceled' on the request if it has not yet
    be completed. If the request is running, a DELETE request will be sent to
    the URL to cancel the operation.
    """
    client = get_redis_client()

    key = REQ_PREFIX + uuid

    # Get the request
    req = _decode_request(client.hgetall(key))

    # Does not exist
    if not req:
        logger.debug('[{}] unknown request'.format(uuid))
        return

    # Already canceled or complete without a result
    if req['status'] == CANCELED:
        logger.debug('[{}] request already canceled'.format(uuid))
        return True

    if req['status'] in {SUCCESS, TIMEOUT, ERROR}:
        logger.debug('[{}] canceling completed request'.format(uuid))

        with client.pipeline() as p:
            p.multi()
            p.hset(key, 'status', 'canceled')
            p.delete(RESP_PREFIX + uuid)
            p.execute()

        return True

    # Handle queued or pending states
    try:
        with client.pipeline() as p:
            p.watch(key)
            p.hset(key, 'status', 'canceled')
            p.execute()
    except redis.WatchError:
        logger.exception('[{}] cancel interrupted, retrying'.format(uuid))
        # Retry cancel since the status most likely changed
        return cancel(uuid)

    # If it was only queued, just return since it will skipped
    # when it is received
    if req['status'] == QUEUED:
        logger.debug('[{}] canceled request'.format(uuid))
        return True

    # Send a DELETE request that may or may not cancel
    # the previous request
    logger.debug('[{}] sending delete request...'.format(uuid))

    try:
        # The req was already running, so send a delete request to
        # the endpoint. It may or may not accept the request
        rp = requests.request(url=req['url'],
                              method='delete',
                              headers=req['headers'],
                              timeout=req['timeout'])

        if 200 <= rp.status_code < 300:
            logger.debug('[{}] successful delete request'.format(uuid))
        else:
            logger.debug('[{}] error handling delete request'.format(uuid))
    except Exception:
        logger.debug('[{}] error sending delete request'.format(uuid))

    return True


def response(uuid):
    "Gets a response by UUID."
    client = get_redis_client()

    return _decode_response(client.hgetall(RESP_PREFIX + uuid))


def purge(uuid):
    "Purge a response."
    client = get_redis_client()

    return client.delete(RESP_PREFIX + uuid)


def receive(uuid):
    "Dequeues and executes a req given it's UUID."
    client = get_redis_client()

    req_key = REQ_PREFIX + uuid

    req = _decode_request(client.hgetall(req_key))

    if not req:
        logger.debug('[{}] unknown request'.format(uuid))
        return

    # Task has been canceled
    if req['status'] == CANCELED:
        logger.debug('[{}] skipping canceled request'.format(uuid))
        return

    # Task in an alternate state
    if req['status'] != QUEUED:
        logger.warning('[{}] request in "{}" state'
                       .format(uuid, req['status']))
        return

    client.hset(req_key, 'status', PENDING)

    try:
        with client.pipeline() as p:
            # Ensure the state does not change from pending
            p.watch(req_key)
            p.multi()

            send_time = _timestamp()

            try:
                logger.debug('[{}] sending request...'.format(uuid))

                rp = requests.request(url=req['url'],
                                      method=req['method'],
                                      data=req.get('data'),
                                      headers=req['headers'],
                                      timeout=req['timeout'])

                logger.debug('[{}] response received'.format(uuid))

                resp = {
                    'uuid': uuid,
                    'status': 'success',
                    'elapsed': rp.elapsed.total_seconds() * 1000,
                    'code': rp.status_code,
                    'reason': rp.reason,
                    'data': rp.text,
                    'headers': dict(rp.headers),
                }
            except requests.Timeout as e:
                logger.debug('[{}] request timeout'.format(uuid))

                resp = {
                    'status': 'timeout',
                    'message': str(e),
                }
            except requests.RequestException as e:
                logger.debug('[{}] request error'.format(uuid))

                resp = {
                    'status': 'error',
                    'message': str(e),
                }

            resp['time'] = send_time
            resp_key = RESP_PREFIX + uuid

            # Update status of request and store response
            p.hset(req_key, 'status', resp['status'])
            p.hmset(resp_key, _encode_response(resp))
            p.execute()

            return resp
    except Exception:
        # Re-queue on front of queue on watch error or some other
        # unexpected error
        client.rpush(REQ_SEND_QUEUE, uuid)

        logger.exception('[{}] receive error, requeuing request'.format(uuid))
