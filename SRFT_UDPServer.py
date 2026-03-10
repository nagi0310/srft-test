from constants import *
from srft_socket import SRFTSocket
from srft_session import SRFTSession
import os
import time
import sys
import hashlib

def run_server(server_ip):
    sock = SRFTSocket(server_ip, SERVER_PORT)
    session = SRFTSession(sock, SERVER_PORT)
    while True:
        try:
            ## Receive file request
            client_ip, client_port, seq, _, flags, _, payload  = session.recv()
            if not (flags & FLAG_DATA):
                continue
            filename = payload.decode(errors="replace").strip()
            print(f"[Server] Request from {client_ip}:{client_port} → file: '{filename}'")
            session.send_ack(client_ip, client_port, seq)

            ## Make the filepath
            filepath = os.path.join(FILES_DIR, filename)
            if not os.path.isfile(filepath):
                # Send error message
                err_msg = f"ERROR: File '{filename}' not found.".encode()
                session.send_reliable(client_ip, client_port, 0, FLAG_DATA, err_msg)
                print(f"[Server] File not found, sent error to client.")
                continue

            print(f"File: '{filename}' founded")

            ## Send file in chunks
            file_size = os.path.getsize(filepath)
            total     = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
            start_time = time.time()

            # send START 
            session.send_reliable(client_ip, client_port, 0, FLAG_START, b'', total=total)

            ## instead of send all chunks, yield one chunk to send_window at a time
            md5_hash = hashlib.md5()

            def chunk_generator():
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        md5_hash.update(chunk)
                        yield chunk

            session.send_window(client_ip, client_port, chunk_generator(), total)
            file_md5 = md5_hash.hexdigest()
                    
            ## Send EOF and md5 as end of the file
            session.send_reliable(client_ip, client_port, total + 1, FLAG_EOF, file_md5.encode())
        

            elapsed = time.time() - start_time

            print(f"[Server] Total packets sent : {total}")
            print(f"[Server] Total bytes Sent   : {file_size}")
            print(f"[Server] Transfer time          : {elapsed:.2f}s")
            print(f"[Server] MD5           : {file_md5}")
            session.retx_counter = 0  ## reset for next transmission

        except KeyboardInterrupt:
            print("\n[Server] Shutting down.")
            break

        except Exception as e:
            print(f"[Server] Error: {e}")
            continue  # keep socket open for next client

    sock.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python SRFT_UDPClient.py <server_ip>")
        sys.exit(1)
    server_ip = sys.argv[1]
    run_server(server_ip)
if __name__ == "__main__":
    main()



