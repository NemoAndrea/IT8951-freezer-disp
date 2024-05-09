
from . import constants
from .constants import Commands, Registers, PixelModes

from time import sleep

class EPD:
    '''
    An interface to the electronic paper display (EPD). 
    
    Values are hardcoded for the Waveshare 10.3inch 1872×1404 display (SKU:26936).

    Parameters
    ----------

    vcom : float
         The VCOM voltage that produces optimal display. Varies from
         device to device.
    '''

    def __init__(self, vcom=-1.5):

        # do this here so we don't have to in the case
        # of a "virtual" display
        from .spi import SPI
        self.spi = SPI()

        self.width            = None
        self.height           = None
        self.img_buf_address  = None
        self.firmware_version = None
        self.lut_version      = None
        self.update_system_info()  # fetch info for the items above

        self._set_img_buf_base_addr(self.img_buf_address)

        # enable I80 packed mode
        self.write_register(Registers.I80CPCR, 0x1)

        self.set_vcom(vcom)

    def load_img_area(self, buf, rotate_mode=constants.Rotate.NONE, xy=None, dims=None):
        '''
        Write the pixel data in buf (an array of bytes, 1 per pixel) to device memory.
        This function does not actually display the image (see EPD.display_area).

        Parameters
        ----------

        buf : bytes
            An array of bytes containing the pixel data

        rotate_mode : constants.Rotate, optional
            A rotation mode for the data to be pasted into device memory

        xy : (int, int), optional
            The x,y coordinates of the top-left corner of the area being pasted. If omitted,
            the image is assumed to be the whole display area.

        dims : (int, int), optional
            The dimensions of the area being pasted. If xy is omitted (or set to None), the
            dimensions are assumed to be the dimensions of the display area.
        '''

        endian_type = constants.EndianTypes.BIG

        if pixel_format is None:
            pixel_format = constants.PixelModes.M_4BPP

        if xy is None:
            self._load_img_start(endian_type, pixel_format, rotate_mode)
        else:
            self._load_img_area_start(endian_type, pixel_format, rotate_mode, xy, dims)

        try:
            bpp = {
                PixelModes.M_2BPP : 2,
                PixelModes.M_4BPP : 4,
                PixelModes.M_8BPP : 8,
            }[pixel_format]
        except KeyError:
            raise ValueError("invalid pixel format") from None

        self.spi.pack_and_write_pixels(buf, bpp)

        self._load_img_end()

    def display_area(self, xy, dims, display_mode):
        '''
        Update a portion of the display to whatever is currently stored in device memory
        for that region. Updated data can be written to device memory using EPD.write_img_area
        '''
        self.spi.write_cmd(Commands.DPY_AREA, xy[0], xy[1], dims[0], dims[1], display_mode)

    def update_system_info(self):
        '''
        Get information about the system, and store it in class attributes
        '''
        self.spi.write_cmd(Commands.GET_DEV_INFO)
        data = self.spi.read(20)

        if all(x == 0 for x in data):
            raise RuntimeError("communication with device failed")
        
        

        self.width  = data[0]
        self.height = data[1]
        self.img_buf_address = data[3] << 16 | data[2]
        self.firmware_version = ''.join([chr(x>>8)+chr(x&0xFF) for x in data[4:12]])
        self.lut_version      = ''.join([chr(x>>8)+chr(x&0xFF) for x in data[12:20]])\
        
        print(f" width is {self.width}")
        print(self.height)
        print(self.img_buf_address)
        print(self.firmware_version)

    def get_vcom(self):
        '''
        Get the device's current value for VCOM voltage
        '''
        self.spi.write_cmd(Commands.VCOM, 0)
        vcom_int = self.spi.read_int()
        return -vcom_int/1000

    def set_vcom(self, vcom):
        '''
        Set the device's VCOM voltage
        '''
        self._validate_vcom(vcom)
        vcom_int = int(-1000*vcom)
        self.spi.write_cmd(Commands.VCOM, 1, vcom_int)

    def _validate_vcom(self, vcom):
        # TODO: figure out the actual limits for vcom
        if not -5 < vcom < 0:
            raise ValueError("vcom must be between -5 and 0")

    def run(self):
        self.spi.write_cmd(Commands.SYS_RUN)

    def standby(self):
        self.spi.write_cmd(Commands.STANDBY)

    def sleep(self):
        self.spi.write_cmd(Commands.SLEEP)

    def wait_display_ready(self):
        while(self.read_register(Registers.LUTAFSR)):
            sleep(0.01)

    def _load_img_start(self, endian_type, pixel_format, rotate_mode):
        arg = (endian_type << 8) | (pixel_format << 4) | rotate_mode
        self.spi.write_cmd(Commands.LD_IMG, arg)

    def _load_img_area_start(self, endian_type, pixel_format, rotate_mode, xy, dims):
        arg0 = (endian_type << 8) | (pixel_format << 4) | rotate_mode
        self.spi.write_cmd(Commands.LD_IMG_AREA, arg0, xy[0], xy[1], dims[0], dims[1])

    def _load_img_end(self):
        self.spi.write_cmd(Commands.LD_IMG_END)

    def read_register(self, address):
        '''
        Read a device register
        '''
        self.spi.write_cmd(Commands.REG_RD, address)
        return self.spi.read_int()

    def write_register(self, address, val):
        '''
        Write to a device register
        '''
        self.spi.write_cmd(Commands.REG_WR, address)
        print(f"value: {val}")
        self.spi.write_data((val,))

    def _set_img_buf_base_addr(self, address):
        word0 = address >> 16
        word1 = address & 0xFFFF
        self.write_register(Registers.LISAR+2, word0)
        print("word 1.....")
        self.write_register(Registers.LISAR, word1)
