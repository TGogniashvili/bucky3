
debug = False
log_level = "INFO"
directory = "/var/lib/bucky"
process_join_timeout = 2
full_trace = False


metadata = []


sentry_enabled = False
sentry_dsn = None
sentry_log_level = "WARNING"
sentry_auto_log_stacks = False


statsd_ip = "127.0.0.1"
statsd_port = 8125
statsd_enabled = True
statsd_flush_time = 10.0
statsd_global_prefix = "stats"
statsd_prefix_counter = "counters"
statsd_prefix_timer = "timers"
statsd_prefix_set = "sets"
statsd_prefix_gauge = "gauges"
statsd_persistent_gauges = False
statsd_gauges_savefile = "gauges.save"
statsd_delete_counters = True
statsd_delete_timers = True
statsd_delete_sets = True
# `statsd_delete_gauges = True` would make gauges in practice useless, except if you get an absolute(!)
# value every flush-interval which would makes this setting irrelevant, so this option doesn't exist.
# send gauge value to graphite only if there was a change
statsd_onlychanged_gauges = True
# Disable this only if you want "bad line" be reported for lines with DataDog extensions
statsd_ignore_datadog_extensions = True
statsd_ignore_internal_stats = False
# Use metadata name=NAME instead of the original naming scheme
statsd_metadata_namespace = False
statsd_percentile_thresholds = [90]  # percentile thresholds for statsd timers
statsd_timer_mean = True
statsd_timer_upper = True
statsd_timer_lower = True
statsd_timer_count = True
statsd_timer_count_ps = True
statsd_timer_sum = True
statsd_timer_sum_squares = True
statsd_timer_median = True
statsd_timer_std = True


graphite_enabled = True
graphite_ip = "127.0.0.1"
graphite_port = 2003
graphite_max_reconnects = 60
graphite_reconnect_delay = 1
graphite_backoff_factor = 1.5
graphite_backoff_max = 60
graphite_pickle_enabled = False
graphite_pickle_buffer_size = 500


name_prefix = None
name_prefix_parts = None
name_postfix = None
name_postfix_parts = None
name_replace_char = '_'
name_strip_duplicates = True
name_host_trim = []


influxdb_enabled = False
influxdb_hosts = [
    "127.0.0.1:8089"
]


prometheus_enabled = False
prometheus_port = 9090
prometheus_timeout = 60
prometheus_path = 'metrics'


system_stats_enabled = False
system_stats_interval = 10
system_stats_filesystem_blacklist = ['tmpfs', 'aufs', 'rootfs', 'devtmpfs']
system_stats_filesystem_whitelist = None
system_stats_interface_blacklist = None
system_stats_interface_whitelist = None
system_stats_disk_blacklist = ['loop0', 'loop1', 'loop2', 'loop3', 'loop4', 'loop5', 'loop6', 'loop7']
system_stats_disk_whitelist = None


docker_stats_enabled = False
docker_stats_interval = 10
docker_stats_version = '1.22'
