import socket
import select
import time
import sys


# Changing the buffer_size and delay, you can improve the speed and bandwidth.
# But when buffer get to high or delay go too down, you can broke things
buffer_size = 1024
delay = 0.0001
forward_to = ('ws://10.78.4.163', 8181)

#Forward类是负责在代理与远程服务器（原始目标）之间建立连接的类
class Forward:
    def __init__(self):
        # socket.AF_INET 表示因特网 IPv4 地址族，
        # SOCK_STREAM 表示使用 TCP 的 socket 类型，协议将被用来在网络中传输消息
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            print (e)
            return False


#TheServer 就是 proxy
class TheServer:

    input_list = []
    channel = {}

    def __init__(self, host, port):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(1111)

    #input_list存储所有将由select.select管理的可用套接字，第一个要附加的是服务器套接字本身，与此套接字的每个新连接
    # 都会触发on accept（）方法。
    #如果当前的套接字输入就绪（通过选择返回）不是新连接，它将被视为传入数据（可能来自服务器，可能来自客户端），如果数据长度为0，
    # 则是关闭请求，否则应转发数据包到正确的端点。
    def main_loop(self):
        self.input_list.append(self.server)
        while 1:
            time.sleep(delay)
            ss = select.select

            #当套接字收到客户端发来的数据，就变成可读，然后select就会把这个套接字取出来，进入下一步程序。

            #select函数阻塞程序运行，监控inputs中的套接字，当其中有套接字满足可读的条件（第一个参数为可读，如果是第二个参数则为可写），
            # 则把这个套接字返回给rs，然后程序继续运行。
            #至于套接字怎么才算可读呢？搜索可知，当套接字缓冲区大于1byte时，就被标记为可读。也就是说，当套接字收到客户端发来的数据，
            # 就变成可读，然后select就会把这个套接字取出来，进入下一步程序。
            inputready, outputready, exceptready = ss(self.input_list, [], [])
            for self.s in inputready:
                if self.s == self.server:
                    self.on_accept()
                    break

                self.data = self.s.recv()
                if len(self.data) == 0:
                    self.on_close()
                    break
                else:
                    self.on_recv()

    #此方法与原始目标（proxy->server）创建新连接，并接受当前客户端连接（client-> proxy）。
    #两个socket都存储在输入列表中，然后由主循环处理。“通道”字典用于关联端点（客户端<=>服务器）。
    def on_accept(self):
        forward = Forward().start(forward_to[0], forward_to[1])
        clientsock, clientaddr = self.server.accept()
        if forward:
            print(clientaddr, "has connected")
            self.input_list.append(clientsock)
            self.input_list.append(forward)
            self.channel[clientsock] = forward
            self.channel[forward] = clientsock
        else:
            print("Can't establish connection with remote server.",)
            print("Closing connection with client side", clientaddr)
            clientsock.close()

    #禁用和删除代理与原始服务器之间的套接字连接，以及客户端与代理本身之间的套接字连接。
    def on_close(self):
        print(self.s.getpeername(), "has disconnected")

        #remove objects from input_list
        self.input_list.remove(self.s)
        self.input_list.remove(self.channel[self.s])

        out = self.channel[self.s]

        # close the connection with client
        self.channel[out].close()  # equivalent to do self.s.close()
        # close the connection with remote server
        self.channel[self.s].close()

        # delete both objects from channel dict
        del self.channel[out]
        del self.channel[self.s]

    #此方法用于处理数据并将其转发到原始目标（客户端<-代理->服务器）。
    def on_recv(self):
        data = self.data
        # here we can parse and/or modify the data before send forward
        print (data)
        self.channel[self.s].send(data)

if __name__ == '__main__':
        server = TheServer('0.0.0.0', 1111)

        try:
            server.main_loop()
        except KeyboardInterrupt:
            print("Ctrl C - Stopping server")
            sys.exit(1)