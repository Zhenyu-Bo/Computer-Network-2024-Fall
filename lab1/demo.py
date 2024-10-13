import socket
import struct
from time import time
import threading

def config(path):
    """根据配置文件提取"""
    name2ip = {}
    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            if line.strip():  # strip()去除首尾空格
                ip, domain = line.rstrip().split(' ', 1)  # 提取ip和域名
                name2ip[domain] = ip  # 存储为字典，可以通过域名查找ip
    file.close()
    return name2ip

class query_part():
    """一条问题记录，解析+打包"""
    def __init__(self) -> None:
        self.name = ""
        self.idx = 0
        self.type = None
        self.classify = None
        self.original_name = None  # 原始域名段labels

    def unpack(self, data):
        """
        TODO: 解析二进制查询报文中的问题节，data -> name, type, class
        """
        self.name = ""
        idx = 0
        # 先处理域名
        while True:
            for i in range(idx + 1, idx + 1 + data[idx]):
                # data[idx]表示后续字符串长度（以点分隔）
                self.name += chr(data[i])
            idx += data[idx] + 1
            if data[idx] == 0:
                break
            self.name += '.'
        self.original_name = data[0:idx+1]  # 获得原始域名段
        self.type, self.classify = struct.unpack('>HH', data[idx + 1: idx + 5])
        # self.type = data[idx] << 8 | data[idx + 1]
        # self.classify = data[idx + 2] << 8 | data[idx + 3]

    def pack(self):
        """
        打包回二进制
        TODO: 将问题节打包回二进制查询报文，name, type, class -> data
        """
        data = bytearray()
        data.extend(self.original_name)
        data += struct.pack('>HH', self.type, self.classify)
        return data

class message():
    """一封DNS报文，解析头部，若是查询报文则进一步解析问题节"""
    def __init__(self, data) -> None:
        self.data = data
        self.unpack(data)

    def unpack(self, data):
        self.id, self.flags, self.quests, self.answers, self.author, self.addition = struct.unpack('>HHHHHH', data[0:12])
        self.qr = data[2] >> 7
        if self.qr == 0:  # 是查询报文
            self.query = query_part()
            self.query.unpack(data[12:])  # 生成问题节

    def r_pack(self, ip):
        """
        TODO: 根据ip资源和当前查询报文内容生成回复报文，注意哪些头部字段要修改
        """
        # 头部
        data = struct.pack('>H', self.id)
        # flags = self.flags | 0x8083 if ip == '0.0.0.0' else self.flags | 0x8081
        flags = 0x8183 if ip == '0.0.0.0' else 0x8180
        data += struct.pack('>HHHHH', flags, self.quests, 1, self.author, self.addition)
        # 问题节
        data += self.query.pack()
        # 答复节
        name = 0xc00c  # 指针，指向问题节的域名段
        ttl = 200  # 生存时间
        length = 4  # 数据长度
        data += struct.pack('>HHHLH', name, self.query.type, self.query.classify, ttl, length)
        ips = ip.split('.')
        data += struct.pack('BBBB', int(ips[0]), int(ips[1]), int(ips[2]), int(ips[3]))
        return data

class relay_server():
    """中继器，接收DNS报文并处理"""
    def __init__(self, path) -> None:
        self.config = config(path)  # 解析配置文件，存储为字典{name: ip}
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(('0.0.0.0', 53))
        self.s.setblocking(False)
        self.nameserver = ('114.114.114.114', 53)  # 一个公共DNS服务器，也可选择其他，注意事先测试
        self.transaction = {}

    def process(self, data, addr):
        """报文处理"""
        start_time = time()
        m = message(data)
        # TODO: 解析收到的报文，生成回复返回给请求方
        # 如果是查询报文，检查是否在配置文件中，若在则返回配置文件中的ip，否则转发给公共DNS服务器
        if m.qr == 0:
            # 是查询报文
            name = m.query.name
            if name in self.config:
                # 在配置文件中
                ip = self.config[name]
                ans = m.r_pack(ip)
                self.s.sendto(ans, addr)
                res_time = time() - start_time
                if ip == '0.0.0.0':
                    print(f'query to {name}, handled as intercepted, takes {res_time:.4f}s')
                else:
                    print(f'query to {name}, handled as local resolve, takes {res_time:.4f}s')
            else:
                # 不在配置文件中，中继
                self.transaction[m.id] = (name, addr, start_time)  # 存储域名，请求端地址，开始时间
                self.s.sendto(data, self.nameserver)  # 转发给公共DNS服务器
        else:
            # 是响应报文
            if m.id in self.transaction:
                name, destination, start_time = self.transaction[m.id]
                self.s.sendto(data, destination)
                res_time = time() - start_time
                print(f'query to {name}, handled as relay, takes {res_time:.4f}s')
                del self.transaction[m.id]

    def run(self):
        """循环接收DNS报文"""
        while True:
            try:
                data, addr = self.s.recvfrom(1024)
                threading.Thread(target=self.process, args=(data, addr)).start()  # 多线程
            except:
                pass

if __name__ == "__main__":
    path = "example.txt"
    r = relay_server(path)
    r.run()
