import logging
import os
import shutil


def download_blob():
    pass


def upload_blob():
    pass


def delete_directory(path: str):
    logging.info(f"Start removing directory '{path}' recursively.")
    if os.path.exists(path=path):
        shutil.rmtree(path=path)
    else:
        logging.error(f"Provided directory path '{path}' does not exist.")
        raise ValueError(f"Provided directory path '{path}' does not exist.")

    logging.info(f"Finished removing directory '{path}' recursively.")
