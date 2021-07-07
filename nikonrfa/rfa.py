"""
Nikon Remote Focus Accessory (RFA)

This module defines a class that simplifies interacting with the RFA.


Implemented commands:
w   MZ XXXX     abs move
r   RESOLUTION  in an underscore method (called in __init__)
r   VERSION     no dedicated method, but used in __init__
r   WHO         no dedicated method, but used in __init__
r   WZ          read position
rw  ENCODER     in an underscore method (called in __init__)
w   HALT        stop the current move
w   RESET           reset the system (as if power was turned off)
w   RZ XXXX         relative move
w   HZ XXXX      int,   redefines current position
w   ZERO

rw  SPEED XXXX      maximum speed: 50-60000 (60000 is slowest)
rw  MINSPEED XXXX   the start-up-speed: 50-60000 (60000 is slowest)
rw  RAMPSLOPE XXX  (1-255)  larger number means slower acceleration


Not (yet) implemented commands


"""



import serial  # pip install pyserial
from serial.tools import list_ports
import logging
import time


class NikonRFA:
    def __init__(self, port=None, newline=b'\r', timeout=2, vid=None, pid=None, *args, **kwargs):
        """
        Control the Nikon Remote Focus Accessory (RFA).
        Specify either the COM-port or search for the COM-port automatically by specifying
        the vid and pid number of the serial ship used to communicate with the RFA.
        (If both are specified, the port is used).

        :param str port: Com port to use e.g. 'COM1' (optional, default: None)
        :param int baudrate: Baudrate used by pyserial (optional, default: 9600)
        :param bytes newline: Line ending used (optional, default: b'\r')
        :param float timeout: Read timeout in seconds (optional, default: 2)
        :param int vid: The serial-chip vendor id number (optional, default: None)
        :param int pid: The serial-chip product id number (optional, default: None)
        :param *args: Additional arguments are passed to pyserial Serial object (optional)
        :param **kwargs: Additional keyword arguments are passed to pyserial Serial object (optional)
        """
        self.logger = logging.getLogger(__name__)
        self._line_ending = newline
        self._timeout = timeout

        self.unit = 'um'

        # If port is not specified, find the device by vid and pid:
        if port is None:
            if type(vid) is not int or type(pid) is not int:
                self.logger.error("If port is not supplied, vid and pid need to be supplied (ints)")
            else:
                matches = [d.device for d in list_ports.comports() if d.vid==vid and d.pid==pid]
                if len(matches) == 0:
                    self.logger.error('No match found for vid={} pis={}'.format(vid, pid))
                    return
                elif len(matches)>1:
                    self.logger.warning('Multiple matches found. Using first one')
                else:
                    port = matches[0]
        self.ser = serial.Serial(port, *args, timeout=timeout, **kwargs)
        idn = self.query('WHO')
        if idn == 'Remote Focus Accessory (M)':
            ver = self.query('VERSION')
            self.logger.info("Connected to {}, firmware: {}".format(idn, ver))
        else:
            self.logger.warning('Device did not identify')

        # Initialize internal variables (directly and through functions):
        self._get_resolution_info() # initializes:
        # _units_per_um             This contains the scaling factor between um and the units the device uses for
        #                           communication. I.e. how much units fit in a micrometer.
        # _smallest_um_step         The smallest step in um. Note that the device will return 0 for values smaller than 1
        #                           One may overwrite this parameter using the smallest_um attribute.
        if not self._get_encoder_status():
            self._set_encoder_status(True)
        self.get_position()         # initializes:
        # _pos                      Stores the last retrieved position
        self._moved_since_last_read = True  # Used to keep track if the stages has moved since last position read

    def _get_encoder_status(self):
        """
        Retrieves the status of the encoder.

        :return: encoder status
        "rtype bool:
        """

        reply = self.query('ENCODER')
        if reply=='OFF':
            return False
        elif reply == 'ON ':
            return True
        else:
            self.logger.warning('Unknown response')

    def _set_encoder_status(self, status):
        """
        Turns encoder on and off.

        :param bool status: Boolean status
        """
        if status:
            reply = self.query('ENCODER ON')
        else:
            reply = self.query('ENCODER OFF')
        self.logger.debug('Setting encoder status {}'.format(status))

    def absmove(self, um):
        """
        Move to absolute position (in um).

        :param float um: position to move to (in um)
        """
        reply = self.query('MZ {}'.format(int(round(um*self._units_per_um))))
        if reply:
            self.logger.warning('unexpected message: '+reply)
        self._moved_since_last_read = True

    def absmove_read(self, um):
        """
        Moves to absolute position (in um), reads out the position and returns it (in um).
        Also warns if device didn't move.

        :param float um: position to move to (in um)
        :return: position to move to (in um)
        :rtype: float
        """
        pos_before_move = self.pos
        self.absmove(um)
        if self.pos == pos_before_move:
            self.logger.warning("Stage didn't move. Perhaps step too small or out of range.")
        return self.pos

    def get_position(self):
        """
        Retrieves the position from device and updates internal memory. And returns the position.

        :return: position in um (retrieved from device)
        :rtype: float
        """
        reply = self.query('WZ')
        try:
            pos = int(reply) / self._units_per_um
            self._pos = pos
            self._moved_since_last_read = False
            return pos
        except:
            self.logger.warning('unexpected message: '+reply)


    def relmove(self, um):
        """
        Move by relative position from the curent position (in um).

        :param float um: relative position to move to (in um)
        """
        reply = self.query('RZ {}'.format(int(round(um*self._units_per_um))))
        if reply:
            self.logger.warning('unexpected message: '+reply)
        self._moved_since_last_read = True

    def relmove_read(self, um):
        """
        Moves by relative position (in um), reads out the position and returns it (in um).
        Also warns if device didn't move.

        :param float um: relative position to move to (in um)
        :return: position to move to (in um)
        :rtype: float
        """
        pos_before_move = self.pos
        self.relmove(um)
        if self.pos == pos_before_move:
            self.logger.warning("Stage didn't move. Perhaps step too small or out of range.")
        return self.pos

    @property
    def pos(self):
        """
        Read-only property attribute that returns position, but avoids unnecessary extra communication with the device.
        If no move command was issued since the position was last retrieved, it returns position from internal memory.
        If a move command was sent, it will retrieve the value from the device and return that (and update the memory).

        the position was retrieved

        :return: position in um (from memory or retrieved )
        :rtype: float
        """
        if self._moved_since_last_read:
            return self.get_position()
        else:
            return self._pos

    def _get_resolution_info(self):
        """
        Retrieves the resolution information from the device and stores those internally.
        Note that this will set/overwrite smallest_um_step.
        """
        reply = self.query('RESOLUTION')
        number, fraction = reply.split(' ')
        if fraction  == 'HUNDREDTHS':
            self._units_per_um = 100.0
        elif fraction  == 'TENTHS':
            self._units_per_um = 10.0
        self._smallest_um_step = int(number)
        self.logger.info("Setting smallest_um_step to {}".format(self._smallest_um_step))

    @property
    def smallest_um_step(self):
        """
        Property attribute that returns internally stored value for the smallest allowed step in um.
        This property may be overwritten by the user to store the correct smallest step size.

        :return: smallest step size in um (from internal memory)
        :rtype: float
        """
        return self._smallest_um_step


    @smallest_um_step.setter
    def smallest_um_step(self, um_step):
        if um_step != self._smallest_um_step:
            self.logger.info("Modifying smallest_um_step from {} to {}".format(self._smallest_um_step, um_step))
            self._smallest_um_step = um_step

    def query(self, command):
        """
        Send message to the device and waits for reply. Cleans up the reply and returns it.

        :param str command: command to send to the device
        :return: reply from the device
        :rtype: str
        """
        self.ser.reset_input_buffer()
        self.ser.write((command + '\r').encode('ascii'))
        buffer = ""
        t0 = time.time()
        while time.time() < t0 + self._timeout:
            oneByte = self.ser.read(1)
            if oneByte == b"\r":  # method should returns bytes
                self.logger.debug(buffer)
                return buffer[3:-1]
            else:
                buffer += oneByte.decode("ascii")

    def close(self):
        """Closes the serial connection."""
        self.ser.close()

    def halt(self):
        """
        It stops the moving by writing halt.
        """
        self.logger.debug('Halting the device')
        self.query("halt")

    def reset(self):
        """
        Resets the device as if the power was turned off.
        """
        self.logger.debug('Halting the device')
        self.query("reset")

    def zero(self):
        """
        It sets the origin to current position.
        :return:
        """
        self.logger.debug('setting the origin')
        self.query("zero")
        self._pos=0.00

    def redefine_position(self,um):
        """
        it redefine the current position to the input value in micrometre (um)

        :param float um: the redefined position (um)
        """
        self.logger.debug('redefining the current position to {}um'.format(um))
        reply = self.query('HZ {}'.format(int(round(um * self._units_per_um))))
        self._pos=um

    @property
    def maxspeed(self):
        """
        reading and setting the maximum speed
        The larger value means slower speed
        Range= 50 to 60000
        """
        reply=self.query('speed')
        return int(reply)

    @maxspeed.setter
    def maxspeed(self,v):
        v=int(v)
        if v<50:
            v=50
            self.logger.warning('minimum speed is 50')
        elif v>60000:
            v=60000
            self.logger.warning('maximum speed is 60000')
        self.query('speed {}'.format(v))

    @property
    def minspeed(self):
        """
        reading and setting the starting speed
        The larger value means slower speed
        Range= 50 to 60000

        """
        reply = self.query('minspeed')
        return int(reply)

    @minspeed.setter
    def minspeed(self, v):
        v=int(v)
        if v < 50:
            v = 50
            self.logger.warning('minimum speed is 50')
        elif v > 60000:
            v = 60000
            self.logger.warning('maximum speed is 60000')
        self.query('minspeed {}'.format(v))

    @property
    def rampslope(self):
        """
        reading and setting the rate at which speed changes
        The larger value means slower acceleration
        Range is 1:255
        """
        reply = self.query('rampslope')
        return int(reply)

    @rampslope.setter
    def rampslope(self, a):
        a=int(a)
        if a < 1:
            a=1
            self.logger.warning('minimum acceleration is 1')
        elif a>255:
            a=255
            self.logger.warning('maximum acceleration is  255')
        self.query('rampslope {}'.format(a))

if __name__ == '__main__':
    # This section contains code that may be used as an example how to use the class and for testing if the class functions

    # Set logging level to DEBUG to print everything (alternatively use INFO, WARNING, ERROR)
    logging.basicConfig(level=logging.DEBUG)

    # Find the device:
    print("listing all devices:")
    print("vid  pid   description")
    for d in list_ports.comports():
        print(d.vid, d.pid, d.description)

    rfa = NikonRFA(vid=6790, pid=29987)  # specify either the COM port (e.g. 'COM1') or the vid and pid
    rfa.smallest_um_step = 0.05  # You may specify (overwrite) the smallest step




