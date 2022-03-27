from bge import logic
import EO_network as n
import time
from EO_config import GameConfig

"""
the property "connection" can be
-"offline" never tried to connect
-"connecting" trying to connect
-"active" is connected
-"failed" failed to connect
"""
cont = logic.getCurrentController()
own = cont.owner
own["EO_connection"] = "connecting"

ip = own["EO_IP"]
port = own["EO_PORT"]
timeout = own["EO_TIMEOUT"]
con_time = own["EO_CONNECT_TIME"]

cfg = GameConfig(timeout, "Client", own["EO_NAME"])
NF = n.NetworkFactory(cfg)

start = time.time()
client = None
endGame = False

def main():
    global client
    if client:
        if client.isRunning():
            cfg.check_global_dict()
            cfg.make_transmissions()
            client.main()
            own["EO_PING"] = client.ping
            own["EO_PLAYERS"] = client.clients_connected
        else:
            if endGame:
                logic.endGame()
    else:
        if time.time()-start < con_time:
            client = NF.connect(ip, port, 1.5)        
            if client != None:
                own["EO_connection"] = "active"
                try:
                    import bpy
                    bpy.EO_client = client # when exiting bge not properly, still want the client to leave
                except:
                    pass # standalone no worries
        else:
            own["EO_connection"] = "failed"
        
    
def disconnect(cont):
    if client:
        client.disconnect()
        
def disconnect_and_close(cont):
    if cont.sensors[0].positive:
        if client:
            client.disconnect()
            global endGame
            endGame = True
        else:
            logic.endGame()
        
def reconnect(cont):
    if client:
        start = time.time()
        own["EO_connection"] = "connecting"