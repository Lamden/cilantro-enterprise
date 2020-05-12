from cilantro_ee.logger.base import get_logger
import zmq

from cilantro_ee.struct import SocketStruct

log = get_logger("BaseServices")

SOCKETS = {}

async def get(socket_id: SocketStruct, msg: bytes, ctx:zmq.Context, timeout=1000, linger=500, retries=10, dealer=True):
    if retries < 0:
        return None

    if SOCKETS.get(str(socket_id)) is not None:
        socket = SOCKETS[str(socket_id)]
        print('bazinga')
    else:
        if dealer:
            socket = ctx.socket(zmq.DEALER)
        else:
            socket = ctx.socket(zmq.REQ)

        socket.setsockopt(zmq.LINGER, linger)
        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
        socket.connect(str(socket_id))
    try:
        # Allow passing an existing socket to save time on initializing a _new one and waiting for connection.
        await socket.send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await socket.recv()

            socket.close()

            return response
        else:
            socket.close()
#            socket.disconnect(str(socket_id))
            return None
    except Exception as e:
        socket.close()
#        socket.disconnect(str(socket_id))
        return await get(socket_id, msg, ctx, timeout, linger, retries-1)

