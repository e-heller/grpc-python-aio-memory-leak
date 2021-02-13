#!/usr/bin/env python3
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
