##
# DIRECT import of https://raw.githubusercontent.com/stanford-futuredata/ASAP/master/ASAP.py
##

import math
import numpy.fft
from decimal import Decimal


def smooth(data, resolution=1000):
    ildr = int(len(data) / resolution)
    data = SMA(data, ildr, ildr)
    acf = ACF(data, round(len(data) / 10))
    peaks = acf.peaks
    orig_kurt = acf.kurtosis
    min_obj = acf.roughness
    window_size = 1
    lb = 1

    largest_feasible = -1
    tail = len(data) / 10
    for i in range(len(peaks) - 1, -1, -1):
        w = peaks[i]

        if w < lb or w == 1:
            break

        elif math.sqrt(1 - acf.correlations[w]) * window_size > math.sqrt(1 - acf.correlations[window_size]) * w:
            continue

        smoothed = SMA(data, w, 1)
        metrics = Metrics(smoothed)
        if metrics.roughness < min_obj and metrics.kurtosis >= orig_kurt:
            min_obj = metrics.roughness
            window_size = w
            lb = round(
                max(w * math.sqrt((acf.max_acf - 1) / (acf.correlations[w] - 1)), lb))

    if largest_feasible > 0:
        if largest_feasible < len(peaks) - 2:
            tail = peaks[largest_feasible + 1]
        lb = max(lb, peaks[largest_feasible] + 1)

    window_size = binary_search(
        lb, tail, data, min_obj, orig_kurt, window_size)
    return SMA(data, window_size, 1)


def binary_search(head, tail, data, min_obj, orig_kurt, window_size):
    while head <= tail:
        w = round((head + tail) / 2.0)
        smoothed = SMA(data, w, 1)
        metrics = Metrics(smoothed)
        if metrics.kurtosis >= orig_kurt:
            if metrics.roughness < min_obj:
                window_size = w
                min_obj = metrics.roughness
            head = w + 1
        else:
            tail = w - 1
    return window_size


def SMA(data, _range, slide):
    ret = []
    s = 0.0
    c = 0.0
    window_start = 0
    for i in range(len(data)):
        if data[i] is None:
            data[i] = 0  # have to force a 0 to keep steps in order
        if i - window_start >= _range or i == len(data) - 1:
            if i == len(data) - 1 or c == 0:
                s += data[i]
                c += 1
            ret.append(s / c)
            old_start = window_start
            while window_start < len(
                    data) and window_start - old_start < slide:
                if data[window_start] is None:
                    # have to force a 0 to keep steps in order
                    data[window_start] = 0
                s -= data[window_start]
                c -= 1
                window_start += 1
        s += data[i]
        c += 1
    return ret


def moving_average(data, _range):
    ret = numpy.cumsum(data, dtype=float)
    ret[_range:] = ret[_range:] - ret[:-_range]
    return ret[_range - 1:] / _range


def moving_average_slide(data, _range, slide):
    return moving_average(data, _range)[::slide]

# x = [42,75,3,5,99,22,88]
# assert SMA(x,3,1) == list(moving_average_slide(x,3,1))
# assert SMA(x,3,3) == list(moving_average_slide(x,3,3))


class Metrics(object):

    def __init__(self, values):
        self.set_values(values)

    def set_values(self, values):
        if not values:
            raise Exception("something is wrong, no values given")
        self.values = values
        self.r = self.d = self.k = self.m = self.s = None
        self.v = {}

    @property
    def mean(self):
        if self.m is None:
            self.m = (sum(self.values)) / len(self.values)
        return self.m

    def _var(self, p=2):
        if self.v.get(p) is None:
            m = self.mean
            self.v[p] = sum([Decimal(x - m) ** p for x in self.values])
        return self.v[p]

    @property
    def u2(self):
        return self._var(2)

    @property
    def var(self):
        return self._var(2) / len(self.values)

    @property
    def u4(self):
        return self._var(4)

    @property
    def std(self):
        if self.s is None:
            self.s = math.sqrt(self.var)
        return self.s

    @property
    def kurtosis(self):
        if self.k is None:
            self.k = (len(self.values) * self.u4) / (self.u2 ** 2)
        return self.k

    @property
    def diffs(self):
        if self.d is None:
            self.d = [self.values[i + 1] - self.values[i]
                      for i in range(len(self.values) - 1)]
        return self.d

    @property
    def roughness(self):
        if self.r is None:
            self.r = Metrics(self.diffs).std if self.diffs else 0
        return self.r


class ACF(Metrics):
    CORR_THRESH = 0.2

    def __init__(self, values, max_lag=None):
        super(ACF, self).__init__(values)
        if max_lag is None:
            max_lag = round(len(values) / 10)
        self.max_lag = int(max_lag)
        self.max_acf = 0.0
        self.correlations = [0.0] * self.max_lag

        # calculate() -- why make a new method for this?
        l = int(2.0 ** (int(math.log(len(self.values), 2.0)) + 1))
        fftv = values + ([0.0] * (l - len(values)))
        assert(len(fftv) == l)
        F_f = numpy.fft.fft(fftv)
        S_f = [x.real ** 2.0 + x.imag ** 2.0 for x in F_f]
        R_t = numpy.fft.ifft(S_f)

        for i in range(1, len(self.correlations), 1):
            self.correlations[i] = R_t[i].real / R_t[0].real

        # findPeaks() -- may as well just precalc this too
        self.peaks = []
        if len(self.correlations) > 1:
            positive = self.correlations[1] > self.correlations[0]
            max = 1
            for i in range(2, len(self.correlations), 1):
                if not positive and self.correlations[
                        i] > self.correlations[i - 1]:
                    max = i
                    positive = not positive
                elif positive and self.correlations[i] > self.correlations[max]:
                    max = i
                elif positive and self.correlations[i] < self.correlations[i - 1]:
                    if max > 1 and self.correlations[max] > self.CORR_THRESH:
                        self.peaks.append(max)
                        if self.correlations[max] > self.max_acf:
                            self.max_acf = self.correlations[max]
                    positive = not positive
