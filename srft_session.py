import struct
from socket import *
from constants import *
import threading
import time
from srft_socket import SRFTSocket
from packet_buffer import PacketBuffer
class SRFTSession:
    def __init__(self, sock: SRFTSocket, port):
        self.sock = sock
        self.port = port
        self.retx_counter = 0
    
    def _make_app_header(self, seq, ack, flags, total=0):
        return struct.pack(APP_HDR_FMT, seq, ack, flags, 0, total)
    
    def _parse_app_header(self, data):
        seq, ack, flags, _, total = struct.unpack_from(APP_HDR_FMT, data)
        return seq, ack, flags, total, data[APP_HDR_SIZE:]
    

    def _send(self, dst_ip, dst_port, seq, flags, data=b'', total=0):
        payload = self._make_app_header(seq, 0, flags, total) + data
        self.sock.send_packet(dst_ip, dst_port, payload)

    def send_ack(self, dst_ip, dst_port, seq):
        packet = self._make_app_header(seq, seq, FLAG_ACK)
        self.sock.send_packet(dst_ip, dst_port, packet)

    def recv(self):
        src_ip, src_port, raw = self.sock.recv_packet()
        seq, ack, flags, total, payload = self._parse_app_header(raw)
        return src_ip, src_port, seq, ack, flags, total, payload

    def send_reliable(self, dst_ip, dst_port, seq, flags, data, total=0):
        for attempt in range(MAX_RETRIES):
            ## send packet
            self._send(dst_ip, dst_port, seq, flags, data, total)
            try:
                self.sock.settimeout(RETX_TIMEOUT)
                ## receive and parse reply
                while True:
                    src_ip, src_port, raw = self.sock.recv_packet()
                    ack_seq, _, ack_flags, _, _ = self._parse_app_header(raw)
                    if ack_flags & FLAG_ACK and ack_seq == seq:
                        return True
            except timeout:
                self.retx_counter += 1 
                print(f"[SRFTSession] Timeout seq={seq}, retry {attempt+1}/{MAX_RETRIES}")
        
        print(f"[SRFTSession] Failed to get ACK for seq={seq} after {MAX_RETRIES} retries")
        return False

    def send_window(self, dst_ip, dst_port, chunks, total):   
        '''
        2 threads: one to send chunk, one to receive acks
        '''
        # convert generator to list so we can index into it for retransmission
        # done lazily — only reads ahead by WINDOW_SIZE chunks at a time
        chunk_list = []
        chunk_iter = iter(chunks)
        exhausted  = False
        base = 0 # first unACKed seq
        next_seq = 0 # next seq to send
        timers = {} # timers for each packet
        done = threading.Event() # if done stop the ACK thread
        lock = threading.Lock()

        ## Thread to receive ACKs
        def ack_receiver():
            nonlocal base
            while not done.is_set():
                try:
                    self.sock.settimeout(RETX_TIMEOUT)
                    ## receive and parse reply
                    src_ip, src_port, raw = self.sock.recv_packet()
                    ack_seq, _, ack_flags, _, _ = self._parse_app_header(raw)
                    if not (ack_flags & FLAG_ACK) :
                        continue
                    with lock:
                        if ack_seq >= base:
                            # remove the timer for already received packet
                            for seq in range(base, ack_seq + 1):
                                timers.pop(seq, None)
                            # update base (move the window)
                            base = ack_seq + 1
                            # print(f"[SRFTSession] ACK={ack_seq}, window=[{base},{base+WINDOW_SIZE})", end='\n')
                            if ack_seq % 10000 == 0:
                                print(f"[SRFTSession] seq={ack_seq} received")

                except timeout:
                    continue
                except Exception as e:
                    print(f"[SRFTSession] ACK recv error: {e}")

        ack_thread = threading.Thread(target=ack_receiver, daemon=True)
        ack_thread.start()

        # Thread to send Chunks
        while True:
            ## Check if all packets received
            with lock:
                all_acked = (base >= total)
            if all_acked:
                break

            with lock:
                # Read ahead from generator to fill window
                while not exhausted and len(chunk_list) < base + WINDOW_SIZE:
                    chunk = next(chunk_iter, None)
                    if chunk is None:
                        exhausted = True
                        total = len(chunk_list)  
                        break
                    chunk_list.append(chunk)

                # All chunks sent and ACKed
                if exhausted and base >= total:
                    break
                # Send packets winthin the window
                while next_seq < total and next_seq < base + WINDOW_SIZE:
                    self._send(dst_ip, dst_port, next_seq, FLAG_DATA, chunk_list[next_seq])
                    timers[next_seq] = time.time()
                    next_seq += 1

                # Retransmit if timeout
                now = time.time()
                for seq in range(base, next_seq):
                    if seq in timers and now - timers[seq] > RETX_TIMEOUT:
                        self._send(dst_ip, dst_port, seq, FLAG_DATA, chunk_list[seq])
                        timers[seq] = now
                        self.retx_counter += 1
                        print(f"[SRFTSession] Retransmit seq={seq+1}")
        done.set()
        ack_thread.join()

    def recv_window(self, total):
        buf = PacketBuffer(WINDOW_SIZE * 2)
        next_seq = 0 # next seq we need to advance cumulative ACK

        while True:
            try:
                self.sock.settimeout(RECV_TIMEOUT)
                src_ip, src_port, raw = self.sock.recv_packet()
                seq, _, flags, _, payload = self._parse_app_header(raw)

                if flags & FLAG_EOF:
                    self.send_ack(src_ip, src_port, seq)
                    return buf, payload.decode().strip()
                
                if flags & FLAG_DATA:
                    buf.add(seq, payload)

                while next_seq in buf.chunks:
                    next_seq += 1
                self.send_ack(src_ip, src_port, next_seq - 1)
            except timeout:
                print("[SRFTSession] Recv timeout waiting for data")
                break
        return buf, None