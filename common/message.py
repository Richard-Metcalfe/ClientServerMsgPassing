import sys
import selectors
import json
import io
import struct
from abc import ABC, abstractmethod
from common.fileactions import FileActionHandler


def encode_json(obj, encoding):
    return json.dumps(obj, ensure_ascii=False).encode(encoding)


def decode_json(json_bytes, encoding):
    io_wrapper = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
    obj = json.load(io_wrapper)
    io_wrapper.close()
    return obj


def create_message(*, content_bytes, content_encoding):
    header = {'byteorder': sys.byteorder, 'content-encoding': content_encoding, 'content-length': len(content_bytes)}
    header_bytes = encode_json(header, "utf-8")
    msg_header = struct.pack(">H", len(header_bytes))
    message = msg_header + header_bytes + content_bytes
    return message


def create_response_content(content, content_encoding):
    response = dict(content_bytes=encode_json(content, content_encoding), content_encoding=content_encoding)
    return response


class AbstractMessage(ABC):
    @abstractmethod
    def __init__(self, selector, sock, address):
        self.selector = selector
        self.sock = sock
        self.address = address
        self.receive_buffer = b""
        self.send_buffer = b""
        self.header_length = None
        self.header = None

    def _set_selector_events_mask(self, mode):
        """
        Sets the selector to listen for the appropriate events: 'r', 'w', or 'rw'.
        :param mode the mode
        """
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {repr(mode)}.")
        self.selector.modify(self.sock, events, data=self)

    def _read(self):
        try:
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Need to catch this otherwise the socket might be unusable
            pass
        else:
            if data:
                self.receive_buffer += data
            else:
                raise RuntimeError("The peer has closed.")

    @abstractmethod
    def _write(self):
        pass

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    def read(self):
        self._read()

        if self.header_length is None:
            self.process_preheader()

        if self.header_length is not None:
            if self.header is None:
                self.process_header()

    @abstractmethod
    def write(self):
        pass

    def close(self):
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print("Error: selector.unregister() exception for {}: {}".format(self.address, repr(e)))

        try:
            self.sock.close()
        except OSError as e:
            print("Error: socket.close() exception for {} : {}".format(self.address, repr(e)))
        finally:
            self.sock = None

    def process_preheader(self):
        length = 2
        if len(self.receive_buffer) >= length:
            self.header_length = struct.unpack(">H", self.receive_buffer[:length])[0]
            self.receive_buffer = self.receive_buffer[length:]

    def process_header(self):
        length = self.header_length
        if len(self.receive_buffer) >= length:
            self.header = decode_json(self.receive_buffer[:length], "utf-8")
            self.receive_buffer = self.receive_buffer[length:]
            for required in (
                    "byteorder",
                    "content-length",
                    "content-encoding",
            ):
                if required not in self.header:
                    raise ValueError(f'Missing required header "{required}".')


class ServerSideMessage(AbstractMessage):
    def __init__(self, selector, sock, address, action_handler: FileActionHandler):
        super().__init__(selector, sock, address)
        self.request = None
        self.response_created = False
        self.file_action_handler = action_handler

    def _write(self):
        if self.send_buffer:
            try:
                sent = self.sock.send(self.send_buffer)
            except BlockingIOError:
                # Need to catch this otherwise the socket might be unusable
                pass
            else:
                self.send_buffer = self.send_buffer[sent:]
                if sent and not self.send_buffer:
                    self.close()

    def read(self):
        super().read()

        if self.header:
            if self.request is None:
                self.process_request()

    def write(self):
        if self.request:
            content = self.file_action_handler.handle_request(self.request)
            if not self.response_created:
                self.create_response(content)

        self._write()

    def process_request(self):
        length = self.header["content-length"]
        if not len(self.receive_buffer) >= length:
            return
        data = self.receive_buffer[:length]
        self.receive_buffer = self.receive_buffer[length:]

        encoding = self.header["content-encoding"]
        self.request = decode_json(data, encoding)

        self._set_selector_events_mask("w")

    def create_response(self, content):
        response = create_response_content(content, 'utf-8')
        message = create_message(**response)
        self.response_created = True
        self.send_buffer += message


class ClientSideMessage(AbstractMessage):
    def __init__(self, selector, sock, address, request, on_response_callback):
        super().__init__(selector, sock, address)
        self.request = request
        self.request_queued = False
        self.response = None
        self.on_response_callback_func = on_response_callback

    def _write(self):
        if self.send_buffer:
            try:
                sent = self.sock.send(self.send_buffer)
            except BlockingIOError:
                # Need to catch this otherwise the socket might be unusable
                pass
            else:
                self.send_buffer = self.send_buffer[sent:]

    def _process_response_content(self):
        content = self.response
        response = content.get("response")
        self.on_response_callback_func(response)

    def read(self):
        super().read()

        if self.header and self.response is None:
            self.process_response()

    def write(self):
        if not self.request_queued:
            self.queue_request()

        self._write()

        if self.request_queued:
            if not self.send_buffer:
                self._set_selector_events_mask("r")

    def queue_request(self):
        content = self.request["content"]
        content_encoding = self.request["encoding"]
        req = {"content_bytes": encode_json(content, content_encoding), "content_encoding": content_encoding}

        message = create_message(**req)
        self.send_buffer += message
        self.request_queued = True

    def process_response(self):
        content_length = self.header["content-length"]
        if not len(self.receive_buffer) >= content_length:
            return
        data = self.receive_buffer[:content_length]
        self.receive_buffer = self.receive_buffer[content_length:]

        encoding = self.header["content-encoding"]

        self.response = decode_json(data, encoding)
        self._process_response_content()

        self.close()
