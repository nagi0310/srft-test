from constants import *
from srft_socket import SRFTSocket
from srft_session import SRFTSession
from packet_buffer import PacketBuffer
import time
import os
import sys
import hashlib
def run_client(server_ip, client_ip, filename):
    ## Make the output path
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, os.path.basename(filename))

    ## Set up connection
    sock    = SRFTSocket(src_ip=client_ip, src_port=CLIENT_PORT)
    sock.settimeout(RECV_TIMEOUT)
    session = SRFTSession(sock, CLIENT_PORT)

    ## Send file request
    session.send_reliable(server_ip, SERVER_PORT, 0, FLAG_DATA, filename.encode())
    print(f"[Client] Requested file '{filename}' from {client_ip}:{CLIENT_PORT}")

    ## Wait for START to learn total number of chunks
    _, server_port, seq, _, flags, total, _ = session.recv()
    if not flags & FLAG_START:
        print("[Client] Expected START packet"); return
    session.send_ack(server_ip, SERVER_PORT, seq)
    print(f"[Client] Expecting {total} chunks")

    ## Receive all chunks
    start_time = time.time()
    buf, received_md5 = session.recv_window(total)
    if received_md5 is None:
        print("[Client] Did not receive MD5 from server")
        return

    ## Calculate the transfer time
    elapsed = time.time() - start_time

    ## Assemble and verify the file:
    file_bytes = buf.assemble()
    actual_md5 = hashlib.md5(file_bytes).hexdigest()
    md5 = actual_md5 == received_md5

    if file_bytes: 
       with open(output_path, "wb") as f:
           f.write(file_bytes)
    else: 
        print("[Client] No data received.")
        return
    
    ## Print out information
    print(f"\n[Client] File saved    : {output_path}")
    print(f"[Client] Packets recvd : {len(buf.chunks)}/{total}")
    print(f"[Client] Bytes recvd   : {len(file_bytes)}")
    print(f"[Client] Time          : {elapsed:.2f}s")
    print(f"[Client] MD5 match     : {'YES' if md5 else 'NO — file corrupted'}")
   

def main():
    if len(sys.argv) < 4:
        print("Usage: python SRFT_UDPClient.py <server_ip> <client_ip> <filename> ")
        sys.exit(1)
    server_ip = sys.argv[1]
    client_ip = sys.argv[2]
    filename = sys.argv[3]
    
    run_client(server_ip, client_ip, filename)

if __name__ == "__main__":
    main()