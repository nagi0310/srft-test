# constants.py
import struct
SERVER_PORT  = 80
CLIENT_PORT  = 12345
CHUNK_SIZE   = 1400
SEND_DELAY   = 0.005
RECV_TIMEOUT = 120.0
MAX_RETRIES  = 10      # maximun number of retransmission
RETX_TIMEOUT = 0.5    # Timeout before retransmission
WINDOW_SIZE = 256      # number of unACKed packets in flight at once    

FLAG_START = 0x08
FLAG_DATA  = 0x01
FLAG_ACK   = 0x02
FLAG_EOF   = 0x04

APP_HDR_FMT  = '!IIBBI'
APP_HDR_SIZE = struct.calcsize(APP_HDR_FMT)

OUTPUT_DIR  = "./received_files"
FILES_DIR = "./"