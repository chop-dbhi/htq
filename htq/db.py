import redis


_redis_client = None


def get_redis_client(*args, **kwargs):
    global _redis_client

    if not _redis_client:
        kwargs['decode_responses'] = True
        _redis_client = redis.StrictRedis(*args, **kwargs)

    return _redis_client
