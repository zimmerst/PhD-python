import psutil
import os

def convert_bytes(bytes, precision=1):
    """ Function taken from 
        http://snipperize.todayclose.com/snippet/py/Converting-Bytes-to-Tb/Gb/Mb/Kb--14257/
    """
    bytes = float(bytes)
    if bytes >= 1099511627776:
        terabytes = bytes / 1099511627776
        size = '%.*fTB' % (precision,terabytes)
    elif bytes >= 1073741824:
        gigabytes = bytes / 1073741824
        size = '%.*fGB' % (precision,gigabytes)
    elif bytes >= 1048576:
        megabytes = bytes / 1048576
        size = '%.*fMB' % (precision,megabytes)
    elif bytes >= 1024:
        kilobytes = bytes / 1024
        size = '%.*fkB' % (precision,kilobytes)
    else:
        size = '%.*fB' % (precision,bytes)
    return size


def get_memory_usage(extra=None):
    """ Simple utility to monitor memory usage of my script. """
    ret = ''

    p = psutil.Process(os.getpid())

    rss, vms = p.get_memory_info()
    if extra is not None:
        ret += "Memory Usage %s:\n" % extra
    else:
        ret += "Memory Usage:\n"
    ret += ".. Resident memory: %s\n" % convert_bytes(rss)
    ret += ".. Virtual memory: %s\n" % convert_bytes(vms)
    percent = p.get_memory_percent()
    ret += ".. Memory percent %.1f%%" % percent
    return ret

def print_memory_usage(*args, **kwargs):
    print get_memory_usage(*args, **kwargs)
