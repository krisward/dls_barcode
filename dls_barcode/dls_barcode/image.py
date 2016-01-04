from pkg_resources import require;  require('numpy')
import cv2

class CvImage:
    """Class that wraps an OpenCV image and can perform various
    operations on it that are useful in this program.
    """

    BLUE = (255,0,0)
    RED = (0,0,255)
    GREEN = (0,255,0)

    YELLOW = (0,255,255)
    CYAN = (255,255,0)
    MAGENTA = (255,0,255)

    ORANGE = (0,128,255)
    PURPLE = (255,0,128)

    CurrentWebcamFrame = None


    def __init__(self, filename, img=None):
        if filename is not None:
            self.img = cv2.imread(filename)
        else:
            self.img = img

    def save_as(self, filename):
        """ Write an OpenCV image to file """
        cv2.imwrite(filename, self.img)

    def popup(self):
        """Pop up a window to display an image until a key is pressed (blocking)."""
        cv2.imshow('dbg', self.img)
        cv2.waitKey(0)

    def draw_rectangle(self, roi, color, thickness=2):
        top_left = tuple([roi[0], roi[1]])
        bottom_right = tuple([roi[2], roi[3]])
        cv2.rectangle(self.img, top_left, bottom_right, color, thickness=thickness)

    def draw_circle(self, center, radius, color, thickness=2):
        cv2.circle(self.img, tuple(center), int(radius), color, thickness=thickness)

    def draw_dot(self, center, color, thickness=5):
        cv2.circle(self.img, tuple(center), radius=0, color=color, thickness=thickness)

    def draw_line(self, p1, p2, color, thickness=2):
        cv2.line(self.img, p1, p2, color, thickness=thickness)

    def draw_text(self, text, position, color, centered=False):
        if centered:
            textsize = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fontScale=1.5, thickness=3)[0]
            position = (position[0]-textsize[0]/2, position[1]+textsize[1]/2)
        cv2.putText(self.img, text, position, cv2.FONT_HERSHEY_SIMPLEX, fontScale=1.5, color=color, thickness=3)

    def to_grayscale(self):
        """Convert the image to a grey image.
        """
        if len(self.img.shape) in (3, 4):
            gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
            return CvImage(filename=None, img=gray)
        else:
            assert len(self.img.shape) == 2
            return CvImage(filename=None, img=self.img)

    def draw_puck_template(self, puck, color):
        self.draw_dot(puck.puck_center, color)
        self.draw_circle(puck.puck_center, puck.puck_radius, color)
        self.draw_circle(puck.puck_center, puck.center_radius, color)
        for center in puck.template_centers:
            self.draw_dot(center, color)
            self.draw_circle(center, puck.slot_radius, color)

    def draw_puck_pin_circles(self, puck, color):
        for circle in puck.pin_circles:
            self.draw_circle(center=circle[0], radius=circle[1], color=color)
            self.draw_dot(center=circle[0], color=color)

    def draw_puck_pin_rois(self, puck, color):
        for roi in puck.pin_rois:
            self.draw_rectangle(roi, color)

    def draw_datamatrix_highlights(self, datamatricies, good_color, bad_color):
        for matrix in datamatricies:
            # Get the Finder Pattern for the datamatrix
            fp = matrix.finderPattern

            # draw circle and line highlights
            color = bad_color if matrix.data == None else good_color
            self.draw_line(fp.c1, fp.c2, color)
            self.draw_line(fp.c1, fp.c3, color)
            self.draw_text(text=str(matrix.pinSlot), position=fp.center, color=color, centered=True)
            for point in matrix.sampleLocations:
                self.draw_dot(tuple(point), color, 1)

    def crop_image(self, center, radius):
        self.img, _ = CvImage.sub_image(self.img, center, radius)

    @staticmethod
    def sub_image(img, center, radius):
        """ Returns a new (raw) OpenCV image that is a section of the existing image.
        The section is square with side length = 2*radius, and centered around the
        enter point
        """
        width = img.shape[1]
        height = img.shape[0]
        xstart = int(max(center[0] - radius, 0))
        xend = int(min(center[0] + radius, width))
        ystart = int(max(center[1] - radius, 0))
        yend = int(min(center[1] + radius, height))
        roi_rect = [xstart, ystart, xend, yend]
        return img[ystart:yend, xstart:xend], roi_rect

    @staticmethod
    def find_circle(img, minradius, maxradius):
        circle = cv2.HoughCircles(img, cv2.HOUGH_GRADIENT, dp=1.2,
            minDist=10000000, minRadius=int(minradius), maxRadius=int(maxradius))

        if circle is not None:
            circle = circle[0][0]
            center = [int(circle[0]), int(circle[1])]
            radius = int(circle[2])
            return [center, radius]
        else:
            return None


    @staticmethod
    def capture_image_from_camera():
        camera_port = 0
        camera = cv2.VideoCapture(camera_port)

        ramp_frames = 60
        for i in range(ramp_frames):
            ret, frame = camera.read()
        print "Taking image"
        ret, frame = camera.read()
        return CvImage(None, frame)

    @staticmethod
    def stream_webcam():
        cap = cv2.VideoCapture(0)
        cap.set(3,1920)
        cap.set(4,1080)
        while(True):
            _, frame = cap.read()
            CvImage.CurrentWebcamFrame = frame
            small = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
            cv2.imshow('frame', small)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    @staticmethod
    def get_current_webcam_frame():
        return CvImage(None, CvImage.CurrentWebcamFrame)

