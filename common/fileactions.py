import base64
import hashlib
from pathlib import Path
from os import path
from enum import IntEnum

"""
    Hex number denoting the block size for the hashing algorithm to use
    65536 bytes 64Kb 
"""
DEFAULT_BLOCK_SIZE = 0x10000


class Action(IntEnum):
    ENUMERATE_REMOTE_DIR_ACTION = 1
    NEW_FILE_ACTION = 2
    MOVED_FILE_ACTION = 3
    DELETED_FILE_ACTION = 4
    FILE_RECIPE_ACTION = 5
    UPDATED_FILE_ACTION = 6

    def describe(self):
        return self.name, self.value



def hash_file(file_path: Path, block_size: int):
    """
    Creates a file hash for the entire file using sha256 algorithm (more secure than md5 and probability of
    hash collisions is almost zero, although slower.
    :param file_path: the file from which to create the hash
    :return: the hash digest
    """
    sha256_hash = hashlib.sha256()

    with file_path.open('rb') as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256_hash.update(block)

    return sha256_hash.hexdigest()


def create_hashed_block_list(file_path: Path, block_size: int):
    """
    Creates a file hash for each block of a entire file using sha256 algorithm
    and stored them in a dictionary object
    :param file_path: the file from which to create the hash
    :return: a list of number hash digests for each block
    """

    block_counter = 0
    hash_blocks = {}
    with file_path.open('rb') as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256_hash = hashlib.sha256(block).hexdigest()
            hash_blocks[block_counter] = sha256_hash
            block_counter += 1

    return hash_blocks


def create_block_list(file_path: Path, block_size: int):
    """
    Create a list of blocks of size block_size from the provided file.

    :param file_path: the path of the file for which the block should be created
    :param block_size: the block size into which the file should split
    :return: a list of blocks of size block size
    """
    block_counter = 0
    blocks = {}
    with file_path.open('rb') as f:
        for block in iter(lambda: f.read(block_size), b""):
            blocks[block_counter] = block
            block_counter += 1

    return blocks


def create_file_from_blks(file_path: Path, blocks: dict):
    """
    Write the content of a file out from the block data in key order such that
    block are written by key in ascending order blk0, blk1, blk2 ... etc.
    :param file_path:
    :param blocks:
    :return:
    """
    with file_path.open('wb+') as f:
        for key in sorted(blocks.keys()):
            f.write(blocks[key])


def enumerate_directory(directory_path: Path, block_size: int):
    """
    Create a list of files, their sizes and hash values in a directory and returns list of these dictionaries
    :param directory_path: the directory to list
    :param block_size: the block-size for the hashing algorithm
    :return: the list dictionaries of filename, their sizes and hashes in
    """
    dir_listing = list(filter(Path.is_file, directory_path.glob('**/*')))
    file_list = [x for x in dir_listing if x.is_file()]

    ''' Each list item is a dictionary that will contain the filename, size and file-hash for each file'''
    files = []
    for f in file_list:
        files.append(dict(filename=f.name, file_size=f.stat().st_size, sha256=hash_file(f, block_size)))

    return files


class FileActionHandlerException(Exception):
    pass


class FileActionHandler:
    def __init__(self, directory: Path, logger, block_size=DEFAULT_BLOCK_SIZE):
        if not directory.exists():
            logger.debug("The directory {} doesn't exist, creating it".format(directory))
            directory.mkdir(parents=True, exist_ok=True)

        self.directory = directory
        self.logger = logger
        self.block_size = block_size

    def create_new_file(self, filename, file_data):
        """
        Creates a new file on in the directory with the provided name and contents
        :param filename: the name of the file to create
        :param file_data: the content of the file
        :return: True is successful, otherwise False
        """
        test_file_name = path.join(self.directory, filename)

        if path.exists(test_file_name):
            self.logger.error("Filename {} already exists, cannot save as new".format(filename))
            return dict(action=Action.NEW_FILE_ACTION, msg="Filename {} already exists, cannot save as new".format(filename))

        file_path = Path(self.directory, filename)
        self.logger.debug("creating file {}".format(file_path))
        with file_path.open(mode="wb") as new_f:
            new_f.write(file_data)

        return dict(action=Action.NEW_FILE_ACTION, msg="Successfully uploaded {}".format(filename))

    def move_file(self, source_filename, destination_filename):
        src_file = Path(self.directory, source_filename)
        dest_file = Path(self.directory, destination_filename)

        if not src_file.exists():
            self.logger.error("The source file {} doesn't exist and cannot be renamed".format(src_file))
            return dict(action=Action.MOVED_FILE_ACTION, msg="The source file {} doesn't exist and cannot be renamed".format(src_file))

        if dest_file.exists():
            self.logger.error("The destination file {} already exists {} cannot be renamed to it".format(dest_file, src_file))
            return False

        src_file.rename(dest_file)

        return dict(action=Action.MOVED_FILE_ACTION, msg="Successfully moved file {} to {}".format(src_file, dest_file))

    def delete_file(self, filename):
        file_path = Path(self.directory, filename)

        if file_path.exists():
            file_path.unlink()
            return dict(action=Action.DELETED_FILE_ACTION, msg="Successfully deleted {}".format(filename))
        else:
            self.logger.error("Filename {} doesn't exist cannot delete".format(filename))
            return dict(action=Action.DELETED_FILE_ACTION, msg="Filename {} doesn't exist, cannot delete".format(filename))

    def enumerate_directory(self):
        """
            Creates dictionary filenames and the corresponding size and file-hash
            The files are residing in self.directory
            This functionis not recursive and will only read the files in the directory
            specified

            TODO: Make this recurse into subdirectories of self.directory
        :return:
        """
        files = enumerate_directory(self.directory, self.block_size)

        return dict(action=Action.ENUMERATE_REMOTE_DIR_ACTION, block_size=self.block_size, file_info=files)

    def create_file_recipe(self, filename):
        """
        Creates a recipe for rebuilding a file from parts of BLOCKSIZE.
        Returns in a JSON object containing metadata describing each block the file
        The number of part and the sha256 for each part is return in a JSON object.
        This doesn't contain any data simple the means to compare each file.
        :param filename: the filename for which to return the file recipe
        :return: JSON object contain the file metadata
        """
        file_path = Path(self.directory, filename)

        if not file_path.exists():
            raise FileActionHandlerException("Error the file doesn't exist, cannot create recipe")

        response = dict(action=Action.FILE_RECIPE_ACTION,
                        recipe_info=dict(filename=filename, block_size=self.block_size,
                                         hash_algorithm=hashlib.sha256().name,
                                         recipe=create_hashed_block_list(file_path, self.block_size)))

        return response

    def update_file(self, recipe: dict):
        """
        Updates an existing file in a block-wise fashion.
        for each of the block in the provide dictionary the file will be updated with the provided block
        block size is provided.
        :param recipe: how to update the file
        :return: True if successful, otherwise false
        """
        filename = recipe.get("filename")
        block_size = recipe.get("block_size")
        blocks = recipe.get("blocks")
        blocks_to_update = {int(k): base64.b64decode(v) for k, v in blocks.items()}

        file_path = Path(self.directory, filename)

        if not file_path.exists():
            self.logger.error("The source file {} doesn't exist and cannot be updated".format(filename))
            return dict(action=Action.UPDATED_FILE_ACTION, msg="The source file {} doesn't exist and cannot be updated".format(filename))

        file_blocks = create_block_list(file_path, block_size)

        """Merge the two file dictionaries. The right most dict takes presidence, if present."""
        updated_blocks = {**file_blocks, **blocks_to_update}

        create_file_from_blks(file_path, updated_blocks)

        return dict(action=Action.UPDATED_FILE_ACTION, msg="Successfully updated {}".format(filename))

    def handle_request(self, request):
        #self.logger.debug("Received request: {}".format(request))
        action = int(request.get("action"))
        #self.logger.debug("action {}".format(action))

        result = None

        if Action.ENUMERATE_REMOTE_DIR_ACTION == action:
            result = self.enumerate_directory()
            self.logger.info("Successfully enumerated dir")
        elif Action.NEW_FILE_ACTION == action:
            data = request.get("data")
            filename = data.get("filename")
            filedata = data.get("filedata")

            file_contents = b''
            if not filedata is None:
                file_contents = base64.b64decode(filedata)

            result = self.create_new_file(filename, file_contents)
        elif action == Action.MOVED_FILE_ACTION:
            data = request.get("data")
            src_file = data.get("source_filename")
            dest_file = data.get("destination_filename")
            result = self.move_file(src_file, dest_file)
        elif action == Action.DELETED_FILE_ACTION:
            data = request.get("data")
            filename = data.get("filename")
            result = self.delete_file(filename)
        elif action == Action.FILE_RECIPE_ACTION:
            data = request.get("data")
            filename = data.get("filename")
            result = self.create_file_recipe(filename)
            self.logger.info("Successfully created file recipe for {}".format(filename))
        elif action == Action.UPDATED_FILE_ACTION:
            data = request.get("data")
            recipe = data.get("recipe_info")
            result = self.update_file(recipe)
        else:
            self.logger.info("Unknown file action {}".format(action))
            result = dict(action, "Unknown file action {}".format(action))

        return dict(response=result)
