from bge import logic
import EO_network as n
from EO_config import GameConfig

cont = logic.getCurrentController()
own = cont.owner
own["EO_connection"] = "server"

port = own["EO_PORT"]

cfg = GameConfig(own["EO_TIMEOUT"], "Server", own["EO_NAME"])
NF = n.NetworkFactory(cfg)
server = NF.createServer(port)
try:
    import bpy
    bpy.EO_server = server # when exiting bge not properly, still want the server shutdown
except:
    pass # standalone no worries

own['x'] = 0
def main():
    if server.isRunning():
        cfg.check_global_dict()
        cfg.make_transmissions()
        server.main()
        own["EO_PLAYERS"] = server.clients_connected
        own['x'] += 1
        if own['x'] > 15:
            own['x'] = 0
            own["EO_PINGS"] = str(dict([(cfg.ce_name[ce], int(ce.ping)) for ce in server.clients]))
    else:
        if endGame:
            logic.endGame()
        
    
def shutdown(cont):
    server.shutdown()

endGame = False
def shutdown_and_close(cont):
    server.shutdown()
    global endGame
    endGame = True