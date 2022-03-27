# can't import anything bge related outside of createTransmitterEvents or createAvatarEvents
# since bpy can't handle it

def getTransmitterTriggerProperties():
    return []

def createTransmitterEvents():
    return []

def getAvatarTriggerProperties():
    return ["gotHit"]

def createAvatarEvents():
    from EO_config import AvatarEvent, TransmitterEvent
    
    def b_onTrigger(avatar):
        return []
        
    def b_onReceive(sender_name, transmitter, data):
        transmitter["HP"] -= 10
    
    def b_onServerPeek(avatar, data):
        pass

    def b_onAnswer(avatar, data):
        pass
   
    N1 = AvatarEvent("gotHit", b_onTrigger, b_onReceive, b_onAnswer, b_onServerPeek)
    return [N1]