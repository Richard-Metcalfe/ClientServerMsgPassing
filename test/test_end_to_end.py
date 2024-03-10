import os
import sys
import shutil
import math
import selectors
import logging
import time
from pathlib import Path
from multiprocessing import Process
from server.server import run_server
from client.client import DirectoryMonitor
from common.fileactions import enumerate_directory, hash_file
from unittest import TestCase

test_dir_path = os.path.dirname(os.path.realpath(__file__))
end2end_client_dir = 'client_dir'
end2end_server_dir = 'server_dir'
data_dir = 'data'

e2e_test_client_directory = Path(test_dir_path, end2end_client_dir)
e2e_test_server_directory = Path(test_dir_path, end2end_server_dir)
test_data_directory = Path(test_dir_path, data_dir)

host = '127.0.0.1'
port = 50001


def test_success(msg='assert OK'):
    """ Helper function to communicate that test have passed"""
    print("End to End test: {}".format(msg))
    return True


def show_proc_info(heading):
    print("== == == == == == == == == == == == == ==")
    print("Process Info for: {}".format(heading))
    print("module name: {}".format(__name__))
    print("parent process: {}".format(os.getppid()))
    print("process id: {}".format(os.getpid()))
    print("== == == == == == == == == == == == == ==")


def server_proc(name):
    """
    Defines the procedure to run in server process
    :param name: the name to display in the process info section
    :return:
    """
    show_proc_info(name)
    log = logging.getLogger('file synchronization server')
    log.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    sel = selectors.DefaultSelector()
    server_address = (host, port)

    log.info('starting server on {} port {}'.format(*server_address))
    run_server(server_address, sel, e2e_test_server_directory, log)


def client_proc(name):
    """
    Defines the client procedure that will be run in the client process
    :param name: the name to display in the proc info section
    :return:
    """
    show_proc_info(name)
    log = logging.getLogger('file synchronization client')
    log.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    monitor = DirectoryMonitor(e2e_test_client_directory, log)
    monitor.run()


def cleanup_directories():
    """
    Removes file from the test directories
    :return:
    """
    file_list = list(filter(Path.is_file, e2e_test_client_directory.glob('**/*'))) + \
                list(filter(Path.is_file, e2e_test_server_directory.glob('**/*')))

    for f in file_list:
        f.unlink()


def setup_test_directories():
    """
    Create a scenario where on starting the client an initial synchronization will take place. 
    This means that some of the files on client will be the same as those on the server and some of them will have
    different contents. The will be some files on the client that do not exist on the server.
    The tested scenario should be:
    
        File with the same name is on both client and server and the same content   : do nothing
        File with the same name is on both client and server and different content  : update the contents
        File is on the client but not on the server                                 : copy file from client to server
        File is on the server but not the client                                    : delete the file from the server
    
    After the initial synch the client and server directories should be identical, then normal copy, update move and 
    delete scenarios can take place.
    """
    e2e_test_client_directory.mkdir(parents=False, exist_ok=True)
    e2e_test_server_directory.mkdir(parents=False, exist_ok=True)

    cleanup_directories()

    test_file_list = list(filter(Path.is_file, test_data_directory.glob('**/*')))
    no_of_files = int(len(test_file_list))

    limit = math.floor(no_of_files / 3)

    to_server = test_file_list[limit:]
    to_client = test_file_list[:-limit]

    for f in to_server:
        shutil.copy(f, e2e_test_server_directory)

    for f in to_client:
        shutil.copy(f, e2e_test_client_directory)


def test_directory_sychronization(test_case: TestCase):
    """
    The the directory synchronization after the client first connects to the server
    :param test_case: used in assertion handling
    :return:
    """
    print("Running Directory Synchronization Test")
    time.sleep(1)

    # The directory should now by synched, let's check this
    client_side_files = enumerate_directory(directory_path=e2e_test_client_directory, block_size=4096)
    server_side_files = enumerate_directory(directory_path=e2e_test_server_directory, block_size=4096)

    test_case.assertListEqual(client_side_files, server_side_files, "Client and Server files are not equal")
    test_case.assertTrue(test_success("Client and Server files are the same"))


def test_create_new_file(test_case: TestCase):
    """
    Tests creating a new file on the client
    :param test_case: used in assertion handling
    :return:
    """
    print("Running Create new file Test")
    new_file_name = "new_file.test"

    filename_on_client = os.path.join(e2e_test_client_directory, new_file_name)
    filename_on_server = os.path.join(e2e_test_server_directory, new_file_name)

    test_case.assertFalse(os.path.exists(filename_on_client))
    test_case.assertFalse(os.path.exists(filename_on_server))

    new_file_path = Path(e2e_test_client_directory, new_file_name)
    new_file_path.touch()

    time.sleep(1)

    test_case.assertTrue(os.path.exists(filename_on_client))
    test_case.assertTrue(os.path.exists(filename_on_server))
    test_case.assertTrue(test_success("The file {} was created successfully".format(new_file_name)))


def test_move_file(test_case: TestCase):
    """
    Tests move a file on the cliet
    :param test_case: used in assertion handling
    :return:
    """
    print("Running Move file Test")
    old_file_name = "new_file.test"

    filename_on_client = os.path.join(e2e_test_client_directory, old_file_name)
    filename_on_server = os.path.join(e2e_test_server_directory, old_file_name)

    test_case.assertTrue(os.path.exists(filename_on_client))
    test_case.assertTrue(os.path.exists(filename_on_server))

    new_file_name = "move_file.test"
    old_file_path = Path(e2e_test_client_directory, old_file_name)
    new_file_path_on_client = Path(e2e_test_client_directory, new_file_name)

    old_file_path.rename(new_file_path_on_client)

    new_file_path_on_server = Path(e2e_test_server_directory, new_file_name)

    time.sleep(3)

    test_case.assertFalse(os.path.exists(filename_on_client))
    test_case.assertFalse(os.path.exists(filename_on_server))
    test_case.assertTrue(new_file_path_on_client.exists())
    test_case.assertTrue(new_file_path_on_server.exists())
    test_case.assertTrue(test_success("The file {} was successfully moved to {}".format(old_file_name, new_file_name)))


def test_update_file(test_case: TestCase):
    """
    Tests updating a file with new content
    :param test_case: used in assertion handling
    :return:
    """
    print("Running Update file Synchronization Test")
    file_name = "file_2_edit.txt"
    file_contents = """TestFileActionHandler.test_write_new_file file contents. cursus faucibus, magna leo accumsan 
    justo, at cursus neque felis sed mauris. Integer accumsan sem et metus vulputate dictum. Integer enim urna, 
    commodo at sodales quis, ultricies non massa. Donec aliquam sem ac tellus eleifend egestas. Vivamus vel quam id 
    diam aliquet pulvinar. Nam pharetra congue odio ut venenatis. Nam accumsan erat elit, ac fermentum tortor 
    sagittis vel.\n\nSed quis dolor elit. Vestibulum et metus volutpat, suscipit risus sit amet, lacinia enim. 
    Quisque egestas placerat lobortis. Nullam quis nisl sit amet risus efficitur feugiat egestas ac neque. 
    Suspendisse quam metus, tincidunt nec feugiat sit amet, venenatis ut turpis. Duis accumsan dui nec sem porttitor 
    bibendum. Nulla massa turpis, posuere at vehicula in, volutpat eget nunc. Sed nisl velit, laoreet eu rhoncus sed, 
    finibus quis turpis. Vestibulum eget viverra orci. Nullam sollicitudin leo eget libero lacinia 
    condimentum.\n\nVivamus bibendum arcu lorem, quis pharetra mi rutrum vitae. Curabitur ultricies nec sapien nec 
    dapibus. Integer quis nulla vel ante cursus faucibus vitae in nunc. Donec aliquam condimentum erat, a eleifend 
    neque bibendum eu. Curabitur commodo pellentesque vestibulum. Aliquam dolor orci, molestie sit amet varius 
    congue, imperdiet sed turpis. Vestibulum euismod diam enim, tempor tempus quam laoreet at. Sed egestas gravida 
    sapien. Cras mattis eros ante, vel porttitor orci pellentesque vel. Morbi mollis, est sagittis elementum semper, 
    augue odio hendrerit lorem, et tempor ante justo vel risus. Pellentesque habitant morbi tristique senectus et 
    netus et malesuada fames ac turpis egestas. Aenean sodales ante mi, ac bibendum odio hendrerit eleifend.\n\nOrci 
    varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Nunc nec magna a ante hendrerit 
    efficitur. Sed non eleifend nulla. Morbi at ultrices diam, eu lobortis libero. Maecenas augue ipsum, 
    ultricies eget mattis a, rhoncus pharetra nunc. Nulla facilisi. Etiam rutrum nunc ac ex imperdiet, non dapibus 
    lorem hendrerit.\n\nDonec at magna non risus commodo lacinia sit amet nec nibh. Curabitur ultrices lorem et 
    convallis gravida. Integer placerat, ligula et egestas consequat, lectus odio tempus mauris, iaculis laoreet 
    libero lectus in tortor. Aliquam ac nibh at ante eleifend aliquam vitae sed massa. Cras sodales ex quis fringilla 
    rutrum. Suspendisse sed lorem at nisi ultrices ullamcorper. Maecenas laoreet sagittis sagittis. Maecenas nec 
    risus sit amet nulla consequat interdum.\n\nVivamus vitae metus eu risus elementum feugiat sit amet nec massa. 
    Morbi nulla justo, luctus et velit quis, tempor tempus lacus. Phasellus porttitor, lacus sollicitudin fermentum 
    luctus, risus ipsum consectetur nunc, eu molestie ipsum velit vel mauris. Mauris congue erat ut ex tempor, 
    sed fermentum sapien imperdiet. Vivamus at mattis urna, non scelerisque quam. Duis non felis purus. Duis sit amet 
    mauris sapien.\n\nVivamus gravida mollis pellentesque. Nam mollis, turpis tempus condimentum vehicula, 
    ex nisi iaculis magna, sed cursus metus quam non orci. Donec pretium porttitor imperdiet. Morbi erat risus, 
    bibendum ac mollis sed, auctor eu dolor. Phasellus in velit in justo egestas sollicitudin. Integer id auctor 
    orci. Vestibulum luctus libero eros. Class aptent taciti sociosqu ad litora torquent per conubia nostra, 
    per inceptos himenaeos.\n\nNunc odio lacus, aliquet eget dolor sit amet, ultricies accumsan libero. Sed pharetra 
    ex ac sem suscipit tempus. Duis tincidunt sapien neque, ac egestas leo facilisis quis. Nam ac eros ipsum. Duis 
    pellentesque tempus finibus. Donec malesuada ligula sit amet metus placerat gravida quis vitae massa. Nulla sed 
    ipsum semper, accumsan felis a, efficitur metus. Pellentesque a tristique lorem, convallis venenatis nisl. 
    Aliquam vulputate rutrum nisi, non gravida turpis cursus vel.\n\nSed eu nisl varius, scelerisque odio nec, 
    tristique felis. Nulla vestibulum elit non vehicula varius. Aliquam semper, metus ut tristique rutrum, 
    magna enim interdum turpis, et tempus ante sapien et ipsum. Praesent placerat risus id metus egestas, 
    ac tristique risus pulvinar. Praesent id ullamcorper """
    file_data = str.encode(file_contents, 'utf-8')
    assert type(file_data).__name__ == "bytes"

    filename_on_client = os.path.join(e2e_test_client_directory, file_name)
    filename_on_server = os.path.join(e2e_test_server_directory, file_name)

    test_case.assertTrue(os.path.exists(filename_on_client))
    test_case.assertTrue(os.path.exists(filename_on_server))

    file_path = Path(e2e_test_client_directory, file_name)

    with file_path.open(mode='wb+') as f:
        f.write(file_data)

    time.sleep(1)

    file_path_on_server = Path(e2e_test_server_directory, file_name)
    src_file_hash = hash_file(file_path, 0x1000)
    dest_file_hash = hash_file(file_path_on_server,0x1000)

    test_case.assertEqual(src_file_hash, dest_file_hash,
                          "The file {} is not the same on the client and server after updating on the client".format(file_name))
    test_case.assertTrue(test_success("The client and server file are equal after updating the client"))


def test_delete_file(test_case):
    """
    Tests deleting a file on the client
    :param test_case: used in assertion handling
    :return:
    """
    print("Running Delete file Synchronization Test")
    file_name = "file_2_delete.txt"

    filename_on_client = os.path.join(e2e_test_client_directory, file_name)
    filename_on_server = os.path.join(e2e_test_server_directory, file_name)

    test_case.assertTrue(os.path.exists(filename_on_client))
    test_case.assertTrue(os.path.exists(filename_on_server))

    file_path = Path(e2e_test_client_directory, file_name)
    file_path.unlink()

    time.sleep(1)


    test_case.assertFalse(os.path.exists(filename_on_client))
    test_case.assertFalse(os.path.exists(filename_on_server))
    test_case.assertTrue(test_success("The file {} has been deleted for the client and server".format(file_name)))


def run_test_scenarios():
    """
    Run the scenario of starting the server and client, after client start the directories should be synchronized
    Subsequently, the scenarios of creating a new file, moving a file updating a file with new content and deleting
    a file are tested - in that order.
    :return:
    """
    show_proc_info('End-to-end tests for client/server')
    tc = TestCase()

    try:
        p_server = Process(target=server_proc, args=('End-to-End test server',))
        p_client = Process(target=client_proc, args=('Move file End-to-End test client',))

        p_server.start()
        time.sleep(1)
        p_client.start()
        time.sleep(1)

        test_directory_sychronization(tc)
        time.sleep(1)
        test_create_new_file(tc)
        time.sleep(1)
        test_move_file(tc)
        time.sleep(1)
        test_update_file(tc)
        time.sleep(1)
        test_delete_file(tc)
        time.sleep(1)
        tc.assertTrue(test_success("End to End Tests Passed"))
    except:
        tc.assertFalse(test_success("End to End Tests Failed"))
    finally:
        p_client.terminate()
        p_client.join()
        p_client.close()

        p_server.terminate()
        p_server.join()
        p_server.close()


if __name__ == '__main__':
    # setup the client and server directories for testing and copy the necessary file into them
    setup_test_directories()
    run_test_scenarios()
    cleanup_directories()

