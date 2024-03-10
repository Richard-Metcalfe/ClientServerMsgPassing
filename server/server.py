import argparse
from sys import stdout as sys_stdout
import socket
import selectors
import traceback
import logging
from pathlib import Path
from common.message import ServerSideMessage
from common.fileactions import FileActionHandler


host = '127.0.0.1'
port = 50001


def accept_connection(sock: socket, selector, directory, log):
    """ Callback for new connection
    :param sock: the socket on which to accept the new connection
    :param selector: the which the connection is registered with
    :param directory: the directory where the changes on the client are mirrored
    :param logger: the log
    """
    new_connection, address = sock.accept()
    log.info("accepted connection from {}".format(address))
    new_connection.setblocking(False)
    file_action_handler = FileActionHandler(directory, log)
    message = ServerSideMessage(selector, new_connection, address, file_action_handler)
    selector.register(new_connection, selectors.EVENT_READ, data=message)


def run_server(address, selector, directory: Path, log):
    if not directory.exists():
        log.error("The path provided does not exist")
        return
    if not directory.is_dir():
        log.error("The path provided is not a directory")
        return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # To avoid address already in use Exception set the option to RESUSEADDR
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setblocking(False)
    server.bind(address)
    server.listen()

    log.info("listening on {}".format(address))

    # set the data to None initially. It will be set to a ServerMessage object
    # after the connection is accepted.
    selector.register(server, selectors.EVENT_READ, data=None)

    try:
        while True:
            try:
                events = selector.select(timeout=5)
                for key, mask in events:
                    if key.data is None:
                        accept_connection(key.fileobj, selector, directory, log)
                    else:
                        message = key.data
                        try:
                            message.process_events(mask)
                        except (SystemExit, KeyboardInterrupt):
                            log.info("keyboard interrupt, stopping server")
                            message.close()
                            break
                        except Exception:
                            log.error("Server error: exception for address {}\n{}".format(message.address, traceback.format_exc()))
                            message.close()

            except (SystemExit, KeyboardInterrupt):
                log.info("keyboard interrupt, stopping server")
                break
    except (SystemExit, KeyboardInterrupt):
        log.info("keyboard interrupt, stopping server")
    finally:
        selector.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--directory", required=True, type=int,
                        help="the directory where file changes are synchronised")

    parser = argparse.ArgumentParser(prog='Directory Synchronized Server',
                                     description='Receives file any changes for a client and keeps those changes synchronised with remote client')
    parser.add_argument('-d', '--directory', help='the path of the directory where changes are stored',
                        type=Path,
                        required=True)

    parsed_args = parser.parse_args()

    """ Set up the logging"""
    log = logging.getLogger('file synchronization server')
    log.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys_stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    log.debug("name: {}, type: {}, exists: {}, is dir: {}".format(parsed_args.directory, type(parsed_args.directory),
                                                                  parsed_args.directory.exists(),
                                                                  parsed_args.directory.is_dir()))

    sel = selectors.DefaultSelector()
    server_address = (host, port)
    dir_path = Path(parsed_args.directory)

    log.info('starting server on {} port {}'.format(*server_address))
    run_server(server_address, sel, dir_path, log)
