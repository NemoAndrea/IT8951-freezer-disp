import board
import digitalio
import busio
import time
from array import array

from .constants import PixelModes, Commands

import adafruit_imageload


class SPI:
    max_transfer_size = 2048   # 4096 works fine

    def __init__(self):
        
        self.cs = digitalio.DigitalInOut(board.IO34)  # chip select pin
        self.cs.direction = digitalio.Direction.OUTPUT
        self.cs.value = True  # and pull it high. Pulling it low will reset board.
        

        self.spi_bus = busio.SPI(board.SCK, MISO=board.MISO, MOSI=board.MOSI)
        while not self.spi_bus.try_lock():
            pass
        print("got lock on SPI bus.")

        # NOTE: max spi clock is 24MHz, but 2MHz seems about limit of disp?. 
        self.spi_bus.configure(baudrate=4000000, phase=0, polarity=0)

        # pre-allocate memory
        self.transfer_buffer = bytearray(self.max_transfer_size)
        self.transfer_view = memoryview(self.transfer_buffer)

    def write_cmd(self, cmd, *args):  # cmd must be 2 byte number, e.g. 0xFF9F
        print(f"[CMD] {hex(cmd)} with {args} arguments.")

        # the fixed preamble for 'commands' is 0x6000.
        data = [0x60,0x00, 0x00, 0x00]

        data[2] = (cmd >> 8) & 0xFF 
        data[3] = cmd & 0xFF 

        self.cs.value = False
        self.spi_bus.write(bytes(data)) #0x6000 -> 0x0302
        self.cs.value = True
        time.sleep(0.1)

        for arg in args:
            self.write_data([arg])

    def write_data(self, arr):
        '''
        Send preamble, and then write the data in arr (16-bit unsigned ints) over SPI
        '''

        # unpack int (16-bit) array into byte (8-bit) array 
        nbytes = len(arr)*2 + 2
        arr_bytes = array('B', (0 for _ in range(nbytes)))  # +2 for the preamble (0x00, 0x00)
        arr_bytes[0] = 0x00
        arr_bytes[1] = 0x00
        for i in range(len(arr)):
            arr_bytes[i*2+2] = (arr[i] >> 8) & 0xFF
            arr_bytes[i*2+3] = arr[i] & 0xFF

        #print(f">> write_data is sending : {arr_bytes}")

        self.cs.value = False
        self.spi_bus.write(arr_bytes) 
        self.cs.value = True
        time.sleep(0.1)

    def write_single_color(self, length, color):
        pixbuf_len = length
        pix_per_byte = PixelModes.M_4BPP  # 2 pixels per byte

        # how many pixels are we sending in a single spi tranmissiong? (remember our smallest valid transmission is per 16 bit words)
        # pix_per_transfer = pixels_per_word * words_per_transfer
        pix_per_transfer = 2*pix_per_byte * ((self.max_transfer_size - 2)//2)

        packed_pixels = (color << 4) | color  # pack 2 pixels into a byte
        print(f"-> packed pixels {bin(packed_pixels)}")

        full_nbytes = 2 + 2 * ((pix_per_transfer + 3) // 4)

        # preamble, indicating it is a "data" transmission
        self.transfer_buffer[0] = 0x00
        self.transfer_buffer[1] = 0x00

        # get local refs
        t_buffer = self.transfer_buffer
        t_view = self.transfer_view
        spi_write = self.spi_bus.write
        cs = self.cs

        print(f"[SPI] will need {pixbuf_len // pix_per_transfer} transfers")
        for block_start in range(0, pixbuf_len, pix_per_transfer):
            
            pix_count = min(pix_per_transfer, pixbuf_len - block_start)
                    
            # Determine exact byte size for this specific chunk
            nbytes = 2 + 2 * ((pix_count + 3) // 4)
            chunk = t_view[:nbytes]

            if nbytes == full_nbytes:
                # For a max-sized block, populate the whole slice instantly
                t_buffer[2:nbytes] = bytes([packed_pixels]) * (nbytes - 2)
            else:
                # remainder block (greedy joink extra bytes (it doesnt seem to care))
                t_buffer[2:nbytes] = bytes([packed_pixels]) * (nbytes - 2)

            cs.value = False
            spi_write(chunk) 
            cs.value = True

    def pack_and_write_pixels(self, pixbuf):
        '''
        Pack pixels into a byte buffer, and write them to the device. Pixbuf should be
        an array with each value an individual pixel, in the range 0x00-0xFF. Note that
        the intended display only has a 4-bit grayscale depth, so intensities above
        2^4 wil not be used.
        '''

        pixbuf_len = pixbuf.width*pixbuf.height
        pix_per_byte = PixelModes.M_4BPP  # 2 pixels per byte

        # how many pixels are we sending in a single spi tranmissiong? (remember our smallest valid transmission is per 16 bit words)
        # pix_per_transfer = pixels_per_word * words_per_transfer
        pix_per_transfer = 2*pix_per_byte * ((self.max_transfer_size - 2)//2)

        print("sending pixel data...")

        # get local refs to variables (for performance)
        transfer_view = self.transfer_view 
        spi_write = self.spi_bus.write
        cs = self.cs

        print(f"\n[SPI] will need {pixbuf_len // pix_per_transfer} transfers. Sending blocks...")
        for block_start in range(0, pixbuf_len, pix_per_transfer):
            
            # final transfer may be shorter than the max we could send per transmission
            pix_count = min(pix_per_transfer, pixbuf_len-block_start)

            # how many bytes must we allocate? (note again that the smallest chunk we can send is
            # a 16-bit word.
            nbytes = 2 + 2*( (pix_count+2*pix_per_byte-1)//(2*pix_per_byte) )  # TODO: seems correct
            

            assert nbytes % 2 == 0, "Number of bytes must be even, as we send in two-byte blocks."
            assert pix_count % 4 == 0, "Number of pixels must be multiple of 4 as the smallest unit we can transmit over SPI is a block of 4 pixels"

            #print(f"need {nbytes}bytes and {pix_count}pix (of max {self.max_transfer_size}) to send image data.")

            chunk = transfer_view[:nbytes] 
            # preamble, indicating it is a "data" transmission
            chunk[0] = 0x00
            chunk[1] = 0x00

            idx = 2  # start at byte at idx 2
            p_index = block_start  # keep track of what data we are reading from pixbuf
            while idx < nbytes:
                if p_index < (pixbuf_len - 1):
                    chunk[idx] = (pixbuf[p_index] << 4) | pixbuf[p_index+1]
                else:
                    chunk[idx] = 0x00
                p_index += 2
                idx += 1

            #print(f"check sending spi.data: {transfer_data[0], transfer_data[1]}") #TOOD remove

            # assert(len(transfer_data) <= self.max_transfer_size)  TTODO: reinsert

            cs.value = False
            spi_write(chunk) 
            cs.value = True
        print("[SPI] all blocks sent...\n")


    def read(self, numwords):
        '''
        Send preamble, and return a buffer of 16-bit unsigned ints of length count
        containing the data received.

        An SPI write or command must be sent beforehand, and this configures the returned data.
        A fixed preamble (MOSI) is required before data bits are returned on MISO. Preamble
        and returned data are on the same transaction (no CS=high in between).
        '''

        write_data = bytearray(numwords*2 + 4)  # 2 dummy bytes that we must read on top of expected data
        write_data[0] = 0x10  # READ preamble
        write_data[1] = 0x00  # READ preamble

        read_data = bytearray(numwords*2 + 4)  # 2 dummy bytes that we must read on top of expected data

        self.cs.value = False
        self.spi_bus.write_readinto(write_data, read_data)
        self.cs.value = True

        # we now need to pack the data into array of 16bit values
        returned = array('I', (0 for _ in range(numwords)))   

        #print(f"[SPI][READ] returned data: {list(hex(val) for val in read_data)}")

        for i in range(numwords):

            returned[i] = (read_data[2*i+4] << 8) +  read_data[2*i+5]

        return returned
    
    def read_int(self):
        '''
        Read a single 16 bit int from the device
        '''
        return self.read(1)[0]
    

    # def read_register(self, register_addr, resp_length):
    #     print(f"Reading register {hex(register_addr)}")
    #     self.write_cmd(Commands.REG_RD, register_addr)
    #     print(self.read(resp_length))

        	