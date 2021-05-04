#!/usr/bin/python3
import cmd
import time
import struct
import socket
import getpass
import hashlib
import os.path
import threading


def wait(lock):
    lock.acquire()
    lock.wait()
    lock.release()


def notify(lock):
    lock.acquire()
    lock.notify()
    lock.release()


class Cmd(cmd.Cmd):
    download_dir = "./download"

    def __init__(self):
        super().__init__()

        self.nickname = input('Nickname: ')
        self.target = self.nickname
        self.set_prompt()

        self.file_size = 0

        if not os.path.exists(Cmd.download_dir):
            os.makedirs(Cmd.download_dir)

        sha512 = hashlib.sha512()
        sha512.update(getpass.getpass('Password: ').encode())
        self.password = sha512.digest()

        self.cmd_login()
        wait(parse)

    def cmd_e(self, ctrl, format, *v):
        vv = [i.encode() if isinstance(i, str) else i for i in v]
        conn.sendall(ctrl.encode() + struct.pack('!' + format, *vv))

    def cmd_login(self):
        self.cmd_e('l', '64s64s', self.nickname, self.password)
        self.download_dir = "/".join([Cmd.download_dir,
                                      self.nickname])

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def do_EOF(self, arg):
        'Exit.'
        exit()
    
    def do_exit(self, arg):
        'Exit.'
        exit()
    
    def do_quit(self, arg):
        'Exit.'
        exit()

    def do_download(self, arg):
        'Usage: download <file_name> [file_new_name]'
        if not arg:
            ERROR("Syntax error.")
            return
        args = arg.split()
        file_name = args[0]
        if len(args) > 1:
            file_alias = args[1]
        else:
            file_alias = file_name
        file_path = "/".join([self.download_dir, file_alias])
        try:
            partial = os.stat(file_path).st_size
        except:
            partial = 0


        self.cmd_e("d", "Q64s", partial, file_name)
        wait(parse)

        print(file_name, file_alias, partial, self.file_size)
        if self.file_size == 0:
            ERROR("File not found.")
            return
        print(self.file_size, partial)
        with open(file_path, "ab") as f:
            while self.file_size > partial:
                slice = conn.recv(self.file_size-partial)
                partial += len(slice)
                f.write(slice)
                INFO("Recieved: {}/{}".format(partial, self.file_size))
        self.file_size = 0
        notify(parse)

    def do_message(self, arg):
        'Usage: message <content>'
        if self.target:
            self.cmd_e('m', '64s256s', self.target, arg)
        else:
            ERROR("No target.")
            return
        wait(parse)

    def do_peers(self, arg):
        'Show online users.'
        self.cmd_e('p', '')
        wait(parse)

    def do_target(self, arg):
        'Usage: target [user_id]'
        self.target = arg if arg else self.nickname
        self.set_prompt()

    def do_upload(self, arg):
        'Usage: upload <file_path> [file_name]'
        if not arg:
            ERROR("Syntax error.")
            return
        args = arg.split()
        file_path = args[0]
        if len(args) > 1:
            file_name = args[1]
        else:
            file_name = os.path.basename(file_path)
        try:
            size = os.stat(file_path).st_size
            with open(file_path, "rb") as f:
                self.cmd_e('u', 'Q64s64s', size, file_name, self.target)
                wait(parse)
                f.seek(self.partial)
                while self.partial < size:
                    slice = f.read(4096)
                    self.partial += 4096
                    INFO("Transmitted: {}/{}".format(self.partial, size))
                    conn.sendall(slice)
                else:
                    INFO("Transmission completed.")
                    self.cmd_e('m', '64s256s', self.target,
                               "File named {} uploaded for u".format(file_name))
        except:
            ERROR("File cannot open.")

    def set_prompt(self):
        self.prompt = self.nickname
        if self.target:
            self.prompt += '@' + self.target
        self.prompt += '> '


def FATAL(fatal):
    print('[FATAL]', fatal)


def ERROR(error):
    print('[ERROR]', error)


def INFO(info):
    print('[INFO]', info)


def MSG(msg):
    print(msg)


def cmd_d(format, size):
    return struct.unpack('!' + format, conn.recv(size))


def read():
    while True:
        ctrl = conn.recv(1)
        if not ctrl:
            exit()
        if ctrl == b'F':  # Fatal
            fatal, = cmd_d('64s', 64)
            FATAL(fatal.decode())
            notify(parse)
            exit()
        elif ctrl == b'E':  # Error
            error, = cmd_d('64s', 64)
            ERROR(error.decode())
            notify(parse)
        elif ctrl == b'I':  # Info
            info, = cmd_d('64s', 64)
            INFO(info.decode())
            notify(parse)
        elif ctrl == b'p':  # do_peers
            cnt_nic, = cmd_d('h', 2)
            for _ in range(cnt_nic):
                nickname, = cmd_d('64s', 64)
                INFO(nickname.decode())
            notify(parse)
        elif ctrl == b'm':  # do_message
            source, content = cmd_d('64s256s', 320)
            MSG((source + b': "' + content + b'"').decode())
        elif ctrl == b'u':  # do_upload
            command.partial, = cmd_d("Q", 8)
            if command.partial:
                INFO("Transmission continued.")
            else:
                INFO("Transmission started.")
            notify(parse)
        elif ctrl == b'd': # do_download
            command.file_size, = cmd_d("Q", 8)
            print(command.file_size)
            notify(parse)
            wait(parse)


if __name__ == '__main__':
    conn = socket.socket()
    # conn.connect(('localhost', 5866))
    conn.connect(('8.140.145.229', 5866))

    parse = threading.Condition()

    read_thrd = threading.Thread(target=read)
    read_thrd.setDaemon(True)
    read_thrd.start()

    command = Cmd()
    cmd_thrd = threading.Thread(target=command.cmdloop)
    cmd_thrd.setDaemon(True)
    cmd_thrd.start()

    while True:
        try:
            if read_thrd.is_alive() and cmd_thrd.is_alive():
                pass
            else:
                break
        except KeyboardInterrupt:
            break
