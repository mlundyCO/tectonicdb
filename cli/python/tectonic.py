"""
python client for tectonic server
"""

import socket
import json
import struct
import time
import sys
import asyncio

class TectonicDB():
    """
    Example Usage:
        from tectonic import TectonicDB
        import json
        import asyncio

        async def subscribe(name):
            db = TectonicDB()
            print(await db.subscribe(name))
            while 1:
                _, item = await db.poll()
                if item == b"NONE":
                    await asyncio.sleep(0.01)
                else:
                    yield json.loads(item)

        class TickBatcher(object):
            def __init__(self, db_name):
                self.one_batch = []
                self.db_name = db_name

            async def batch(self):
                generator = subscribe(self.db_name)
                async for item in generator:
                    self.one_batch.append(item)
            
            async def timer(self):
                while 1:
                    await asyncio.sleep(5)
                    print(len(self.one_batch))
                
            
        if __name__ == '__main__':
            loop = asyncio.get_event_loop()
            proc = TickBatcher("bnc_xrp_btc")
            loop.create_task(proc.batch())
            loop.create_task(proc.timer())
            loop.run_forever()
            loop.close()
    """
    def __init__(self, host="localhost", port=9001):
        self.subscribed = False
        self.host = host
        self.port = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (host, port)
        self.sock.connect(server_address)

    async def cmd(self, cmd):
        loop = asyncio.get_event_loop()

        if type(cmd) != str:
            message = (cmd.decode() + '\n').encode()
        else:
            message = (cmd+'\n').encode()
        loop.sock_sendall(self.sock, message)

        header = await loop.sock_recv(self.sock, 9)
        current_len = len(header)
        while current_len < 9:
            header += await loop.sock_recv(self.sock, 9-current_len)
            current_len = len(header)

        success, bytes_to_read = struct.unpack('>?Q', header)
        if bytes_to_read == 0:
            return success, ""

        body = await loop.sock_recv(self.sock, 1)
        body_len = len(body)
        while body_len < bytes_to_read:
            len_to_read = bytes_to_read - body_len
            if len_to_read > 32:
                len_to_read = 32
            body += await loop.sock_recv(self.sock, len_to_read)
            body_len = len(body)
        return success, body

    def destroy(self):
        self.sock.close()

    async def info(self):
        return await self.cmd("INFO")

    async def countall(self):
        return await self.cmd("COUNT ALL")

    async def countall_in_mem(self):
        return await self.cmd("COUNT ALL IN MEM")

    async def ping(self):
        return await self.cmd("PING")
    
    async def help(self):
        return await self.cmd("HELP")

    async def insert(self, ts, seq, is_trade, is_bid, price, size, dbname):
        return await self.cmd("INSERT {}, {}, {} ,{}, {}, {}; INTO {}"
                        .format( ts, seq, 
                            't' if is_trade else 'f',
                            't' if is_bid else 'f', price, size,
                            dbname))

    async def add(self, ts, seq, is_trade, is_bid, price, size):
        return await self.cmd("ADD {}, {}, {} ,{}, {}, {};"
                        .format( ts, seq, 
                            't' if is_trade else 'f',
                            't' if is_bid else 'f', price, size))
    async def bulkadd(self, updates):
        await self.cmd("BULKADD")
        for update in updates:
            ts, seq, is_trade, is_bid, price, size = update

            await self.cmd("{}, {}, {} ,{}, {}, {};"
                    .format( ts, seq,
                            't' if is_trade else 'f', 
                            't' if is_bid else 'f', price, size))
        await self.cmd("DDAKLUB")

    async def getall(self):
        return json.loads(await self.cmd("GET ALL AS JSON"));

    async def get(self, n):
        success, ret = await self.cmd("GET {} AS JSON".format(n))
        if success:
            return json.loads(ret)
        else:
            return None

    async def clear(self):
        return await self.cmd("CLEAR")

    async def clearall(self):
        return await self.cmd("CLEAR ALL")

    async def flush(self):
        return await self.cmd("FLUSH")

    async def flushall(self):
        return await self.cmd("FLUSH ALL")

    async def create(self, dbname):
        return await self.cmd("CREATE {}".format(dbname))

    async def use(self, dbname):
        return await self.cmd("USE {}".format(dbname))

    async def unsubscribe(self):
        await self.cmd("UNSUBSCRIBE")
        self.subscribed = False

    async def subscribe(self, dbname):
        res = await self.cmd("SUBSCRIBE {}".format(dbname))
        if res[0]:
            self.subscribed = True
        return res
    
    async def poll(self):
        return await self.cmd("")

    async def range(self, dbname, start, finish):
        self.use(dbname)
        data = await self.cmd("GET ALL FROM {} TO {} AS CSV".format(start, finish).encode())
        data = data[1]
        return data

def measure_latency():
    dts = []

    db = TectonicDB()

    t = time.time()
    for i in range(10000):
        db.insert(0,0,True, True, 0., 0., 'default')
        t_ = time.time()
        dt = t_ - t
        t = t_
        dts.append(dt)
    print("AVG:", sum(dts) / len(dts))
    db.destroy()

def insert_n(n):
    db = TectonicDB()
    for i in range(n):
        db.insert(0,0,True, True, 0., 0., 'default')

def example_subscribe():
    db = TectonicDB()
    print(db.subscribe('default'))

    import threading
    def send_req():
        while 1:
            print("----------------------------")
            insert_n(100)
            time.sleep(3)
    t = threading.Thread(target=send_req)
    t.start()

    while 1:
        _, item = db.poll()
        if item == "NONE\n":
            time.sleep(0.01)
        else:
            print(item[0],)
