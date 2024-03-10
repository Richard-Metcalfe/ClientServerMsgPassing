import sys
import logging
import unittest
import base64
from pathlib import Path
from os import path, remove
from common.fileactions import FileActionHandler, Action, create_block_list
from shutil import copyfile


test_dir_path = path.dirname(path.realpath(__file__))
temp_data_dir = 'temp_data'
data_dir = 'data'


class TestFileActionHandler(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger()
        self.orig_handlers = self.logger.handlers
        self.log_level = self.logger.level
        self.stream_handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(self.stream_handler)

        self.test_directory = Path(test_dir_path, temp_data_dir)
        self.test_data_directory = Path(test_dir_path, data_dir)
        self.test_directory.mkdir(parents=False, exist_ok=True)
        self.logger.info("Using temporary directory {}".format(self.test_directory))

    def tearDown(self):
        self.logger.handlers = self.orig_handlers
        self.logger.level = self.log_level

        for f in Path(self.test_directory).glob('*.test'):
            remove(path.join(self.test_directory, f))

    def test_create_new_file(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger)
        new_file_name = "new_file.test"
        file_contents = "TestFileActionHandler.test_write_new_file file contents"
        file_data = str.encode(file_contents, 'utf-8')
        assert type(file_data).__name__ == "bytes"

        full_filename = path.join(self.test_directory, new_file_name)

        assert not path.exists(full_filename)

        result = file_action_handler.create_new_file(new_file_name, file_data)
        expected_result = dict(action=Action.NEW_FILE_ACTION,
                               msg='Successfully uploaded new_file.test')
        assert result == expected_result
        assert path.exists(full_filename)
        new_file_path = Path(full_filename)

        with new_file_path.open("r") as f:
            actual_content = f.read()
            assert actual_content == file_contents

        new_file_path.unlink()

    def test_create_new_file_when_exists(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger)
        new_file_name = "new_file.test"
        file_contents = "TestFileActionHandler.test_write_new_file file contents"
        file_data = str.encode(file_contents, 'utf-8')
        assert type(file_data).__name__ == "bytes"

        new_file_path = Path(self.test_directory, new_file_name)
        new_file_path.touch()
        assert new_file_path.exists()

        result = file_action_handler.create_new_file(new_file_name, file_data)
        expected_result = dict(action=Action.NEW_FILE_ACTION,
                               msg='Filename new_file.test already exists, cannot save as new')

        assert result == expected_result

        new_file_path.unlink()

    def test_move_file(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger)
        file_to_move = "move_file.test"
        dest_filename = "dest_file.test"

        src_file = Path(self.test_directory, file_to_move)
        src_file.touch()
        assert path.exists(src_file)

        result = file_action_handler.move_file(file_to_move, dest_filename)

        dest_file = Path(self.test_directory, dest_filename)

        expected_result = dict(action=Action.MOVED_FILE_ACTION,
                               msg='Successfully moved file {} to {}'.format(src_file.resolve(), dest_file.resolve()))

        assert result == expected_result

        assert dest_file.exists()
        assert not src_file.exists()

        dest_file.unlink()

    def test_move_file_when_src_not_exist(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger)
        file_to_move = "move_file_when_src_not_exist.test"
        dest_filename = "move_file_when_src_not_exist_dest_file.test"

        src_file = Path(self.test_directory, file_to_move)
        assert not src_file.exists()

        result = file_action_handler.move_file(file_to_move, dest_filename)
        expected_result = dict(action=Action.MOVED_FILE_ACTION,
                               msg="The source file {} doesn't exist and cannot be renamed".format(src_file.resolve()))

        assert result == expected_result

        dest_file = Path(self.test_directory, dest_filename)

        assert not path.exists(dest_file)

    def test_delete_file_when_exists(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger)
        file_to_delete = "delete_file.test"
        file_path = Path(self.test_directory, file_to_delete)
        file_path.touch()

        assert path.exists(file_path)

        result = file_action_handler.delete_file(file_to_delete)
        expected_result = dict(action=Action.DELETED_FILE_ACTION,
                               msg='Successfully deleted delete_file.test')

        assert result == expected_result

    def test_delete_file_when_not_exists(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger)
        file_to_delete = "delete_file.test"
        full_filename = path.join(self.test_directory, file_to_delete)

        assert not path.exists(full_filename)

        result = file_action_handler.delete_file(file_to_delete)

        expected_result = dict(action=Action.DELETED_FILE_ACTION,
                               msg="Filename delete_file.test doesn't exist, cannot delete")
        assert result == expected_result

    def test_emunerate_directory(self):
        file_action_handler = FileActionHandler(self.test_directory, self.logger, 0x1000)

        # Create 3 new files with contents
        file_data = {
            "enumerate_dir_1.test": str.encode("Enumerate directory test file number 1, first test guid:09e4216b-f4b8-4ede-a628-4c77c5a608b2\nHad repulsive dashwoods suspicion sincerity but advantage now him. Remark easily garret nor nay. Civil those mrs enjoy shy fat merry. You greatest jointure saw horrible. He private he on be imagine suppose. Fertile beloved evident through no service elderly is. Blind there if every no so at. Own neglected you preferred way sincerity delivered his attempted. To of message cottage windows do besides against uncivil.", 'utf-8'),
            "enumerate_dir_2.test": str.encode("Enumerate directory test file number 2, second test guid:709f23c8-3b4b-462c-ad69-8950449ade21\nou vexed shy mirth now noise. Talked him people valley add use her depend letter. Allowance too applauded now way something recommend. Mrs age men and trees jokes fancy. Gay pretended engrossed eagerness continued ten. Admitting day him contained unfeeling attention mrs out.", 'utf-8'),
            "enumerate_dir_3.test": str.encode("Enumerate directory test file number 3, third test guid:709f23c8-3b4b-462c-ad69-8950449ade21\nKindness to he horrible reserved ye. Effect twenty indeed beyond for not had county. The use him without greatly can private. Increasing it unpleasant no of contrasted no continuing. Nothing colonel my no removed in weather. It dissimilar in up devonshire inhabiting.", 'utf-8'),
        }

        for name, contents in file_data.items():
            fp = Path(self.test_directory, name)
            fp.touch()
            assert fp.exists()
            with fp.open(mode="wb") as f:
                f.write(contents)

        result = file_action_handler.enumerate_directory()

        expected_result = dict(action=Action.ENUMERATE_REMOTE_DIR_ACTION, block_size=4096, file_info=[
            {
                'filename': 'enumerate_dir_1.test',
                'file_size': 510,
                'sha256': '63c7d191af92e174d38b0969e6fa09efbfe278489ea0142c2727af809f36ea62'
            },
            {
                'filename': 'enumerate_dir_2.test',
                'file_size': 369,
                'sha256': '4a072b62fc3d46f07dcc528eb09c2973e3acd128d8dc7de5829e348a62282779'
            },
            {
                'filename': 'enumerate_dir_3.test',
                'file_size': 360,
                'sha256': '111e2df6c4d69d8a5b5e5aefc9fd475615a86ad382159e29cb0aaa6973120cbb'
            }
        ])

        self.assertDictEqual(result, expected_result)


    def test_create_file_recipe(self):
        # use a small value for block size so that we don't have to have a hugh file
        # in order to get more than one block
        file_action_handler = FileActionHandler(self.test_data_directory, self.logger, 0x1000)

        recipe_file_name = "block_file_data.test"
        recipe = file_action_handler.create_file_recipe(recipe_file_name)

        expected_recipe = {
            'action': Action.FILE_RECIPE_ACTION,
            'recipe_info': {
                'filename': 'block_file_data.test',
                'block_size': 4096,
                'hash_algorithm': 'sha256',
                'recipe': {
                    0: "b25e960c1b798c308578c321e1fbd2465fa2820238277443c51b88920bd6085f",
                    1: "f9b7e476c2883cbfd554f4c31ff63b40ff125a6d148facfd90bbb027eee4f636",
                    2: "9bceca5bac6333abb2f40541dc3d85407892fe54a4d3fdfb1f492963fe95575c"
                }
            }
        }

        self.assertDictEqual(recipe, expected_recipe)

    def test_update_file(self):
        # use a small value for block size so that we don't have to have a hugh file
        # in order to get more than one block
        file_action_handler = FileActionHandler(self.test_directory, self.logger, 0x1000)

        update_file_name = "update_file.test"
        src_file_path = Path(self.test_data_directory, "block_file_data.test")
        test_file_path = Path(self.test_directory, update_file_name)
        test_file_path.touch()

        copyfile(src_file_path.resolve(), test_file_path.resolve())

        update_content = b"""Nullam dictum a nunc nec consequat. Class aptent taciti sociosqu ad litora torquent per conubia nostra, per inceptos himenaeos. Morbi egestas finibus risus. Donec commodo mattis luctus. Integer consequat est at leo feugiat mollis. Maecenas volutpat ante at ante congue, non efficitur nulla tempus. Fusce non varius felis. Praesent fermentum eget tellus at tempor. Mauris ipsum nisl, aliquam et erat sed, laoreet interdum quam. Aliquam nec tincidunt velit. Ut sollicitudin egestas tristique. Sed ultrices ligula luctus tortor lobortis, sit amet pellentesque erat tempus. Donec iaculis purus a elit vestibulum venenatis quis eget dolor. Integer pellentesque tellus eu turpis pulvinar, et consectetur nisi egestas. Nunc nec consectetur dolor. Morbi fringilla, nibh a viverra dapibus, mi massa gravida mauris, egestas malesuada quam eros at enim. Sed pellentesque nibh eget mauris varius, non mattis ipsum scelerisque. Aliquam leo augue, imperdiet et arcu ut, sodales iaculis purus. Proin volutpat vehicula ex nec ultrices. Nunc laoreet dui et mauris venenatis, lobortis posuere velit accumsan. Morbi eget ipsum feugiat, maximus nibh a, commodo arcu. Nam massa ipsum, porta a libero quis, sodales iaculis mi. Cras aliquam, mi nec facilisis tempor, mi eros malesuada nulla, sit amet egestas turpis magna ac augue. Suspendisse dignissim, risus tempus placerat mollis, mi nunc porttitor nisl, in faucibus eros est vitae justo. Quisque scelerisque, tortor rhoncus tristique consequat, augue libero varius mi, vitae ornare sem libero quis urna. Vivamus laoreet ac enim at mattis. In luctus metus eleifend nisi maximus, non hendrerit dui maximus. Duis vel lobortis sapien. Cras ultrices, lacus vel cursus ornare, sapien tortor pharetra justo, eu efficitur justo nunc eget nibh. Aenean auctor ex eget orci auctor, eu rhoncus urna dignissim. Duis finibus consectetur erat ut pretium. Nulla maximus purus lacus. In hac habitasse platea dictumst. Aenean id imperdiet est, eu suscipit felis. Integer et neque sit amet turpis pretium rhoncus. Donec sagittis consectetur fermentum. Etiam sollicitudin mattis eros, ac feugiat diam finibus nec. Ut et ipsum vitae magna consectetur eleifend. Phasellus nec pulvinar magna. Suspendisse a tellus lectus. Nunc pretium sapien diam, non tincidunt mauris accumsan eget. Fusce erat sapien, fermentum ac eleifend ut, lacinia eget lorem. Suspendisse viverra nisl ornare, tempor tortor non, auctor felis. Duis varius vulputate lorem ut lobortis. Phasellus eu sapien mauris. In ultricies molestie euismod. Donec vel aliquam nisi. Vestibulum ac nunc id magna accumsan scelerisque porttitor eu quam. Donec rutrum auctor velit ac facilisis. Maecenas eu semper enim, dignissim scelerisque justo. Nullam nunc est, accumsan nec nisl ac, convallis congue mauris. Sed ac enim sed dui tincidunt vehicula eu a leo. Etiam mi dolor, facilisis vitae feugiat sodales, pulvinar non elit. Nunc ut feugiat justo. Quisque mattis varius ultricies. Suspendisse ultrices metus in justo convallis, ornare convallis orci efficitur. Interdum et malesuada fames ac ante ipsum primis in faucibus. Pellentesque vehicula sodales quam, ac placerat ante auctor ac. Sed semper, lacus at interdum posuere, purus elit porta augue, in condimentum tortor diam et massa. Vivamus facilisis enim vitae justo accumsan finibus. Vivamus rhoncus purus at velit dapibus, ut tincidunt sem congue. Interdum et malesuada fames ac ante ipsum primis in faucibus. Aenean venenatis leo mi, nec dapibus mi tincidunt quis. Nulla ac hendrerit urna. Quisque vestibulum aliquet magna eget venenatis. Curabitur quis finibus dui. Aenean rutrum volutpat nisl at fermentum. Nulla cursus, tellus in fringilla sagittis, sem eros gravida neque, id dignissim est nisl ut augue. Sed risus tellus, luctus ut placerat quis, rhoncus et urna. Mauris mollis eleifend urna sit amet maximus. Aenean pellentesque ligula eu tristique rhoncus. Nam sagittis purus vitae aliquam porta. Pellentesque semper eu purus at porttitor. Aenean et orci non felis maximus efficitur. Maecenas viverra, magna a fermentum egestas, massa est imperdiet dui, in posuere """

        update_dict = {
            'filename':  update_file_name,
            'block_size': 4096,
            'blocks': {
                1: base64.b64encode(update_content).decode('utf8')
            }
        }

        blks_before_update = create_block_list(test_file_path, 0x1000)

        file_action_handler.update_file(update_dict)

        blks_after_update = create_block_list(test_file_path, 0x1000)

        assert len(blks_after_update) == len(blks_before_update)
        for k in blks_after_update.keys():
            assert len(blks_after_update[k]) == len(blks_before_update[k])

        assert blks_after_update[0] == blks_before_update[0]
        assert blks_after_update[1] != blks_before_update[1]
        assert blks_after_update[1] == update_content
        assert blks_after_update[2] == blks_before_update[2]


if __name__ == '__main__':
    unittest.main()
