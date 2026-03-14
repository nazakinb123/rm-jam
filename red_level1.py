#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: red level 1 tx
# Author: 13386
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio import analog
import math
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import iio
import sip
import threading



class red_level1(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "red level 1 tx", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("red level 1 tx")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "red_level1")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 2e6
        self.j1_sym_rate = j1_sym_rate = 500e3
        self.bc_sym_rate = bc_sym_rate = 250e3
        self.tx_lo = tx_lo = 432.7e6
        self.j1_sps = j1_sps = int(samp_rate / j1_sym_rate)
        self.j1_freq_dev = j1_freq_dev = 125e3
        self.j1_cf = j1_cf = 432.2e6
        self.bc_sps = bc_sps = int(samp_rate / bc_sym_rate)
        self.bc_cf = bc_cf = 433.2e6
        self.sens = sens = 2*3.1415926/samp_rate
        self.rx_lo = rx_lo = 432.7e6
        self.quad_gain = quad_gain = samp_rate/(2*3.1415926)
        self.norm_k = norm_k = 1.0/j1_freq_dev
        self.j1_shift = j1_shift = j1_cf - tx_lo
        self.j1_ntaps = j1_ntaps = 11 * j1_sps
        self.j1_alpha = j1_alpha = 0.25
        self.bc_shift = bc_shift = bc_cf - tx_lo
        self.bc_ntaps = bc_ntaps = 11 * bc_sps
        self.bc_freq_dev = bc_freq_dev = 62.5e3
        self.bc_alpha = bc_alpha = 0.25

        ##################################################
        # Blocks
        ##################################################

        self.root_raised_cosine_filter_0_0 = filter.interp_fir_filter_fff(
            j1_sps,
            firdes.root_raised_cosine(
                8,
                samp_rate,
                j1_sym_rate,
                j1_alpha,
                j1_ntaps))
        self.qtgui_time_sink_x_1 = qtgui.time_sink_f(
            1024, #size
            samp_rate, #samp_rate
            "after qd and mc j1", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_1.set_update_time(0.10)
        self.qtgui_time_sink_x_1.set_y_axis(-1, 1)

        self.qtgui_time_sink_x_1.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_1.enable_tags(True)
        self.qtgui_time_sink_x_1.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_1.enable_autoscale(True)
        self.qtgui_time_sink_x_1.enable_grid(False)
        self.qtgui_time_sink_x_1.enable_axis_labels(True)
        self.qtgui_time_sink_x_1.enable_control_panel(False)
        self.qtgui_time_sink_x_1.enable_stem_plot(False)


        labels = ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_1.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_1.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_1.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_1.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_1.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_1.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_1_win = sip.wrapinstance(self.qtgui_time_sink_x_1.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_time_sink_x_1_win)
        self.qtgui_histogram_sink_x_0 = qtgui.histogram_sink_f(
            1024,
            100,
            (-1),
            1,
            "",
            1,
            None # parent
        )

        self.qtgui_histogram_sink_x_0.set_update_time(0.10)
        self.qtgui_histogram_sink_x_0.enable_autoscale(True)
        self.qtgui_histogram_sink_x_0.enable_accumulate(False)
        self.qtgui_histogram_sink_x_0.enable_grid(False)
        self.qtgui_histogram_sink_x_0.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers= [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_histogram_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_histogram_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_histogram_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_histogram_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_histogram_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_histogram_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_histogram_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_histogram_sink_x_0_win = sip.wrapinstance(self.qtgui_histogram_sink_x_0.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_histogram_sink_x_0_win)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            "after_lpf_j1", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0.set_y_axis((-140), 10)
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(False)
        self.qtgui_freq_sink_x_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.top_layout.addWidget(self._qtgui_freq_sink_x_0_win)
        self.low_pass_filter_0 = filter.interp_fir_filter_ccf(
            1,
            firdes.low_pass(
                1,
                samp_rate,
                650e3,
                150e3,
                window.WIN_HAMMING,
                6.76))
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32('192.168.2.1' if '192.168.2.1' else iio.get_pluto_uri(), [True, True], 32768)
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency(int(rx_lo))
        self.iio_pluto_source_0.set_samplerate(int(samp_rate))
        self.iio_pluto_source_0.set_gain_mode(0, 'slow_attack')
        self.iio_pluto_source_0.set_gain(0, 64)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(False)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
        self.iio_pluto_sink_0_0 = iio.fmcomms2_sink_fc32('' if '' else iio.get_pluto_uri(), [True, True], 32768, True)
        self.iio_pluto_sink_0_0.set_len_tag_key('')
        self.iio_pluto_sink_0_0.set_bandwidth(20000000)
        self.iio_pluto_sink_0_0.set_frequency(int(tx_lo))
        self.iio_pluto_sink_0_0.set_samplerate(int(samp_rate))
        self.iio_pluto_sink_0_0.set_attenuation(0, 30)
        self.iio_pluto_sink_0_0.set_filter_params('Auto', '', 0, 0)
        self.digital_chunks_to_symbols_xx_0_0 = digital.chunks_to_symbols_bf([-3, -1, 1, 3], 1)
        self.blocks_vector_source_x_0_0 = blocks.vector_source_b([0x41,0x42,0x31,0x32,0x43,0x39], True, 1, [])
        self.blocks_rotator_cc_1 = blocks.rotator_cc((-2*3.1415926*j1_shift/samp_rate), False)
        self.blocks_rotator_cc_0_0 = blocks.rotator_cc((2*3.1415926*j1_shift/samp_rate), False)
        self.blocks_repack_bits_bb_0_0 = blocks.repack_bits_bb(8, 2, "", False, gr.GR_MSB_FIRST)
        self.blocks_multiply_const_vxx_1 = blocks.multiply_const_ff(norm_k)
        self.blocks_multiply_const_vxx_0_0 = blocks.multiply_const_ff(j1_freq_dev)
        self.blocks_keep_one_in_n_0 = blocks.keep_one_in_n(gr.sizeof_float*1, 4)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(quad_gain)
        self.analog_frequency_modulator_fc_0_0 = analog.frequency_modulator_fc(sens)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_frequency_modulator_fc_0_0, 0), (self.blocks_rotator_cc_0_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.blocks_multiply_const_vxx_1, 0))
        self.connect((self.blocks_keep_one_in_n_0, 0), (self.qtgui_histogram_sink_x_0, 0))
        self.connect((self.blocks_keep_one_in_n_0, 0), (self.qtgui_time_sink_x_1, 0))
        self.connect((self.blocks_multiply_const_vxx_0_0, 0), (self.analog_frequency_modulator_fc_0_0, 0))
        self.connect((self.blocks_multiply_const_vxx_1, 0), (self.blocks_keep_one_in_n_0, 0))
        self.connect((self.blocks_repack_bits_bb_0_0, 0), (self.digital_chunks_to_symbols_xx_0_0, 0))
        self.connect((self.blocks_rotator_cc_0_0, 0), (self.iio_pluto_sink_0_0, 0))
        self.connect((self.blocks_rotator_cc_1, 0), (self.low_pass_filter_0, 0))
        self.connect((self.blocks_vector_source_x_0_0, 0), (self.blocks_repack_bits_bb_0_0, 0))
        self.connect((self.digital_chunks_to_symbols_xx_0_0, 0), (self.root_raised_cosine_filter_0_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.blocks_rotator_cc_1, 0))
        self.connect((self.low_pass_filter_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.low_pass_filter_0, 0), (self.qtgui_freq_sink_x_0, 0))
        self.connect((self.root_raised_cosine_filter_0_0, 0), (self.blocks_multiply_const_vxx_0_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "red_level1")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_bc_sps(int(self.samp_rate / self.bc_sym_rate))
        self.set_j1_sps(int(self.samp_rate / self.j1_sym_rate))
        self.set_quad_gain(self.samp_rate/(2*3.1415926))
        self.set_sens(2*3.1415926/self.samp_rate)
        self.blocks_rotator_cc_0_0.set_phase_inc((2*3.1415926*self.j1_shift/self.samp_rate))
        self.blocks_rotator_cc_1.set_phase_inc((-2*3.1415926*self.j1_shift/self.samp_rate))
        self.iio_pluto_sink_0_0.set_samplerate(int(self.samp_rate))
        self.iio_pluto_source_0.set_samplerate(int(self.samp_rate))
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.samp_rate, 650e3, 150e3, window.WIN_HAMMING, 6.76))
        self.qtgui_freq_sink_x_0.set_frequency_range(0, self.samp_rate)
        self.qtgui_time_sink_x_1.set_samp_rate(self.samp_rate)
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(8, self.samp_rate, self.j1_sym_rate, self.j1_alpha, self.j1_ntaps))

    def get_j1_sym_rate(self):
        return self.j1_sym_rate

    def set_j1_sym_rate(self, j1_sym_rate):
        self.j1_sym_rate = j1_sym_rate
        self.set_j1_sps(int(self.samp_rate / self.j1_sym_rate))
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(8, self.samp_rate, self.j1_sym_rate, self.j1_alpha, self.j1_ntaps))

    def get_bc_sym_rate(self):
        return self.bc_sym_rate

    def set_bc_sym_rate(self, bc_sym_rate):
        self.bc_sym_rate = bc_sym_rate
        self.set_bc_sps(int(self.samp_rate / self.bc_sym_rate))

    def get_tx_lo(self):
        return self.tx_lo

    def set_tx_lo(self, tx_lo):
        self.tx_lo = tx_lo
        self.set_bc_shift(self.bc_cf - self.tx_lo)
        self.set_j1_shift(self.j1_cf - self.tx_lo)
        self.iio_pluto_sink_0_0.set_frequency(int(self.tx_lo))

    def get_j1_sps(self):
        return self.j1_sps

    def set_j1_sps(self, j1_sps):
        self.j1_sps = j1_sps
        self.set_j1_ntaps(11 * self.j1_sps)

    def get_j1_freq_dev(self):
        return self.j1_freq_dev

    def set_j1_freq_dev(self, j1_freq_dev):
        self.j1_freq_dev = j1_freq_dev
        self.set_norm_k(1.0/self.j1_freq_dev)
        self.blocks_multiply_const_vxx_0_0.set_k(self.j1_freq_dev)

    def get_j1_cf(self):
        return self.j1_cf

    def set_j1_cf(self, j1_cf):
        self.j1_cf = j1_cf
        self.set_j1_shift(self.j1_cf - self.tx_lo)

    def get_bc_sps(self):
        return self.bc_sps

    def set_bc_sps(self, bc_sps):
        self.bc_sps = bc_sps
        self.set_bc_ntaps(11 * self.bc_sps)

    def get_bc_cf(self):
        return self.bc_cf

    def set_bc_cf(self, bc_cf):
        self.bc_cf = bc_cf
        self.set_bc_shift(self.bc_cf - self.tx_lo)

    def get_sens(self):
        return self.sens

    def set_sens(self, sens):
        self.sens = sens
        self.analog_frequency_modulator_fc_0_0.set_sensitivity(self.sens)

    def get_rx_lo(self):
        return self.rx_lo

    def set_rx_lo(self, rx_lo):
        self.rx_lo = rx_lo
        self.iio_pluto_source_0.set_frequency(int(self.rx_lo))

    def get_quad_gain(self):
        return self.quad_gain

    def set_quad_gain(self, quad_gain):
        self.quad_gain = quad_gain
        self.analog_quadrature_demod_cf_0.set_gain(self.quad_gain)

    def get_norm_k(self):
        return self.norm_k

    def set_norm_k(self, norm_k):
        self.norm_k = norm_k
        self.blocks_multiply_const_vxx_1.set_k(self.norm_k)

    def get_j1_shift(self):
        return self.j1_shift

    def set_j1_shift(self, j1_shift):
        self.j1_shift = j1_shift
        self.blocks_rotator_cc_0_0.set_phase_inc((2*3.1415926*self.j1_shift/self.samp_rate))
        self.blocks_rotator_cc_1.set_phase_inc((-2*3.1415926*self.j1_shift/self.samp_rate))

    def get_j1_ntaps(self):
        return self.j1_ntaps

    def set_j1_ntaps(self, j1_ntaps):
        self.j1_ntaps = j1_ntaps
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(8, self.samp_rate, self.j1_sym_rate, self.j1_alpha, self.j1_ntaps))

    def get_j1_alpha(self):
        return self.j1_alpha

    def set_j1_alpha(self, j1_alpha):
        self.j1_alpha = j1_alpha
        self.root_raised_cosine_filter_0_0.set_taps(firdes.root_raised_cosine(8, self.samp_rate, self.j1_sym_rate, self.j1_alpha, self.j1_ntaps))

    def get_bc_shift(self):
        return self.bc_shift

    def set_bc_shift(self, bc_shift):
        self.bc_shift = bc_shift

    def get_bc_ntaps(self):
        return self.bc_ntaps

    def set_bc_ntaps(self, bc_ntaps):
        self.bc_ntaps = bc_ntaps

    def get_bc_freq_dev(self):
        return self.bc_freq_dev

    def set_bc_freq_dev(self, bc_freq_dev):
        self.bc_freq_dev = bc_freq_dev

    def get_bc_alpha(self):
        return self.bc_alpha

    def set_bc_alpha(self, bc_alpha):
        self.bc_alpha = bc_alpha




def main(top_block_cls=red_level1, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
