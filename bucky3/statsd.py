# -*- coding: utf-8 -
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
#
# Copyright 2011 Cloudant, Inc.


import re
import bucky3.module as module


class StatsDServer(module.MetricsSrcProcess, module.UDPConnector):
    def __init__(self, *args):
        super().__init__(*args)
        self.socket = None
        self.timers = {}
        self.histograms = {}
        self.gauges = {}
        self.counters = {}
        self.sets = {}
        self.current_timestamp = self.last_timestamp = 0
        # Some of those are illegal in Graphite, so Carbon module has to handle them separately.
        self.metadata_regex = re.compile('^([a-zA-Z][a-zA-Z0-9_]*)[:=]([a-zA-Z0-9_:=\-\+\@\?\#\.\/\%\<\>\*\;\&\[\]]+)$', re.ASCII)

    def flush(self, monotonic_timestamp, system_timestamp):
        self.last_timestamp = self.current_timestamp
        self.current_timestamp = monotonic_timestamp
        self.enqueue_timers(system_timestamp)
        self.enqueue_histograms(system_timestamp)
        self.enqueue_counters(system_timestamp)
        self.enqueue_gauges(system_timestamp)
        self.enqueue_sets(system_timestamp)
        return super().flush(monotonic_timestamp, system_timestamp)

    def init_config(self):
        super().init_config()
        percentile_thresholds = self.cfg.get('percentile_thresholds', ())
        self.percentile_thresholds = sorted(set(round(float(t), 2) for t in percentile_thresholds if t > 0 and t <= 100))
        self.histogram_selector = self.cfg.get('histogram_selector')

    def run(self):
        super().run(loop=False)
        self.current_timestamp = self.last_timestamp = module.monotonic_time()
        while True:
            try:
                self.socket = self.socket or self.get_udp_socket(bind=True)
                data, addr = self.socket.recvfrom(65535)
                self.handle_packet(data, addr)
            except InterruptedError:
                pass

    def enqueue(self, bucket, stats, timestamp, metadata):
        if 'bucket' in metadata:
            bucket = metadata['bucket']
            del metadata['bucket']
        self.buffer.append((bucket, stats, timestamp, metadata))

    def enqueue_timers(self, system_timestamp):
        interval = self.current_timestamp - self.last_timestamp
        timeout = self.cfg['timers_timeout']
        bucket = self.cfg['timers_bucket']
        for k, (recv_timestamp, cust_timestamp, v) in tuple(self.timers.items()):
            if system_timestamp - recv_timestamp > timeout:
                del self.timers[k]
                continue

            self.timers[k] = recv_timestamp, cust_timestamp, []

            if not v:
                # Skip timers that haven't collected any values
                self.enqueue(bucket, dict(count=0.0, count_ps=0.0), cust_timestamp or system_timestamp, dict(k))
                continue

            v.sort()
            count = len(v)
            thresholds = ((count if t == 100 else (t * count) // 100, t) for t in self.percentile_thresholds)

            try:
                next_i, next_t = next(thresholds)
                vlen = vsum = vsum_squares = 0
                for i, x in enumerate(v):
                    vlen += 1
                    vsum += x
                    vsum_squares += x * x
                    while i >= next_i - 1:
                        mean = vsum / vlen
                        stats = dict(
                            count=vlen,
                            count_ps=vlen/interval,
                            lower=v[0],
                            upper=x,
                            sum=vsum,
                            sum_squares=vsum_squares,
                            mean=mean
                        )
                        if vlen > 1:
                            var = (vsum_squares - 2 * mean * vsum + vlen * mean * mean) / (vlen - 1)
                            stats['stdev'] = var ** 0.5
                        metadata = dict(percentile=str(next_t))
                        metadata.update(k)
                        self.enqueue(bucket, stats, cust_timestamp or system_timestamp, metadata)
                        next_i, next_t = next(thresholds)
            except StopIteration:
                pass

    def enqueue_histograms(self, system_timestamp):
        interval = self.current_timestamp - self.last_timestamp
        timeout = self.cfg['histograms_timeout']
        bucket = self.cfg['histograms_bucket']
        for k, (recv_timestamp, cust_timestamp, selector, buckets) in tuple(self.histograms.items()):
            if system_timestamp - recv_timestamp > timeout:
                del self.histograms[k]
                continue
            for histogram_bucket, (vlen, vsum, vsum_squares, vmin, vmax) in tuple(buckets.items()):
                stats = dict(count=vlen, count_ps=vlen / interval)
                if vlen > 0:
                    mean = vsum / vlen
                    stats['lower'] = vmin
                    stats['upper'] = vmax
                    stats['sum'] = vsum
                    stats['sum_squares'] = vsum_squares
                    stats['mean'] = mean
                    if vlen > 1:
                        var = (vsum_squares - 2 * mean * vsum + vlen * mean * mean) / (vlen - 1)
                        stats['stdev'] = var ** 0.5
                metadata = dict(histogram=str(histogram_bucket))
                metadata.update(k)
                self.enqueue(bucket, stats, cust_timestamp or system_timestamp, metadata)
                buckets[histogram_bucket] = 0, 0, 0, None, None

    def enqueue_sets(self, system_timestamp):
        timeout = self.cfg['sets_timeout']
        bucket = self.cfg['sets_bucket']
        for k, (recv_timestamp, cust_timestamp, v) in tuple(self.sets.items()):
            if system_timestamp - recv_timestamp <= timeout:
                self.enqueue(bucket, {"count": float(len(v))}, cust_timestamp or system_timestamp, dict(k))
                self.sets[k] = recv_timestamp, cust_timestamp, set()
            else:
                del self.sets[k]

    def enqueue_gauges(self, system_timestamp):
        timeout = self.cfg['gauges_timeout']
        bucket = self.cfg['gauges_bucket']
        for k, (recv_timestamp, cust_timestamp, v) in tuple(self.gauges.items()):
            if system_timestamp - recv_timestamp <= timeout:
                self.enqueue(bucket, float(v), cust_timestamp or system_timestamp, dict(k))
            else:
                del self.gauges[k]

    def enqueue_counters(self, system_timestamp):
        interval = self.current_timestamp - self.last_timestamp
        timeout = self.cfg['counters_timeout']
        bucket = self.cfg['counters_bucket']
        for k, (recv_timestamp, cust_timestamp, v) in tuple(self.counters.items()):
            if system_timestamp - recv_timestamp <= timeout:
                stats = {
                    'rate': float(v) / interval,
                    'count': float(v)
                }
                self.enqueue(bucket, stats, cust_timestamp or system_timestamp, dict(k))
                self.counters[k] = recv_timestamp, cust_timestamp, 0
            else:
                del self.counters[k]

    def handle_packet(self, data, addr=None):
        # Adding a bit of extra sauce so clients can
        # send multiple samples in a single UDP packet.
        try:
            recv_timestamp, data = round(module.system_time(), 3), data.decode("ascii")
        except UnicodeDecodeError:
            return
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.handle_line(recv_timestamp, line)

    def handle_line(self, recv_timestamp, line):
        # DataDog special packets for service check and events, ignore them
        if line.startswith('sc|') or line.startswith('_e{'):
            return
        try:
            recv_timestamp, cust_timestamp, line, metadata = self.handle_metadata(recv_timestamp, line)
        except ValueError:
            return
        if not line:
            return
        bits = line.split(":")
        if len(bits) < 2:
            return
        name = bits.pop(0)
        if not name.isidentifier():
            return
        key, metadata = self.handle_key(name, metadata)
        if not key:
            return

        # I'm not sure if statsd is doing this on purpose
        # but the code allows for name:v1|t1:v2|t2 etc etc.
        # In the interest of compatibility, I'll maintain
        # the behavior.
        for sample in bits:
            if "|" not in sample:
                continue
            fields = sample.split("|")
            valstr = fields[0]
            if not valstr:
                continue
            typestr = fields[1]
            ratestr = fields[2] if len(fields) > 2 else None
            try:
                if typestr == "ms":
                    self.handle_timer(recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr)
                elif typestr == "h":
                    self.handle_histogram(recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr)
                elif typestr == "g":
                    self.handle_gauge(recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr)
                elif typestr == "s":
                    self.handle_set(recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr)
                else:
                    self.handle_counter(recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr)
            except ValueError:
                pass

    def handle_metadata(self, recv_timestamp, line):
        # http://docs.datadoghq.com/guides/dogstatsd/#datagram-format
        bits = line.split("|#", 1)  # We allow '#' in tag values, too
        cust_timestamp, metadata = None, {}
        if len(bits) < 2:
            return recv_timestamp, cust_timestamp, line, metadata
        for i in bits[1].split(","):
            # DataDog docs / examples use key:value, we also handle key=value.
            m = self.metadata_regex.match(i)
            if not m:
                return None, None, None, None
            k, v = m.group(1), m.group(2)
            if k == 'timestamp':
                cust_timestamp = float(v)
                # 2524608000 = secs from epoch to 1 Jan 2050
                if cust_timestamp > 2524608000:
                    cust_timestamp /= 1000
                if cust_timestamp < recv_timestamp - 600 or cust_timestamp > recv_timestamp + 600:
                    raise ValueError()
                cust_timestamp = round(cust_timestamp, 3)
            elif k == 'bucket':
                if not v.isidentifier():
                    raise ValueError()
                metadata[k] = v
            else:
                metadata[k] = v
        return recv_timestamp, cust_timestamp, bits[0], metadata

    def handle_key(self, name, metadata):
        metadata.update(name=name)
        key = tuple((k, metadata[k]) for k in sorted(metadata.keys()))
        return key, metadata

    def handle_timer(self, recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr):
        val = float(valstr)
        if key in self.timers:
            buf = self.timers[key][2]
            buf.append(val)
            self.timers[key] = recv_timestamp, cust_timestamp, buf
        else:
            self.timers[key] = recv_timestamp, cust_timestamp, [val]

    def handle_histogram(self, recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr):
        if self.histogram_selector is None:
            return
        val = float(valstr)
        histogram = self.histograms.get(key)
        if histogram is None:
            selector = self.histogram_selector(metadata)
            if selector is None:
                return
            buckets = {}
        else:
            selector = histogram[2]
            buckets = histogram[3]
        for k, f in selector:
            if f(val):
                vlen, vsum, vsum_squares, vmin, vmax = buckets.get(k, (0, 0, 0, None, None))
                if vmin is None:
                    vmin = val
                if vmax is None:
                    vmax = val
                buckets[k] = (
                    vlen + 1, vsum + val, vsum_squares + val * val, min(val, vmin), max(val, vmax)
                )
                self.histograms[key] = recv_timestamp, cust_timestamp, selector, buckets
                return

    def handle_gauge(self, recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr):
        val = float(valstr)
        delta = valstr[0] in "+-"
        if delta and key in self.gauges:
            self.gauges[key] = recv_timestamp, cust_timestamp, self.gauges[key][2] + val
        else:
            self.gauges[key] = recv_timestamp, cust_timestamp, val

    def handle_set(self, recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr):
        if key in self.sets:
            buf = self.sets[key][2]
            buf.add(valstr)
            self.sets[key] = recv_timestamp, cust_timestamp, buf
        else:
            self.sets[key] = recv_timestamp, cust_timestamp, {valstr}

    def handle_counter(self, recv_timestamp, cust_timestamp, key, metadata, valstr, ratestr):
        if ratestr and ratestr[0] == "@":
            rate = float(ratestr[1:])
            if rate > 0 and rate <= 1:
                val = float(valstr) / rate
            else:
                return
        else:
            val = float(valstr)
        if key in self.counters:
            val += self.counters[key][2]
        self.counters[key] = recv_timestamp, cust_timestamp, val
