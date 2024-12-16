import os
import superset

from hq_superset.tasks import delete_redundant_shared_files
from hq_superset.tests.base_test import SupersetTestCase


class TestDeleteRedundantSharedFiles(SupersetTestCase):
    def test_delete_redundant_shared_files(self):
        file_path = self._create_shared_file()

        self.assertTrue(os.path.exists(file_path))
        delete_redundant_shared_files()
        self.assertFalse(os.path.exists(file_path))

    def _create_shared_file(self):
        directory = superset.config.SHARED_DIR
        path = os.path.join(directory, 'temp.txt')

        # Ensure the directory exists
        if not os.path.exists(directory):
            os.makedirs(directory)

        with open(path, "wb") as f:
            f.write(b"Just a temp file")
        return path
