import bge
from socket import socket, AF_INET, SOCK_STREAM
from mathutils import Vector, Euler, Matrix
import time
import Data
    
def getData(obj, attribute, type, decimals):
    if type == 0:   # types: Integer, Float                          (Attribute)
        return round(getattr(obj, attribute), decimals)
    elif type == 1: # types: Boolean, String                         (Attribute)
        return getattr(obj, attribute)
    elif type == 2: # types: Vector                                  (Attribute)
        return [round(value, decimals) for value in getattr(obj, attribute)]
    elif type == 3: # types: Matrix                                  (Attribute)
        return [round(value, decimals) for value in getattr(obj, attribute).to_euler()]
    elif type==4:   # types: Integer, Float                           (Property)
        return round(obj[attribute], decimals)
    elif type==5:   # type: Boolean, String, List, Dictionary, Tuple  (Property)
        return obj[attribute]
            
def setData(ObjectInfo, data):
    obj = ObjectInfo[0]
    AttributeInfo = ObjectInfo[1]
    for d in data:
        attribute, type = AttributeInfo[d[0]]
        if type == 0: # Integer & Float
            setattr(obj, attribute, float(d[1]))
        elif type == 1: # Boolean
            setattr(obj, attribute, bool(d[1]))
        elif type == 2: # Vector
            setattr(obj, attribute, Vector(list(d[1])))
        elif type == 3: # Matrix
            setattr(obj, attribute, Euler(list(d[1])).to_matrix())  
        elif type == 4 or type == 5:
            obj[attribute] = d[1] 
            
def NumberStringIdentifier(string):
    try:
        return float(string)
    except ValueError:
        return string                   
def getRightValue(obj, string):
    "The string in a PropertySensor can either be a interpreted as a number, a sting or a KX_GameObject Property"
    if string not in obj:
        return NumberStringIdentifier(string)
    else:    
        return obj[string]            
def checkSensorPositive(obj, sensor):
    "A PropertySensor will not register the changes made to a property, when these changes were made in the same tick"
    if str(type(sensor)) != "<class 'SCA_PropertySensor'>":
        return sensor.positive        
    if sensor.mode==1: return obj[sensor.propName]==getRightValue(obj, sensor.value)
    elif sensor.mode==2: return obj[sensor.propName]!=getRightValue(obj, sensor.value)
    elif sensor.mode==3: return getRightValue(obj, sensor.min)<=obj[sensor.propName]<=getRightValue(obj, sensor.max)
    elif sensor.mode==4: return sensor.positive,
    elif sensor.mode==6: return obj[sensor.propName]<getRightValue(obj, sensor.value)
    elif sensor.mode==7: return obj[sensor.propName]>getRightValue(obj, sensor.value)
    
def ExtraPrint(string):
    print(string)
    bge.logic.sendMessage(string)
    
def close():
    if not bge.Client.socket._closed:
        bge.Client.execute = bge.Client.send = lambda : None       
        bge.Client.socket.close()  
        ExtraPrint("Connection closed")
        
def main(): 
    bge.Client.execute() 

class Client():
    
    command_splitter = chr(30)
    value_splitter = chr(29)
    
    def __init__(self, ip, port, connection_attempts, bufsize, name, transmitters_settings, observers_settings):
        
        # Receive Variables
        self.current_string = ""
        self.bufsize = bufsize
        
        # Transmitters, Representatives, Observers
        self.Transmitters = {}
        self.fake_Transmitters = {}       
        self.transmitters_settings = transmitters_settings
        self.Representatives = {}
        self.observers = {}
        self.observers_settings = observers_settings
        
        # Client Settings
        self.name = name
        self.MasterString = ""
        self.id = 0
        
        # Other
        self.check_objects = []
        self.oldSceneObjects = []
        self.tick = 0
        
        if "Message" in own.sensors:
            self.Message = own.sensors["Message"]
        else:
            self.Message = None    

        self.connect((ip, port), connection_attempts)
                    
    def connect(self, adr, connection_attempts):
        try:
            import bpy
            self.socket = bpy.types.Scene.Socket = socket(AF_INET, SOCK_STREAM)
        except:
            self.socket = socket(AF_INET, SOCK_STREAM)
            
        ExtraPrint("Tries to establish Connection")
        for connect_attempt in range(connection_attempts):
            try:
                self.socket.connect(adr) 
                self.execute = self.receive
                self.socket.setblocking(False)
                ExtraPrint("Connected to Server")
                return
            except:
                time.sleep(0.4)            
        self.execute = lambda: None        
        
    def Id(self):
        self.id += 1
        return str(self.id)
    
    def receive(self):
        while True:
            try:
                data = self.socket.recv(self.bufsize).decode()
                if data=="":
                    raise ConnectionResetError     
                self.current_string += data
                if self.command_splitter  in self.current_string:
                    commands = self.current_string.split(self.command_splitter )
                    for command in commands[:-1]:
                        try:
                            self.filter(command)
                        except KeyError: # When the Client still receives data, but the Client already removed the Representative
                            pass
                    self.current_string = commands[-1]    
            except BlockingIOError:
                break
            except:
                close()
                break
            
    def filter(self, data):
        command = data.split(self.value_splitter)        

        if command[0] == "A":
            setData(self.Representatives[command[1]], eval(command[2]))              
        elif command[0] == "P" or command[0] == "PS": # Representative Request from Client / Representative Request from Server
            obj = self.Transmitters[command[1]][0]
            if command[3] == "ASSIGN":
                obj[command[2]] = NumberStringIdentifier(command[4])
            elif command[3] == "ADD":
                obj[command[2]] += NumberStringIdentifier(command[4])
            for pack in eval(command[5]):
                if checkSensorPositive(obj, obj.sensors[pack[0]]):
                    self.MasterString += self.value_splitter.join([{"PS":"SS", "P":"S"}[command[0]], command[1], pack[1], pack[2], str(getRightValue(obj, pack[3])),command[6]])+self.command_splitter                   
                        
        elif command[0] == "S": # Representative Respond
            if command[3] == "ASSIGN":
                self.Representatives[command[1]][0][command[2]] = NumberStringIdentifier(command[4])
            elif command[3] == "ADD":
                self.Representatives[command[1]][0][command[2]] += NumberStringIdentifier(command[4])
                
        elif command[0] == "M":
            bge.logic.sendMessage(command[1])        
                
        elif command[0] == "init" or command[0] == "change": # What do I realy Need? --> "init", nameforspawninig, attrs, data, serverID, OwnersClientname, Sending
            # "init"/"change" ServerID, RepresentativeName, Sender, Attrs, data, 
            if command[0] == "change": # change, ServerId, Cube2, CLIENT, [[IndexNumber, POSITION, type, decimals, ALWAYS]...], data,  CreatorID, ownID
                if command[7] in self.fake_Transmitters: # If the object dies before the server send the "change" messages
                    obj = self.fake_Transmitters[command[7]]
                else:
                    self.MasterString += "DS"+self.value_splitter+command[1]+self.command_splitter 
                    return
            elif command[0] == "init": # init, ServerID, Cube2, CLIENT, [[IndexNumber, POSITION, type, decimals, ALWAYS]...], data, CreatorID, name
                obj = scene.addObject(command[2])        
                if command[3] == "CLIENT":
                    obj['Name'] = command[7]
            self.Representatives[command[1]] = [obj, dict([(pack[0], pack[1:3]) for pack in eval(command[4])]), command[6]]
            self.checkForObserverCharacteristic(command[2], obj, command[1])
            setData(self.Representatives[command[1]], eval(command[5]))        
            
        # change, Id, Cube2, Server, attrs, data, kx.name, Server-ID, Client's obj Id    
                
        elif command[0] == "CR": # Correct the Id used for own Transmitters
            self.Transmitters[command[2]] = self.Transmitters.pop(command[1])[:2]+["A"+self.value_splitter+command[2]+self.value_splitter]
                
        elif command[0] == "DS": # Remove Server Representative
            self.Representatives[command[1]][0].endObject()
            del self.Representatives[command[1]]
            if command[1] in self.observers:
                del self.observers[command[1]]
                
        elif command[0] == "DC": # Remove Own Transmitter
            self.Transmitters[command[1]][0].endObject()    
            del self.Transmitters[command[1]]                   
            
        elif command[0] == "R": # The Player Limit isn't reached
            self.execute = self.main   
            self.MasterString += "N"+self.value_splitter+self.name+self.command_splitter
            
        elif command[0] == "exec":
            exec(command[1])         
        
    def handleSceneChanges(self):
        for obj in self.oldSceneObjects:
            if not obj.invalid:
                if obj not in self.check_objects:
                    if obj.name in self.transmitters_settings:
                        self.embed_Transmitter(obj)
                    self.check_objects.append(obj)        
            elif obj in self.check_objects:
                for id in dict(self.Transmitters):
                    if self.Transmitters[id][0] == obj:
                        self.MasterString += ["DC", "DIC"]["B" in self.Transmitters[id][2]]+self.value_splitter+id+self.command_splitter 
                        del self.Transmitters[id]
                for id in dict(self.Representatives):
                    if self.Representatives[id][0] == obj:
                        if self.Representatives[id][2] == "0":
                            self.MasterString += "DS"+self.value_splitter+id+self.command_splitter    
                        else:    
                            self.MasterString += "DCN"+self.value_splitter+id+self.value_splitter+self.Representatives[id][2]+self.command_splitter 
                        del self.Representatives[id]            
                        if id in self.observers:
                            del self.observers[id]
                for id in dict(self.fake_Transmitters):
                    if self.fake_Transmitters[id] == obj:
                        del self.fake_Transmitters[id]        
                self.check_objects.remove(obj)        
        self.oldSceneObjects = list(scene.objects)        
                
    def embed_Transmitter(self, obj):
        object_settings = self.transmitters_settings[obj.name]
        id = self.Id()
        Sending = object_settings[0]
        Representative = object_settings[1]
        all_settings = []
        all_data = []
        if Sending == "CLIENT":
            self.Transmitters[id] = [obj, [], "B"+self.value_splitter+id+self.value_splitter]   
        for setting in enumerate(object_settings[3]):
            #setting - (AttributeIndex, (POSITION, 3, Frequency, ChangeRequired))
            if setting[1][0] in obj:
                Type = {int:4, float:4, bool:5, str:5, list:5, dict:5, tuple:5}.get(type(obj[setting[1][0]]))   
            else:
                Type = {int:0, float:0, bool:1, Vector:2, Matrix:3}.get(type(getattr(obj, setting[1][0])))
            all_settings.append([str(setting[0]),setting[1][0],Type, setting[1][1], setting[1][2], setting[1][3]])
            all_data.append((str(setting[0]), getData(obj, setting[1][0], Type, setting[1][1])))
            obj['sending'] = Sending
            if Sending == "CLIENT":
                obj['M_id'] = id
                if setting[1][2] != -1:
                    self.Transmitters[id][1].append([0,setting[1][2], str(setting[0]), setting[1][0], Type, setting[1][1], setting[1][3], None])
        if Sending == "SERVER":
            self.fake_Transmitters[id] = obj        
            self.MasterString += self.value_splitter.join(["ST", id, Representative, Sending, str(all_settings), str(all_data), obj.name, str(object_settings[2])])+self.command_splitter    
        else: 
            self.MasterString += self.value_splitter.join(["CT", id, Representative, Sending, str(all_settings), str(all_data)])+self.command_splitter          
                  
    def send(self):
        for id in self.Transmitters:
            values = self.Transmitters[id]
            if values[1]:
                all_data = []
                for value in values[1]:
                    if not value[6]:
                        if self.tick > value[0]:
                            all_data.append((value[2], getData(values[0], value[3], value[4], value[5])))
                            value[0] = self.tick+value[1]    
                    else:
                        single_data = (value[2], getData(values[0], value[3], value[4], value[5]))
                        if self.tick > value[0] and single_data != value[7]:
                            all_data.append(single_data)
                            value[0] = self.tick+value[1]
                            value[7] = single_data
                if all_data:        
                    self.MasterString += values[2]+str(all_data)+self.command_splitter        
        if self.MasterString:
            try:
                self.socket.send(self.MasterString.encode())
            except BlockingIOError:
                pass
            self.MasterString = ""
            
    def checkForObserverCharacteristic(self, name, obj, id):
        if name in self.observers_settings:
            self.observers[id] = []
            for pack in self.observers_settings[name]:
                self.observers[id].append([obj, obj.sensors[pack[0]], pack[1], pack[2], pack[3], pack[4], self.Representatives[id][2]])                           
            
    def checkObservers(self):
        for id in self.observers:
            for pack in self.observers[id]:
                if pack[1].positive:
                    self.MasterString += self.value_splitter.join(["P", id, pack[2], pack[3], str(getRightValue(pack[0], pack[4])), pack[5], pack[6]])+self.command_splitter               

    def checkMessage(self):
        if self.Message:
            for subject in self.Message.subjects:
                if subject[:3] in ["[C]", "[S]", "[A]"]:
                    self.MasterString += self.value_splitter.join(["M", subject[:3], subject[3:]])+self.command_splitter
                
    def main(self):
        self.tick += 1
        self.handleSceneChanges()
        self.checkObservers()
        self.checkMessage()
        self.receive()
        self.send() 
            
# Initial Varibles                         
own = bge.logic.getCurrentController().owner
scene = bge.logic.getCurrentScene()

# Collect User Data
for property in [(0,"IP"), (1,"Port"), (2, "Connection_Tries"), (5, "Size_Buffer"), (3, "Name")]:
    if property[1] in own:
        Data.Network[property[0]] = own[property[1]]
bge.Client = Client(Data.Network[0], Data.Network[1], Data.Network[2], Data.Network[5], Data.Network[3], Data.Transmitters, Data.Observers)        

