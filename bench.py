import re
import sys
import time
import responses
import htq


@responses.activate
def run(n):
    responses.add(responses.GET,
                  url=re.compile(r'http://localhost/\d+'),
                  body='{"ok": 1}',
                  status=200,
                  content_type='application/json')

    t0 = time.time()

    for i in range(n):
        htq.send('http://localhost/' + str(i))

    print('sent {} in {}'.format(n, time.time() - t0))

    t0 = time.time()

    for i in range(n):
        uuid = htq.pop()
        htq.receive(uuid)

    print('received {} in {}'.format(n, time.time() - t0))


if __name__ == '__main__':
    from htq.api import get_redis_client

    c = get_redis_client()
    c.flushdb()

    if sys.argv[1:]:
        n = int(sys.argv[1])
    else:
        n = 1000

    run(n)
