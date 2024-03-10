#!/usr/bin/env python3
import argparse
import logging
import pathlib
import sys
import time
from os import path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
try:
    from client_requests import RequestDispatcher
except ImportError:
    from .client_requests import RequestDispatcher

host = '127.0.0.1'
port = 50001


class MonitoredFileEventHandler(FileSystemEventHandler):
    def __init__(self, request_dispatcher: RequestDispatcher):
        """
        Handles the events triggered by file system changes to the monitored directory
        :type mon: DirectoryMonitor - callback for file operations
        TODO: Handle events that act on subdirectory
        """
        self.request_dispatcher = request_dispatcher

    @staticmethod
    def on_any_event(event):
        if event.is_directory:
            #print("Watchdog received event on subdirectory: {}".format(event.src_path))
            '''
            TODO: handle recurse into subdirectories
            '''
        elif event.event_type == 'created':
            # Event is created, you can process it now
            print("Watchdog received created event: {}".format(event.src_path))
        elif event.event_type == 'modified':
            # Event is modified, you can process it now
            print("Watchdog received modified event: {}".format(event.src_path))
        elif event.event_type == 'moved':
            print("Watchdog received moved event: {}".format(event.src_path))
        elif event.event_type == 'deleted':
            print("Watchdog received deleted event: {}".format(event.src_path))

    def on_created(self, event):
        if event.is_directory:
            return

        filename = path.basename(event.src_path)
        self.request_dispatcher.create_new_file_request(filename)

    def on_modified(self, event):
        if event.is_directory:
            return

        #print("Updating file: {}".format(event.src_path))
        filename = path.basename(event.src_path)
        self.request_dispatcher.update_file_request(filename)

    def on_moved(self, event):
        if event.is_directory:
            return

        #print("Moving file: {} to {}".format(event.src_path, event.dest_path))
        src_filename = path.basename(event.src_path)
        dest_filename = path.basename(event.dest_path)
        self.request_dispatcher.move_file_request(src_filename, dest_filename)

    def on_deleted(self, event):
        if event.is_directory:
            return

        filename = path.basename(event.src_path)
        self.request_dispatcher.delete_file_request(filename)


class DirectoryMonitor:
    def __init__(self, directory_path: pathlib.Path, logger):
        self.monitored_directory = directory_path
        self.observer = Observer()
        self.log = logger

    def run(self):
        if not self.monitored_directory.exists():
            self.log.error("The path provided does not exist")
            return
        if not self.monitored_directory.is_dir():
            self.log.error("The path provided is not a directory")
            return

        request_dispatcher = RequestDispatcher(self.monitored_directory, host, port)
        """
        Synchorizes the monitor directory with the remote by requesting a directory listing complete with file hashes
        for the remote directory and comparing this with the contents of the monitored directory
        :return:
        """
        request_dispatcher.enumerate_remote_directory()

        event_handler = MonitoredFileEventHandler(request_dispatcher)
        self.observer.schedule(event_handler, self.monitored_directory, recursive=False)
        self.observer.start()
        self.log.info("Starting monitoring {}".format(self.monitored_directory))
        try:
            while True:
                time.sleep(5)
        except:
            self.observer.stop()
            self.log.info("Stopped monitoring {}".format(self.monitored_directory))

        self.observer.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory", required=True, type=int, help="the directory to monitor")

    parser = argparse.ArgumentParser(prog='Directory Synchronization Client',
                                     description='Monitors a directory and synchonizes any changes with a remote server')
    parser.add_argument('-d', '--directory', help='the path of the monitored directory', type=pathlib.Path,
                        required=True)

    parsed_args = parser.parse_args()

    """ Set up the logging"""
    log = logging.getLogger('file synchronization client')
    log.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    log.debug("name: {}, type: {}, exists: {}, is dir: {}".format(parsed_args.directory, type(parsed_args.directory),
                                                                  parsed_args.directory.exists(),
                                                                  parsed_args.directory.is_dir()))

    monitor = DirectoryMonitor(parsed_args.directory, log)
    monitor.run()

    # close the log handlers
    for handler in log.handlers:
        handler.close()
        log.removeFilter(handler)
