class PacketBuffer:
    def __init__(self, window_size = 256):
        self.chunks = {}
        self.window_size = window_size
        self.seen = set()
        self.base = 0

    def add(self, seq, data):
        ## Reject packets outside the window
        if seq <  self.base or seq >= self.base + self.window_size:
            print(f"[PacketBuffer] seq={seq} outside window, dropping")
            return False
        ## Reject duplicated packets
        if seq in self.seen:
            print(f"[PacketBuffer] seq={seq} duplicated, dropping")
            return False
        ## Add newly received packets and move the window
        self.chunks[seq] = data
        self.seen.add(seq)

        ## slide forward window (prevent packets arrive out of order)
        while self.base in self.seen:
            self.base += 1
        return True

    def is_complete(self, total):
        if len(self.chunks) == total:
            return True
        else:
            return False
        
    def assemble(self):
        return b''.join(self.chunks[i] for i in sorted(self.chunks))