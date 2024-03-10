import socket
import selectors
import traceback
import base64
from pathlib import Path
from common.message import ClientSideMessage
from common.fileactions import Action, create_hashed_block_list, create_block_list, enumerate_directory


def create_request(action, data):
    return dict(type="text/json", encoding="utf-8", content=dict(action=action, data=data))


class RequestDispatcherException(Exception):
    pass


class RequestDispatcher:
    def __init__(self, directory, host, port):
        self.directory = directory
        self.address = (host, port)

    def _open_connection(self, request, selector):
        print("starting connection to", self.address)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(self.address)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        message = ClientSideMessage(selector, sock, self.address, request, self.on_response_callback)
        selector.register(sock, events, data=message)

    def _update_file_by_recipe(self, recipe_info):
        """
        The method calculates the difference between the the file recipe (file block hashes) of a file on in the client
        directory and the same file in the server directory.
        The recipe consists of a dictionary of file block hashes, the file block size is in the element block_size
        :param recipe_info: The file data and recipe info needed create the file.
        :return:
        """
        filename = recipe_info.get("filename")
        block_size = recipe_info.get("block_size")
        recipe = recipe_info.get("recipe")

        file_path = Path(self.directory, filename)

        if file_path.exists():
            hash_blocks = create_hashed_block_list(file_path, block_size)
            src_blk_set = set(hash_blocks.items())
            dest_block_set = set(recipe.items())
            update_blocks_keys = dict(src_blk_set.difference(dest_block_set)).keys()
            #print("Keys to update {}".format(update_blocks_keys))

            src_blks = create_block_list(file_path, block_size)

            update_blks = {k: base64.b64encode(v).decode('utf8') for k, v in src_blks.items() if k in update_blocks_keys}
            #print("blks to update {}".format(update_blks))

            info = dict(filename=filename, block_size=block_size, blocks=update_blks)
            request = create_request(Action.UPDATED_FILE_ACTION.value, dict(recipe_info=info))
            #print(request)
            self._dispatch(request)

    def _dispatch(self, request):
        select = selectors.DefaultSelector()
        self._open_connection(request, select)

        try:
            while True:
                events = select.select(timeout=1)
                for key, mask in events:
                    message = key.data
                    try:
                        message.process_events(mask)
                    except Exception:
                        print("main: error: exception for, f{}:\n{}".format(message.address, traceback.format_exc()))
                        message.close()

                if not select.get_map():
                    break
        except KeyboardInterrupt:
            print("caught keyboard interrupt, exiting")
        finally:
            select.close()

    def _directory_synch(self, remote_file_info: list, block_size: int):
        """
         Callback for on enumeration request
         Synchronizes the monitored directory with the remote
        """

        local_dir_listing = enumerate_directory(self.directory, block_size)

        same_on_both = [i for i in remote_file_info if i in local_dir_listing]
        diff_on_remote = [i for i in remote_file_info if i not in local_dir_listing]
        diff_on_local = [i for i in local_dir_listing if i not in remote_file_info]

        diff_remote_file_names = [i['filename'] for i in diff_on_remote]
        diff_local_file_name = [i['filename'] for i in diff_on_local]

        on_both_different = list(filter(lambda file: file['filename'] in diff_remote_file_names, diff_on_local))
        on_local_only = list(filter(lambda file: file['filename'] not in diff_remote_file_names, diff_on_local))
        on_remote_only = list(filter(lambda file: file['filename'] not in diff_local_file_name, diff_on_remote))

        #print("files are the same on both client and server and the same : do nothing")
        #for i in same_on_both:
        #    print(i['filename'])

        #print("files on both client and server but different : should update")
        for i in on_both_different:
            self.update_file_request(i['filename'])

        #print("file are on remote only : should delete")
        for i in on_remote_only:
            self.delete_file_request(i['filename'])

        #print("file are on local only : should copy")
        for i in on_local_only:
            self.create_new_file_request(i['filename'])

    def on_response_callback(self, response):
        # print("Response callback {}".format(response))
        action = response.get("action")

        if action == Action.FILE_RECIPE_ACTION:
            recipe_info = response.get("recipe_info")
            self._update_file_by_recipe(recipe_info)
        elif action == Action.ENUMERATE_REMOTE_DIR_ACTION:
            file_info = response.get("file_info")
            block_size = int(response.get("block_size"))
            self._directory_synch(file_info, block_size)

    def create_new_file_request(self, filename):
        file_path = Path(self.directory, filename)

        if not file_path.exists():
            raise RequestDispatcherException("Error the file {} doesn't exist, cannot copy".format(filename))

        try:
            with file_path.open(mode="rb") as f:
                content = f.read()
        except IOError:
            '''
            If the file system (Windows) doesn't release the file lock in time then file open can fail with a 
            permissions error. In which case the file will most likely be empty anyway. If the file isn't empty 
            and the read fails the file will still be created in the remote directory but the content will not be
            copied -- This is a defect.
            '''
            content = b''

        #print("request data {} {} {}".format(Action.NEW_FILE_ACTION.value, filename, content))
        encoded_content = base64.b64encode(content).decode('utf-8')
        request = create_request(Action.NEW_FILE_ACTION.value, dict(filename=filename, filedata=encoded_content))
        print("Uploading file: {}".format(file_path))
        self._dispatch(request)

    def move_file_request(self, src_filename, dest_filename):
        request = create_request(Action.MOVED_FILE_ACTION.value,
                                      dict(source_filename=src_filename, destination_filename=dest_filename))
        #print(request)
        print("Moving {} to {}".format(src_filename, dest_filename))
        self._dispatch(request)

    def delete_file_request(self, filename):
        request = create_request(Action.DELETED_FILE_ACTION.value, dict(filename=filename))
        #print(request)
        print("deleting {}".format(filename))
        self._dispatch(request)

    def update_file_request(self, filename):
        request = create_request(Action.FILE_RECIPE_ACTION.value, dict(filename=filename))
        #print(request)
        self._dispatch(request)

    def enumerate_remote_directory(self):
        request = create_request(Action.ENUMERATE_REMOTE_DIR_ACTION, None)
        #print(request)
        self._dispatch(request)
