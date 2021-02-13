### What version of gRPC and what language are you using?
Language: python
gRPC:  `grpcio==1.35.0`

### What operating system (Linux, Windows,...) and version?
Linux (Fedora 32)

### What runtime / compiler are you using (e.g. python version or version of gcc)
python 3.8.7


### What did you do?

In the `aio` implementation, I have observed that long-lived stream-stream RPCs leak memory -- but **only** when an interceptor is also used.

Example code is posted to this repo: https://github.com/e-heller/grpc-python-aio-memory-leak

[*Note: I would have preferred to use a canned example like `route_guide.proto` here, but the stream-stream RouteChat RPC is just not conducive to this example.
Instead, I defined an "EchoService" with a single simple stream-stream RPC*]

The example uses this no-op interceptor:
```python
class Interceptor(grpc.aio.StreamStreamClientInterceptor):
    """Noop interceptor"""
    async def intercept_stream_stream(
            self, continuation, call_details, request_iterator):
        return await continuation(call_details, request_iterator)
```

- If you use the interceptor, you observe the memory leaks. 
- If you *remove* the interceptor, there is no apparent leak.

Once the stream-stream call terminates, it appears that all of these objects are finally released and collected. So the leak persists only for the duration of the RPC.


#### How to reproduce?

1.  Compile the [echo.proto](https://github.com/e-heller/grpc-python-aio-memory-leak/blob/main/echo.proto) file

2.  Start the [server.py](https://github.com/e-heller/grpc-python-aio-memory-leak/blob/main/server.py)

3.  Run the [client.py](https://github.com/e-heller/grpc-python-aio-memory-leak/blob/main/client.py)

4.  Observe that the process memory RSS/VSZ grows unbounded. 

    If you like, inject some code into the client to observe what objects are accumulating. 
    I used the [pympler](https://pypi.org/project/Pympler/) lib in the example code (e.g. [here](https://github.com/e-heller/grpc-python-aio-memory-leak/blob/main/client.py#L57))

5.  Observe that if you remove the interceptor and run the `client.py`, the process memory RSS/VSZ remains constant.
    Using `pympler` as above does not show large numbers of uncollected objects.


If you don't want to click through the links above, here is the full `client.py` code. (The other files are really unremarkable.)

```python
import asyncio
import logging
import grpc.aio
import echo_pb2
import echo_pb2_grpc


class Interceptor(grpc.aio.StreamStreamClientInterceptor):

    async def intercept_stream_stream(
            self, continuation, call_details, request_iterator):
        return await continuation(call_details, request_iterator)


async def main():
    # If you remove the interceptor, there does not appear to be any leak
    channel = grpc.aio.insecure_channel('[::]:50051', interceptors=[Interceptor()])

    stream = echo_pb2_grpc.EchoServiceStub(channel).Echo()

    # start tasks to send / receive on the stream
    tasks = [asyncio.create_task(send(stream)),
             asyncio.create_task(recv(stream))]

    # Add this task to log the top objects in memory using pympler library.
    # Demonstrates which objects are not being collected.
    # tasks.append(asyncio.create_task(log_object_summary(interval=30.0)))

    await asyncio.gather(*tasks)


async def send(stream: grpc.aio.StreamStreamCall):
    await stream.wait_for_connection()

    for n in range(0, 1_000_000):
        await asyncio.sleep(0.001)
        await stream.write(echo_pb2.EchoRequest(
            message=f"message: {n}"
        ))

    await stream.done_writing()


async def recv(stream: grpc.aio.StreamStreamCall):
    await stream.wait_for_connection()

    async for response in stream:
        pass


async def log_object_summary(interval: float):
    from pympler import muppy, summary

    while True:
        await asyncio.sleep(interval)
        lines = summary.format_(summary.summarize(muppy.get_objects()), limit=20)
        logging.info('top objects:\n%s', '\n'.join(lines))


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    asyncio.run(main())
```


### What did you expect to see?

No memory leaks!


### What did you see instead?

Memory leaks!

Specifically, you will observe a buildup of these object types, with a clear correlation between them.
```
coroutine
coroutine_wrapper
grpc._cython.cygrpc.__pyx_scope_struct_27_status
_asyncio.Task
_asyncio.FutureIter
weakref
Context
TaskWakeupMethWrapper
```

These objects are not being garbage collected, indicating some kind of leak in the grpc library. The process RSS/VSZ grows without bound as well.

One way to see the uncollected objects building up in memory is to use a library like [pympler](https://pypi.org/project/Pympler/) and print out an object summary periodically.

For example, I injected this as a `Task` in my client code:
```python
async def log_object_summary(interval: float):
    from pympler import muppy, summary

    while True:
        await asyncio.sleep(interval)
        lines = summary.format_(summary.summarize(muppy.get_objects()), limit=20)
        logging.info('top objects:\n%s', '\n'.join(lines))
``` 

After a short while, it will start logging reports like this:
```
                                             types |   # objects |   total size
================================================== | =========== | ============
                                         coroutine |     1424930 |    179.38 MB
                                     _asyncio.Task |      712464 |    108.71 MB
                                   _asyncio.Future |      712461 |     81.53 MB
                                           weakref |      713870 |     49.02 MB
                                           Context |      712472 |     43.49 MB
                                               str |      728402 |     42.72 MB
  grpc._cython.cygrpc.__pyx_scope_struct_27_status |      712456 |     32.61 MB
                                               set |         150 |     32.08 MB
                             TaskWakeupMethWrapper |      712462 |     27.18 MB
                               _asyncio.FutureIter |      712461 |     27.18 MB
                                 coroutine_wrapper |      712458 |     27.18 MB
```

**Note:** once the stream-stream call terminates, it appears that all of these objects are finally collected.  So the leak persists only for the duration of the RPC.


### Anything else we should know about your project / environment?

All files are also in the attached ZIP:

[grpc-python-aio-memory-leak.zip](https://github.com/grpc/grpc/files/5976321/grpc-python-aio-memory-leak.zip)
