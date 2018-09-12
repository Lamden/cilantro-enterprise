import zmq.asyncio
import asyncio
from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.logger import get_logger
from collections import deque
from cilantro.constants.overlay_network import CLIENT_SETUP_TIMEOUT
from cilantro.utils.utils import is_valid_hex
from cilantro.protocol import wallet
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol.structures import EnvelopeAuth
from cilantro.protocol.overlay.ironhouse import Ironhouse
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from nacl.signing import SigningKey

# TODO Better name for SocketManager? SocketManager is also responsible for handling the OverlayClient, so maybe we
# should name it something that makes that more obvious
class SocketManager:

    def __init__(self, signing_key: str, context=None, loop=None):
        assert is_valid_hex(signing_key, 64), "signing_key must a 64 char hex str not {}".format(signing_key)

        self.log = get_logger(type(self).__name__)

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)
        self.public_key = Ironhouse.vk2pk(self.verifying_key)
        self.secret = crypto_sign_ed25519_sk_to_curve25519(SigningKey(seed=bytes.fromhex(signing_key))._signing_key)

        self.loop = loop or asyncio.get_event_loop()
        self.context = context or zmq.asyncio.Context()
        self.secure_context, self.auth = Ironhouse.secure_context(context, async=True)

        self.sockets = []
        self.pending_lookups = {}   # A dict of 'event_id' to socket instance
        self.overlay_client = OverlayClient(self._handle_overlay_event, loop=self.loop, ctx=self.context)

    def create_socket(self, socket_type, secure=False, domain='*', *args, **kwargs) -> LSocket:
        assert type(socket_type) is int and socket_type > 0, "socket type must be an int greater than 0, not {}".format(socket_type)

        ctx = self.secure_context if secure else self.context
        zmq_socket = ctx.socket(socket_type, *args, **kwargs)

        socket = LSocket(zmq_socket, manager=self, secure=secure, domain=domain)
        self.sockets.append(socket)

        return socket

    def _handle_overlay_event(self, e):
        self.log.spam("SocketManager got overlay event {}".format(e))
        self.log.important2("SocketManager got overlay event {}".format(e))  # TODO remove

        if e['event'] == 'got_ip':
            assert e['event_id'] in self.pending_lookups, "Overlay returned event {} that is not in pending_lookups {}!"\
                                                          .format(e, self.pending_lookups)

            sock = self.pending_lookups.pop(e['event_id'])
            sock.handle_overlay_event(e)
        else:
            # TODO handle all events. Or write code to only subscribe to certain events
            self.log.warning("Composer got overlay event {} that it does not know how to handle. Ignoring.".format(e))
            return
