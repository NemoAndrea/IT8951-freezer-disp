
import displayio
import random
import adafruit_imageload

from .constants import DisplayModes
from .interface import EPD


class AutoDisplay:
    '''
    This base class tracks changes to its frame_buf attribute, and automatically
    updates only the portions of the display that need to be updated

    Updates are done by calling the update() method, which derived classes should
    implement.

    Note: width and height should be of the physical display, and don't depend on
    rotation---they will be swapped automatically if rotate is set to CW or CCW
    '''

    def __init__(self, width, height, rotate=None, mirror=False, track_gray=False):

        self.display_dims = (width, height)
        print(f"getting display dims {width} x {height}, fetched from IT8951.")

        
        self.setup_display_groups(width, height)  # configure the display buffers

        self.frame_buf = displayio.Bitmap(width, height, 0x10)  # 4 bit grayscale

        # self.clear()  full display refresh in mode

        x_start = random.randint(0, width-101)
        y_start = random.randint(0, height-101)

        for i in range(100):
            for j in range(100):
                self.frame_buf[x_start+i, y_start+j] = 0xF

        # keep track of what we have updated,
        # so that we can automatically do partial updates of only the
        # relevant portions of the display
        self.prev_frame = None

        self.track_gray = track_gray
        if track_gray:
            # keep track of what has changed since the last grayscale update
            # so that we make sure we clear any black/white intermediates
            # start out with no changes
            self.gray_change_bbox = None

    
    def setup_display_groups(self, disp_width, disp_height):
        # we set up our main "root group" for displayio
        self.root_group = displayio.Group()

        # and a loading screen
        self.splash_screen = displayio.Group()
        self.root_group.append(self.splash_screen)

        # and a subgroup that will hold the static elements of the UI 
        self.static_ui_group = displayio.Group()
        self.root_group.append(self.static_ui_group)

        # and a subgroup that will hold the static elements of the UI 
        self.text_labels = displayio.Group()
        self.root_group.append(self.text_labels)

    # TODO: remove test function
    def draw_square(self, x, y, fill):
        self.splash_screen[0].x = x
        self.splash_screen[0].y = y
        self.splash_screen[0].bitmap.fill(fill)


    def draw_full(self, mode=DisplayModes.GC16):
        '''
        Write the full image to the device, and display it using mode. Draws the
        displayio groups in their normal order stack. Multiple transmissions.
        '''

        # TODO make proper recursive check

        # load the different sprites into memory sequentially # TODO: can we flatten beforehand?
        for group in self.root_group:
            if not group.hidden:
                for item in group:
                    if isinstance(item, displayio.TileGrid):
                        print("drawing tilegrid")
                        self.draw_partial(item, mode, skip_show=True)
                    # elif isinstance(item, adafruit_imageload.Label):
                    #     print("drawing label")
                    #     for letter in item:
                    #         print(letter)


        # redraw the entire display
        self.show_buffer((0,0), self.display_dims, mode)

    def draw_partial(self, tile, mode=DisplayModes.GC16, skip_show=False):
        '''
        Write only the rectangle bounding the pixels of the image that have changed
        since the last call to draw_full or draw_partial
        '''

        print(f"-- tile is:")
        print(tile)

        pixels = tile.bitmap
        xy = (tile.x, tile.y)
        dims = (tile.tile_width, tile.tile_height)

        assert xy[0] >= 0, "cannot draw with negative X origin"
        assert xy[1] >= 0, "cannot draw with negative Y origin"

        print(dims)
        if not skip_show:
            self.update(pixels, xy, dims, mode)
        else:
            self.update_buffer(pixels, xy, dims)

    def clear(self):
        '''
        Clear display, device image buffer, and frame buffer (e.g. at startup)
        '''
        self.fill(0xF)
    
    def fill(self, color):
        raise NotImplementedError

    def update(self, data, xy, dims, mode):
        raise NotImplementedError
    
    def update_buffer(self, data, xy, dims, mode):
        raise NotImplementedError
    
    def show_buffer(self, data, xy, dims, mode):
        raise NotImplementedError


class AutoEPDDisplay(AutoDisplay):
    '''
    This class initializes the EPD, and uses it to display the updates
    '''

    def __init__(self, epd=None, vcom=-2.06,
                 bus=0, device=0, spi_hz=24000000,
                 **kwargs):

        epd = EPD(vcom=vcom)

        self.epd = epd
        AutoDisplay.__init__(self, self.epd.width, self.epd.height, **kwargs)

    def update(self, data, xy, dims, mode=DisplayModes.GC16):
        self.update_buffer(data, xy, dims)
        self.show_buffer(xy, dims, mode)

    def update_buffer(self, data, xy, dims):
        # send image to controller
        self.epd.wait_display_ready()

        self.epd.load_img_area(
            data,
            xy=xy,
            dims=dims
        )

    def show_buffer(self, xy, dims, mode=DisplayModes.GC16):
        self.epd.display_area(
            xy,
            dims,
            mode
        )

    def fill(self, color):
        # transmit single color for each pixel over SPI
        self.epd.load_single_color(color)

        # and show the fill color
        self.epd.display_area(
            (0,0),
            (self.epd.width, self.epd.height),
            display_mode=DisplayModes.GC16
        )
