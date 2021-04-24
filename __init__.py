bl_info = {
    "name": "Easy Online",
    "description": "An addon which makes it possible to create multiplayer games.",
    "author": "BleGaDev, Jorge Bernal (lordloki)",
    "version": (1, 1, 0),
    "blender": (2, 80, 0),
    "location": "LOGIC_EDITOR > UI > MULTIPLAYER",
    "category": "Game Engine",
}

import bpy
import os
from bpy.app.handlers import persistent

@persistent
def Update_GameProperty(self, context):

    if bpy.types.Scene.Network_Type != "NONE":
        obj = context.object
        scn = context.scene
            
        all_objects = [object for scene in bpy.data.scenes for object in scene.objects]
        if scn.Network_Type == "SERVER":
            Transmitter_dictonary = dict([(obj.name, [obj.Representative, [[{"CUSTOM":item.Custom}.get(item.Type, item.Type), item.Decimals, item.Skip, item.ChangeRequired] for item in obj.Transmissions]]) for obj in all_objects if obj.Type=="Transmitter"])
            Observer_dictonary = dict(    [(obj.name, [[item.Sensor, item.Property, item.Mode, item.Value, str([[counter.Sensor, counter.Property, counter.Mode, counter.Value] for counter in item.Counter])] for item in obj.Rules]) for obj in all_objects if obj.Type=="Observer"])
        elif scn.Network_Type == "CLIENT":
            Transmitter_dictonary = dict([(obj.name, [obj.Sender,obj.Representative, obj.Lifetime, [[{"CUSTOM":item.Custom}.get(item.Type, item.Type), item.Decimals, item.Skip, item.ChangeRequired] for item in obj.Transmissions]]) for obj in all_objects if obj.Type=="Transmitter"])
            Observer_dictonary = dict([(obj.name, [[item.Sensor, item.Property, item.Mode, item.Value, str([[counter.Sensor, counter.Property, counter.Mode, counter.Value] for counter in item.Counter])] for item in obj.Rules]) for obj in all_objects if obj.Type=="Observer"])

        if "Data.py" not in bpy.data.texts:
            bpy.ops.text.new()
            bpy.data.texts[-1].name = "Data.py"
        bpy.data.texts["Data.py"].clear()
        bpy.data.texts["Data.py"].write("Network="+str([scn.IP, scn.Port, scn.Connection_Attempts, scn.Name, scn.Max_Players, scn.Size_Buffer])+"\nTransmitters="+str(Transmitter_dictonary)+"\nObservers="+str(Observer_dictonary))



    
    return
    activeobject = bpy.context.scene.objects.active
    for object in all_objects:
        for cont in object.game.controllers:
            if cont.module in ["server.main", "client.main"]:
                bpy.context.scene.objects.active = object
                for prop in enumerate(object.game.properties):
                    if prop[1].name == "Multiplayer Options":
                        bpy.ops.object.game_property_remove(index=prop[0])
                bpy.ops.object.game_property_new(name="Multiplayer Options", type="STRING")
                object.game.properties[-1].value=str([scn.IP, scn.Port, scn.Connection_Attempts, scn.Name, scn.Max_Players, scn.Size_Buffer, Transmitter_dictonary, Observer_dictonary])
    bpy.context.scene.objects.active = activeobject        

network_type = [
    ("SERVER", "Server", "The Blend functions as Server", "URL", 1),
    ("CLIENT", "Client", "The Blend functions as Client ", "LOGIC", 2),
    ("NONE", "None", "The Blend has no network qualities", 3)]
type_type = [
    ("Transmitter", "Transmitter", "The object will be visualized (at the other clients and at the Server) by a Representative.", "PARTICLES", 1),
    ("Observer", "Observer", "Makes it possible to set up Rules and Counter-Rules. The ‘Observer’ Type may only be applied to a Representative.", "HIDE_OFF", 2),
    ("NONE", "None", "The Object will not be influence by the network and neither influence it", 3)]
Sending_type = [
        ("CLIENT", "Client", "The Client sends the Transmissions", 1),
        ("SERVER", "Server", "The Server sends the Transmissions", 2)]

bpy.types.Object.Type = bpy.props.EnumProperty(name="Type", items=type_type, default="NONE", update=Update_GameProperty)
bpy.types.Object.Representative = bpy.props.StringProperty(name="Representative", default="", description="Represents a Transmitter by being created when the Transmitter gets created and being deleted when the Transmitter gets deleted", update=Update_GameProperty)
bpy.types.Object.Sender = bpy.props.EnumProperty(name="Sender", items=Sending_type, default="CLIENT", description="Defines which part of the network will send the Transmissions and thereby determinate the value of the Attribute", update=Update_GameProperty)
bpy.types.Object.Lifetime = bpy.props.IntProperty(name="Lifetime", default=0, min=0, description="The amount of logic ticks the Transmitter(at the Server) will live, 0 = unlimted", update=Update_GameProperty)

bpy.types.Scene.IP = bpy.props.StringProperty(name = "IP", description="The IP used for establishing a connection to the server", update=Update_GameProperty)
bpy.types.Scene.Port = bpy.props.IntProperty(name = "Port", min=0, description="The Port used for establishing a connection to the server", update=Update_GameProperty) 
bpy.types.Scene.Network_Type = bpy.props.EnumProperty(name="Network Type", items=network_type, default="NONE", update=Update_GameProperty)
bpy.types.Scene.Name = bpy.props.StringProperty(name = "Name", description="The Client's name. It will be saved in a \"Name\" property of the representative", update=Update_GameProperty)
bpy.types.Scene.Connection_Attempts = bpy.props.IntProperty(name = "Connection Attempts", min=1, description="The amount of attempt made to establish a connection", update=Update_GameProperty)
bpy.types.Scene.Size_Buffer = bpy.props.IntProperty(name = "Size Buffer", min=1, max=65535,default=2048, description="The maximum amount of data which can be received at once", update=Update_GameProperty)
bpy.types.Scene.Max_Players = bpy.props.IntProperty(name = "Max Players", min=0, description="The maximum amount of players allowed on the server", update=Update_GameProperty)
bpy.types.Scene.Socket = None

class Transmission(bpy.types.PropertyGroup):

    transmission_type = [
        ("worldPosition", "Position", "The global Position of the object", 1),
        ("worldOrientation", "Rotation", "The global Rotation of the object", 2),
        ("worldScale", "Scale", "The global Scale of the object", 3),
        ("color", "Colour", "The colour of the object", 4),
        ("linearVelocity", "Velocity", "The global Velocity of the object", 5),
        ("CUSTOM", "Custom", "Customly choosen a KX_GameObject attribute or a normal property", 6)
        ]
    
    Type = bpy.props.EnumProperty(name="Transmission Type", items=transmission_type, default="worldPosition", update=Update_GameProperty)
      
    Decimals = bpy.props.IntProperty(name="Decimals", min=0, max=10, description="Sets the number of decimals of the Transmissions", update=Update_GameProperty)
    Skip = bpy.props.IntProperty(name="Skip", min=-1, description="Amount of logic ticks that has to be passed, before sending the Transmission(-1 = will only be sent once)", update=Update_GameProperty)
    ChangeRequired = bpy.props.BoolProperty(name="Change Required", description="Sets if the value of the attribute must change before it is sent", update=Update_GameProperty) 
    Custom = bpy.props.StringProperty(name="Custom", update=Update_GameProperty)

class CounterRule(bpy.types.PropertyGroup):
    mode_type = [
    ("ASSIGN", "Assign", "Assign the value", 1),
    ("ADD", "Add", "Add to the current value", 2)]
    Sensor = bpy.props.StringProperty(name="Sensor", description="Triggers the Counter Rule, has to be connected to a controller, is a sensor of the Transmitter", update=Update_GameProperty)
    Mode = bpy.props.EnumProperty(name="Mode", items=mode_type, default="ASSIGN", description="How to apply the value to the property", update=Update_GameProperty)
    Property = bpy.props.StringProperty(name="Property", default="", description="The Property that will be changed on this object", update=Update_GameProperty)
    Value = bpy.props.StringProperty(name="Value", default="", description="The value to operate with, properties would be associated with the Transmitter", update=Update_GameProperty)
    
class Rule(bpy.types.PropertyGroup):
    mode_type = [
    ("ASSIGN", "Assign", "Assign the value", 1),
    ("ADD", "Add", "Add to the current value", 2)]
    Sensor = bpy.props.StringProperty(name="Sensor", description="Triggers the Rule, has to be connected to a controller", update=Update_GameProperty)
    Mode = bpy.props.EnumProperty(name="Mode", items=mode_type, default="ASSIGN", description="How to apply the value to the property", update=Update_GameProperty)
    Property = bpy.props.StringProperty(name="Property", default="", description="The Property that will be changed at the Transmitter", update=Update_GameProperty)
    Value = bpy.props.StringProperty(name="Value", default="", description="The value to operate with, properties would be associated with this object", update=Update_GameProperty)
    Counter = bpy.props.CollectionProperty(type=CounterRule)
    Counter_Active = bpy.props.IntProperty()
    
class LOGIC_PT_multiplayer_panel(bpy.types.Panel):
    bl_space_type = "LOGIC_EDITOR"
    bl_region_type = "UI"
    bl_category = "Logic"
    bl_label = "Multiplayer Addon"

    def draw(self, context):

        layout = self.layout
        obj = context.object
        scn = context.scene

        if scn.Network_Type != "NONE":
            OSbox = layout.box()
            OSbox.label(text="Object Settings", icon="OBJECT_DATA")
            OSbox.prop(obj, "Type")
            if obj.Type == "Transmitter":
                OSbox.prop(obj, "Representative",icon="ORIENTATION_GIMBAL")
                if scn.Network_Type != "SERVER":
                    OSbox.prop(obj, "Sender")
                    if obj.Sender == "SERVER":
                        OSbox.prop(obj, "Lifetime")
                OSbox.operator("object.transmission_add", icon="PLUS", text="Add Transmission")
                OSbox.template_list("TRANSMISSION_UL_transmission_list", "", obj, "Transmissions", obj, "Transmissions_Active")
                if len(obj.Transmissions) != 0:
                    item = obj.Transmissions[obj.Transmissions_Active]
                    box = OSbox.box()
                    box.label("Transmission Options")
                    box.prop(item, "Decimals")
                    box.prop(item, "Skip")
                    box.prop(item, "ChangeRequired")
                    if item.Type == "CUSTOM":
                        box.prop(item, "Custom")
            elif obj.Type == "Observer":
                OSbox.operator("object.rule_add", icon="PLUS", text="Add Rule")
                OSbox.template_list("RULE_UL_rule_list", "", obj, "Rules", obj, "Rules_Active")
                if len(obj.Rules) != 0:
                    item = obj.Rules[obj.Rules_Active]
                    Cbox = OSbox.box()
                    Cbox.label("Counter Rules:")
                    Cbox.template_list("COUNTER_RULE_UL_counter_rule_list", "", item, "Counter", item, "Counter_Active")
                
        box = layout.box()
        box.label(text="Network", icon="COMMUNITY")
        box.prop(scn, 'Network_Type')
        row = box.row(align=True)
        if scn.Network_Type != "NONE":
            if scn.Network_Type == "SERVER":
                row.prop(scn, 'Port')
                box.prop(scn, 'Max_Players')
            elif scn.Network_Type == "CLIENT":
                row.prop(scn, 'IP')
                row.prop(scn, 'Port')
                box.prop(scn, 'Name')
                box.prop(scn, "Connection_Attempts")
            box.prop(scn, "Size_Buffer")
           
class TRANSMISSION_UL_transmission_list(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(icon="DRIVER")
        layout.prop(item, "Type")
        layout.operator("object.transmission_remove", icon="PANEL_CLOSE", text="").index = index

class RULE_UL_rule_list(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(icon="FILE_TEXT")
        layout.prop_search(item, "Sensor", context.object.game, "sensors")
        layout.prop(item, "Property")
        layout.prop(item, "Mode")
        layout.prop(item, "Value")
        layout.operator("object.counter_rule_add", icon="PLUS", text="Add Counter Rule").index = index
        layout.operator("object.rule_remove", icon="PANEL_CLOSE", text="").index = index

class COUNTER_RULE_UL_counter_rule_list(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "Sensor")
        layout.prop(item, "Property")
        layout.prop(item, "Mode")
        layout.prop(item, "Value")
        layout.operator("object.counter_rule_remove", icon="PANEL_CLOSE", text="").index = index

class OBJECT_OT_transmission_add(bpy.types.Operator):
    bl_idname = "object.transmission_add"
    bl_description = bl_label = "Add Transmission"

    def execute(self, context):
        context.object.Transmissions.add()
        Update_GameProperty(self, context)
        return {'FINISHED'}
    
class OBJECT_OT_transmission_remove(bpy.types.Operator):
    bl_idname = "object.transmission_remove"
    bl_description = bl_label = "Remove Transmission"
    index = bpy.props.IntProperty()
    
    def execute(self, context):
        context.object.Transmissions.remove(self.index)
        Update_GameProperty(self, context)
        return {'FINISHED'}

class OBJECT_OT_rule_add(bpy.types.Operator):
    bl_idname = "object.rule_add"
    bl_description = bl_label = "Add Rule"
    
    def execute(self, context):
        context.object.Rules.add()
        Update_GameProperty(self, context)
        return {'FINISHED'}
    
class OBJECT_OT_rule_remove(bpy.types.Operator):
    bl_idname = "object.rule_remove"
    bl_description = bl_label = "Remove Rule"
    index = bpy.props.IntProperty()
    
    def execute(self, context):
        context.object.Rules.remove(self.index)
        Update_GameProperty(self, context)
        return {'FINISHED'}

class OBJECT_OT_counter_rule_add(bpy.types.Operator):
    bl_idname = "object.counter_rule_add"
    bl_description = bl_label = "Add Counter Rule"
    index = bpy.props.IntProperty()

    def execute(self, context):
        context.object.Rules[self.index].Counter.add()
        Update_GameProperty(self, context)
        return {'FINISHED'}

class OBJECT_OT_counter_rule_remove(bpy.types.Operator):
    bl_idname = "object.counter_rule_remove"
    bl_description = bl_label = "Remove Counter Rule"
    index = bpy.props.IntProperty()
    
    def execute(self, context):
        item = context.object.Rules[context.object.Rules_Active]
        item.Counter.remove(self.index)
        Update_GameProperty(self, context)
        return {'FINISHED'}

@persistent
def check_socket(dummy):
    if bpy.types.Scene.Socket:
        if type(bpy.types.Scene.Socket) != list: # Client
            if bpy.types.Scene.Socket._closed == False:
                bpy.types.Scene.Socket.close()
        else: # Server
            bpy.types.Scene.Socket[0].close()
            for client in bpy.types.Scene.Socket[1]:
                client.socket.close()
@persistent
def add_scripts(dummy):
    if add_scripts in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(add_scripts)
    for script in ["client.py", "server.py", "Readme.md"]:
        if script not in bpy.data.texts:
            path = os.path.dirname(os.path.abspath(__file__))+"\\"+script
            file = open(path)
            bpy.ops.text.new()
            bpy.data.texts[-1].name = script
            bpy.data.texts[script].write(file.read())
            file.close()

classes = (
    Transmission,
    CounterRule,
    Rule,
    LOGIC_PT_multiplayer_panel,
    TRANSMISSION_UL_transmission_list,
    RULE_UL_rule_list,
    COUNTER_RULE_UL_counter_rule_list,
    OBJECT_OT_transmission_add,
    OBJECT_OT_transmission_remove,
    OBJECT_OT_rule_add,
    OBJECT_OT_rule_remove,
    OBJECT_OT_counter_rule_add,
    OBJECT_OT_counter_rule_remove,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    
    bpy.types.Object.Transmissions = bpy.props.CollectionProperty(type=Transmission)
    bpy.types.Object.Rules = bpy.props.CollectionProperty(type=Rule)
    bpy.types.Object.Transmissions_Active = bpy.props.IntProperty()
    bpy.types.Object.Rules_Active = bpy.props.IntProperty()
    
    bpy.app.handlers.game_post.append(check_socket)
    bpy.app.handlers.game_pre.append(Update_GameProperty)
    bpy.app.handlers.depsgraph_update_post.append(add_scripts)
    bpy.app.handlers.load_post.append(add_scripts)
    
def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    bpy.app.handlers.game_post.remove(check_socket)
    bpy.app.handlers.game_pre.remove(Update_GameProperty)
    bpy.app.handlers.load_post.remove(add_scripts)
        
if __name__ == "__main__":
    register()




