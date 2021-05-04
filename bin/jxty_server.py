#!/usr/bin/python3
import time
import struct
import os.path
import threading
import socketserver


class Shadow:
    shadow = {}

    def __init__(self):
        try:
            with open('shadow', 'br') as shadow:
                while True:
                    username = shadow.read(64)
                    password = shadow.read(64)
                    if username and password:
                        self.shadow[username] = password
                    else:
                        break
        except OSError:
            pass

    def __contains__(self, item):
        return item in self.shadow

    def __getitem__(self, key):
        return self.shadow[key]

    def __setitem__(self, key, value):
        self.shadow[key] = value

    def insert(self, nickname, password):
        self.shadow[nickname] = password

    def save(self):
        with open('shadow', 'bw') as shadow:
            for username, password in self.shadow.items():
                shadow.write(username)
                shadow.write(password)


class Main(socketserver.StreamRequestHandler):
    buf = {}  # nickname -> msg_buffer
    online = {}  # address -> nickname
    upload_dir = "./upload"

    def cmd_d(self, format, size):
        return struct.unpack('!' + format, self.rfile.read(size))

    def cmd_e(self, ctrl, format, *v):
        vv = [i.encode() if isinstance(i, str) else i for i in v]
        self.wfile.write(ctrl.encode() + struct.pack('!' + format, *vv))

    def done_login(self):
        print(self.nickname.decode().rstrip("\0"), "online")
        Main.buf[self.nickname] = []
        Main.online[self.client_address] = self.nickname

        self.upload_dir = "/".join([Main.upload_dir, self.nickname.decode().rstrip("\0")])
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

    def done_logout(self):
        if Main.online[self.client_address]:
            print(self.nickname.decode().rstrip("\0"), "offline")
            del Main.buf[Main.online[self.client_address]]
        del Main.online[self.client_address]

    def done_download(self):
        partial, file_name = self.cmd_d("Q64s", 72)
        file_name = file_name.decode().rstrip("\0")
        target = self.nickname.decode().rstrip("\0")
        file_path = "/".join([Main.upload_dir, target, file_name])
        try:
            size = os.stat(file_path).st_size
        except:
            size = 0

        print(size)

        self.lock.acquire()
        self.cmd_e("d", "Q", size)
        if size == 0:
            self.lock.release()
            return 
        with open(file_path, 'rb') as f:
            f.seek(partial)
            while partial < size:
                slice = f.read(4096)
                partial += 4096
                self.wfile.write(slice)
        self.lock.release()

    def done_upload(self):
        size, file_name, target = self.cmd_d('Q64s64s', 136)
        file_name = file_name.decode().rstrip("\0")
        target = target.decode().rstrip("\0")
        file_path = "/".join([Main.upload_dir, target, file_name])
        try:
            partial = os.stat(file_path).st_size
        except:
            partial = 0
        self.lock.acquire()
        self.cmd_e("u", "Q", partial)
        self.lock.release()
        with open(file_path, "ab") as f:
            while size > partial:
                slice = self.rfile.read(size-partial)
                partial += len(slice)
                f.write(slice)

    def forward(self):
        try:
            while self.client_address in Main.online:
                nickname = Main.online[self.client_address]
                if nickname in Main.buf:
                    buf = Main.buf[nickname]
                    if buf:
                        self.lock.acquire()
                        for nickname, content in buf:
                            self.cmd_e('m', '64s256s', nickname, content)
                        buf.clear()
                        self.lock.release()
        except KeyError:
            print("Jackpot!")

    def setup(self):
        super().setup()
        Main.online[self.client_address] = None
        self.lock = threading.Condition()

        if not os.path.exists(Main.upload_dir):
            os.makedirs(Main.upload_dir)

    def handle(self):
        forward_thrd = threading.Thread(target=self.forward)
        forward_thrd.start()

        while True:
            ctrl = self.rfile.read(1)
            if not ctrl:
                return  # auto close connection
            self.lock.acquire()
            if ctrl == b'l':
                self.nickname, password = self.cmd_d('64s64s', 128)
                if self.nickname in shadow:
                    if password == shadow[self.nickname]:
                        if self.nickname in Main.buf:
                            self.cmd_e('F', '64s', 'The same user is online.')
                        else:
                            self.done_login()
                            self.cmd_e('I', '64s', 'Login succeeded.')
                    else:
                        self.cmd_e('F', '64s', 'Wrong password.')
                else:
                    # register
                    shadow.insert(self.nickname, password)
                    # login
                    self.done_login()
                    self.cmd_e('I', '64s', 'Register succeeded.')
            elif ctrl == b'p':
                self.cmd_e('p', 'h', len(Main.buf))
                for nickname in Main.buf:
                    self.cmd_e('', '64s', nickname)
            elif ctrl == b'm':
                target, content = self.cmd_d('64s256s', 320)
                if target in Main.buf:
                    Main.buf[target].append((self.nickname, content))
                    self.cmd_e('I', '64s', 'Message Sent.')
                else:
                    self.cmd_e('E', '64s', 'Unreachable target.')
            elif ctrl == b'u':
                self.done_upload()
            elif ctrl == b'd':
                self.done_download()
            self.lock.release()

    def finish(self):
        self.done_logout()
        super().finish()


if __name__ == '__main__':
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    shadow = Shadow()
    try:
        with socketserver.ThreadingTCPServer(('', 5866), Main) as main:
            main.serve_forever()
    except KeyboardInterrupt:
        shadow.save()
