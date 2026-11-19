import json
import socket
import threading
import struct
import time
from typing import Callable, Optional


class MessageCodec:
    @staticmethod
    def encode(message) -> bytes:
        return json.dumps(message, separators=(",", ":"), sort_keys=True).encode("utf-8")

    @staticmethod
    def decode(payload: bytes):
        return json.loads(payload.decode("utf-8"))


class UDPChannel:
    """Dependency-free UDP datagram transport."""
    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 codec: Optional[MessageCodec] = None):
        self.address = (host, port)
        self.codec = codec or MessageCodec()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.address)
        self.address = self.socket.getsockname()
        self.socket.settimeout(0.1)
        self._closed = False
        self._lock = threading.RLock()

    def send(self, message, address):
        payload = self.codec.encode(message)
        if len(payload) > 65507:
            raise ValueError("UDP payload exceeds maximum datagram size")
        with self._lock:
            return self.socket.sendto(payload, address)

    def receive(self) -> Optional[tuple]:
        try:
            payload, address = self.socket.recvfrom(65535)
            return self.codec.decode(payload), address
        except socket.timeout:
            return None
        except json.JSONDecodeError:
            return None

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self.socket.close()


class TCPChannel:
    """Length-prefixed JSON stream transport."""
    def __init__(self, sock: Optional[socket.socket] = None,
                 codec: Optional[MessageCodec] = None):
        self.socket = sock or socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.codec = codec or MessageCodec()
        self._buffer = bytearray()
        self._lock = threading.RLock()

    def connect(self, address):
        self.socket.connect(address)

    def listen(self, address, backlog: int = 5):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(address)
        self.socket.listen(backlog)

    def accept(self):
        connection, address = self.socket.accept()
        return TCPChannel(connection, self.codec), address

    def send(self, message) -> None:
        payload = self.codec.encode(message)
        framed = struct.pack(">I", len(payload)) + payload
        with self._lock:
            return self.socket.sendall(framed)

    def receive(self) -> Optional[object]:
        while len(self._buffer) < 4:
            payload = self.socket.recv(4096)
            if not payload:
                return None
            self._buffer.extend(payload)
        length = struct.unpack(">I", self._buffer[:4])[0]
        if length > 16 * 1024 * 1024:
            raise ValueError("TCP message exceeds 16 MiB")
        while len(self._buffer) < 4 + length:
            payload = self.socket.recv(4096)
            if not payload:
                return None
            self._buffer.extend(payload)
        message = self.codec.decode(bytes(self._buffer[4:4 + length]))
        del self._buffer[:4 + length]
        return message

    def close(self):
        self.socket.close()


class ReliablePacketChannel:
    """Sequence/acknowledgement wrapper for lossy UDP datagrams."""
    def __init__(self, udp: UDPChannel):
        self.udp = udp
        self.sequence = 0
        self.acknowledged = set()
        self.pending = {}

    def send_reliable(self, message, address,
                      retransmit_interval: float = 0.25):
        sequence = self.sequence
        self.sequence += 1
        envelope = {
            "sequence": sequence,
            "reliable": True,
            "message": message,
            "sent_at": time.monotonic(),
        }
        self.pending[sequence] = (envelope, address, retransmit_interval)
        self.udp.send(envelope, address)
        return sequence

    def receive_reliable(self):
        received = self.udp.receive()
        if received is None:
            return None
        envelope, address = received
        if isinstance(envelope, dict) and "ack" in envelope:
            self.acknowledge(int(envelope["ack"]))
            return None
        if not isinstance(envelope, dict) or "sequence" not in envelope:
            return envelope, address
        sequence = envelope["sequence"]
        if sequence in self.acknowledged:
            self.udp.send({"ack": sequence}, address)
            return None
        self.acknowledged.add(sequence)
        self.udp.send({"ack": sequence}, address)
        return envelope.get("message"), address

    def update(self):
        now = time.monotonic()
        for sequence, (envelope, address, interval) in list(self.pending.items()):
            if now - envelope["sent_at"] >= interval:
                envelope["sent_at"] = now
                self.udp.send(envelope, address)

    def acknowledge(self, sequence: int):
        self.pending.pop(sequence, None)
