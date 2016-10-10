#!/usr/bin/env python
"""
This module contains the class SerMesProtocol().

This class implements a message-based protocol over the serial port
in Master slave mode: This is the starting mode. The master (PC)
starts communication with slave(peripheral) sending a message. Slave 
process the message and gives an answer.

The class uses serial port to implement the protocol.
In master-slave data from the device is simply passed as return from 
a function that exist for every command implemented. 
"""
import time
import serial
import struct
import math
import sys

import binascii

class SerMesProtocol():
    #---------------------- INITIALIZATION ----------------------#

    def __init__(self, port,
                       baudrate,
                       stopbits=serial.STOPBITS_ONE,
                       parity=serial.PARITY_NONE,
                       timeout=0.5):
        # IDs of the master and slave.
        self.MASTER_ID ='\x01' 
        self.SLAVE_ID ='\x02' 
        self.serial = serial.Serial(port=port, 
                                    baudrate=baudrate, 
                                    stopbits=stopbits, 
                                    parity=parity, 
                                    timeout=timeout)
        self.serial.flushInput()

    #----------------DISCONNECT FROM SERIAL PORT----------------#
    def disconnect(self):
        self.serial.close()

    #-------------------MASTER-SLAVE COMMANDS-------------------#
    def ready(self, tries=10):
        """
        Asks if ready. If ACK is returned is ready

        Parameters
        ----------
        tries : int
            number of tries before exiting and raising an error.

        Returns
        -------
        ready : boolean
            returns a true or false condition which confirms that 
            the message was received.
        """
        ready = False
        #send configuration message.
        count = 0
        while not ready:     
            if count == tries:
                print "Unable to connect. Exited after {} tries".format(tries)
                sys.exit(1)
            self.send_message(self.READY)     
            #wait for the response from the device
            fun_code = self.read_message()[1]
            if fun_code == self.ACK_MSG :
                ready = True	
            count += 1            
        return ready   

    def move(self, setpoint=[0,0]):
        """
        Asks to move. If ACK is action was performed

        Parameters
        ----------

        setpoint[] : int list object
            List with element values values from 0 to 255. Velocity of
            the AGV. First element corresponds to right wheels, and 
            second element to left wheels. Values must be integers. They
            are rounded if decimal.

        Returns
        -------
        move : boolean
            returns a true or false condition which confirms that the 
            message was received.
        """
        # Check that the values are correct. Invalid values may crash 
        # the Arduino program.
        while any(x > 255 or x < 0  for x in setpoint):
            print ('Invalid set points. Please enter 2 values between \
                    0 and 255 (Decimal values will be rounded)')
            if any( type(x) == float for x in setpoint ):
                setpoint = [int(round (x) ) for x in setpoint]
        #Values casted into C 'char' variables
        char_sp = '{}{}'.format(struct.pack('>h', setpoint[0])[1],
                                struct.pack('>h', setpoint[1])[1])
        #send configuration messager
        self.send_message(SerMesProtocol.MOVE, char_sp)     
        #wait for the response from the device
        result = self.read_message()
        if (result==0):#if an error was detected
            return 0
        else: #no errors
            fun_code = result[1]
            if fun_code :
                return True	   
            else:
                return False 



    #-------------MASTER-SLAVE COMMANDS AUXILIAR FUNCTIONS-------------#
    def send_message(self, fun_code, data='', send_delay=0.01):
        """
        Sends a message using the serial message protocol

        Parameters
        ----------
        fun_code : str object
	        fuction code of the command that is going to be sent.
        length : str object
	        LENGTH field in the message.size of the DATA field in bytes.
        data : str object
	        DATA field of the message. 
        send_delay : float
	        Delay time to wait between sent bytes.
        """
        # Prepares message.
        # The data length bytes are little endian according to the protocol. 
        # Thus, these bytes have to be reversed.
        Data_Length =  struct.pack( '>H',len(data) )[::-1]
        message='{stx}{slave}{master}{ln}{func}{sent_data}{etx}'.format(
                                                    stx = self.STX,
                                                    slave = self.SLAVE_ID,
                                                    master = self.MASTER_ID,  
                                                    ln = Data_Length, 
                                                    func = fun_code, 
                                                    sent_data = data,
                                                    etx = self.ETX)
        #sends message.
        print 'sending... {}'.format(" ".join( hex(ord(n)) for n in message ) )

        self.serial.write(message)


    def read_message(self):
        """
        Reads a message using the serial message protocol. Checks the
        auxiliary bytes for assuring the consistence of the message

        Returns
        -------
        Rx_OK : Boolean
            Rx_OK is 0 if an error ocurred.

        fun_code : String
            non decodified hex-data corresponding to the function code 
            given by slave.

        data : String
            non decodified hex-data corresponding to the data given by 
            slave.

        length : int
            size of the main data, measured in bytes.
        """
        Rx_OK = False
        fun_code = ""
        length = 0
        data = ""
        _STX = ""
        ### Reading of the auxiliary initial bytes ###
        # The 1st byte of transmission corresponds to the 'start transmission'.
        start_time = time.time()
        while _STX != self.STX :
            current_time = time.time()
            # Gives the slave 2 seconds to return an answer.
            if current_time - start_time > 2:
                print 'Error, STX was not found'
                return (Rx_OK, fun_code, length, data) 	
            _STX = self.serial.read(1)         	
        # The 2nd and 3rd bytes of transmission correspond to the master 
        # and slave IDs
        id_dest = self.serial.read(1)
        id_org = self.serial.read(1)
        ##### Reading of the length-of-data bytes #####
        # With the try-except statements, it is checked that there 
        # is data available in the 2 length bytes.
        try:
            length = struct.unpack('>H',self.serial.read(2))[0]
        except error:
            print 'Received length bytes are not valid'
            return (Rx_OK, fun_code, length, data)
        print ('received data length = {}'.format(length) )
        ### Reading of the function code and the main data ###
        fun_code = self.serial.read(1)      
        for i in range(length):
            data = '{previous_data} {new_data}'.format(previous_data = data, 
                                                 new_data = self.serial.read(1))
        # Reading of the last byte, corresponding to end of transmission check.
        _ETX=self.serial.read(1)
        ##### Check of message validity #####
        if (_STX == self.STX) and (_ETX == self.ETX) \
                                    and (id_dest == self.MASTER_ID):          
            print 'Succesfull communication'
            Rx_OK = True
        elif _ETX != SerMesProtocol.ETX :
            print 'Error, ETX was not found'  
        elif id_dest != self.MASTER_ID :
            print 'Message for other device'
 
        return (Rx_OK, fun_code, length, data) 

    #---------- CLASS CONSTANTS ----------#
	#message fields
    STX ='\x02'
    ETX ='\x03'
    # slave-to-master answers
    ACK_MSG ='\x01'
    NACK_MSG ='\x02'
    DONE_MSG ='\x03'
    # master-to-slave orders
    READY = '\x04'
    MOVE = '\x05'
