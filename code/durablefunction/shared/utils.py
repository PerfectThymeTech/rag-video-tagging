import logging
import os
import shutil
from urllib.parse import unquote

import azure.durable_functions as df
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient


async def download_blob(
    file_path: str,
    storage_domain_name: str,
    storage_container_name: str,
    storage_blob_name: str,
) -> str:
    """Download file from blob storage async to local storage.

    file_path (str): The file path to which the file will be downloaded.
    storage_domain_name (str): The domain name of the storage account.
    storage_container_name (str): The container name of the storage account.
    storage_blob_name (str): The blob name of the storage account.
    RETURNS (str): The file path to which the file was downloaded.
    """
    logging.info(f"Start downloading file from blob storage to '{file_path}'.")

    # Preprocess storage blob name
    storage_blob_name_cleansed = unquote(storage_blob_name)
    logging.debug(
        f"Storage Details: Domain='{storage_domain_name}', Container='{storage_container_name}', Blob='{storage_blob_name_cleansed}'."
    )

    # Create credentials
    credential = DefaultAzureCredential()

    # Create client
    blob_service_client = BlobServiceClient(
        f"https://{storage_domain_name}", credential=credential
    )
    blob_client = blob_service_client.get_blob_client(
        container=storage_container_name, blob=storage_blob_name_cleansed
    )

    # Download blob
    with open(file=file_path, mode="wb") as sample_blob:
        download_stream = await blob_client.download_blob()
        data = await download_stream.readall()
        sample_blob.write(data)

    logging.info(f"Finished downloading file from blob storage to '{file_path}'.")

    # Return file path of downloaded blob
    return file_path


async def upload_blob(
    file_path: str,
    storage_domain_name: str,
    storage_container_name: str,
    storage_blob_name: str,
) -> str:
    """Upload file to blob storage async from local storage.

    file_path (str): The file path to which the file will be downloaded.
    storage_domain_name (str): The domain name of the storage account.
    storage_container_name (str): The container name of the storage account.
    storage_blob_name (str): The blob name of the storage account.
    RETURNS (str): The url of the uploaded blob.
    """
    logging.info(f"Start uploading file '{file_path}' to blob storage.")

    # Preprocess storage blob name
    storage_blob_name_cleansed = unquote(storage_blob_name)
    logging.debug(
        f"Storage Details: Domain='{storage_domain_name}', Container='{storage_container_name}', Blob='{storage_blob_name_cleansed}'."
    )

    # Create credentials
    credential = DefaultAzureCredential()

    # Create client
    blob_service_client = BlobServiceClient(
        f"https://{storage_domain_name}", credential=credential
    )
    container_client = blob_service_client.get_container_client(
        container=storage_container_name
    )

    # Upload blob
    with open(file=file_path, mode="rb") as data:
        blob_client = await container_client.upload_blob(
            name=storage_blob_name_cleansed, data=data, overwrite=True
        )

    logging.info(f"Finished uploading file '{file_path}' to blob storage.")

    # Return blob url
    return blob_client.url


async def load_blob(
    storage_domain_name: str,
    storage_container_name: str,
    storage_blob_name: str,
    encoding: str = "utf-8",
) -> str:
    """Download file from blob storage async and return data.

    storage_domain_name (str): The domain name of the storage account.
    storage_container_name (str): The container name of the storage account.
    storage_blob_name (str): The blob name of the storage account.
    RETURNS (str): The data within the file.
    """
    logging.info(f"Start downloading file from blob storage.")

    # Preprocess storage blob name
    storage_blob_name_cleansed = unquote(storage_blob_name)
    logging.debug(
        f"Storage Details: Domain='{storage_domain_name}', Container='{storage_container_name}', Blob='{storage_blob_name_cleansed}'."
    )

    # Create credentials
    credential = DefaultAzureCredential()

    # Create client
    blob_service_client = BlobServiceClient(
        f"https://{storage_domain_name}", credential=credential
    )
    blob_client = blob_service_client.get_blob_client(
        container=storage_container_name, blob=storage_blob_name_cleansed
    )

    # Download blob
    download_stream = await blob_client.download_blob()
    data_bytes = await download_stream.readall()
    data = data_bytes.decode(encoding=encoding)

    logging.info(f"Finished downloading file from blob storage to memory.")

    # Return data
    return data


async def upload_string(
    data: str,
    storage_domain_name: str,
    storage_container_name: str,
    storage_blob_name: str,
) -> str:
    """Upload file to blob storage async from local storage.

    file_path (str): The file path to which the file will be downloaded.
    storage_domain_name (str): The domain name of the storage account.
    storage_container_name (str): The container name of the storage account.
    storage_blob_name (str): The blob name of the storage account.
    RETURNS (str): The url of the uploaded blob.
    """
    logging.info(f"Start uploading string to blob storage.")

    # Create credentials
    credential = DefaultAzureCredential()

    # Create client
    blob_service_client = BlobServiceClient(
        f"https://{storage_domain_name}", credential=credential
    )
    container_client = blob_service_client.get_container_client(
        container=storage_container_name
    )

    # Upload blob
    blob_client = await container_client.upload_blob(
        name=storage_blob_name, data=data, overwrite=True
    )

    logging.info(f"Finished uploading string to blob storage.")

    # Return blob url
    return blob_client.url


def delete_directory(directory_path: str) -> bool:
    """Remove local directory recursively.

    directory_path (str): The directory path which will be removed.
    RETURNS (None): Returns no value.
    """
    logging.info(f"Start removing directory '{directory_path}' recursively.")

    # Check existence of directory and remove dir recursively
    if os.path.exists(path=directory_path):
        shutil.rmtree(path=directory_path, ignore_errors=True)
    else:
        logging.error(f"Provided directory path '{directory_path}' does not exist.")
        raise ValueError(f"Provided directory path '{directory_path}' does not exist.")

    logging.info(f"Finished removing directory '{directory_path}' recursively.")


def set_custom_status(
    context: df.DurableOrchestrationContext, completion_percentage: float, status: str
) -> None:
    """Set custom status for orchestration function.

    context (DurableOrchestrationContext): The context of the orchestrator function.
    completion_percentage (float): The percentage of completion of the orchestrator function.
    status (str): The status message of the orchestrator function.
    RETURNS (None): Returns no value.
    """
    logging.info(f"Set custom status.")
    # Create custom status message
    custom_status = {"completion_percentage": completion_percentage, "status": status}

    # Set custom status
    context.set_custom_status(custom_status)
