#!/usr/bin/env python3
import concurrent.futures
import logging

import grpc

import echo_pb2
import echo_pb2_grpc


class EchoServicer(echo_pb2_grpc.EchoServiceServicer):

    def Echo(self, request_iterator, context):
        for request in request_iterator:
            yield echo_pb2.EchoResponse(
                message=request.message,
            )


def serve():
    server = grpc.server(concurrent.futures.ThreadPoolExecutor())
    echo_pb2_grpc.add_EchoServiceServicer_to_server(
        EchoServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    serve()
