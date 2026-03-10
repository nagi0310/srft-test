from constants import *
from socket import *
import struct
import os

class SRFTSocket:
    def __init__(self, src_ip, src_port, rcvbuf=1024*1024*4):
        self.src_ip = src_ip
        self.src_port = src_port
        self.sock = socket(AF_INET, SOCK_RAW, IPPROTO_UDP)
        self.sock.setsockopt(IPPROTO_IP, IP_HDRINCL, 1)
        self.sock.setsockopt(SOL_SOCKET, SO_RCVBUF, rcvbuf)
        self.sock.settimeout(RECV_TIMEOUT)
        #self.sock.bind(("", self.src_port))  # so kernel delivers UDP for this port to us

    def settimeout(self, t):
        self.sock.settimeout(t)

    def close(self):
        self.sock.close()

    def _checksum(self, data):
        if len(data) % 2:
            data += b"\x00"
        s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
        s = (s >> 16) + (s & 0xffff)
        s += s >> 16
        return ~s & 0xffff 

    def _make_ip_header(self, dst_ip, payload_len, protocol=IPPROTO_UDP):
        version = 4
        ihl = 5
        tos = 0
        total_len = ihl * 4 + payload_len
        ip_id = os.getpid() & 0xFFFF
        frag_off = 0
        ttl = 64 
        checksum = 0
        src = inet_aton(self.src_ip)
        dst = inet_aton(dst_ip)

        ver_ihl = (version << 4) | ihl 

        header = struct.pack('!BBHHHBBH4s4s',
            ver_ihl, tos, total_len, ip_id, frag_off, ttl, protocol, checksum, src, dst
        )

        cs = self._checksum(header)
        header = struct.pack('!BBHHHBBH4s4s',
            ver_ihl, tos, total_len, ip_id, frag_off, ttl, protocol, cs, src, dst
        )
        return header

    def _make_udp_header(self, dst_port, payload):
        length = 8 + len(payload)
        header = struct.pack("!HHHH", self.src_port, dst_port, length, 0)

        ## Calculate checksum based on the header and payload
        cs = self._checksum(header + payload)
        header = struct.pack("!HHHH", self.src_port, dst_port, length, cs)
        return header

    def _parse_ip_header(self, data):
        ip_header = data[:20]
        fields = struct.unpack('!BBHHHBBH4s4s', ip_header)
        ihl = (fields[0] & 0x0F) * 4
        protocol = fields[6]
        src_ip = inet_ntoa(fields[8])
        dst_ip = inet_ntoa(fields[9])
        return ihl, protocol, src_ip, dst_ip

    def _parse_udp_header(self, data):
        udp_header = data[:8]
        src_port, dst_port, length, _ = struct.unpack('!HHHH', udp_header)
        payload = data[8:]
        ## Validate checksum to check if packet get corrupted
        if self._checksum(data[:length]) != 0:
            raise ValueError(f"UDP checksum failed: packet corrupted")
        return src_port, dst_port, payload


    def send_packet(self, dst_ip, dst_port, payload):
        udp_hdr = self._make_udp_header(dst_port, payload)
        ip_hdr = self._make_ip_header(dst_ip, len(udp_hdr) + len(payload))
        self.sock.sendto(ip_hdr + udp_hdr + payload, (dst_ip, 0))

    def recv_packet(self):
        while True:
            raw, _ = self.sock.recvfrom(65535)
            try:
                ihl, _, src_ip, _       = self._parse_ip_header(raw)
                src_port, dst_port, payload = self._parse_udp_header(raw[ihl:])
                if dst_port != self.src_port:
                    continue
                return src_ip, src_port, payload
            except ValueError as e:
                print(f"[SRFTSocket] {e}, dropping")
                continue
