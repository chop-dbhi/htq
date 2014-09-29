# HTTP Task Queue (htq)

The HTTP Task Queue provides buffering between sending requests and receiving responses.


- The client POSTs a description of a request to be sent at a later time
- The client recieves an immediate response with a 303 See Other to the queued request with a status. This also contains a link to the response to be accessed once it has been received.
- A worker sends the request in the background and stores the response to be retrieved by the client.
- Once the request's status is in the `success`, `error`, or `timeout` state, the response is ready to be accessed.

See the [tutorial](#tutorial) below for further explanation.

## Dependencies

- Python 3.3+
- Redis 2.4+

## Command-line Interface

```
$ htq -h
HTTP Task Queue (htq) command-line interface

Usage:
    htq server [--host <host>] [--port <port>] [--redis <redis>] [--debug]
    htq worker [--threads <n>] [--redis <redis>] [--debug]

Options:
    -h --help           Show this screen.
    -v --version        Show version.
    --debug             Turns on debug logging.
    --host <host>       Host of the HTTP service [default: localhost].
    --port <port>       Port of the HTTP service [default: 5000].
    --redis <redis>     Host/port of the Redis server [default: localhost:6379].
    --threads <n>       Number of threads a worker should spawn [default: 10].
```

Run the server for the HTTP REST interface.

```
htq server
```

Run the worker to send requests and receive responses.

```
htq worker
```

## API

- `GET /` - Gets all queued requests.
- `POST /` - Sends (queues) a request
- `GET /<uuid>/` - Gets a request by UUID
- `DELETE /<uuid>/` - Cancels a request, deleting it's response if already received
- `GET /<uuid>/response/` - Gets a request's response if it has been received
- `DELETE /<uuid>/response/` - Delete a request's response to clear up space

## Tutorial

Start the HTQ server:

```bash
$ htq server
Starting htq REST server...
 * Running on http://localhost:5000/
```

Send a POST to the service with a JSON encoded structure of the request to be sent. This immediately returns a `303 See Other` response with the `Location` header to the request

```bash
$ curl -i -X POST -H 'Content-Type: application/json' http://localhost:5000 -d '{"url": "http://httpbin.org/ip"}'
HTTP/1.0 303 SEE OTHER
Content-Type: text/html; charset=utf-8
Content-Length: 0
Location: http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 17:18:49 GMT
```

See what the request resource looks like (use the URL from the `Location` header in your output):

```bash
$ curl -i http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 185
Link: <http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/response/>; rel="response",
      <http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/>; rel="self",
      <http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/status/>; rel="status"
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 17:26:05 GMT

{
    "timeout": 60,
    "status": "queued",
    "data": null,
    "headers": {},
    "url": "http://httpbin.org/ip",
    "method": "get",
    "uuid": "a936e1a1-68d8-4433-a0c0-4f4b2111670d",
    "time": 1412011537783
}
```

The above response shows the details of the request such as the URL, method, headers, and request data. Additionally metadata has been captured when the request was queued including the UUID, the time (in milliseconds) when the request was queued, the status of the request and a timeout. The `Link` header shows the related links from this resource including one to the response and the status. The status link is a lightweight:


```bash
$ curl -i http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/status/
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 20
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 17:30:21 GMT

{"status": "queued"}
```

If we were to `curl` the response link, it would block until the response is ready. Since we have not started a worker yet, this would be forever. Let's start a worker to actual send the request. Execute this in a separate shell:

```bash
$ htq worker --debug
Started 10 workers...
[a936e1a1-68d8-4433-a0c0-4f4b2111670d] sending request...
[a936e1a1-68d8-4433-a0c0-4f4b2111670d] response received
```

Starting the worker daemon immediately starts consuming the queue and sending the requests. As you can see, the one sent above has been sent and the response received. Let's check the status of our request.

```bash
$ curl -i http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/status/
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 21
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 17:36:56 GMT

{"status": "success"}
```

Success! Now let's use the link to the response itself.

```bash
$ curl -i http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/response/
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 19291
Link: <http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/>; rel="request",
      <http://localhost:5000/a936e1a1-68d8-4433-a0c0-4f4b2111670d/response/>; rel="self"
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 17:38:22 GMT

{
    "status": "success",
    "time": 1412012019457,
    "code": 200,
    "reason": "OK",
    "elapsed": 79.81,
    "uuid": "62db48a4-e511-4c8e-9c11-32b39758d1ff",
    "headers": {
        "Age": "0",
        "Content-Length": "32",
        "Connection": "Keep-Alive",
        "Access-Control-Allow-Origin": "*",
        "Server": "gunicorn/18.0",
        "Access-Control-Allow-Credentials": "true",
        "Date": "Mon, 29 Sep 2014 17:50:29 GMT",
        "Content-Type": "application/json"
    },
    "data": "{\n  \"origin\": \"159.14.243.254\"\n}"
}
```

The response contains all the elements of an HTTP response including code, reason, headers, and the data (which has been removed for brevity). In addition, the time (in milliseconds) the response was received and the elapsed time (in milliseconds) join the UUID and status metadata.

### Canceling a request

HTQ defines an interface for services to implement for allowing requests to be canceled. For example, if I send a request that is taking longer than I expect (delayed for 30 seconds):

```bash
$ curl -i -X POST -H Content-Type:application/json http://localhost:5000 -d '{"url": "http://httpbin.org/delay/30"}'
HTTP/1.0 303 SEE OTHER
Content-Type: text/html; charset=utf-8
Content-Length: 0
Location: http://localhost:5000/1686e1b7-3b05-4d45-95e8-caf934f540aa/
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 18:00:28 GMT
```

Then I can send a DELETE to the request URL:

```bash
$ curl -i -X DELETE http://localhost:5000/1686e1b7-3b05-4d45-95e8-caf934f540aa/
HTTP/1.0 204 NO CONTENT
Content-Type: text/html; charset=utf-8
Content-Length: 0
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 18:00:41 GMT
```

Now if we check the status, we should see the status has changed to `canceled` (the response is also empty).

```bash
$ curl -i http://localhost:5000/9619b267-760d-4f0a-9f15-eb8ad99cd1c4/status/
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 22
Server: Werkzeug/0.9.6 Python/3.4.1
Date: Mon, 29 Sep 2014 18:01:23 GMT

{"status": "canceled"}
```

Internally this interrupts the request, but also sends a DELETE request to the endpoint (in this `http://httpbin.org/delay/30`). Implementors of services can support the DELETE request to cancel the underlying processing that is occurring. Of course this is specific to the underlying task being performed, but this simple service-level contract provides a consistent mechanism for signaling the the cancellation.
