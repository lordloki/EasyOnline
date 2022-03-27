import abc
import struct
import threading
from socket import AF_INET, socket, SOCK_STREAM, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR, timeout, SHUT_RDWR, SHUT_WR, create_connection, IPPROTO_TCP, TCP_NODELAY
from datetime import datetime
import traceback
import time


###################################
# EXCEPTIONS -------------------- #
class ConfigError(Exception):
    pass
###################################
# CONSTANTS --------------------- #
PROTOCOL_UDP = 0
PROTOCOL_TCP = 1
PROTOCOL_OUDP = 2

HEADER_UDP = 2
HEADER_TCP = 6

TYPE_INTEGER_S = 0
TYPE_INTEGER_U = 1
TYPE_INTEGER = TYPE_INTEGER_S
TYPE_FLOAT = 2
TYPE_DOUBLE = 3
TYPE_LONG_S = 4
TYPE_LONG_U = 5
TYPE_LONG = TYPE_LONG_S 
TYPE_SHORT_S = 6
TYPE_SHORT_U = 7
TYPE_SHORT = TYPE_SHORT_S
TYPE_STRING = 8
TYPE_BYTES = 9
TYPE_BOOLEAN = 10

# "A" is not a real format character, I use it to mark a dynamic type (string or bytearray)
char_format_dict = {
    TYPE_INTEGER_S:"i",
    TYPE_INTEGER_U:"I",
    TYPE_FLOAT:"f",
    TYPE_DOUBLE:"d",
    TYPE_LONG_S:"q",
    TYPE_LONG_U:"Q",
    TYPE_SHORT_S:"h",
    TYPE_SHORT_U:"H",
    TYPE_STRING:"A",
    TYPE_BYTES:"A",
    TYPE_BOOLEAN:"?",
}

REASON_CONNECTION_LOST  = 0
REASON_TIMEOUT          = 1
REASON_QUIT             = 2
REASON_KICK             = 3
REASON_SERVER_CLOSED    = 4

server_text_reasons = {
    REASON_CONNECTION_LOST:"Lost connection to {}",
    REASON_TIMEOUT:"{} timed out",
    REASON_QUIT:"{} has left the server",
    REASON_KICK:"{} was kicked from the server",
    REASON_SERVER_CLOSED:"disconnected {}, because server is shutting down"
    }

client_text_reasons = {
    REASON_CONNECTION_LOST:"you lost the connection to the server",
    REASON_TIMEOUT:"you timed out",
    REASON_QUIT:"you successfully left the server",
    REASON_KICK:"you got kicked from the server",
    REASON_SERVER_CLOSED:"the server closed"
    }

TCP_bufsize = 4096 # buffer used for receiving data
UDP_bufsize = 1024 # 1500 bytes is upper bound for single packet

###################################
# HELP FUNCTIONS----------------- #
def log(msg):
    print("["+str(datetime.fromtimestamp(time.time()))+"]: "+msg)
###################################

class Runner:
    def __init__(self):
        self._running = True

    def isRunning(self):
        return self._running

    def setRunning(self,val):
        self._running = val

class NetworkActor(Runner):
    "Server or Client. This class is used to capture shared parameters or methods of the server and client class"

    PING_FREQUENCY = 0.5
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.socket_udp = socket(AF_INET, SOCK_DGRAM)
        self.socket_udp.setblocking(False)
        
        self.errorCounter = 0 # I only want to print out exceptions occuring when trying to receive, if they keep comming, if they stop it's allright
        self.lastError = 0
        self.clients_connected = 0
        self.next_ping = 0

    def recv(self):
        "responseable for receiving all network traffic in this tick. Will do just the UDP receive"
        self.socket_processor.process_UDP()

    def main(self):
        pass
    
    def handleErrorCounter(self, e):
        t = time.time()
        dif = t-self.lastError
        if dif < 3:
            self.errorCounter += 1
            if self.errorCounter > 50:
                print(e)
                raise e
        else:
            self.errorCounter = 0
        self.lastError = t
        

class Server(NetworkActor):
    
    def __init__(self, config, port):
        super().__init__(config)
        config.server = self

        self.clients = []
        self.pending_clients = [] # waiting for UDP socket to be synced with TCP, can receice TCP UDP, but only send TCP
        self.clients_registration = {} # addr(from TCP socket of ce) : ce
        self.data_processor_map = {} # addr(from UDP socket) : dataprocessor
        self.nagle = True
        self.isShuttingDown = False

        self.socket_tcp = socket(AF_INET, SOCK_STREAM)
        self.socket_tcp.setblocking(False)
        self.socket_processor = SocketProcessor(DataProcessor(config), self, self.socket_udp, self.socket_tcp)

        self.socket_udp.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket_udp.bind(("", port))
        self.socket_tcp.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket_tcp.bind(("", port))
        self.socket_tcp.listen() 

        log("Server started")
        config.onServerStart()

    def useNagle(use_nagle):
        self.nagle = use_nagle
        for ce in self.clients + self.pending_clients:
            ce.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, not use_nagle)

    def sendTo(self, ce, ID, *data):
        cmd = self.config.commands[ID]
        try:
            if cmd.Protocol == PROTOCOL_TCP:
                ce.socket.sendall(cmd.network_encode(data))
            else:
                self.socket_udp.sendto(cmd.network_encode(data), ce.socket_address_udp)
        except OSError:
            pass

    def sendToAll(self, ID, *data):
        for ce in self.clients:
            self.sendTo(ce, ID, *data)

    def sendToAllExcept(self, ce, ID, *data):
        for ce_ in self.clients:
            if ce_ != ce:
                self.sendTo(ce_, ID, *data)

    def recv(self):
        super().recv()
        for ce in self.pending_clients:
            ce.recv()
        for ce in self.clients:
            ce.recv()

    def _disconnect_client(self, ce, reason):
        self.sendTo(ce, Config.CMD_CLIENTLEAVE, reason)
        try:
            ce.socket.shutdown(SHUT_WR)
        except:
            pass            
        
    def shutdown(self):
        if not self.isShuttingDown:
            self.isShuttingDown = True
            with self.socket_tcp:
                pass 
            with self.socket_udp:
                pass
            if len(self.clients) == 0 and len(self.pending_clients) == 0: # There are not clients, just shut down
                self._shutdown()
            else:
                for ce in self.clients + self.pending_clients:
                    self._disconnect_client(ce, REASON_SERVER_CLOSED)
            
    def _shutdown(self):
        self.setRunning(False)
        log("Server shut down")

    def kick(self, ce):
        self._disconnect_client(ce, REASON_KICK)
        
        #ce._shutdown(REASON_KICK)

    def accept_clients(self):
        "a TCP connection has been establish, but the server waits for the client's metadata(udp port)"
        if self.isRunning():
            try:
                csock, addr = self.socket_tcp.accept()
                csock.setblocking(False)
                csock.setsockopt(IPPROTO_TCP, TCP_NODELAY, not self.nagle)
                ce = ClientEntity(csock, addr, self)
                self.pending_clients.append(ce)
                #log("accepted TCP socket "+ str(addr))
                self.clients_registration[addr] = ce
                self.sendTo(ce, Config.CMD_CLIENT_REGISTER_INIT, addr[1])
            except BlockingIOError:
                pass
            except OSError as e:
                if self.isShuttingDown:
                    print("accepting clients error")
                else:
                    raise e
                    
    def updatePlayerCount(self, amount):
        self.clients_connected += amount
        self.sendToAll(Config.CMD_PLAYERCOUNT, self.clients_connected)

    def main(self):
        self.accept_clients()
        self.recv()
        
        # Ping & TCP Timeout
        now = time.time()
        if now >= self.next_ping:
            for ce in self.clients:
                self.sendTo(ce, Config.CMD_SERVER_PING, time.time())
                self.sendTo(ce, Config.CMD_DUMMYTIMEOUT)
                self.next_ping = now+self.PING_FREQUENCY
                if now-ce.socket_processor.lastTcpReceive > self.config.timeout:
                    ce._shutdown(REASON_TIMEOUT)
            
class Client(NetworkActor):

    STATE_WAITING_FOR_REGISTER = 0
    STATE_REGISTERING = 1
    STATE_CONNECTED = 2

    def __init__(self, config, ip, port, socket_tcp):
        super().__init__(config)
        config.client = self

        self.server_socket_address = (ip, port)
        self.socket_udp.bind(("", 0))
        self.socket_tcp = socket_tcp
        self.socket_tcp.setblocking(False)
        self.socket_processor = SocketProcessor(DataProcessor(config), self, self.socket_udp, self.socket_tcp)

        self.connection_state = self.STATE_WAITING_FOR_REGISTER
        self.external_tcp_port = 0
        self.ping = 80
        self.disconnect_reason = REASON_QUIT

        log("Connected to server!")
        config.onClientConnectedToServer()    

    def useNagle(use_nagle):
        self.socket_tcp.setsockopt(IPPROTO_TCP, TCP_NODELAY, not use_nagle)

    def send(self, ID, *data):
        cmd = self.config.commands[ID]
        try:
            if cmd.Protocol == PROTOCOL_TCP:
                self.socket_tcp.sendall(cmd.network_encode(data))
            else:
                self.socket_udp.sendto(cmd.network_encode(data), self.server_socket_address)
        except OSError: # receive handles errors, send can let them pass
            pass

    def disconnect(self):
        #with self.socket_tcp:#
        try:
            self.send(Config.CMD_CLIENTLEAVE, REASON_QUIT)
            self.socket_tcp.shutdown(SHUT_WR) # this triggers EOF at Server
        except:
            pass
        #self.send(Config.CMD_CLIENTLEAVE)
        #self._shutdown(REASON_QUIT)

    def _shutdown(self, reason):
        "shuts down the socket"
        if self.isRunning():
            self.send(Config.CMD_CLIENTLEAVE, self.disconnect_reason) # when server inits leave, cliententity will allready have called shutdown(SHUT_WR), so this won't/shall not work, but it's okay, since all errors are ignored when sending. Same for Client
            self.setRunning(False)
            with self.socket_tcp: # with calls .close
                self.socket_tcp.shutdown(SHUT_RDWR)
            with self.socket_udp:
                pass
            log(client_text_reasons[reason])
            self.config.onClientDisconnectedFromServer(reason)

    def recv(self):
        super().recv()
        self.socket_processor.process_TCP()

    def main(self):
        self.recv()
        if self.connection_state == self.STATE_CONNECTED:
            now = time.time()
            if now >= self.next_ping:
                self.send(Config.CMD_CLIENT_PING, time.time())
                self.send(Config.CMD_DUMMYTIMEOUT)
                self.next_ping = now+self.PING_FREQUENCY
                if now-self.socket_processor.lastTcpReceive > self.config.timeout:
                    self._shutdown(REASON_TIMEOUT)
        elif self.connection_state == self.STATE_REGISTERING: # the server hasn't linked the client TCP connection with it's UDP addr, so can't use command system
            self.send(Config.CMD_CLIENT_REGISTER_DGRAM, self.external_tcp_port)
        

class ClientEntity(Runner):
    "A Represenation of a client(in server code)"

    PING_FREQUENCY = 0.5
    
    def __init__(self, socket, addr, server):
        super().__init__()
        self.socket = socket
        self.addr = addr
        self.server = server

        self.data_processor = DataProcessor(server.config, self)
        self.socket_processor = SocketProcessor(self.data_processor, self, socket_tcp=socket)
        
        self.ping = 80
        self.disconnect_reason = REASON_QUIT

    def _shutdown(self, reason):
        #log("ClientEntity shutdown[isRunning = "+ str(self.isRunning()) + "]; "+ server_text_reasons[reason].format(str(self)))
        if self.isRunning():
            self.server.sendTo(self, Config.CMD_CLIENTLEAVE, self.disconnect_reason)
            self.setRunning(False)
            with self.socket:
                self.socket.shutdown(SHUT_RDWR)

            if self in self.server.clients: # if true: then client did connect(pure socket) to server, but server hasn't received the initial meta data
                self.server.clients.remove(self)
                del self.server.data_processor_map[self.socket_address_udp]
                log(server_text_reasons[reason].format(str(self)))
                self.server.config.onClientDisconnected(self, reason)
                self.server.updatePlayerCount(-1)
                
            elif self in self.server.pending_clients: # when not fully connected
                self.server.pending_clients.remove(self)
                del self.server.clients_registration[self.addr]
                
            if self.server.isShuttingDown and len(self.server.pending_clients) == 0 and len(self.server.clients) == 0:
                self.server._shutdown()

    def sync_to_UDP(self, udp_port):
        """
        Called when the clientenity has send it's udp port. Before this call the 
        server doesn't regonize the client e.g. you cannot send to the client, it only receives.
        """
        self.socket_address_udp = (self.addr[0], udp_port)
        self.server.pending_clients.remove(self)
        del self.server.clients_registration[self.addr]
        self.server.clients.append(self)
        self.server.data_processor_map[self.socket_address_udp] = self.data_processor
        self.server.sendTo(self, Config.CMD_CLIENT_REGISTER_FINAL)

        log("A Client connected! - "+str(self))
        self.server.config.onClientConnected(self)
        self.server.updatePlayerCount(1)

    def recv(self):
        self.socket_processor.process_TCP()

    def __str__(self):
        return str(self.addr)

class SocketProcessor:
    """
    Processes a socket by starting a new thread, which as long as the server or client is running, will
    try to read from the socket. The received data will be processed by a dataprocessor.
    """

    def __init__(self, data_processor, owner, socket_udp=None, socket_tcp=None):
        """
        owner - Client, Server or ClientEntity
        """
        self.data_processor = data_processor
        self.owner = owner
        self.udpsocket = socket_udp
        self.tcpsocket = socket_tcp
        self.isServer = isinstance(self.owner, Server)
        self.lastTcpReceive = time.time()

    def process_TCP(self):
        "Reads from the TCP socket and feeds the data to the dataprocessor"
        if self.owner.isRunning():
            while True:
                try:
                    data = self.tcpsocket.recv(TCP_bufsize)
                    self.lastTcpReceive = time.time()
                    if data:
                        self.data_processor.process_TCP(data)
                    else: # graceful socket close
                        self.owner._shutdown(self.owner.disconnect_reason)
                        break
                except BlockingIOError:
                    break
                except timeout:
                    self.owner._shutdown(REASON_TIMEOUT)
                    break
                except ConnectionError:
                    self.owner._shutdown(REASON_CONNECTION_LOST)
                    break
                except OSError:
                    raise e

    def process_UDP(self):
        """
        Reads all from the UDP socket and feeds the data to the dataprocessor
        server_structure - if given the socket is assumed to be from a server, so each address received attached to
        a datagram is important, because it tells from which client it got send(Contrary to the client, which only
        gets messages from the server).
        """
        if self.owner.isRunning():
            while True:
                try:
                    data, addr = self.udpsocket.recvfrom(UDP_bufsize)
                    if self.isServer:
                        if addr in self.owner.data_processor_map:
                            self.owner.data_processor_map[addr].process_UDP(data)
                        elif len(data) == 4: # client registration
                            tcp_addr = (addr[0], struct.unpack("!H", data[2:])[0])
                            if tcp_addr in self.owner.clients_registration:
                                ce = self.owner.clients_registration[tcp_addr]
                                ce.sync_to_UDP(addr[1])
                    else:
                        self.data_processor.process_UDP(data)
                except BlockingIOError:
                    break
                except ConnectionError:
                    if not self.isServer:
                        self.owner._shutdown(REASON_CONNECTION_LOST)
                    break
                except OSError as e:
                    if (not self.isServer and self.owner.isRunning()) or (self.isServer and not self.owner.isShuttingDown):
                        raise e
                    break


class DataProcessor:
    "Can process the data directly received by the network by decoding and executing it"

    def __init__(self, config, ce=None):
        "ce - when processing data at the server one must know who send the data, which ClientEntity"
        if ce == None:
            self.execute_command = lambda id, data: config.commands[id].client_execute(config.commands[id].decode(data))
        else:
            self.execute_command = lambda id, data: config.commands[id].server_execute(config.commands[id].decode(data), ce)

        self.bytes = b''
        self.header_read = False
        self.ID = 0 # the id of the current command to read
        self.size = 0 # the size(without header) of the current command to read
        
        self.lastUDPID = {} # for all commands that have UDP(and not OUDP) as Protocol
        for id, cmd in config.commands.items():
            if cmd.Protocol == PROTOCOL_OUDP:
                self.lastUDPID[id] = -1

    def process_TCP(self, data):
        """
        data - the data received by the network
        """
        if data:
            self.bytes += data

        if self.header_read == False:
            if len(self.bytes) >= HEADER_TCP:
                self.header_read = True
                self.ID = self.bytes[0]<<8 | self.bytes[1]
                self.size = self.bytes[2]<<24 | self.bytes[3]<<16 | self.bytes[4]<<8 | self.bytes[5]
                self.bytes = self.bytes[HEADER_TCP:]
            else:
                return

        if len(self.bytes) >= self.size:
            self.execute_command(self.ID, self.bytes[:self.size])
            self.bytes = self.bytes[self.size:]
            self.header_read = False
            if self.bytes:
                self.process_TCP(None)

    def process_UDP(self, data):
        "[UPD] data - 2 bytes header (command ID) followed by raw data"
        cmdid = data[0]<<8 | data[1]
        if cmdid not in self.lastUDPID:
            self.execute_command(cmdid, data[2:])
        else:
            udpid = data[2]<<8 | data[3]
            if udpid > self.lastUDPID[cmdid] or (udpid < 32768 and self.lastUDPID[cmdid] > 32768):
                self.lastUDPID[cmdid] = udpid
                self.execute_command(cmdid, data[4:])
            else:
                print("OUDP TOO LATE", udpid, "is too late, since we allready got", self.lastUDPID[cmdid]) 

class Config(abc.ABC):
    """
    Stores parameters, like maxplayers etc. but also defines all commands, via their ID, Protocoltype(UDP
    /TCP), what kind of data they send and finally how the data is handled.

    Add command by using registerCommands.

    self.server is the current server instance (and None at the client)
    self.client is the current Client instance (and None at the server)
    """

    CMD_CLIENT_REGISTER_INIT = 2**16-1
    CMD_CLIENT_REGISTER_FINAL = 2**16-2
    CMD_CLIENT_REGISTER_DGRAM = 2**16-3 #This is just as a decoy, because some of these udp grams will stil be on their way even the the client is allready synched, therefore it has to be in the command format
    CMD_CLIENT_PING = 2**16-5
    CMD_SERVER_PING = 2**16-6
    CMD_PLAYERCOUNT = 2**16-7
    CMD_DUMMYTIMEOUT = 2**16-8
    CMD_CLIENTLEAVE = 2**16-9

    def __init__(self, timeout):
        "timeout - max time a server/client hasn't heard from the other before cutting the connection"
        self.commands = {}
        self.server = None
        self.client = None
        self.timeout = timeout

        def cmd_reg_init(data, ce): # server -> client (TCP)
            self.client.connection_state = Client.STATE_REGISTERING
            self.client.external_tcp_port = data[0]

        def cmd_reg_final(data, ce): # server -> client (TCP)
            self.client.connection_state = Client.STATE_CONNECTED

        def cmd_reg_dgram(data,ce):
            pass
            #print("obsolete grams msg arrived")
                
        def cmd_kick(data, ce):
            self.client._shutdown(REASON_KICK)

        def cmd_client_ping(data, ce):
            if ce:
                self.server.sendTo(ce, Config.CMD_CLIENT_PING, data[0])
            else:
                ping = 1000*(time.time()-data[0])
                self.client.ping = 0.75*self.client.ping + 0.25*ping
                
        def cmd_server_ping(data, ce):
            if ce:
                ping = 1000*(time.time()-data[0])
                ce.ping = 0.75*ce.ping + 0.25*ping
            else:
                self.client.send(Config.CMD_SERVER_PING, data[0])
                
                
        def cmd_playercount(data, ce):
            self.client.clients_connected =  data[0]
            
        def cmd_dummytimeout(data, ce):
            pass
        
        def cmd_clientleave(data, ce):
            if ce:
                ce.disconnect_reason = data[0]
            else:
                self.client.disconnect_reason = data[0]

        self.registerCommands(
            Command(self.CMD_CLIENT_REGISTER_INIT, PROTOCOL_TCP, cmd_reg_init, TYPE_SHORT_U),
            Command(self.CMD_CLIENT_REGISTER_DGRAM, PROTOCOL_UDP, cmd_reg_dgram, TYPE_SHORT_U),
            Command(self.CMD_CLIENT_REGISTER_FINAL, PROTOCOL_TCP, cmd_reg_final),
            Command(self.CMD_CLIENT_PING, PROTOCOL_UDP, cmd_client_ping, TYPE_DOUBLE),
            Command(self.CMD_SERVER_PING, PROTOCOL_UDP, cmd_server_ping, TYPE_DOUBLE),
            Command(self.CMD_PLAYERCOUNT, PROTOCOL_TCP, cmd_playercount, TYPE_INTEGER),
            Command(self.CMD_DUMMYTIMEOUT, PROTOCOL_TCP, cmd_dummytimeout),
            Command(self.CMD_CLIENTLEAVE, PROTOCOL_TCP, cmd_clientleave, TYPE_INTEGER)
        )

    @abc.abstractmethod
    def onServerClose(self):
        "The Server shut down(Client callback)"
        pass
    @abc.abstractmethod
    def onServerStart(self):
        "The Server has started"
        pass
    @abc.abstractmethod
    def onClientConnected(self, ce):
        "Server notices a client connected(Server callback)"
        pass
    @abc.abstractmethod
    def onClientDisconnected(self, ce, reason):
        "Server notices a client disconnected(Server callback)"
        pass
    @abc.abstractmethod
    def onClientConnectedToServer(self):
        "client succesfully connected to the server(Client callback)"
        pass
    @abc.abstractmethod
    def onClientDisconnectedFromServer(self,reason):
        "client disconnected from the server(Client callback)"
        pass

    def registerCommands(self, *commands):
        for cmd in commands:
            self.commands[cmd.ID] = cmd

class Command:
    """
    A Command is a convienient way to let the Server and Client communicate.
    You can specify what kind of data should be send from e.g. Client to server and what
    the server does with this data

    Command.encode and Command.decode are each inverse
    """
    
    def __init__(self, ID, Protocol, function, *types):
        """
        ID - each command must be assign an unique identification (unsigned short)
        Protocol - how to send via network, UDP(faster) or TCP(100% safe)
        types - what kind of data to be send, e.g 2 integers and 1 string. All types are signed!
                OBS: can't send infinite precision python integers and if Integer type or Long type is selected
                (both signed) then the values may not be out of bounds.
        function - what to do with data, a function taking (data, ce) as input. data(as list) and ce(as ClientEnity) is the sender of data.
                Clients do always receive data from the server, so at the client ce = None.
        """
        self.ID = ID
        self.Protocol = Protocol
        self.types = types
        self.function = function

        self.dynamicIDs = []
        self.dynamics = 0
        self.struct_format = "!" # format string for command, has to be modified in runtime when dynamics > 0
        for i in range(len(types)):
            t = types[i]
            if t == TYPE_STRING or t == TYPE_BYTES:
                self.struct_format += str(i)+"A"
                self.dynamicIDs.append(i)
            else:
                self.struct_format += char_format_dict[t]
        self.dynamics = len(self.dynamicIDs)

        if self.Protocol == PROTOCOL_TCP: # super useless optimization
            self.network_encode = self._network_encode_tcp
        elif self.Protocol == PROTOCOL_UDP:
            self.network_encode = self._network_encode_udp
        elif self.Protocol == PROTOCOL_OUDP:
            self.network_encode = self._network_encode_oudp
            
        self.UDPID_gen = (i for j in range(2**32) for i in range(2**16)) # a counter for each command(not global), generates unsigned shorts
    
    def encode(self, data):
        "Makes data consisting of integers, strings, floats.. to a bytearray."
        if self.dynamics == 0:
            return struct.pack(self.struct_format, *data)

        data_ = list(data) # before .pack all strings must be encoded
        SizeArray = b'' # need to prepend the header which tells how big the encoded strings or byte arrays are
        struct_format_now = self.struct_format # need to add the actual size of strings/bytearray in format string

        for i in self.dynamicIDs:
            dat = data[i].encode("UTF-8") if self.types[i] == TYPE_STRING else data[i]
            size = len(dat)
            SizeArray += struct.pack("!i", size)
            struct_format_now = struct_format_now.replace(str(i)+"A", str(size)+"s")
            if self.types[i] == TYPE_STRING:
                data_[i] = dat
        #print("struct_format_now:", struct_format_now)
        #print("data:", data_)
        return SizeArray+struct.pack(struct_format_now, *data_)
    
    def decode(self, bytedata):
        "Converts bytedata back to data specified by the types given in the constructor"
        if self.dynamics == 0:
            return struct.unpack(self.struct_format, bytedata)
                
        struct_format_now = self.struct_format # need to add the actual size of strings/bytearray in format string
        sizes = struct.unpack("!"+self.dynamics*"i", bytedata[:self.dynamics*4])
        #print("sizes:", sizes)
        size_it = iter(sizes)
        for i in self.dynamicIDs:
            struct_format_now = struct_format_now.replace(str(i)+"A", str(next(size_it))+"s")
        #print("struct_format_now:", struct_format_now)
        # strings must be decoded at the end
        return [ dat.decode("UTF-8") if (i in self.dynamicIDs and self.types[i]==TYPE_STRING) else dat 
                for (i,dat) in enumerate(struct.unpack(struct_format_now, bytedata[self.dynamics*4:]))]

    def _network_encode_udp(self, data):
        "puts the command id(encoded) as header in front of the encoded data"
        return struct.pack("!H", self.ID)+self.encode(data)

    def _network_encode_tcp(self, data):
        "puts the command id(encoded) and length(encoded) of the following bytes as header in front of the encoded data"
        data_byte = self.encode(data)
        return struct.pack("!H", self.ID)+struct.pack("!I", len(data_byte))+data_byte
    
    def _network_encode_oudp(self, data):
        "puts the command id(encoded) and UDPID(encoded) as header in front of the encoded data"
        return struct.pack("!H", self.ID)+struct.pack("!H", next(self.UDPID_gen))+self.encode(data)

    def network_encode(self, data):
        "encodes the data with a header relevant for the network"
        pass # funtion is overwritten in constructor

    def server_execute(self, data, ce):
        """
        Command being executed from the server
        data - decoded data
        ce - A ClientEntity representing the client who send the command
        """
        self.function(data, ce)

    def client_execute(self, data):
        """
        Command being executed from a client
        data - decoded data
        """
        self.function(data, None)

    def __repr__(self):
        return "(ID="+str(self.ID)+",PROTOCOL="+{PROTOCOL_UDP:"UDP", PROTOCOL_TCP:"TCP", PROTOCOL_OUDP:"OUDP"}[self.Protocol]+",TYPES="+str(self.types)+")"


class NetworkFactory:
    """
    The NetworkFactory can create a server or try to create a connected Client.
    """
    def __init__(self, config):
        """
        Forwards the configuration to server or client(it's important that both
        use the same config, since it defines how to handle data).

        config - should be a superclass of Config
        """
        if not config:
            raise ConfigError("No Configuration given")
        self.config = config
        self.client = None
        
    def createServer(self, port):
        "Returns a running Server instance"
        return Server(self.config, port);

    def connect(self, ip, port, connecttime=10):
        "Returns a connected client or None. Attempts to connect for connecttime seconds"
        if self.client:
            self.client.main()
            if self.client.connection_state == Client.STATE_CONNECTED:
                return self.client
            return None
        try:
            self.client =  Client(self.config, ip, port, create_connection((ip, port), connecttime))
        except timeout:
            pass