"""Minimal WebSocket client (RFC 6455) for Hyperion on 127.0.0.1:8090.

Stdlib sockets only. Server frames are unmasked; client frames are masked.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import struct
from typing import List, Optional, Tuple

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def accept_key(client_key: str) -> str:
    digest = hashlib.sha1((client_key + _GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_client_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    header = bytes((0x80 | (opcode & 0x0F),))
    length = len(payload)
    if length < 126:
        header += bytes((0x80 | length,))
    elif length < 65536:
        header += bytes((0x80 | 126,)) + struct.pack(">H", length)
    else:
        header += bytes((0x80 | 127,)) + struct.pack(">Q", length)
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return header + mask + masked


def decode_server_frames(buf: bytes) -> Tuple[List[Tuple[int, bytes]], bytes]:
    """Pull complete server frames out of ``buf``. Return (frames, leftover)."""
    frames: List[Tuple[int, bytes]] = []
    i = 0
    n = len(buf)
    while i + 2 <= n:
        start = i
        b1 = buf[i + 1]
        opcode = buf[i] & 0x0F
        masked = (b1 & 0x80) != 0
        length = b1 & 0x7F
        i += 2
        if length == 126:
            if i + 2 > n:
                return frames, buf[start:]
            length = struct.unpack(">H", buf[i : i + 2])[0]
            i += 2
        elif length == 127:
            if i + 8 > n:
                return frames, buf[start:]
            length = struct.unpack(">Q", buf[i : i + 8])[0]
            i += 8
        mask_key = b""
        if masked:
            if i + 4 > n:
                return frames, buf[start:]
            mask_key = buf[i : i + 4]
            i += 4
        if i + length > n:
            return frames, buf[start:]
        data = buf[i : i + length]
        i += length
        if masked:
            data = bytes(b ^ mask_key[j % 4] for j, b in enumerate(data))
        frames.append((opcode, data))
    return frames, buf[i:]


class WsConnection:
    """One blocking WebSocket. Callers set their own timeouts."""

    def __init__(self, host: str, port: int, timeout: float = 1.5, path: str = "/") -> None:
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self.path = path or "/"
        self._sock: Optional[socket.socket] = None
        self._buf = b""

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), self.timeout)
        sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s:%s\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ) % (self.path, self.host, self.port, key)
        sock.sendall(req.encode("ascii"))
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise OSError("websocket handshake closed")
            data += chunk
            if len(data) > 16384:
                sock.close()
                raise OSError("websocket handshake too large")
        head, rest = data.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0]
        if b"101" not in status:
            sock.close()
            raise OSError("websocket upgrade rejected")
        self._sock = sock
        self._buf = rest

    def send_text(self, text: str) -> None:
        if self._sock is None:
            raise OSError("websocket closed")
        self._sock.sendall(encode_client_frame(text.encode("utf-8"), 0x1))

    def recv_data(self) -> List[Tuple[int, bytes]]:
        if self._sock is None:
            raise OSError("websocket closed")
        try:
            chunk = self._sock.recv(65536)
        except socket.timeout:
            chunk = b""
        if chunk:
            self._buf += chunk
        frames, self._buf = decode_server_frames(self._buf)
        return frames

    def close(self) -> None:
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
