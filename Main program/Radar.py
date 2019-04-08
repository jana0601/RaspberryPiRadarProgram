import time
import threading
import numpy as np
import queue
import copy       # import for static variable run in class

from acconeer_utils.clients.reg.client import RegClient
from acconeer_utils.clients.json.client import JSONClient
from acconeer_utils.clients import configs
from acconeer_utils import example_utils
from acconeer_utils.mpl_process import PlotProcess, PlotProccessDiedException, FigureUpdater


class Radar(threading.Thread):

    def __init__(self, HR_filter_queue, go):  # Lägg till RR_filter_queue som inputargument
        self.go = go
        # Setup for collecting data from radar
        self.args = example_utils.ExampleArgumentParser().parse_args()
        example_utils.config_logging(self.args)
        if self.args.socket_addr:
            self.client = JSONClient(self.args.socket_addr)
            # Test för att se vilken port som används av radarn
            print("RADAR Port = " + self.args.socket_addr)
        else:
            port = self.args.serial_port or example_utils.autodetect_serial_port()
            self.client = RegClient(port)

        self.client.squeeze = False
        self.config = configs.IQServiceConfig()
        self.config.sensor = self.args.sensors

        self.config.range_interval = [0.2, 0.6]  # Measurement interval
        self.config.sweep_rate = 100  # Frequency for collecting data
        self.config.gain = 1  # Gain between 0 and 1.
        self.time = 1  # Duration for a set amount of sequences
        self.seq = self.config.sweep_rate * self.time  # Amount of sequences during a set time and sweep freq

        self.info = self.client.setup_session(self.config)  # Setup acconeer radar session
        self.num_points = self.info["data_length"]  # Amount of data points per sampel

        # Vector for radar values from tracked data
        self.seq = 1200     # number of sequences to save
        self.peak_vector = np.zeros((1, self.seq), dtype=np.csingle)
        self.data_idx = 0  # Inedex for peak vector used for filtering
        self.data_matrix = np.zeros((self.seq, self.num_points))      # matrix for old data values
        self.I_peak = np.zeros((self.seq, 1))       # indexes of peaks

        self.HR_filter_queue = HR_filter_queue
        #self.a = a
        #self.RR_filter_queue = RR_filter_queue
        # Initiation for tracking method
        super(Radar, self).__init__()  # Inherit threading vitals

    # Loop which collects data from the radar, tracks the maximum peak and filters it for further signal processing. The final filtered data is put into a queue.
    def run(self):

        self.client.start_streaming()  # Starts Acconeers streaming server
        # static variable impported from bluetooth_app class (In final version)
        while not self.go:
            # for i in range(self.seq*2):
            self.get_data()
            self.tracker()
            self.filter_HeartRate()
            self.filter_RespRate()
            self.data_idx += 1
            if self.data_idx % self.config.sweep_rate == 0:
                print("Still getting data")
                self.HR_filter_queue.put(2)
            if self.data_idx >= self.seq:  # Resets matrix index to zero for filtering.
                self.data_idx = 0
        print("End of getting data from radar")

        self.client.disconnect()

    # Method to collect data from the streaming server
    def get_data(self):
        # self.data should be accessable from all other methods
        self.info, self.data = self.client.get_next()

    # Filter for heart rate using the last X sampels according to data_idx. Saves data to queue
    def filter_HeartRate(self):
        HR_peak_vector = copy.copy(self.peak_vector)
        for i in range(5):
            HR_peak_vector[0][i] = 0
        # self.HR_filter_queue.put(HR_peak_vector)

    # Filter for Respitory rate. Saves data to queue

    def filter_RespRate(self):
        # RR_peak_vector = copy.copy(self.peak_vector)
        # for i in range(5):
        #     RR_peak_vector[0][i] = 0
        # self.RR_filter_queue.put(RR_peak_vector)
        pass

    # Tracks the maximum peak from collected data which is filtered for further signal processing
    def tracker(self):
