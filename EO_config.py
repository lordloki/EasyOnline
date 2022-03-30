import EO_network as n
import EO_DATA
from mathutils import Euler, Vector, Matrix
from bge import logic
import re
import copy
import struct
import importlib

scene = logic.getCurrentScene()

CMD_TRANS_SPAWN = 1     # ID:INT    REP:STRING    NAME:str  transmissionInfo:str    str:struct_format   init_data:bytes
CMD_TRANS_DEL = 2       # ID:INT
CMD_TRANS_DATA = 3      # ID:INT    
CMD_AVATAR_SCRIPT_FORWARD = 6       # format:STRING     data:BYTES    -   dynamic(w.r.t. data types) msg comming from user template network messages
CMD_AVATAR_SCRIPT_BACKWARD = 7
CMD_REQUESTID = 8       # localID:INT   globalID:INT   
CMD_AVATAR_MSG = 9       # ID:INT    PROPNAME:str    type:INT    value:str   isnotString:boolean

CMD_TRANS_worldPosition_UDP = 10       # ID:INT    x:FLOAT       y:FLOAT   z:FLOAT  
CMD_TRANS_worldPosition_TCP = 11       # ID:INT    x:FLOAT       y:FLOAT   z:FLOAT  
CMD_TRANS_worldOrientation_UDP = 12    # ID:INT    x:FLOAT       y:FLOAT   z:FLOAT   
CMD_TRANS_worldOrientation_TCP = 13       # ID:INT    x:FLOAT       y:FLOAT   z:FLOAT   
CMD_TRANS_GAME_PROPERTY_UDP = 14 # ID:INT   propname:str    value:str   isnotString:boolean     isOverwrite:boolean 
CMD_TRANS_GAME_PROPERTY_TCP = 15 # ID:INT   propname:str    value:str   isnotString:boolean     isOverwrite:boolean
CMD_TRANS_OBJ_PROPERTY_UDP = 16 # ID:INT   propname:str    notMatrix:bool   value:str   isnotString:boolean
CMD_TRANS_OBJ_PROPERTY_TCP = 17 # ID:INT   propname:str    notMatrix:bool   value:str   isnotString:boolean

CMD_TRANS_REQUEST_INIT = 18     # using custom user msg
CMD_TRANS_DO_INIT = 19          # using custom user msg

CMD_NAME = 20
CMD_TRANS_SCRIPT = 21           # format:STRING     data:BYTES    -   dynamic(w.r.t. data types) msg comming from user template network messages
CMD_GLOBALTRANS_SPAWN = 22  # ID:INT    OBJNAME:str     NAME:str    str:struct_format   init_data:bytes

def getData(kx, attribute, noMatrix):
    if attribute == "worldPosition":
        return kx.worldPosition
    elif attribute == "worldOrientation":
        return kx.worldOrientation.to_euler()
    if noMatrix:
        return getattr(kx, attribute)
    return getattr(kx, attribute).to_euler()

def setData(kx, attribute, noMatrix, data):
    if noMatrix:
        setattr(kx, attribute, data)
    else:
        setattr(kx, attribute, Euler(data).to_matrix())
    
def decode_user_msg(data):
    #print("cmd_decode_user_msg", data)
    format = data[0]
    data_ = list(struct.unpack(format.replace("S", "s").replace("B","s"), data[1]))
    # need to decode strings:
    occ = re.findall("S | B | i | \? | d", format, flags=re.X)
    #print("occ:", occ)
    for (i,c) in enumerate(occ): # i is now the index of the information w.r.t. all data
        if c == "S":
            #print("translate bytes to string for", i)
            data_[i] = data_[i].decode("UTF-8") 
    return data_

def encode_user_msg(data):    
    "data can be a list of arbitrary data(length and type)"
    data_ = list(data)
    format_map = {int:"i", float:"d", bool:"?"}
    struct_format = "!"
    for (i,x) in enumerate(data):
        t = type(x)
        if t == str:
            x = x.encode("UTF-8")
            data_[i] = x
            struct_format += str(len(x))+"S"
        elif t == bytes:
            struct_format += str(len(x))+"B"
        else:
            struct_format += format_map[t]
    return struct_format, struct.pack(struct_format.replace("S", "s").replace("B","s"), *data_)

class GameConfig(n.Config):

    def getID(self):
        self.ID += 1
        return self.ID
    
    def getUDPIS(self):
        self.UDPID += 1
        return self.UDPID
    
    def apply_init_data(self, data): # this is only at client
        "data - decoded"
        id = data[0]
        for i in range(1, len(data), 2):
            trans_type = data[i]
            trans_data = eval(data[i+1])
            self.cmds[trans_type]([id]+trans_data, None)
        
    def __init__(self, timeout, networkType, username):
        super().__init__(timeout)

        self.networkType = networkType
        self.username = username
        self.ID = -1
        self.UDPID = -1
        self.objid_ce = {} # id of transmitter |-> client
        self.ce_id = {} # ce |-> id (global id of client)
        self.id_ce = {} # id |-> ce
        self.ce_name = {} # ce |-> name
        self.avatars = {} # id(global) |-> obj
        self.own_transmitter = {} # id(possible local) |-> obj
        self.servervised_transmitter = [] # ids of avatars that have server controller attributes
        self.pending_id = {} # id |-> transmitter (waiting for global ID)
        

        def cmd_trans_spawn_(data, ce):
            id = data[0]
            rep = data[1]
            obj = scene.addObject(rep)
            if ce: # server must inform other clients
                data[2] = self.ce_name[ce]
                self.server.sendToAllExcept(ce, CMD_TRANS_SPAWN, id, rep, data[2], "", *data[4:])
                self.objid_ce[id] = ce
                info = filterTransmitterData(eval(data[3]), "Server for Client") # extrainfo for server, because of server controlled attributes
                if info:
                    self.servervised_transmitter.append(id)
                    obj["EO_transmitter_data"] = info
                    for trans in info:
                        if trans[0] == "GAME_PROPERTY" and not trans[10]:
                            obj["EO_LAST_"+trans[7]] = 0.0
            
            if obj.name in EO_DATA.data["AVATAR"]:
                script, msgs = EO_DATA.data["AVATAR"][obj.name]
                obj['EO_script'] = script
                prop_type = {}    
                for (type, name) in msgs:
                    prop_type[name] = type
                obj['EO_trigger_properties'] = prop_type
    
            obj["EO_id"] = id
            obj["EO_NAME"] = data[2]
            self.avatars[id] = obj
            #print("data[4:6]:", data[4], data[5])
            self.apply_init_data([id]+decode_user_msg(data[4:6]))
                
            
        def cmd_globaltrans_spawn(data, ce):
            obj = None
            scene = logic.getCurrentScene()
            for object in scene.objects:
                if object.name == data[1]: # name of global object
                    obj = object
                    break
            if obj == None:
                print("cmd_globaltrans_spawn - No global object by the name of", data[1])
                return
            id = data[0]
            obj["EO_id"] = id
            obj["EO_NAME"] = data[2]
            self.avatars[id] = obj
            #print("data[3:5]:", data[3], data[4])
            self.apply_init_data([id]+decode_user_msg(data[3:5]))
            
        def cmd_trans_del_(data, ce):
            id = data[0]
            if ce:
                self.removeTransmitter(id)
            if id in self.avatars:
                self.avatars[id].endObject()
                del self.avatars[id]
                
        def cmd_trans_attr_(data, ce, attributeID):
            id = data[0]
            if id in self.avatars: # the initial spawn of the transmitter can be exceeded by the first UDP packages
                if ce: # forward to other clients
                    self.server.sendToAllExcept(ce, attributeID, id, *data[1:])
                obj = self.avatars[id]
                if attributeID == CMD_TRANS_worldPosition_UDP or attributeID == CMD_TRANS_worldPosition_TCP:
                    obj.worldPosition = data[1:]
                elif attributeID == CMD_TRANS_worldOrientation_UDP or attributeID == CMD_TRANS_worldOrientation_TCP:
                    obj.worldOrientation = Euler(data[1:]).to_matrix()
            elif id in self.own_transmitter and not ce:
                obj = self.own_transmitter[id]
                if attributeID == CMD_TRANS_worldPosition_UDP or attributeID == CMD_TRANS_worldPosition_TCP:
                    obj.worldPosition = data[1:]
                elif attributeID == CMD_TRANS_worldOrientation_UDP or attributeID == CMD_TRANS_worldOrientation_TCP:
                    obj.worldOrientation = Euler(data[1:]).to_matrix()
            #else:
                #print("id", id, "not in self.avatars")
                
        def cmd_trans_pos_(data, ce, cmd_proto):
            id = data[0]
            #print("cmd_trans_pos_", ce, id in self.avatars)
            if id in self.avatars:
                if ce:
                    self.server.sendToAllExcept(ce, cmd_proto, id, *data[1:])
                obj = self.avatars[id]
                obj.worldPosition = data[1:]
            elif id in self.own_transmitter and not ce:
                obj = self.own_transmitter[id]
                obj.worldPosition = data[1:]
            #else:
                #print("id", id, "not in self.avatars")
                
        def cmd_trans_pos_udp(data, ce):
            cmd_trans_pos_(data, ce, CMD_TRANS_worldPosition_UDP)
            
        def cmd_trans_pos_tcp(data, ce):
            cmd_trans_pos_(data, ce, CMD_TRANS_worldPosition_TCP)
        
        def cmd_avatar_script_forward(data, ce):
            data_ = decode_user_msg(data)
            id = data_[0]
            triggerclientID = data_[1] # blank if send by client, when server is forwarding it will be added
            script = data_[2]
            prop = data_[3]
            username = data_[4]
            msg_data = data_[5:]
            event = self.avatar_events[script][prop]
            
            if ce:
                username = self.ce_name[ce]
            
            if id in self.own_transmitter:
                obj = self.own_transmitter[id]
                res = event.onReceive(username, obj, msg_data)
                if res != None:
                    self.send_user_msg(CMD_AVATAR_SCRIPT_BACKWARD, [id, triggerclientID, prop]+res, ce)
            elif ce:
                if id in self.avatars:
                    obj = self.avatars[id]
                    event.onServerPeek(obj, msg_data)
                    data_[1] = self.ce_id[ce]
                    self.send_user_msg(CMD_AVATAR_SCRIPT_FORWARD, data_, self.objid_ce[id])
                    #self.server.sendTo(self.objid_ce[id], CMD_AVATAR_SCRIPT_FORWARD, *data)
                else:
                    print("id", id, "not a avatar here at server")
            else:
                print("id", id, "not a transmitter here")
                
        def cmd_avatar_script_backward(data, ce): # id, propName, response-data
            data_ = decode_user_msg(data)
            id = data_[0]
            trigger = data_[1]
            if ce: 
                if trigger != -1: # not meant for server, forward
                    self.server.sendTo(self.id_ce[trigger], CMD_AVATAR_SCRIPT_BACKWARD, *data)
                    return
            if id in self.avatars:
                obj = self.avatars[id]
                prop = data_[2]
                event = self.avatar_events[obj["EO_script"]][prop]
                event.onAnswer(obj, data_[3:])
            else:
                print("on net-msg answer: can't find avatar with id", id)
            
        def cmd_request_id(data,ce):
            if ce:
                self.server.sendTo(ce, CMD_REQUESTID, data[0], self.getID())
            else:
                self.include_transmitter(self.pending_id[data[0]], data[1])
            
        def cmd_avtar_msg(data, ce): # for avatars
            id, prop, type, value, notString = data
            if notString:
                value = eval(value)
            if id in self.own_transmitter: # meant for you(server/client)
                if type == 0:
                    self.own_transmitter[id][prop] += value
                else:
                    self.own_transmitter[id][prop] = value
            elif ce and id in self.avatars: # from client to client and server must forward
                self.server.sendTo(self.objid_ce[id], CMD_AVATAR_MSG, *data)
            else:
                print("on user prop: can't find id", id)
                
        def cmd_trans_prop(data, ce, cmd_proto): # for transmitters
            id, prop, value, notString, overwrite = data
            if notString:
                value = eval(value)
            if id in self.avatars:
                if ce:
                    self.server.sendToAllExcept(ce, cmd_proto, id, *data[1:])
                obj = self.avatars[id]
                if overwrite:
                    obj[prop] = value
                else:
                    obj[prop] += value
            elif id in self.own_transmitter and not ce:
                obj = self.own_transmitter[id]
                if overwrite:
                    obj[prop] = value
                else:
                    obj[prop] += value
            #else:
                #print("id", id, "not in self.avatars")
                
        def cmd_trans_prop_udp(data, ce):
            cmd_trans_prop(data, ce, CMD_TRANS_GAME_PROPERTY_UDP)
                
        def cmd_trans_prop_tcp(data, ce):
            cmd_trans_prop(data, ce, CMD_TRANS_GAME_PROPERTY_TCP)
        
        def cmd_trans_objprop(data, ce, cmd_proto):
            id, attrname, noMatrix, value, notString = data
            if notString:
                value = eval(value)
            if id in self.avatars:
                if ce:
                    self.server.sendToAllExcept(ce, cmd_proto, id, *data[1:])
                obj = self.avatars[id]
                setData(obj, attrname, noMatrix, value)
            elif id in self.own_transmitter and not ce:
                obj = self.own_transmitter[id]
                setData(obj, attrname, noMatrix, value)
            #else:
                #print("id", id, "not in self.avatars")
                
        def cmd_trans_objprop_tcp(data, ce):
            cmd_trans_objprop(data, ce, CMD_TRANS_OBJ_PROPERTY_TCP)
            
        def cmd_trans_objprop_udp(data, ce):
            cmd_trans_objprop(data, ce, CMD_TRANS_OBJ_PROPERTY_UDP)
            
        def cmd_trans_request_init(data, ce):
            data_ = decode_user_msg(data)
            if ce:
                clientid = data_[0]
                if clientid in self.id_ce:
                    recv = self.id_ce[clientid]
                    self.send_user_msg(CMD_TRANS_DO_INIT, data_[1:], recv)    
                else:
                    print("ups receiver of init data is wrong; id =", clientid)
                    
            else:
                clientid = data_[0]
                for id, obj in  self.own_transmitter.items():
                    self.send_user_msg(CMD_TRANS_REQUEST_INIT, [clientid, id]+self.get_transmissions_data(obj))
                    
        def cmd_trans_do_init(data, ce):
            self.apply_init_data(decode_user_msg(data))
                
        def cmd_name(data, ce):
            if ce:
                name = data[0]
                x = 2
                while name in self.ce_name.values() or name == self.username:
                    name = data[0]+str(x)
                    x += 1
                if x != 2: # name changed
                    self.server.sendTo(ce, CMD_NAME, name)
                self.ce_name[ce] = name
            else:
                logic.getCurrentController().owner["EO_NAME"] = data[0]
                self.username = data[0]
                
        def cmd_trans_script(data, ce):
            data_ = decode_user_msg(data)
            id, script, prop, username = data_[:4]
            user_data = data_[4:]
            if id in self.avatars:
                event = self.transmitter_events[script][prop]
                obj = self.avatars[id]
                if ce:
                    username = self.ce_name[ce]
                    for client in self.server.clients:
                        if client != ce:
                            self.send_user_msg(CMD_TRANS_SCRIPT, data_, client)
                event.onReceive(username, obj, user_data)
            else:
                print("cmd_trans_script - avatar with id", id, "not found")
            
            
            
        self.registerCommands(
            n.Command(CMD_TRANS_SPAWN, n.PROTOCOL_TCP, cmd_trans_spawn_, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_BYTES),
            n.Command(CMD_TRANS_DEL, n.PROTOCOL_TCP, cmd_trans_del_, n.TYPE_INTEGER),
            n.Command(CMD_AVATAR_SCRIPT_FORWARD, n.PROTOCOL_TCP, cmd_avatar_script_forward, n.TYPE_STRING, n.TYPE_BYTES),
            n.Command(CMD_AVATAR_SCRIPT_BACKWARD, n.PROTOCOL_TCP, cmd_avatar_script_backward, n.TYPE_STRING, n.TYPE_BYTES),
            n.Command(CMD_REQUESTID, n.PROTOCOL_TCP, cmd_request_id, n.TYPE_INTEGER, n.TYPE_INTEGER),
            n.Command(CMD_AVATAR_MSG, n.PROTOCOL_TCP, cmd_avtar_msg, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_BOOLEAN),
            n.Command(CMD_TRANS_worldPosition_UDP, n.PROTOCOL_OUDP, cmd_trans_pos_udp,  n.TYPE_INTEGER, n.TYPE_FLOAT, n.TYPE_FLOAT, n.TYPE_FLOAT),
            n.Command(CMD_TRANS_worldPosition_TCP, n.PROTOCOL_TCP, cmd_trans_pos_tcp, n.TYPE_INTEGER, n.TYPE_FLOAT, n.TYPE_FLOAT, n.TYPE_FLOAT),
            n.Command(CMD_TRANS_worldOrientation_UDP, n.PROTOCOL_OUDP, lambda data, ce: cmd_trans_attr_(data, ce, CMD_TRANS_worldOrientation_UDP), n.TYPE_INTEGER, n.TYPE_FLOAT, n.TYPE_FLOAT, n.TYPE_FLOAT),
            n.Command(CMD_TRANS_worldOrientation_TCP, n.PROTOCOL_TCP, lambda data, ce: cmd_trans_attr_(data, ce, CMD_TRANS_worldOrientation_TCP), n.TYPE_INTEGER, n.TYPE_FLOAT, n.TYPE_FLOAT, n.TYPE_FLOAT),
            n.Command(CMD_TRANS_GAME_PROPERTY_UDP, n.PROTOCOL_OUDP, cmd_trans_prop_udp, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_BOOLEAN, n.TYPE_BOOLEAN),
            n.Command(CMD_TRANS_GAME_PROPERTY_TCP, n.PROTOCOL_TCP, cmd_trans_prop_tcp, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_BOOLEAN, n.TYPE_BOOLEAN),
            n.Command(CMD_TRANS_OBJ_PROPERTY_UDP, n.PROTOCOL_OUDP, cmd_trans_objprop_udp, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_BOOLEAN, n.TYPE_STRING, n.TYPE_BOOLEAN),
            n.Command(CMD_TRANS_OBJ_PROPERTY_TCP, n.PROTOCOL_TCP, cmd_trans_objprop_tcp, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_BOOLEAN, n.TYPE_STRING, n.TYPE_BOOLEAN),
            n.Command(CMD_TRANS_REQUEST_INIT, n.PROTOCOL_TCP, cmd_trans_request_init, n.TYPE_STRING, n.TYPE_BYTES),
            n.Command(CMD_TRANS_DO_INIT, n.PROTOCOL_TCP, cmd_trans_do_init, n.TYPE_STRING, n.TYPE_BYTES),
            n.Command(CMD_NAME, n.PROTOCOL_TCP, cmd_name, n.TYPE_STRING),
            n.Command(CMD_TRANS_SCRIPT, n.PROTOCOL_TCP, cmd_trans_script, n.TYPE_STRING, n.TYPE_BYTES),
            n.Command(CMD_GLOBALTRANS_SPAWN, n.PROTOCOL_TCP, cmd_globaltrans_spawn, n.TYPE_INTEGER, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_STRING, n.TYPE_BYTES)
        )
        
        self.cmds = {"worldPosition":cmd_trans_pos_tcp, "worldOrientation":lambda data, ce: cmd_trans_attr_(data, ce, CMD_TRANS_worldOrientation_TCP),
                "GAME_PROPERTY":cmd_trans_prop_tcp, "OBJ_PROPERTY":cmd_trans_objprop_tcp}   
        
        
        
        logic.globalDict["EO_config"] = self
        avatar_script_prop_events = {}
        transmitter_script_prop_events = {}
        for script in EO_DATA.data["scripts"]:
            module = script[:-3]
            exec("import "+module)
            importlib.reload(eval(module))
            prop_event = {}
            avt_net_events =  eval(module+".createAvatarEvents()")
            for event in avt_net_events:
                prop_event[event.trigger_property] = event
            avatar_script_prop_events[script] = prop_event
            prop_event = {}
            trans_net_events =  eval(module+".createTransmitterEvents()")
            for event in trans_net_events:
                prop_event[event.trigger_property] = event
            transmitter_script_prop_events[script] = prop_event
        self.avatar_events = avatar_script_prop_events
        self.transmitter_events = transmitter_script_prop_events
        
        if "EO_transmitters" not in logic.globalDict:
            logic.globalDict["EO_transmitters"] = []

    def onServerClose(self):
        pass
    
    def onServerStart(self):
        self.send_fct = self.server.sendToAll

    def onClientConnected(self, ce):
        
        # Are there any transmitters the client must know about?
        for id, obj in self.avatars.items():
            self.server.sendTo(ce, CMD_TRANS_SPAWN, id, obj.name, self.ce_name[self.objid_ce[id]], "", *encode_user_msg(["worldPosition", str(list(obj.worldPosition))]))
            if id in self.servervised_transmitter: # server controlled attributes on avatars
                self.send_user_msg(CMD_TRANS_DO_INIT, [id]+self.get_transmissions_data(obj), ce)
        for id, obj in self.own_transmitter.items():
            init_data = encode_user_msg(self.get_transmissions_data(obj))
            if not obj["EO_global_object"]:
                self.server.sendTo(ce, CMD_TRANS_SPAWN, id, obj["EO_Rep"], self.username, "", *init_data)
            else:
                self.server.sendTo(ce, CMD_GLOBALTRANS_SPAWN, id, obj.name, self.username, *init_data)
            
        # bla bla clients IDs
        id = self.getID()
        self.id_ce[id] = ce
        self.ce_id[ce] = id
        
        # Catch up with the init values of all transmitters
        for client in self.server.clients: # request init data from the other clients
            if client != ce:
                self.send_user_msg(CMD_TRANS_REQUEST_INIT, [id], client)
        """for id, obj in  self.own_transmitter.items(): # own Server data
            init_data = [id]
            for trans_data in obj["EO_transmitter_data"]:
                init_data.append(trans_data[0]) # trans_data[0] € [worldPosition, GAME_PROPERTY...]
                init_data.append(str(self.get_transmission_data(obj, trans_data))) 
            self.send_user_msg(CMD_TRANS_DO_INIT, init_data)"""
        
    def removeTransmitter(self, id): # at Server
        self.server.sendToAll(CMD_TRANS_DEL, id)
        if id in self.avatars:
            if not self.avatars[id].invalid:
                self.avatars[id].endObject()        
            del self.avatars[id]
            if id in self.servervised_transmitter:
                self.servervised_transmitter.remove(id)
        del self.objid_ce[id]

    def onClientDisconnected(self, ce, reason):
        
        # Did this client have any transmitters?
        for id, obj in list(self.avatars.items()):
            owner = self.objid_ce[id]
            if owner == ce:
                self.removeTransmitter(id)
            
        # id
        del self.id_ce[self.ce_id[ce]]
        del self.ce_id[ce]
        if ce in self.ce_name:
            del self.ce_name[ce]

    def onClientConnectedToServer(self):
        self.send_fct = self.client.send
        self.send_fct(CMD_NAME, self.username)


    def onClientDisconnectedFromServer(self,reason):
        pass
    
    def include_transmitter(self, obj, id):
        obj["EO_id"] = id
        init_data = encode_user_msg(self.get_transmissions_data(obj))
        if not obj["EO_global_object"]:
            self.send_fct(CMD_TRANS_SPAWN, id, obj["EO_Rep"], self.username, str(obj["EO_transmitter_data"]), *init_data)
        else:
            self.send_fct(CMD_GLOBALTRANS_SPAWN, id, obj.name, self.username, *init_data)
        obj["EO_transmitter_data"] = filterTransmitterData(obj["EO_transmitter_data"], self.networkType)
        self.own_transmitter[id] = obj
    
    def check_global_dict(self):
        # Any new transmitters spawned? (or allready spawned before network started)
        T = logic.globalDict["EO_transmitters"]
        for obj in T:
            if self.networkType=="Server":
                self.include_transmitter(obj, self.getID())
            else:
                if obj["EO_global_object"]:
                    continue
                id = self.getID() # request global id from server
                self.pending_id[id] = obj
                self.send_fct(CMD_REQUESTID, id, 0)
        logic.globalDict["EO_transmitters"] = []   
        
    def get_transmissions_data(self, obj):
        res = []
        for trans_data in obj["EO_transmitter_data"]:
            res.append(trans_data[0]) # trans_data[0] € [worldPosition, GAME_PROPERTY...]
            res.append(str(self.get_transmission_data(obj, trans_data)))
        return res
                        
    def get_transmission_data(self, obj, trans_data):
        if trans_data[0] == "GAME_PROPERTY":
            if trans_data[10]:
                value = [trans_data[7], str(obj[trans_data[7]]), type(obj[trans_data[7]])!=str, True]
            else:
                val_ = obj[trans_data[7]] - obj["EO_LAST_"+trans_data[7]]
                obj["EO_LAST_"+trans_data[7]] =   obj[trans_data[7]]
                value = [trans_data[7], str(val_), type(obj[trans_data[7]])!=str, False]
        elif trans_data[0] == "OBJ_PROPERTY":
            data = getData(obj, trans_data[7], trans_data[8])
            if trans_data[6]:
                value = [trans_data[7], trans_data[8], str(list(data)), True]
            else:
                value = [trans_data[7], trans_data[8], str(data), type(data)!=str]
        else: #pos, rot
            value = list(getData(obj, trans_data[0], trans_data[8]))
        return value
                    
    # attributeName, cmdName, curSkip, skipFreq, change, lastValue, isList, GameProp, notMatrix, server controlled, (is overwrite)
    def transmit_object(self, obj, id):
        #print("transmit_object", obj, id)
        for trans_data in obj["EO_transmitter_data"]:
            if trans_data[0] == "GAME_PROPERTY":
                val = obj[trans_data[7]]
            elif trans_data[0] == "OBJ_PROPERTY":
                val = getattr(obj, trans_data[7])
            else:
                val = getattr(obj, trans_data[0])
                    
            if trans_data[2] != 0:
                trans_data[2] -= 1
                if not trans_data[4]:
                    continue
                if trans_data[5] == val:
                    continue
                    
            trans_data[2] = trans_data[3]
            if trans_data[4]:
                trans_data[5] = copy.deepcopy(val)
            
            value = self.get_transmission_data(obj, trans_data)
            #print("send", trans_data[1], *value)
            self.send_fct(trans_data[1], id, *value)        
                
                
    def make_transmissions(self):
        for id, obj in self.own_transmitter.items():
            self.transmit_object(obj, id)
        if self.networkType == "Server":    
            for id in self.servervised_transmitter:
                self.transmit_object(self.avatars[id], id)
                
            
    def send_user_msg(self, cmd, data, ce=None):    
        """data can be a list of arbitrary data(length and type), we will send the format string with the data
            Uses CMD_USER_MSG cmd
            Sends either from Client to Server or Server to CLient, depends on the value of ce"""
        if ce:
            self.server.sendTo(ce, cmd, *encode_user_msg(data))
        else:
            self.send_fct(cmd, *encode_user_msg(data))
            
            
class AvatarEvent():
    """
    Transmitters are a one-way communication in and of themselves. But an avatar object can send a message back to the transmitter, for exmaple
    when a Player shoots at you. Each NetworkEvent will be triggered/send the message, when the defined trigger property(a bool of the avatar object)
    is True - for exmaple isHit, which is true when a player has it's mouse over your avatar and presses the left mouse button.
    
    An extra feature of this communication is that the Transmitter can reply to the message of the avatar, the specific avatar that triggered 
    the message! Normally a transmitter sends it's data to all clients at once and can't differentiate them, but when sending a reply it
    goes to just 1 client - the one who triggered the initial message.
    """
    def __init__(self, trigger_property, onTrigger, onReceive, onAnswer, onServerPeek):
        self.onTrigger = onTrigger
        self.onReceive = onReceive
        self.onAnswer = onAnswer
        self.onServerPeek = onServerPeek
        self.trigger_property = trigger_property
        
        """
        HOW TO IMPLEMENT
        
        onTrigger:
            input:  avatar (KX_GAME_OBJECT)
            return: a list of data(int, float, string or bytes) 
            desc:   when the trigger_property is True onTrigger will be executed and it's return list will be send to the transmitter
                    on the server onServerReceive will be invoked with this data and onClientReceive at the client(if the transmitter was spawned by a Client)
                    
        onReceive:
            input:  sender_name(of the client that triggered), transmitter(KX_GAME_OBJECT), data(from onTrigger)
            return: (optional) a list of data(int, float, string or bytes)  
            desc:   here you write the body of what is happening at the transmitter. data could for exmaple be the amount of damage some other client
                    did to you. So in onReceive you decrease the HP of transmitter by that value. Note that this method is being called both for client and server transmitters  
                
        onAnswer:
            input:  avatar(same object as in onTrigger), data(coming from onServerReceive or onClientReceive)
            return: None
            desc:   If onServerReceive/onClientReceive returned something, onAnswer will be invoked at the avatar. Giving the opportunity to let
                    the transmitter reaction on the initial triggering event. In onAnswer you again write the body of what happens.
                    
        onServerPeek
            input:  avatar (KX_GAME_OBJECT), data(from onTrigger)
            return: None
            desc:   When a client sends data to another client, it has to pass through the server, that's when onServerPeek get's invoked.
                    When a attribute of the transmitter(spawned by a client) is controlled server-side you must change it in this method and not in onReceive.
    """
    
class TransmitterEvent():
    """
    Transmitters are a one-way communication in and of themselves. But an avatar object can send a message back to the transmitter, for exmaple
    when a Player shoots at you. Each NetworkEvent will be triggered/send the message, when the defined trigger property(a bool of the avatar object)
    is True - for exmaple isHit, which is true when a player has it's mouse over your avatar and presses the left mouse button.
    
    An extra feature of this communication is that the Transmitter can reply to the message of the avatar, the specific avatar that triggered 
    the message! Normally a transmitter sends it's data to all clients at once and can't differentiate them, but when sending a reply it
    goes to just 1 client - the one who triggered the initial message.
    """
    def __init__(self, trigger_property, onTrigger, onReceive):
        self.onTrigger = onTrigger
        self.onReceive = onReceive
        self.trigger_property = trigger_property
        
        """
        HOW TO IMPLEMENT
        
        onTrigger:
            input:  avatar (KX_GAME_OBJECT)
            return: a list of data(int, float, string or bytes) 
            desc:   when the trigger_property is True onTrigger will be executed and it's return list will be send to the transmitter
                    on the server onServerReceive will be invoked with this data and onClientReceive at the client(if the transmitter was spawned by a Client)
                    
        onReceive:
            input:  sender_name(of the client that triggered), transmitter(KX_GAME_OBJECT), data(from onTrigger)
            return: None
            desc:   here you write the body of what is happening at the transmitter. data could for exmaple be the amount of damage some other client
                    did to you. So in onReceive you decrease the HP of transmitter by that value. Note that this method is being called both for client and server transmitters  
                    
    """
    
def filterTransmitterData(data, context): # filter w.r.t. server controlled attributes. I can't do this in getTransmitterData because at that point it's unknown if you are client or server
    return [trans for trans in data if not (trans[9] and context == "Client" or (not trans[9] and context == "Server for Client"))]

        
def getTransmitterData(kx, data):
    transmits = [] # attributeName, cmdName, curSkip, skipFreq, change, lastValue, isList, GameProp, notMatrixAsType, server-controlled, (is overwrite)
    for trans in data[3]:
        if trans[0] == "GAME_PROPERTY":
            name, skip, change, server_contr, reliable, propname, isoverwrite = trans
        elif trans[0] == "OBJ_PROPERTY":
            name, skip, change, server_contr, reliable, propname = trans
        else:
            name, skip, change, server_contr, reliable = trans
        proto = "_TCP" if reliable else "_UDP"
        temp = [name, eval("CMD_TRANS_"+name+proto), 0, skip, change, None]
        if name == "GAME_PROPERTY":
            t = type(kx[propname])
            isoverwrite = isoverwrite or t not in [int, float] # can't be add change if str or boolean
            temp += [t not in [int, float, str, bool], propname, False, server_contr, isoverwrite]
            if not isoverwrite:
                kx["EO_LAST_"+propname] = 0.0
        elif name == "OBJ_PROPERTY":
            t = type(getattr(kx, propname))
            temp += [t not in [int, float, str, bool], propname, t!=Matrix, server_contr]
        else:
            temp += [type(getattr(kx, name)) not in [str, float, int, bool], "", type(getattr(kx, name))!=Matrix, server_contr]
        transmits.append(temp)
    return transmits

def registerTransmitter(cont):
    if not cont.sensors[0].positive:
        return
    own = cont.owner
    data = EO_DATA.data["TRANSMITTER"][own.name]
    own["EO_transmitter_data"] = getTransmitterData(own, data)
    if "EO_transmitters" not in logic.globalDict:
        logic.globalDict["EO_transmitters"] = [own]
    else:
        logic.globalDict["EO_transmitters"].append(own)

    own["EO_Rep"] = data[1]
    own["EO_script"] = data[0]
    own["EO_global_object"] = data[2]
    
def deleteTransmitter(cont):
    if not cont.sensors[0].positive:
        return
    own = cont.owner
    if "EO_config" in logic.globalDict and "EO_id" in own:
        cfg = logic.globalDict["EO_config"]
        id = own["EO_id"]
        cfg.send_fct(CMD_TRANS_DEL, id)
        cfg.own_transmitter[id].endObject()
        del cfg.own_transmitter[id]
        
    
def transmitter_script(cont):
    own = cont.owner
    cfg = logic.globalDict["EO_config"]
    events = cfg.transmitter_events[own["EO_script"]]
    for sensor in cont.sensors:
        if sensor.positive:
            prop = sensor.propName
            if own[prop]:
                event = events[prop]
                own[prop] = False
                cfg.send_user_msg(CMD_TRANS_SCRIPT, [own["EO_id"], own["EO_script"], prop, cfg.username] + event.onTrigger(own))
    
def avatar_script(cont):
    own = cont.owner
    cfg = logic.globalDict["EO_config"]
    if own['EO_script']: # this fct will be invoked if avtar has messages, so not only with script
        events = cfg.avatar_events[own['EO_script']] #prop |-> NetworkEvent
    props = own['EO_trigger_properties'] #prop |-> type(overwrite/change/script)
    for sensor in cont.sensors:
        if sensor.positive:
            prop = sensor.propName
            msg_type = props[prop]
            if msg_type == "SCRIPT": # this means prop is a boolean(change can also mean back to false, so we have to check for true)
                if own[prop]:
                    event = events[prop]
                    own[prop] = False
                    if cfg.networkType == "Server": # we are at server and send to client
                        cfg.send_user_msg(CMD_AVATAR_SCRIPT_FORWARD, [own["EO_id"], -1,  own["EO_script"], prop, cfg.username]+event.onTrigger(own), cfg.objid_ce[own["EO_id"]])
                    else: # we are at client and send to server
                        cfg.send_user_msg(CMD_AVATAR_SCRIPT_FORWARD, [own["EO_id"], -1, own["EO_script"], prop, cfg.username]+event.onTrigger(own))
            else:
                if type(own[prop]) in [str, bool] or msg_type == "OVERWRITE":
                    val = str(own[prop])
                else:
                    prop_ = "EO_LAST_"+prop
                    if prop_ not in own:
                        own[prop_] = 0.0
                    val = str(own[prop] - own[prop_])
                    own[prop_] = own[prop]
                    
                cfg.send_fct(CMD_AVATAR_MSG, own["EO_id"], prop, 0 if msg_type=="CHANGE" else 1, val, type(own[prop]) != str)
        