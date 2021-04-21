import bge
from socket import socket, AF_INET, SOCK_STREAM
from mathutils import Matrix, Euler, Vector
import time
import Data

def getData(obj, attribute, type, decimals):
    if type == 0: # Integer & Float
        return round(getattr(obj, attribute), decimals)
    elif type == 1: # Boolean & String
        return getattr(obj, attribute)
    elif type == 2: # Vector
        return [round(v, decimals) for v in getattr(obj, attribute)]
    elif type == 3: # Matrix
        return [round(v, decimals) for v in getattr(obj, attribute).to_euler()]
    elif type==4: # Property Integer & Float
        return round(obj[attribute], decimals)
    elif type==5: # Property Boolean & String & List & Dictionary & Tuple
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
    "A PropertySensor will not register the changes made to a property when these changes were made in the same tick"
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

class Server:
    
    command_splitter = chr(30)
    value_splitter = chr(29)

    def __init__(self, port, max_players, bufsize, involved_objects, representative_settings):

        # Socket settings
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.setblocking(False)
        self.socket.bind(("", port))
        self.socket.listen(0)    

        # Client attributes
        self.connected_clients = []
        self.IdToClient = {}

        # Server attributes
        self.execute = self._main
        self.may_players = max_players
        self.bufsize = bufsize
        self.Transmitters = {} # Id: [obj, attributes, normal_send-string, Initial_send-string1, Initial_send-string2]
        self.Transmitter_id = 0
        self.Client_id = 0
        self.MasterString = ""
        self.check_objects = []
        self.involved_objects = involved_objects
        self.representative_settings = representative_settings
        self.representative_monitoring = {}
        self.lastScene = []
        self.tick = 0
        
        # Other
        try:
            import bpy
            bpy.types.Scene.Socket = [self.socket, self.connected_clients]
        except:
            pass    
        
        if "Message" in own.sensors:
            self.Message = own.sensors["Message"]
        else:
            self.Message = None
        ExtraPrint("Server started")
        
    def Id(self, var):
        setattr(self, var, getattr(self, var)+1)
        return str(getattr(self, var))
    
    def UpdateClientsClientKnowledge(self):
        for client in self.connected_clients:
            client.other_clients = list(self.connected_clients)
            client.other_clients.remove(client)
            
    def getName(self, name):
        names = [Oclient.name for Oclient in self.connected_clients]  
        extra = ""
        while name+extra in names:
            if extra=="":
                extra = "2"
            else:
                extra = str(int(extra)+1)
        return name+extra

    def accept_clients(self): # Accept new Connections Requests
        try:
            while True:
                new_connection = self.socket.accept()
                if len(self.connected_clients) < self.may_players:
                    new_client = Client(new_connection[0], self.bufsize)
                    for client in self.connected_clients:
                        for id, option in client.Representatives.items():
                            new_client.MasterString += option[3]+str([(AIndex, getData(option[0], option[1][AIndex][0], option[1][AIndex][1], option[2][AIndex])) for AIndex in option[1]])+option[4]
                    for id, option in self.Transmitters.items():
                        new_client.MasterString += option[4]+str([(attrs[0], getData(option[0], *attrs[1:4])) for attrs in option[2]])+option[5]
                    self.connected_clients.append(new_client)
                    self.IdToClient[new_client.Id] = new_client
                    self.UpdateClientsClientKnowledge()  
                    ExtraPrint("User Joins")      
                    new_client.MasterString += "R"+self.command_splitter
                    continue
                new_connection[0].close()        
        except BlockingIOError:
            pass
        except SystemError:
            pass

    def receive(self, client):
        # Receive Data
        while True:
            try:
                data = client.recv().decode()
                if data == "":
                    raise ConnectionResetError  
                client.current_string += data
                if self.command_splitter in client.current_string:
                    commands = client.current_string.split(self.command_splitter)
                    for command in commands[:-1]:
                        try:
                            self.filter(command, client)
                        except KeyError:#KeyError: # When the Server still receives data, but the Server already removed the Representative
                            pass
                    client.current_string = commands[-1]
            except BlockingIOError:
                break
            except:
                self.remove_client(client)    
                break
                        
    def filter(self, raw_data, client):
        command = raw_data.split(self.value_splitter)    
        ready_data = raw_data+self.command_splitter
        
        if command[0] == "A":
            setData(client.Representatives[command[1]], eval(command[2]))   
            for Oclient in client.other_clients:
                Oclient.MasterString += ready_data 
                  
        elif command[0] == "B":
            self.filter("A"+raw_data[1:].replace(command[1], client.RepresentativesCorrector[command[1]], 1), client)                
                    
        elif command[0] == "P": # Representative Request..
            if command[1] in self.Transmitters: # Server's Transmitter
                obj = self.Transmitters[command[1]][0]
                if command[3] == "ASSIGN":
                    obj[command[2]] = NumberStringIdentifier(command[4])
                elif command[3] == "ADD":
                    obj[command[2]] += NumberStringIdentifier(command[4])
                for pack in eval(command[5]):
                    if checkSensorPositive(obj, obj.sensors[pack[0]]):
                        client.MasterString += self.value_splitter.join(["S", command[1], pack[1], pack[2], str(getRightValue(obj, pack[3]))])+self.command_splitter
            else: # Transfer Request to Client's Transmitter
                self.IdToClient[command[6]].MasterString += self.value_splitter.join([command[0], command[1], command[2], command[3], command[4], command[5], client.Id])+self.command_splitter
                    
        elif command[0] == "S": # Representative Responds Transfer
            self.IdToClient[command[5]].MasterString += ready_data           
                
        elif command[0] == "SS": # Representative Responds
            if command[3] == "ASSIGN":
                client.Representatives[command[1]][0][command[2]] = NumberStringIdentifier(command[4])
            elif command[3] == "ADD":
                client.Representatives[command[1]][0][command[2]] += NumberStringIdentifier(command[4])
                
        elif command[0] == "M":
            self.SpreadMessage(command[1], command[2], client.other_clients)
                        
        elif command[0] == "CT": # Client Transmitter
            # CT, Id, Cube2, CLIENT, [[IndexNumber, POSITION, type, decimals, frequency]...], data
            obj = scene.addObject(command[2])
            obj['Name'] = client.name
            Id = self.Id("Transmitter_id")
            
            client.Representatives[Id] = [obj, dict(   [(pack[0], pack[1:3]) for pack in eval(command[4])]   ), dict([(pack[0], pack[3]) for pack in eval(command[4])])] # obj, attr_type[Id], decimals[Id](because of performance), raw_data_init_
            setData(client.Representatives[Id], eval(command[5]))    
            client.RepresentativesCorrector[command[1]] = Id
            final_data = self.value_splitter.join(["init", Id, command[2], command[3], command[4], command[5], client.Id, client.name])+self.command_splitter # removed one,after command[5]
            client.Representatives[Id] += final_data.split(command[5])
            for Oclient in client.other_clients:
                Oclient.MasterString += final_data
            client.MasterString += self.value_splitter.join(["CR", command[1], Id])+self.command_splitter
                    
            self.checkForObserverCharacteristic(command[2], obj, Id, client)   
            
        elif command[0] == "ST": # Server Transmitter
            obj = scene.addObject(command[6], None, eval(command[7]))
            Id = self.Id("Transmitter_id")
            setData([obj, dict([(pack[0], pack[1:3]) for pack in eval(command[4])])], eval(command[5]))        
                
            self.Transmitters[Id] = [obj, [], [], "A"+self.value_splitter+Id+self.value_splitter]
            for pack in eval(command[4]):
                if pack[4] != -1:
                    self.Transmitters[Id][1].append([0, pack[4], pack[0], pack[1], pack[2], pack[3], pack[5], None]) # TickCounter, Frequency, IndexNumber, attr, type, decimals, ChangeRequired, LastSentData
                self.Transmitters[Id][2].append([0, pack[4], pack[0], pack[1], pack[2], pack[3], pack[5], None])    
            client.MasterString += self.value_splitter.join(["change", Id, command[2], command[3], command[4], command[5], "0", command[1]])+self.command_splitter # change, ServerId, Cube2, CLIENT, [[IndexNumber, POSITION, type, decimals, ALWAYS]...], data,  CreatorID, ownID
            final_data = self.value_splitter.join(["init", Id, command[2], command[3], command[4], command[5], "0"])+self.command_splitter
            self.Transmitters[Id] += final_data.split(command[5])
            for Oclient in client.other_clients:
                Oclient.MasterString += final_data

        elif command[0] == "DC": # Remove Client Representative 
            self.RemoveRepresentative(command[1], client)
            
        elif command[0] == "DCN": # Remove Client Representative (Messages comming from another client)
            self.IdToClient[command[2]].MasterString += "DC"+self.value_splitter+command[1]+self.command_splitter
            self.RemoveRepresentative(command[1], self.IdToClient[command[2]])    
            
        elif command[0] == "DIC": # Remove Client Representative(with an incorrect ID tranfered, therefor it needs to be corrected)
            self.RemoveRepresentative(client.RepresentativesCorrector[command[1]], client) 
               
        elif command[0] == "DS": # Remove Server Transmitter
            self.Transmitters[command[1]][0].endObject()
            for Oclient in client.other_clients:
                Oclient.MasterString += ready_data
            del self.Transmitters[command[1]]
            
        elif command[0] == "N":
            client.name = self.getName(command[1])
                 
        elif command[0] == "exec":
            exec(command[1])                                      
            
    def RemoveRepresentative(self, id, client, delete=True):
        if delete:
            client.Representatives[id][0].endObject()
        for c in client.other_clients:
            c.MasterString += self.value_splitter.join(["DS", id])+self.command_splitter          
        del client.Representatives[id]
        if id in self.representative_monitoring:
            del self.representative_monitoring[id]

    def remove_client(self, client):
        for id in dict(client.Representatives):
            self.RemoveRepresentative(id, client)
        
        client.socket.close()
        client.send = lambda: None
        self.connected_clients.remove(client)
        del self.IdToClient[client.Id]   
        self.UpdateClientsClientKnowledge()
        ExtraPrint("User Disconnects")
        
    def search(self):
        for obj in self.lastScene:
            if not obj.invalid:
                if obj not in self.check_objects:
                    if obj.name in self.involved_objects:
                        self.send_once(obj)
                    self.check_objects.append(obj)        
            elif obj in self.check_objects:
                for client in self.connected_clients:
                    for id in dict(client.Representatives):
                        if client.Representatives[id][0] == obj:
                            self.RemoveRepresentative(id, client,delete=False)
                            client.MasterString += "DC"+self.value_splitter+id+self.command_splitter
                for id in dict(self.Transmitters):
                    if self.Transmitters[id][0] == obj:
                        self.MasterString += "DS"+self.value_splitter+id+self.command_splitter
                        del self.Transmitters[id]
                self.check_objects.remove(obj)        
        self.lastScene = list(scene.objects)  
        
    def send_once(self, obj):
        object_settings = self.involved_objects[obj.name]
        id = self.Id("Transmitter_id")
        Representative = object_settings[0]
        all_settings = []
        all_data = []
        self.Transmitters[id] = [obj, [], [], "A"+self.value_splitter+id+self.value_splitter]        
        for setting in enumerate(object_settings[1]): 
            #setting - (IndexNumber, (POSITION, 3, ALWAYS/ONCE))
            if setting[1][0] in obj:
                Type = {int:4, float:4, bool:5, str:5, list:5, dict:5, tuple:5}.get(type(obj[setting[1][0]]))   
            else:
                Type = {int:0, float:0, bool:1, Vector:2, Matrix:3}.get(type(getattr(obj, setting[1][0])))
            all_settings.append([str(setting[0]), setting[1][0],Type, setting[1][1], setting[1][2], setting[1][3]])
            all_data.append((str(setting[0]), getData(obj, setting[1][0], Type, setting[1][1])))
            obj['sending'] = "SERVER"
            obj['M_id'] = id
            if setting[1][2] != -1:
                self.Transmitters[id][1].append([0, setting[1][2], str(setting[0]), setting[1][0], Type, setting[1][1], setting[1][3], None])        
            self.Transmitters[id][2].append([str(setting[0]), setting[1][0], Type, setting[1][1], setting[1][3], None])            
        self.Transmitters[id] += [self.value_splitter.join(["init", id, Representative, "SERVER", str(all_settings)])+self.value_splitter, self.value_splitter+"0"+self.command_splitter]
        self.MasterString += self.value_splitter.join(["init", id, Representative, "SERVER", str(all_settings), str(all_data), "0"])+self.command_splitter
        
    def RuleObservation(self):
        for id in self.representative_monitoring:
            for pack in self.representative_monitoring[id][0]: # pack - SensorName, PropertyName, Mode, Value, [[SensorName, PropertyName, Mode, Value]...]
                if pack[0].positive:
                    client = self.representative_monitoring[id][1]
                    client.MasterString += self.value_splitter.join(["PS", id, pack[1], pack[2], str(getRightValue(self.representative_monitoring[id][2],pack[3])), pack[4], "0"])+self.command_splitter
    def checkForObserverCharacteristic(self, name, obj, Id, client):
        if name in self.representative_settings:
            self.representative_monitoring[Id] = [[], client, obj] 
            for pack in self.representative_settings[name]:
                self.representative_monitoring[Id][0].append([obj.sensors[pack[0]], pack[1], pack[2], pack[3], pack[4]])                                           
                
    def SpreadMessage(self, prefix, message, receivers):                                        
            if prefix in ["[S]", "[A]"]:
                bge.logic.sendMessage(message)
            if prefix in ["[C]", "[A]"]:    
                for client in receivers:
                    client.MasterString += self.value_splitter.join(["M", message])+self.command_splitter                
                
    def checkMessage(self):
        if self.Message:
            for subject in self.Message.subjects:
                if subject[:3] in ["[C]", "[S]", "[A]"]:
                    self.SpreadMessage(subject[:3], subject[3:], self.connected_clients)

    def _main(self):
        self.tick += 1
        
        self.accept_clients()
        self.search()
        self.checkMessage()
        self.RuleObservation()

        for id in self.Transmitters: # Collect Transmitter Data
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
                    self.MasterString += values[3]+str(all_data)+self.command_splitter                          
            
        for client in self.connected_clients:
            # Receive
            self.receive(client)
            # Send    
            client.MasterString += self.MasterString
            if client.MasterString:
                client.send()            
                
        self.MasterString = ""        
                               
class Client():

    def __init__(self, socket, bufsize):
        
        # Client Settings
        self.Id = bge.Server.Id("Client_id")
        self.name = ""
        
        # Socket Settings
        self.socket = socket
        self.socket.setblocking(False)
        
        # Receive Attributes
        self.current_string = ""    
        self.bufsize = bufsize
        
        # Objects
        self.Representatives = {}
        self.RepresentativesCorrector = {}
        self.MasterString = ""
        self.other_clients = []
        
    def recv(self):
        return self.socket.recv(self.bufsize)
        
    def send(self):
        try:
            self.socket.send(self.MasterString.encode())
        except BlockingIOError:
             pass
        self.MasterString = ""

own = bge.logic.getCurrentController().owner
scene = bge.logic.getCurrentScene()

for prop in [(1, "Port"), (4, "Max_Players"), (5, "Size_Buffer")]:
    if prop[1] in own:
        Data.Network[prop[0]] = own[prop[1]]
bge.Server = Server(Data.Network[1], Data.Network[4], Data.Network[5], Data.Transmitters, Data.Observers)        

def main():
    bge.Server.execute()    
            
def close():
    if not bge.Server.socket._closed:
        bge.Server.socket.close()
        bge.Server.execute = lambda : None            
            
