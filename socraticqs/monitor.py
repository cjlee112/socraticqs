#import Queue
#import thread

class TtyMonitor(object):
    def __init__(self, tty='wf'):
        ## self.queue = Queue.Queue() # thread-safe mechanism
        print '''Please monitor this server in another window by typing:
        cat /dev/pty%s
This thread will block until you start that monitor process...''' % tty
        self.ifile = open('/dev/tty' + tty, 'w')
    ##     self.threadID = thread.start_new_thread(self.sender, ())

    ## def sender(self):
    ##     self.on = True
    ##     while self.on:
    ##         msg = self.queue.get()
    ##         print >>self.ifile, msg

    def message(self, msg):
        ## if exit:
        ##     self.on = False
        ## self.queue.put(msg)
        print >> self.ifile, msg # file writing is thread-safe

    def __del__(self):
        self.ifile.close()
