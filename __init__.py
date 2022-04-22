bl_info = {
    "name": "Easy Online",
    "description": "An addon which makes it possible to create multiplayer games.",
    "author": "BleGaDev, Jorge Bernal (lordloki)",
    "version": (2, 0, 0),
    "blender": (2, 80, 0),
    "location": "LOGIC_EDITOR > UI > MULTIPLAYER",
    "category": "Game Engine",
}

import bpy
import os
import pickle
import importlib
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       BoolVectorProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       CollectionProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       UIList,
                       )
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.app.handlers import persistent
import textwrap 


def f(x, real=0):
    print(10*"#")
    if real == 1:
        print(x)
        if hasattr(x,"bl_rna") and hasattr(x.bl_rna, "description"):
            print(x.bl_rna.description)
    elif real == 0:
        print(*dir(x), sep="\n")
    print(10*"#")
    
def ShowMessageBox(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)
    
def CreateNewText(name):
    'creates a new script in the text editor with the given name. Returns the instance'
    bpy.ops.text.new()    
    probe = "Text"
    last = "Text"
    i = 0
    while probe in bpy.data.texts:
        last = probe
        i += 1
        probe = "Text.{:03}".format(i)
    script = bpy.data.texts[last] # the newly added script
    script.name = name
    return script

def executeModuleFct(module, fct):
    exec("import "+module)
    importlib.reload(eval(module))
    return eval(module+"."+fct+"()")

def getOrderedName(name, names):
    endname = name
    i = 1
    while endname in names:
        endname = name+".{:03}".format(i)
        i += 1
    return endname

Addon_Scripts = ["EO_client.py", "EO_DATA.py", "EO_server.py", "EO_config.py", "EO_network.py", "EO_script_template.py", "EO_damage.py", "EO_file.py", "Readme.md"]
@persistent
def updateScripts(dummy):
    'checks if certain script are in the .blend, and adds them if they are not there. Also updates EO_DATA'
    
    if updateScripts in bpy.app.handlers.depsgraph_update_post: # workaround to execute updateScripts after the addon is registered
        bpy.app.handlers.depsgraph_update_post.remove(updateScripts)
    
    for script_name in Addon_Scripts:
        if script_name not in bpy.data.texts:
            script = CreateNewText(script_name)
            path = os.path.dirname(os.path.abspath(__file__))+"\\"+script_name
            with open(path, "r") as file:
                script.write(file.read())
    
    data = bpy.data.texts["EO_DATA.py"]
    data.clear()
    data.write("#Don't edit this file! It's just a way to get data from bpy to bge and make it work in standalone too.\n")
    
    # write relevant data of all objects to EO_DATA.py
    datas = {"TRANSMITTER":{}, "AVATAR":{}}
    scripts = []
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if obj.eo.type == "NONE":
                continue
            
            obj_data = [obj.eo.script.name if (obj.eo.script != None) else None]
            if obj_data[0] and obj_data[0] not in scripts:
                scripts.append(obj_data[0])
            if obj.eo.type == "TRANSMITTER":
                obj_data += [obj.eo.avatar, obj.eo.global_object]
                ATTR = []
                for trans in obj.eo.trans_attrs:
                    if trans.type == "GAME_PROPERTY":
                        ATTR.append((trans.type, trans.Skip, trans.Change, trans.ServerOwned, trans.Reliable, trans.GameProp, trans.GameProp_TransferType == "OVERWRITE"))
                    elif trans.type == "OBJ_PROPERTY":
                        ATTR.append((trans.type, trans.Skip, trans.Change, trans.ServerOwned, trans.Reliable, trans.Custom))
                    else:
                        ATTR.append((trans.type, trans.Skip, trans.Change, trans.ServerOwned, trans.Reliable))
                obj_data.append(ATTR)
            elif obj.eo.type == "AVATAR":
                MSG = []
                for msg in obj.eo.avat_msg:
                    MSG.append((msg.type, msg.prop))
                if obj.eo.script:
                    for trigger_prop in executeModuleFct(obj.eo.script.name[:-3], "getAvatarTriggerProperties"):
                        MSG.append(("SCRIPT", trigger_prop))
                obj_data.append(MSG)
            datas[obj.eo.type][obj.name] = obj_data
    datas["scripts"] = scripts
    data.write("data="+str(datas))
    
def initNetworkSetup(obj, state, scripts):
    sensors = obj.game.sensors
    controllers = obj.game.controllers
    
    bpy.ops.logic.controller_add(type="PYTHON", object=obj.name)    
    cont = controllers[-1]
    cont.states = state
    cont.mode = "MODULE"
    cont.module = scripts[0]
    
    bpy.ops.logic.sensor_add(type="ALWAYS", object=obj.name)
    sens = sensors[-1]
    sens.use_tap = True
    sens.link(cont)
    sens.use_pulse_true_level = True
    
    bpy.ops.logic.controller_add(type="PYTHON", object=obj.name)    
    cont = controllers[-1]
    cont.states = state
    cont.mode = "MODULE"
    cont.module = scripts[1]
    
    bpy.ops.logic.sensor_add(type="KEYBOARD", object=obj.name)
    sens = sensors[-1]
    sens.use_tap = True
    sens.key = "ESC"
    sens.link(cont)

def hasScript(cont, script): # checks if the controller uses this script(can be list of scripts)
    if type(script) == list:
        return cont.type == "PYTHON" and cont.mode == "MODULE" and cont.module in script    
    return cont.type == "PYTHON" and cont.mode == "MODULE" and cont.module == script

def removeController(obj, cont): # removes controller and all sensors
    sensors = obj.game.sensors
    for sens in sensors:
        if cont.name in sens.controllers:
            bpy.ops.logic.sensor_remove(sensor=sens.name, object=obj.name) # remove all sensors
    bpy.ops.logic.controller_remove(controller=cont.name, object=obj.name) # remove cont
    
def removeControllerWith(obj, script): # removes all controllers with this script(script can also be a lists os possible scripts)
    controllers = obj.game.controllers
    for cont in controllers:
        if hasScript(cont, script):
            removeController(obj, cont)
            
def manageInitScript(obj, state, scriptnames, delete, addprop, delprop):
    """adds an always sensors, executing scriptname once. Includes state as initial state"""
    sensors = obj.game.sensors
    controllers = obj.game.controllers
    
    removeControllerWith(obj, delete)
    
    for cont in controllers:
        if cont.type == "PYTHON" and cont.mode == "MODULE" and cont.module in delete: # right controller
            for sens in sensors:
                if cont.name in sens.controllers:
                    bpy.ops.logic.sensor_remove(sensor=sens.name, object=obj.name) # remove all sensors
            bpy.ops.logic.controller_remove(controller=cont.name, object=obj.name) 
            
    for type, scriptname in enumerate(scriptnames):
        addController = True
        for cont in controllers:
            if hasScript(cont, scriptname):
                addController = False
                for sens in sensors:
                    if cont.name in sens.controllers:
                        bpy.ops.logic.sensor_remove(sensor=sens.name, object=obj.name) # remove all sensors
                break
        if addController:
            bpy.ops.logic.controller_add(type="PYTHON", object=obj.name)    
            cont = controllers[-1]
            cont.states = state
            cont.mode = "MODULE"
            cont.module = scriptname
        
        if type == 0:
            bpy.ops.logic.sensor_add(type="ALWAYS", object=obj.name)
        else:
            bpy.ops.logic.sensor_add(type="PROPERTY", object=obj.name)
            sensors[-1].property = "EO_remove"
            sensors[-1].value = "True"
        sens = sensors[-1]
        sens.use_tap = True
        sens.link(cont)
        
        
    for targetprop in delprop:
        for indx in range(len(obj.game.properties)):
            prop = obj.game.properties[indx]
            if prop.name == targetprop:
                bpy.ops.object.game_property_remove(index=indx)
                break
    if addprop:
        if addprop[0] not in obj.game.properties:
            bpy.ops.object.game_property_new(name=addprop[0], type=addprop[1])   
            if addprop[1] == "STRING": # for EO_NAME in avatar
                obj.game.properties[addprop[0]].show_debug = True
    
    obj.game.states_initial[state-1] = True
    
def addToController(obj, state, script, propertyname): # add cont executing script, and a prop changed sensor with propertyname linked to it
    controllers = obj.game.controllers
    sensors = obj.game.sensors
    addController = True
    
    if propertyname not in obj.game.properties:
        bpy.ops.object.game_property_new(name=propertyname, type="BOOL")
        
    for cont in controllers:# maybe controller allready there?
        if hasScript(cont, script):
            addController = False
            break
        
    if addController:
        bpy.ops.logic.controller_add(type="PYTHON", object=obj.name)    
        cont = controllers[-1]
        cont.states = state
        cont.mode = "MODULE"
        cont.module = script
    
    for sen in sensors: # maybe sensors allready there?
        if sen.type == "PROPERTY" and sen.property == propertyname and cont.name in sen.controllers and sen.evaluation_type=="PROPCHANGED":
            return
        
    bpy.ops.logic.sensor_add(type="PROPERTY", object=obj.name)
    sen = sensors[-1]
    sen.property = propertyname
    sen.evaluation_type = "PROPCHANGED"
    sen.use_tap = True
    sen.link(cont)
    
    obj.game.states_initial[state-1] = True
    
def msgControllerCleanup(obj, state, script): # only for avatar; remove all sensors linked to controller with script of object, where the properties are unused
    controllers = obj.game.controllers
    cont = None
    for cont_ in controllers:
        if hasScript(cont_, script):
            cont = cont_
            break
    if cont:
        props = [item.prop for item in obj.eo.avat_msg] # delte all prop sensors connected to cont without one of these props
        if obj.eo.script:
            props += executeModuleFct(obj.eo.script.name[:-3], "getAvatarTriggerProperties")
        for sen in obj.game.sensors:
            if cont.name in sen.controllers and sen.type == "PROPERTY" and sen.property not in props:
                bpy.ops.logic.sensor_remove(sensor=sen.name, object=obj.name)


class FEEDBACK_UL_List(UIList):

    def filter_items(self,context, data, propname):
        props = getattr(data, propname)
        filtered = [self.bitflag_filter_item  if prop.name != "EO_sendmessage" else 0 for prop in props]
        return filtered, []
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = context.object
        icons = ["CHECKBOX_DEHLT", "CHECKBOX_HLT"]
        
        is_feedback = active_data.is_feedback(item.name)
             
        layout.label(item.name+str(), icon=icons[is_feedback])
      
class FeedbackItem(PropertyGroup):
    name : StringProperty()
    is_feedback : BoolProperty()
    
class PropertyMessage(PropertyGroup):
    msg_types = [
    ("OVERWRITE", "Overwrite", "will overwrite the existing value of the property(at the transmitter)", 0),
    ("CHANGE", "Add Change", "when a change happens to the property(at the avatar) the property of the transmitter will change by that amount. \n\nFor example If the property goes from 5 to 30, then the property of the transmitter will go from x to x+25. \n\nThis method is useful since the 'overwrite' method can be problematic - if multiple clients want to assign their (local) value of their property to the transmitter, then in the end only 1 client will actually have overwritten the value at the transmitter. 'Add Change' is a compromise, so that each client has some influence on the value", 1)]
    #"used for scripts, to signal that some event just happend.\n\nFor exmaple a property called 'got_hit' to signal that you shot the avatar of someone"
    def release(self, context): # any property can max be used in 1 msg, so any msg allready using this prop will release it
        "get's called when PropertyMessage is created, deleted or changed"
        if self.isPartOfTemplate:
            return
        obj = context.object
        if self.prop == "":
            msgControllerCleanup(obj, 17, "EO_config.avatar_script")
            return
        for item in obj.eo.avat_msg:
            if item != self and item.prop == self.prop:
                item.prop = ""
                msgControllerCleanup(obj, 17, "EO_config.avatar_script")
                return
        addToController(obj, 17, "EO_config.avatar_script", self.prop) # propname hasn't been seen before, so add it
        msgControllerCleanup(obj, 17, "EO_config.avatar_script")
    prop : StringProperty(update=release, description="this property will be updated at the transmitter")
    type : EnumProperty(items = msg_types)
    prop_type : StringProperty()
    prop_val : StringProperty()
    isPartOfTemplate : BoolProperty()
    
    
    def apply(self, obj, data):# propname nettype value proptype
        "obj can be None, in that case it's a template not object_data of object"
        self.prop = data[0]
        self.type = data[1]
        self.prop_val = data[2]
        self.prop_type = data[3]
        if obj:
            if self.prop not in obj.game.properties:
                bpy.ops.object.game_property_new(type=data[3], name=self.prop)
            obj.game.properties[self.prop].type = data[3]
            obj.game.properties[self.prop].value = eval(data[2]) if data[3] != "STRING" else data[2]
        
    def serialize(self, obj, collectKXData=True):
        props = obj.game.properties
        if collectKXData:
            #if self.prop not in props:
            #    ShowMessageBox(obj.name+" is missing property '"+self.prop+"'", "Property not found", icon="ERROR")
            #else:
            self.prop_type = props[self.prop].type
            self.prop_val = str(props[self.prop].value)
        return (self.prop, self.type, self.prop_val, self.prop_type)
    
class PROPERTYMSG_UL_List(UIList):
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop_search(item, "prop", context.object.game, "properties", text="")
        row.prop(item, "type", text="")
        row.operator("eo.remove_msg", text="", icon="PANEL_CLOSE").index = index
         
class TRANSMISSION_UL_List(UIList):
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        
        row.label(icon="MOD_PARTICLE_INSTANCE")
        row.prop(item, "name", text="", emboss=False)
        #row.operator("eo.remove_trans", text="", icon="PANEL_CLOSE").index = index
        #row.prop(item, "type",text="")
        
class TransmissionAttribute(PropertyGroup):
    
    attr_types = [
    ("worldPosition", "Position", "Global position of the object", 0),
    ("worldOrientation", "Rotation", "Global rotation of the object", 1),
    ("GAME_PROPERTY", "Game Property", "Normal game property", 2),
    ("OBJ_PROPERTY", "Object Attribute", "any property of the KX_GameObject", 3)]
    type : EnumProperty(items = attr_types)
    Skip : IntProperty(min=-1, description = "how many ticks to skip before sending data")
    Change : BoolProperty(description="additionally(in addition to skip) send data when the value changes")
    name : StringProperty(default="Data Transmission")
    Custom : StringProperty(description="""Blender's game objects are called KX_GameObject and here's a list of (some) attributes of that class:\n\nangularDamping
angularVelocity
angularVelocityMax
angularVelocityMin
collisionGroup
collisionMask
color
currentLodLevel
debug
debugRecursive
invalid
isSuspendDynamics
linVelocityMax
linVelocityMin
linearDamping
linearVelocity
localAngularVelocity
localInertia
localLinearVelocity
localOrientation
localPosition
localScale
localTransform
mass
name
orientation
position
record_animation
scaling
state
timeOffset
visible
worldAngularVelocity
worldLinearVelocity
worldOrientation
worldPosition
worldScale
worldTransform\n\nWrite any attribute of the list into this field""")
    GameProp : StringProperty(description="this property will be updated at the avatar")
    GameProp_type : StringProperty()
    GameProp_value : StringProperty()
    transfer_types = [("OVERWRITE", "Overwrite", "will overwrite the existing value of the property(at the avatar)", 0),
    ("CHANGE", "Add Change", "when a change happens to the property(here at the transmitter) the property of the avatar will change by that amount. \n\nFor example If the property goes from 5 to 30, then the property of the avatar will go from x to x+25. \n\nThis method is useful since the avatar can modify its property without it being reset by any transmission from the transmitter", 1)]
    GameProp_TransferType : EnumProperty(items = transfer_types)
    ServerOwned : BoolProperty(description="At the client-side, the transmissions of a transmitter have ownership. That is either the client or the server controlls the data. For example should the position and rotation of your player model be controlled by you, but you maybe want the server to control your health to prevent cheating.\n\nTransmitters spawned in the server blend will always have all their transmissions be server-controlled")
    Reliable : BoolProperty(description="Unreliable Transmission may not arrive because they get lost, which means the avatar won't receive your data. But Reliable Transmission on the other hand take longer to send.\n\nUse Reliable for events where you absolutely need it to arive, like pressing 'e' to open a door or shooting a weapon and use unrealiable for data you send constanly and want to update quickly like position or rotation")
    
    
    def apply(self, obj, data):
        "obj can be None, in that case it's a template not object_data of object"
        self.type = data[0]
        self.Skip = data[1]
        self.Change = data[2]
        self.Custom = data[3]
        self.ServerOwned = data[7]
        self.Reliable = data[8]
        self.GameProp_TransferType = data[9]
        self.name = data[10]
        if self.type == "GAME_PROPERTY" and data[4] != "":
            self.GameProp = data[4]
            self.GameProp_type = data[5]
            self.GameProp_value = data[6]
            if obj:
                if data[4] not in obj.game.properties:
                    bpy.ops.object.game_property_new(type=data[5], name=data[4])
                obj.game.properties[data[4]].type = data[5]
                obj.game.properties[data[4]].value = eval(data[6]) if data[5] != "STRING" else data[6]
        
    def serialize(self, obj, collectKXData=True):
        if collectKXData and self.type == "GAME_PROPERTY" and self.GameProp != "":
            if self.GameProp not in obj.game.properties:
                ShowMessageBox(obj.name+" is missing property '"+self.GameProp+"'", "Property not found", icon="ERROR")
            prop = obj.game.properties[self.GameProp]
            self.GameProp_type = prop.type
            self.GameProp_value = str(prop.value)
        return (self.type,self.Skip, self.Change, self.Custom, self.GameProp, self.GameProp_type, self.GameProp_value, self.ServerOwned, self.Reliable, self.GameProp_TransferType, self.name)

        

def handle_feedback_properties(self, context):
    "toggle the feedback boolean of the clicked property & check for dead properties"
    obj = context.object
    i = obj.eo.feedback_index
    obj.eo.toggle_feedback(obj.game.properties[i].name)
    
    props = obj.eo.feedback_properties
    toberemoved = []
    for index, prop in enumerate(props):
        #check if property got deleted from the object
        if prop.name not in obj.game.properties:
            toberemoved.append(index)
    #standard method of removing from something you are iterating over
    offset = 0
    for index in toberemoved:
        props.remove(index-offset)
        offset+=1

def add_template(context, template_data, loading=False):
    scn_eo = context.scene.eo
    behavs = scn_eo.network_behaviours
    item = behavs.add()
    item.name = getOrderedName(template_data["name"], behavs)
    item.description = template_data["description"]
    item.apply(None, template_data, loading)
    

class ApplyTemplateOperator(bpy.types.Operator):
    bl_idname = "eo.apply_template"
    bl_label = "Apply Template"
    bl_description = "Replace the current network settings of this object with the ones from template"
    
    def execute(self, context):
        obj = context.object
        scn = context.scene
        for template in scn.eo.network_behaviours:
            if template.name == scn.eo.net_behaviour:
                obj.eo.apply(obj, template.serialize(obj, collectKXData=False))
                break
        return {'FINISHED'}
    
class SaveOperator(bpy.types.Operator):
    bl_idname = "eo.save_template"
    bl_label = "Save Settings as Template"
    bl_description ="makes current settings into a template"
    
    eo_name : StringProperty(default="My Template", name="name")
    eo_description : StringProperty(default="My awesome template", name="description")
    export : BoolProperty(default=False) # wheter to export the template afterwards
    
    def execute(self, context):
        obj = context.object
        obj.eo.name = self.eo_name
        obj.eo.description = self.eo_description
        add_template(context, obj.eo.serialize(obj))
        
        if self.export:
            bpy.ops.eo.export_template("INVOKE_DEFAULT")
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
class RemoveNetBehaviourOperator(Operator):
    bl_idname = "eo.remove_net"
    bl_label = "Remove network behaviour"
    bl_description = "Remove template"
    
    def execute(self, context):
        selected_name = context.scene.eo.net_behaviour
        behavs = context.scene.eo.network_behaviours
        for id, x in enumerate(behavs):
            if x.name == selected_name:
                behavs.remove(id)
                break
        return {'FINISHED'}
    
class ExportOperator(Operator, ExportHelper):

    bl_idname = "eo.export_template"
    bl_label = "Export template"
    bl_description = "exporting"
    
    filename_ext = ".eot"

    def execute(self, context):
        obj = context.object
        print("export:", obj.eo)
        with open(self.filepath, "wb") as file:
            pickle.dump(obj.eo.serialize(obj), file)
        return {'FINISHED'}
    
class OpenOperator(Operator, ImportHelper):

    bl_idname = "eo.open_template"
    bl_label = "Open Behaviour"
    bl_description = "Load a new template from file"
    
    filter_glob : StringProperty(
        default="*.eot",
        options={'HIDDEN'}
    )

    def execute(self, context):
        
        with open(self.filepath, "rb") as file:
            data = pickle.load(file)
        add_template(context, data, True)
        return {'FINISHED'}
    
class AddTransOperator(Operator):

    bl_idname = "eo.add_trans"
    bl_label = "Add Data Tansmission"
    bl_description = "Adds a new Data Transmission. Each Data Transmission transmits one thing, like position or health."
    
    def execute(self, context):
        obj = context.object
        datatr = obj.eo.trans_attrs.add()
        datatr.name = getOrderedName("Data Transmission", obj.eo.trans_attrs)
        return {'FINISHED'}
    
class RemoveTransOperator(Operator):

    bl_idname = "eo.remove_trans"
    bl_label = "Remove Transmission"
    bl_description = "Remove Data Transmission"
    
    index : IntProperty()
    
    def execute(self, context):
        obj = context.object
        obj.eo.trans_attrs.remove(self.index)
        obj.eo.trans_attr_index = -1
        return {'FINISHED'}
    
class AddMsgOperator(Operator):

    bl_idname = "eo.add_msg"
    bl_label = "Add Feedback Transmission"
    bl_description = "Adds a new Feedback Transmission. Each Feedback Transmission transmits the value of a game property"
    
    def execute(self, context):
        obj = context.object
        obj.eo.avat_msg.add()
        return {'FINISHED'}
    
class RemoveMsgOperator(Operator):

    bl_idname = "eo.remove_msg"
    bl_label = "Remove Transmission"
    bl_description = "Remove attribute"
    
    index : IntProperty()
    
    def execute(self, context):
        obj = context.object
        obj.eo.avat_msg.remove(self.index)
        msgControllerCleanup(obj, 17, "EO_config.avatar_script")
        return {'FINISHED'}

class AddClientOperator(bpy.types.Operator):
    bl_idname = "eo.add_client"
    bl_label = "Add empty with client setup"
    bl_description = "Spawn an empty with client script setup. It will have important network related game properties like ip and port"
    
    def client_stuff(self, context):
        bpy.ops.object.empty_add(type='PLAIN_AXES')
        props = context.selected_objects[0].game.properties
        
        bpy.ops.object.game_property_new(name="EO_IP", type="STRING")
        props["EO_IP"].value = "127.0.0.1"
        bpy.ops.object.game_property_new(name="EO_PORT", type="INT")
        props["EO_PORT"].value = 8303
        bpy.ops.object.game_property_new(name="EO_NAME", type="STRING")
        props["EO_NAME"].value = "Player"
        bpy.ops.object.game_property_new(name="EO_TIMEOUT", type="INT")
        props["EO_TIMEOUT"].value = 10
        bpy.ops.object.game_property_new(name="EO_CONNECT_TIME", type="INT")
        props["EO_CONNECT_TIME"].value = 10
        bpy.ops.object.game_property_new(name="EO_connection", type="STRING")
        props["EO_connection"].value = "not connected"
        props["EO_connection"].show_debug = True
        bpy.ops.object.game_property_new(name="EO_PING", type="INT")
        props["EO_PING"].value = 81
        props["EO_PING"].show_debug = True
        bpy.ops.object.game_property_new(name="EO_PLAYERS", type="INT")
        props["EO_PLAYERS"].show_debug = True
        
    def execute(self, context):
        self.client_stuff(context)
                
        initNetworkSetup(context.selected_objects[0], 1, ["EO_client.main", "EO_client.disconnect_and_close"])
        return {'FINISHED'}
    
class AddServerOperator(bpy.types.Operator):
    bl_idname = "eo.add_server"
    bl_label = "Add empty with server setup"
    bl_description = "Spawn an empty with server script setup. It will have important network related game properties like port or timeout time"
    
    def execute(self, context):
        scn = context.scene
        bpy.ops.object.empty_add(type='PLAIN_AXES')
        obj = context.selected_objects[0]
        props = obj.game.properties
        
        bpy.ops.object.game_property_new(name="EO_PORT", type="INT")
        props["EO_PORT"].value = 8303
        bpy.ops.object.game_property_new(name="EO_NAME", type="STRING")
        props["EO_NAME"].value = "Server"
        bpy.ops.object.game_property_new(name="EO_TIMEOUT", type="INT")
        props["EO_TIMEOUT"].value = 10
        bpy.ops.object.game_property_new(name="EO_PINGS", type="STRING")
        props["EO_PINGS"].show_debug = True
        bpy.ops.object.game_property_new(name="EO_PLAYERS", type="INT")
        props["EO_PLAYERS"].show_debug = True
        
        initNetworkSetup(obj, 1, ["EO_server.main", "EO_server.shutdown_and_close"])
        return {'FINISHED'}
    
class AddMixedClientServerOperator(bpy.types.Operator):
    
    bl_idname = "eo.add_mixed"
    bl_label = "Add empty both client and server setup"
    bl_description = "Spawn empty with server setup in state 2 and client setup in state 3. Press 'S' to switch to state 2 and 'C' for state 3"
    
    def execute(self, context):
        AddClientOperator.client_stuff(None, context)
        obj = context.selected_objects[0]
        initNetworkSetup(obj, 2, ["EO_server.main", "EO_server.shutdown_and_close"])
        initNetworkSetup(obj, 3, ["EO_client.main", "EO_client.disconnect_and_close"])
        
        bpy.ops.object.game_property_new(name="EO_PINGS", type="STRING")
        obj.game.properties["EO_PINGS"].show_debug = True
            
        sensors = obj.game.sensors
        controllers = obj.game.controllers
        actuators = obj.game.actuators
        
        def transition(key, state):
            bpy.ops.logic.actuator_add(type="STATE", object=obj.name)    
            act = actuators[-1]
            act.states[state] = True
                    
            bpy.ops.logic.controller_add(type="LOGIC_AND", object=obj.name)    
            cont = controllers[-1]
            act.link(cont)
            
            if key == "S":
                bpy.ops.logic.actuator_add(type="PROPERTY", object=obj.name)     
                act = actuators[-1]
                act.property = "EO_NAME"
                act.value = "\"SERVER\""
                act.link(cont)

            bpy.ops.logic.sensor_add(type="KEYBOARD", object=obj.name)
            sens = sensors[-1]
            sens.use_tap = True
            sens.key = key
            sens.link(cont)
        transition("S", 1)
        transition("C", 2)
        return {'FINISHED'}

def net_behav_item_callback(self, context):
    global BLENDER_BUG_FIX # I have to assign the return of this function to some global variable, blender bug
    behavs = context.scene.eo.network_behaviours
    EnumList = []
    for id, behav in enumerate(behavs):
        EnumList.append((behav.name, behav.name, behav.name, id))
    #BLENDER_BUG_FIX = EnumList
    return EnumList
    
class EO_Object_Settings(PropertyGroup):
    # Never clicked means there is no FeedbackIteam, but it also means not checked
    # If it was clicked at some point there will be a FeedbackItem, but could be True or False
    feedback_properties : CollectionProperty(type=FeedbackItem)
    feedback_index : IntProperty(update=handle_feedback_properties)
    message_object : PointerProperty(type=bpy.types.Object, name="Message event", description="This object will be spawned at the receiving client.")
    
    trans_attr_index : IntProperty()
    trans_attrs : CollectionProperty(type=TransmissionAttribute)
    
    avat_msg : CollectionProperty(type=PropertyMessage)
    avat_msg_index : IntProperty()
    
    lastscript : StringProperty()
    def manageScript(self, context):
        if self.script:
            module = self.script.name[:-3]
            exec("import "+module)
            importlib.reload(eval(module))
            if self.type == "AVATAR":
                props =  eval(module+".getAvatarTriggerProperties()")
                Script = "EO_config.avatar_script"
            elif self.type == "TRANSMITTER":
                props =  eval(module+".getTransmitterTriggerProperties()")
                print(module+".getTransmitterTriggerProperties()")
                Script = "EO_config.transmitter_script" 
            for prop in props:
                addToController(context.object, 17, Script, prop)
            self.lastscript = Script
        elif self.lastscript:
            removeControllerWith(context.object, self.lastscript)
            
    script : PointerProperty(type=bpy.types.Text, name="script", update=manageScript, description="Note: the trigger properties will automatically be set to False")
    
    types = [
    ("TRANSMITTER", "Transmitter", "Transmitter update their attributes - for example position - at other clients/server", "MOD_PARTICLE_INSTANCE", 1),
    ("AVATAR", "Avatar", "Object used to represent a Transmitter. The avatar will adopt the data received from the transmitter. Must be in inactive layer.", "COMMUNITY", 2),
    ("NONE", "None", "The object has no network properties", 3)]
    def manageInits(self, context):
        obj = context.object
        addscript = {"TRANSMITTER":["EO_config.registerTransmitter", "EO_config.deleteTransmitter"], "AVATAR":[], "NONE":[]}
        delscripts = {"TRANSMITTER":["EO_config.avatar_script"], "AVATAR":["EO_config.transmitter_script", "EO_config.registerTransmitter", "EO_config.deleteTransmitter"], "NONE":["EO_config.registerTransmitter", "EO_config.deleteTransmitter", "EO_config.transmitter_script", "EO_config.avatar_script"]}
        addprop = {"TRANSMITTER":("EO_remove", "BOOL"), "AVATAR":("EO_NAME", "STRING"), "NONE":None}
        delprop = {"TRANSMITTER":["EO_NAME"], "AVATAR":["EO_remove"], "NONE":["EO_NAME", "EO_remove"]}
        t = obj.eo.type
        manageInitScript(obj, 17, addscript[t], delscripts[t], addprop[t], delprop[t])
        if t != "NONE":
            self.manageScript(context)
        if t == "AVATAR":
            for msg_prop in self.avat_msg:
                msg_prop.release(context)
                
                
    type : EnumProperty(name="Type", items=types, default="NONE", update=manageInits)
    
    name : StringProperty()
    description : StringProperty()
    
    avatar : StringProperty(name="Avatar", description="Other clients or the server need to spawn a blender game object to represent this transmitter - the avatar of the transmitter. So what is the name of that object?\n\nThis object must of course be in an inactive layer, because it will be spawned")
    global_object : BoolProperty(name = "global object", description="Use this if the object is allready in the active layer of both the server and client, stuff that doesn't spawn. \n\nOn the other hand will each new player joining the server lead to a new player model being spawned, so that shouldn't be a global object. \n\nGlobal objects don't need an avatar, because nothing will be spawned. \n\nThe Server has control over this object and the client will just apply attributes(like pos, rot...) coming from the server")
     
    def toggle_feedback(self, propname):
        for item in self.feedback_properties:
            if item.name == propname:
                item.is_feedback = 1-item.is_feedback
                return
        # no item in feedback_properties yet, add it
        item = self.feedback_properties.add()
        item.name = propname
        item.is_feedback = True
        
    def is_feedback(self, propname):
        item = self.feedback_properties.get(propname, None)
        if item:
            return item.is_feedback
        return False  
    
    def apply(self, obj, template_data, loading=False):
        "assign attributes values from a template"
        self.avatar = template_data["avatar"]
        self.type = template_data["type"]
        self.global_object = template_data["global"]

        if template_data["script"]:
            if template_data["script_name"] not in bpy.data.texts:
                scr = CreateNewText(template_data["script_name"])
                scr.write(template_data["script_text"])
            elif loading:
                ShowMessageBox("Imported template "+template_data["name"]+
                " contains a script called '"+template_data["script_name"]+"', but this name is allready taken. The current '"+template_data["script_name"]+"' will not be replaced, but will nevertheless be used as script by the template.",
                "Import Error", "ERROR")
            self.script = bpy.data.texts[template_data["script_name"]]
            
        self.trans_attrs.clear()
        for tran_data in template_data["Trans"]:
            item = self.trans_attrs.add()
            item.apply(obj, tran_data)
            
        self.avat_msg.clear()
        for avat_data in template_data["Avatar"]:
            item = self.avat_msg.add()
            item.isPartOfTemplate = (obj == None)
            item.apply(obj, avat_data)
        
        self.manageInits(bpy.context)
    
    def serialize(self, obj, collectKXData=True, withscript=True):
        "turns it into a dictionary, which is serializable"
        T = {
            "name":self.name,
            "description":self.description,
            "script":(self.script!=None),
            "avatar":self.avatar,
            "type":self.type,
            "global":self.global_object
        }
        
        if self.script!=None:
            if withscript:
                T["script_text"] = self.script.as_string()
            T["script_name"] = self.script.name
        
        T["Trans"] = [tran.serialize(obj, collectKXData) for tran in self.trans_attrs]
        T["Avatar"] = [msg.serialize(obj, collectKXData) for msg in self.avat_msg if msg.prop != ""]
        return T
    
class OBJECT_PT_EO_Panel(bpy.types.Panel):
    """Creates a Panel in the Logic properties window"""
    bl_label = "Easy Online"
    bl_idname = "OBJECT_PT_EO_Panel"
    bl_space_type = "LOGIC_EDITOR"
    bl_region_type = "UI"

    def draw(self, context): 
        layout = self.layout
        obj = context.object
        scn = context.scene
        
        if not obj:
            return
        
        box = layout.box()
        box.label(text="Setting Templates", icon = "GROUP_VERTEX")
        
        row = box.row(align=True)
        
        #row.prop(obj.eo, "net_behaviour", text="", icon="ERROR")
        #row.props_enum(obj.eo, "net_behaviour")
        row.prop(scn.eo, "net_behaviour", text="Template", icon="NODETREE")
        row.operator("eo.open_template",   text="", icon="FILE_FOLDER")
        row.operator("eo.remove_net",      text="", icon="PANEL_CLOSE")
        
        row1 = box.row(align=True)
        row1.operator("eo.apply_template")
        
        splitrow = box.row()
        col1 = splitrow.column()
        col2 = splitrow.column()
        row = col1.row(align=True)
        
        
        # write desc
        desc = ""
        cur_template = ""
        for a in scn.eo.network_behaviours:
            if a.name == scn.eo.net_behaviour:
                desc = a.description
                cur_template = "'"+a.name+"' template:"
                break
        wrapp = textwrap.TextWrapper(width=50) #50 = maximum length       
        col2.label(text = cur_template)
        for text in wrapp.wrap(text=desc): 
            row = col2.row(align = True)
            row.alignment = 'EXPAND'
            row.label(text = text)
        layout.separator()
        
        box = layout.box()
        box.label(text = "Settings", icon="SETTINGS")
        box.prop(obj.eo, "type")
        if obj.eo.type != "NONE":
        
            box.prop(obj.eo, "script")
            #box.prop(obj.eo, "is_transmitter", icon="DRIVER")
            
            if obj.eo.type == "TRANSMITTER":
                box.label(text = "Transmission Settings", icon="TOOL_SETTINGS")
                rep = box.row()
                rep.prop(obj.eo, "avatar", icon="COMMUNITY")
                rep.enabled = not obj.eo.global_object
                box.prop(obj.eo, "global_object")
                
                box.separator()
                box.operator("eo.add_trans", icon="PLUS")
                row = box.row()
                col1 = row.column()
                col2 = row.column()
                col1.template_list("TRANSMISSION_UL_List", "", obj.eo, "trans_attrs", obj.eo, "trans_attr_index")
                
                # Transmission Options  
                if obj.eo.trans_attrs:
                    if obj.eo.trans_attr_index != -1:
                        item = obj.eo.trans_attrs[obj.eo.trans_attr_index]
                        #col2.prop(item, "name", text="")
                        col2.prop(item, "type", text="Data")
                        col2.prop(item, "Skip")
                        col2.prop(item, "Change")
                        col2.prop(item, "ServerOwned", text="server-controlled")
                        col2.prop(item, "Reliable")
                        if item.type == "GAME_PROPERTY":
                            col2.prop_search(item, "GameProp", obj.game, "properties", text="property")
                            col2.prop(item, "GameProp_TransferType",text="mode")
                        elif item.type == "OBJ_PROPERTY":
                            col2.prop(item, "Custom", text="kx property")
                        col2.operator("eo.remove_trans", text="Delete", icon="PANEL_CLOSE").index = obj.eo.trans_attr_index
            elif obj.eo.type == "AVATAR":
                box.label(text = "Avatar Settings", icon="TOOL_SETTINGS")
                box.operator("eo.add_msg", icon="PLUS")
                box.template_list("PROPERTYMSG_UL_List", "", obj.eo, "avat_msg", obj.eo, "avat_msg_index")

            box.operator("eo.save_template", icon="CHECKMARK")

        """
        layout.separator()
        
        box = layout.box()
        box.label("Communication Settings", icon="TOOL_SETTINGS")
        box.prop(obj.eo, "message_object")
        box.label("Direct Message Properties:")
        box.template_list("FEEDBACK_UL_List", "", obj.game, "properties", obj.eo, "feedback_index")
        """
        
class EO_Scene_Settings(PropertyGroup):
    network_behaviours : CollectionProperty(type=EO_Object_Settings)
    net_behaviour : EnumProperty(items=net_behav_item_callback)
     
class OBJECT_PT_EO_SCENE_Panel(bpy.types.Panel):
    """Creates a Panel in the Logic properties window"""
    bl_label = "Easy Online"
    bl_idname = "OBJECT_PT_EO_SCENE_Panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context): 
        layout = self.layout
        obj = context.object
        scn = context.scene
        
        layout.operator("eo.add_client")
        layout.operator("eo.add_server")
        layout.operator("eo.add_mixed")
        
classes = (
    TransmissionAttribute,
    PropertyMessage,
    OpenOperator,
    RemoveNetBehaviourOperator,
    ApplyTemplateOperator,
    SaveOperator,
    ExportOperator,
    FeedbackItem,
    AddTransOperator,
    RemoveTransOperator,
    AddClientOperator,
    AddServerOperator,
    AddMixedClientServerOperator,
    AddMsgOperator,
    RemoveMsgOperator,
    FEEDBACK_UL_List,
    TRANSMISSION_UL_List,
    PROPERTYMSG_UL_List,
    EO_Object_Settings,
    OBJECT_PT_EO_Panel,
    OBJECT_PT_EO_SCENE_Panel,
    EO_Scene_Settings,
)


#bpy.context.blend_data.eo[0].add()
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.eo = PointerProperty(type=EO_Object_Settings)
    bpy.types.Scene.eo = PointerProperty(type=EO_Scene_Settings)
    
    bpy.app.handlers.game_post.append(bpy_shutdown_network)
    for handlers in [bpy.app.handlers.load_post, bpy.app.handlers.save_pre, bpy.app.handlers.game_pre, bpy.app.handlers.depsgraph_update_post]:
        handlers.append(updateScripts)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Object.eo
    del bpy.types.Scene.eo
    
    bpy.app.handlers.game_post.remove(bpy_shutdown_network)
    for handlers in [bpy.app.handlers.load_post, bpy.app.handlers.save_pre, bpy.app.handlers.game_pre]:
        handlers.remove(updateScripts)
        
    for script in Addon_Scripts:
        if script in bpy.data.texts:
            bpy.data.texts.remove(bpy.data.texts[script])


def show():
    obj = bpy.context.object
    props = obj.eo.feedback_properties
    print(10*"-")
    for item in props:
        print(item)

@persistent
def bpy_shutdown_network(scene): # cleanup if bge didn't exit right and there is bpy (not executed in .exe form)
    if hasattr(bpy, "EO_server"):
        if bpy.EO_server.isRunning():
            print("BGE closed, but server, running! Shutting it down.")
            bpy.EO_server.shutdown()
            delattr(bpy, "EO_server")
    if hasattr(bpy, "EO_client"):
        if bpy.EO_client.isRunning():
            print("BGE closed, but client is connected! Leaving.")
            bpy.EO_client.disconnect()
            delattr(bpy, "EO_client")
            
        
if __name__ == "__main__":
    #print(*dir(bpy.types), sep="\n")
    #bpy.app.handlers.game_post.clear() # REMOVE THIS ONCE THE HANDLER IS ONLY ADDED ONCE
    register()
    #f(bpy.types)
    obj = bpy.context.object
    """
    print(obj.name, "herererer")
    for item in obj.eo.trans_attrs:
        print(item.name, item.type, item.Change, item.GameProp)
    """
