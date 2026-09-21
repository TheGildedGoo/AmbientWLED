import json
import socket

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen


class WledClient(object):
    def __init__(self, host, http_port=80):
        self.host = host
        self.http_port = http_port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def info(self):
        url = "http://%s:%s/json/info" % (self.host, self.http_port)
        req = Request(url)
        with urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def release_live(self):
        payload = json.dumps({"live": False}).encode("utf-8")
        url = "http://%s:%s/json/state" % (self.host, self.http_port)
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            urlopen(req, timeout=2).read()
        except Exception:
            pass

    def send_ddp(self, pixels, rgbw=False, brightness=255):
        channels = 4 if rgbw else 3
        data = bytearray()
        for pix in pixels:
            data.extend(pix[:channels])
        header = bytearray(10)
        header[0] = 0x41
        header[1] = 0x01
        header[2] = 0x00
        header[3] = 0x01
        header[8] = (len(pixels) >> 8) & 0xFF
        header[9] = len(pixels) & 0xFF
        packet = header + data
        if brightness < 255:
            scale = brightness / 255.0
            packet = header + bytearray(int(b * scale) for b in data)
        self._sock.sendto(packet, (self.host, 4048))
