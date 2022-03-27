# can't import anything bge related outside of createTransmitterEvents or createAvatarEvents
# since bpy can't handle it

def getTransmitterTriggerProperties():
    return ["sendFileToServer"]

def createTransmitterEvents():
    from EO_config import AvatarEvent, TransmitterEvent
    import bpy
    
    def b_onTrigger(transmitter):
        fileName = transmitter["EO_fileName"]
        filepath = bpy.path.abspath("//"+fileName)
        filedata = None
        with open(filepath, "rb") as file:
            filedata = file.read()
        return [fileName, filedata]
        
    def b_onReceive(sender_name, avatar, data): 
        from bge import logic
        createFile(*data)
        logic.globalDict["File"] = data
   
    N1 = TransmitterEvent("sendFileToServer", b_onTrigger, b_onReceive)
    return [N1]

def getAvatarTriggerProperties():
    return ["sendFileToClient"]

def createAvatarEvents():
    from EO_config import AvatarEvent, TransmitterEvent
    from bge import logic
    import bpy
    
    def b_onTrigger(avatar):
        if "File" in logic.globalDict:
            return logic.globalDict["File"]
        else:
            return []
        
    def b_onReceive(sender_name, transmitter, data):
        createFile(*data)
    
    def b_onServerPeek(avatar, data):
        pass

    def b_onAnswer(avatar, data):
        pass
   
    A1 = AvatarEvent("sendFileToClient", b_onTrigger, b_onReceive, b_onAnswer, b_onServerPeek)
    return [A1]

def createFile(name, filedata):
    import bpy
    fileName = "recv_"+name 
    filepath = bpy.path.abspath("//"+fileName)
    with open(filepath, "wb") as file:
        file.write(filedata)