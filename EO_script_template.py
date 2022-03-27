# can't import anything bge related outside of createTransmitterEvents or createAvatarEvents
# since bpy can't handle it

def getTransmitterTriggerProperties():
    return ["transmitter_prop"]

def createTransmitterEvents():
    from EO_config import AvatarEvent, TransmitterEvent
    from bge import logic
    
    def b_onTrigger(transmitter):
        print("Transmitter onTrigger")
        return ["Hello world", 1138]
        
    def b_onReceive(sender_name, avatar, data):
        print("Transmitter onReceive:", data)
    
    T1 = TransmitterEvent("transmitter_prop", b_onTrigger, b_onReceive)
    return [T1]

def getAvatarTriggerProperties():
    return ["avatar_prop"]

def createAvatarEvents():
    from EO_config import AvatarEvent, TransmitterEvent
    from bge import logic
    
    def b_onTrigger(avatar):
        print("Avatar onTrigger")
        return ["Hello world", 1138]
        
    def b_onReceive(sender_name, transmitter, data):
        print("Avatar onReceive:", data)
    
    def b_onServerPeek(avatar, data):
        print("Avatar onServerPeek")

    def b_onAnswer(avatar, data):
        print("Avatar onAnswer")
   
    A1 = AvatarEvent("avatar_prop", b_onTrigger, b_onReceive, b_onAnswer, b_onServerPeek)
    return [A1]