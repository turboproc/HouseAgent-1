import os, sys
import time
from twisted.internet.serialport import SerialPort
from twisted.protocols import basic
import ConfigParser
from houseagent.plugins import pluginapi
from twisted.internet import reactor, defer
from twisted.python import log

# Platform specific imports
if os.name == "nt":
    import win32service
    import win32serviceutil
    import win32event
    import win32evtlogutil

class JeelabsDevice(object):
    '''
    Abstract class to represent a JeelabsDevice
    '''
    def __init__(self, id, type, subtype, rssi):
        self.id = id
        self.type = type
        self.subtype = subtype
        self.rssi = rssi


class RoomNode(JeelabsDevice):
    '''
    Anstract class to represent a RoomNode device.
    '''
    def __init__(self, id, type, subtype, rssi):
        JeelabsDevice.__init__(self, id, type, subtype, rssi)
        self.counter = None
        
    def __repr__(self):
        return '[RoomNode] id: %r, type: %r, subtype: %r, counter: %r, rssi: %r' % (self.id, self.type, self.subtype, self.counter, self.rssi)

class MeterNode(JeelabsDevice):
    '''
    Anstract class to represent a RoomNode device.
    '''
    def __init__(self, id, type, subtype, rssi):
        JeelabsDevice.__init__(self, id, type, subtype, rssi)
        self.counter = None
        
    def __repr__(self):
        return '[RoomNode] id: %r, type: %r, subtype: %r, counter: %r, rssi: %r' % (self.id, self.type, self.subtype, self.counter, self.rssi)


class JeelabsProtocol(basic.LineReceiver):
    '''
    This class handles the JeeLabs protocol, i.e. the wire level stuff.
    '''
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self._devices = []
           
    def lineReceived(self, line):
        if line.startswith("OK"):
            self._handle_data(line)
            
    def _handle_data(self, line):
        '''
        This function handles incoming node data, current the following sketches/node types are supported:
        - Roomnode sketch
        - Outside node sketch
        @param line: the raw line of data received.
        '''
        data = line.split(" ")
        
#        log.msg (line)
#        log.msg (data[2])
#        log.msg (len(data))
        
        if len(data) > 6:
    	    if int(data[2]) == 1:
            
        	# Raw data packets (information from host.tcl (JeeLabs))
        	a   = int(data[4]) 
        	b   = int(data[5])
        	c   = int(data[6])
        	d   = int(data[7])       
        	node_id = str(int(data[1]) & 0x1f)
		msg_seq = str(int(data[3]))
		
        	type = 'JeeLabs'
        	subtype = 'RoomNode'
        	rssi = 88
            
        	device = self._device_exists(id, type)
        
        	if not device:
                    device = RoomNode(node_id, type, subtype, rssi)
                    self._devices.append(device)

        	light       = a 
        	motion      = b & 1
        	humidity    = b >> 1
        	temperature = str(((256 * (d&3) + c) ^ 512) - 512)
        	battery     = (d >> 2) & 1
        	temperature = temperature[0:2] + '.' + temperature[-1]

#		print(subtype)

        	log.msg("Received data from rooms jeenode; channel: %s, sequence: %s LDR: %s, " \
                  "humidity: %s, temperature: %s, motionsensor: %s, battery: %s" % (node_id, msg_seq, light, humidity, temperature, motion, battery))
                  
        	values = {'Light': str(light), 'Humidity': str(humidity),
                      'Temperature': str(temperature), 'Motion': str(motion), 'Battery': str(battery)}
           
        	self.wrapper.pluginapi.value_update(node_id, values)         
            
    	    # Handle outside node sketch
    	    elif int(data[2]) == 2:
        
        	node_id = str(int(data[1]) & 0x1f)
            
        	type = 'JeeLabs'
        	subtype = 'OutsideNode'
            
        	# temperature from pressure chip (16bit)
        	temp = str((int(data[4]) << 8) + int(data[3]))
        	temp = temp[0:2] + '.' + temp[-1]
            
        	# Lux level (32bit)
        	lux = str((int(data[8]) << 24) + (int(data[7]) << 16) + (int(data[6]) << 8) + int(data[5]))
            
        	# barometric pressure (32bit)
        	pressure = str((int(data[-1]) << 24) + (int(data[-2]) << 16) + (int(data[-3]) << 8) + int(data[-4]))
        	pressure = pressure[0:4] + "." + pressure[-2:]

        	log.msg("Received data from outside sketch jeenode; channel: %s, lux: %s, " \
                  "pressure: %s, temperature: %s" % (node_id, lux, pressure, temp))
            
        	values = {'Lux': str(lux), 'Pressure': str(pressure), 'Temperature': str(temp)}
#        	print('Received data')
        	self.wrapper.pluginapi.value_update(node_id, values)

            # handle moternode sketch
    	    elif int(data[2]) == 3:
            
        	# Raw data packets (information from host.tcl (JeeLabs))
        	a   = int(data[4]) 
        	b   = int(data[5])
        	c   = int(data[6])
        	d   = int(data[7])       
        	node_id = str(int(data[1]) & 0x1f)
		msg_seq = str(int(data[3]))
		
        	type = 'JeeLabs'
        	subtype = 'MeterNode'
        	rssi = 88
            
        	device = self._device_exists(id, type)
        
        	if not device:
                    device = MeterNode(node_id, type, subtype, rssi)
                    self._devices.append(device)

                counter = d << 24 | c << 16 | b << 8 | a
                cnt = str(int(counter / 100)) + '.' + str(counter % 100) 
#		print(subtype)

        	log.msg("Received data from MeterNode; channel: %s, sequence: %s Counter: %s, " % (node_id, msg_seq, cnt))
                  
        	values = {'Counter': cnt}
           
        	self.wrapper.pluginapi.value_update(node_id, values)         
            


            
    def _device_exists(self, id, type):
        '''
        Helper function to check whether a device exists in the device list.
        @param id: the id of the device
        @param type: the type of the device
        '''
        for device in self._devices:
            if device.id == id and device.type == type:
                return device
            
        return False
        


class JeelabsWrapper():

    def __init__(self):
        '''
        Load initial JeeLabs configuration from jeelabs.conf
        '''
        from houseagent.utils.generic import get_configurationpath
        config_path = "/etc"
        
        config = ConfigParser.RawConfigParser()
        config.read(os.path.join(config_path, 'jeelabs.conf'))
        self.port = config.get("serial", "port")

        # Get broker information (RabbitMQ)
        self.broker_host = config.get("broker", "host")
        self.broker_port = config.getint("broker", "port")
        self.broker_user = config.get("broker", "username")
        self.broker_pass = config.get("broker", "password")
        self.broker_vhost = config.get("broker", "vhost")
        
        self.logging = config.getboolean('general', 'logging')

        self.log = pluginapi.Logging("Jeenode plugin")

        self.id = config.get('general', 'id')
                
    def start(self):
        '''
        Function that starts the JeeLabs plug-in. It handles the creation 
        of the plugin connection and connects to the specified serial port.
        '''
        callbacks = {'custom': self.cb_custom}
        
        self.pluginapi = pluginapi.PluginAPI(self.id, 'Jeelabs', broker_host=self.broker_host, broker_port=self.broker_port, **callbacks)
        
        self.protocol = JeelabsProtocol(self) 
        myserial = SerialPort (self.protocol, self.port, reactor, rtscts=0, xonxoff=1, baudrate=57600)

	log.startLogging(open('/var/log/houseagent/jeelabs.log','w'))
	
	self.log.debug("Started plugin")
	
        self.pluginapi.ready()

        reactor.run(installSignalHandlers=0)
        return True
        
    def cb_custom(self, action, parameters):
        '''
        This function is a callback handler for custom commands
        received from the coordinator.
        @param action: the custom action to handle
        @param parameters: the parameters passed with the custom action
        '''
        if action == 'get_devices':
            devices = {}
            for dev in self.protocol._devices:
                devices[dev.id] = [dev.type, dev.subtype, dev.rssi]
            d = defer.Deferred()
            d.callback(devices)
            return d


if os.name == "nt":    
    
    class JeelabsService(win32serviceutil.ServiceFramework):
        '''
        This class is a Windows Service handler, it's common to run
        long running tasks in the background on a Windows system, as such we
        use Windows services for HouseAgent.
        '''        
        _svc_name_ = "hajeelabs"
        _svc_display_name_ = "HouseAgent - Jeelabs Service"
        
        def __init__(self,args):
            win32serviceutil.ServiceFramework.__init__(self,args)
            self.hWaitStop=win32event.CreateEvent(None, 0, 0, None)
            self.isAlive=True
    
        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            reactor.stop()
            win32event.SetEvent(self.hWaitStop)
            self.isAlive=False
    
        def SvcDoRun(self):
            import servicemanager
                   
            win32evtlogutil.ReportEvent(self._svc_name_,servicemanager.PYS_SERVICE_STARTED,0,
            servicemanager.EVENTLOG_INFORMATION_TYPE,(self._svc_name_, ''))
    
            self.timeout=1000  # In milliseconds (update every second)
            jeelabs = JeelabsWrapper()
            
            if jeelabs.start():
                win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE) 
    
            win32evtlogutil.ReportEvent(self._svc_name_,servicemanager.PYS_SERVICE_STOPPED,0,
                                        servicemanager.EVENTLOG_INFORMATION_TYPE,(self._svc_name_, ''))
    
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
    
            return

if __name__ == '__main__':
    
    if os.name == "nt":    
        
        if len(sys.argv) == 1:
            try:
    
                import servicemanager, winerror
                evtsrc_dll = os.path.abspath(servicemanager.__file__)
                servicemanager.PrepareToHostSingle(JeelabsService)
                servicemanager.Initialize('JeelabsService', evtsrc_dll)
                servicemanager.StartServiceCtrlDispatcher()
    
            except win32service.error, details:
                if details[0] == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                    win32serviceutil.usage()
        else:    
            win32serviceutil.HandleCommandLine(JeelabsService)
    else:
        jeelabs = JeelabsWrapper()
        jeelabs.start()