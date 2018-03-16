from mpl_finance import candlestick_ohlc
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import logging
import math

from analysis.backtest_trader import SimulatedTrader
from utils import set_options, config, format_value

logger = logging.getLogger()


class Plot():

    def __init__(self, size=(), subplot_opts={}, custom_config=None):
        _config = custom_config if custom_config else config
        self.config = _config['matplot']
        self._config = _config

        # Create subplots, to access subplots use indexing,
        # eg. ax[0][1] for upper right subplot
        self.fig, self.axs = plt.subplots(**subplot_opts)
        self.set_active_subplot()  # set to first subplot automatically

        # Change window size
        if not size:
            size = tuple(self.config['window_size'])

        self.fig.set_size_inches(size[0], size[1])

    def set_active_subplot(self, row=0, col=0):
        """ Set currently active subplut to make user easier to change subplots to plot. """
        if not isinstance(self.axs, np.ndarray):
            # make a single subplot two dimensional (easier to index)
            self.axs = np.array([self.axs])

        dim = self.axs.shape
        if len(dim) is 1:
            if row > 0 and col > 0:
                raise ValueError(f"({row}, {col}) index is invalid for one dimensional subplots.")

            n = max(row, col)
            self.ax = self.axs[n]

        elif len(dim) == 2:
            if row >= dim[0] or col >= dim[1]:
                raise ValueError(f"({row}, {col}) index is invalid for {dim} subplots.")

            self.ax = self.axs[row][col]

    def plot_ohlc(self, ohlc, fmt="%m-%d %H:%M", **options):
        # TODO: Add mouse motion detection for tracking both y values

        def add_percentage_yaxis(ax):
            ticks = ax.get_yticks()
            ymin, ymax = ax.get_ylim()

            mean = (ohlc.high.max() + ohlc.low.min()) / 2
            mean = self.nearest_tick(mean, ticks)
            perc_max = (ymax / mean - 1) * 100
            perc_min = (ymin / mean - 1) * 100

            ax2 = ax.twinx()
            ax2.set_ylim(perc_min, perc_max)
            ax2.set_ylabel('(%)')

        if len(ohlc) == 0:
            logger.warning("No ohlc to plot.")
            return

        tf = int(config['analysis']['indicator_tf'][:-1])
        opts = {
            'width': 1 / math.log(len(ohlc)) / 7 * tf,
            'colorup': 'g',
            'colordown': 'r',
            'alpha': 1
        }
        set_options(options, **opts)

        dt_name = ohlc.index.name
        dat = ohlc.reset_index()[[dt_name, "open", "high", "low", "close"]]
        dat[dt_name] = dat[dt_name].map(mdates.date2num)

        ax = self.ax
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        ax.set_xlim(left=ohlc.index[0], right=ohlc.index[-1])
        plt.xticks(rotation=30)

        # options: which=('major')/'minor'/'both', axis=('both')/'x'/'y'
        ax.grid(True, which='both', axis='both')

        candlestick_ohlc(ax, dat.values, **options)
        add_percentage_yaxis(ax)

    def plot_order_annotation(self, orders, ohlc):
        """
            Param
                orders: List of orders
                ohlc: DataFrame used to plot ohlc
        """
        ## TODO: use hover to display order's information

        for order in orders:

            if order['canceled']:
                continue

            if order['margin']:
                # Annotate margin open
                side = order['side']
                time = order['open_time']
                price = format_value(order['open_price'])
                cost = format_value(order['cost'])
                # text = f"#{order['#']}\nmargin\nopen\nP: {price}\nV: {cost}"
                text = f"#{order['#']}"
                self._ohlc_order_annotate(ohlc, side, time, text)

                # Annotate margin close
                side = 'buy' if order['side'] == 'sell' else 'sell'
                time = order['close_time']
                price = format_value(order['close_price'])
                earn = format_value(order['close_price'] * order['amount'] * (1-self._config['analysis']['fee']))
                # text = f"#{order['#']}\nmargin\nclose\nP: {price}\nV: {earn}"
                text = f"#{order['#']}"
                self._ohlc_order_annotate(ohlc, side, time, text)

            else: # Annotate normal orders
                side = order['side']
                time = order['close_time']
                price = format_value(order['open_price'])
                cost = format_value(order['cost'])
                if side == 'buy':
                    earn = format_value(order['amount'])
                else:
                    earn = format_value(order['amount'] * order['open_price'])
                # text = f"#{order['#']}\nnormal\nP: {price}\nV: {cost}/{earn}"
                text = f"#{order['#']}"
                self._ohlc_order_annotate(ohlc, side, time, text)

    def _ohlc_order_annotate(self, ohlc, side, time, text):
        ymin, ymax = self.ax.get_ylim()
        y_delta_head = (ymax - ymin) / 70
        y_delta_tail = y_delta_head * 2

        if side == 'sell':
            y_value = ohlc.high.asof(time)
            color = 'red'
            v_align =  'top'
        else:
            y_value = ohlc.low.asof(time)
            y_delta_head *= -1
            y_delta_tail *= -1
            color = 'green'
            v_align =  'down'

        opts = {
            'xy': (time, y_value + y_delta_head),
            'xytext': (time, y_value + y_delta_tail * 2),
            'arrowprops': dict(facecolor=color, headwidth=10, width=5, headlength=5),
            'horizontalalignment': 'center',
            'verticalalignment': v_align
        }
        self.ax.annotate(text, **opts)

    def legend(self, **options):
        self.ax.legend(loc='best', **options)

    def show(self):
        plt.show()

    def tight_layout(self):
        plt.tight_layout()

    @staticmethod
    def nearest_tick(v, ticks):
        tmp = ticks
        if not isinstance(ticks, np.ndarray):
            tmp = np.array(tmp)

        tmp = abs(tmp - v)
        return ticks[tmp == tmp.min()][0]

    @staticmethod
    def round_lim(lim, interval):
        min, max = lim
        max += interval - max % interval
        min -= min % interval
        return min, max
