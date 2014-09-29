from .api import REQ_SEND_QUEUE
from .db import get_redis_client


def iter_queue():
    "Returns a blocking iterator of request UUIDs from the queue."
    client = get_redis_client()

    while True:
        yield client.brpop(REQ_SEND_QUEUE)[1]
