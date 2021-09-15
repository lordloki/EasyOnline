Original Author: BleGaDev (https://www.youtube.com/channel/UCvu5-PR79qHyB1PxLXEDARQ)

Me, lordloki, adapted this code for current UPBGE 0.3 only.

"""
Some general aspects to consider:

 - The Network activities first start when the controller with the server.py/client.py script is triggered.

 - Every Message that is printed in the Console will also be sent as Message in the BGE.
 
 - For the "Value" of a Rule a possible property will be checked for in the Properties of the Representative
  and for a Counter-Rule possible properties will be checked for in the Transmitter.   
  
 - If one sets the 'Sender' of a Transmitter (located in a Client) to "Server", it is automatically assumed,
  that an object of the same name exists on the Server as exists on the Client, The Object on the server must have "Type" set to "None".
  
 - If one sets the 'Value' of a Rule or CounterRule without using "" (and no fitting property is found), 
  it will nonetheless be interpreted as a string and not as an error, as is usually the case with PropertySensors.
  
 - A Representative must always be in an inactive layer, because it will always be spawned into the active layer.
 
 - The Network Options can be changed by adding properties(with the corresponding name) to the object which is executing the server.py/client.py script.

For scripters:

 - The Server Instance is stored as bge.Server and the Client instances (from the Server's point of view) are stored as bge.Server.connected_clients.
 
 - The Client Instance is stored as bge.Client. 

 - By adding >"exec"+chr(29)+STRING+chr(30)< to bge.Server.MasterString, STRING will be executed at the Clients. For example: "bge.Server.MasterString += "exec"+chr(29)+"print(\"A Message from the Server\")"+chr(30)"
  will print "A Message from the Server" at the Clients' consoles. It also works the other way round, "bge.Client.MasterString += "exec"+chr(29)+"print(\"A Message from a Client\")"+chr(30)" will print
  "A Message from a Client" at the Server's console.
 
Definitions:
 
 Transmitter:
  - The object will be visualized (at the other clients and at the Server) by a Representative. 
    It is possible to specify which attribute(s) of the Representative shall be overwritten 
	by the value(s) (of the associated attribute(s)) from the Transmitter. 
	
  - Representative:
    Represents a Transmitter by being created when the Transmitter gets created and being 
	deleted when the Transmitter gets deleted. Will overwrite the specified Attributes with 
	the Transmitter’s value (of the associated attribute(s)). 
	
  - Observer:
    Makes it possible to set up Rules and Counter-Rules. The ‘Observer’ Type may only be applied to a Representative. 
    An Observer is good for making changes for just one transmitter from one certain Client or the Server.  
	If the desired change involves all transmitters from all clients, or the Server, then the normal Transmission would be the right solution. 
	
  - Transmission:
    The value of an attribute of the Transmitter is transferred to a Representative and will overwrite the value of the Representatives attribute.
	
  - Rule:
    If the sensor of the Representative is positive the value of a property of the Transmitter will be changed.
	
  - Counter-Rule:
    If the sensor of the Representative is positive and if a another sensor of the Transmitter is positive the value of a property of the Representative will be changed.
"""



 
