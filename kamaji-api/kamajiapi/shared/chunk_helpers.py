# -*- coding: utf-8 -*-
import requests


def chunked_get(url, chunk_size=4096):
    """
    Chunk a large response from a GET of a url.
    :param url: The url to get.
    :param chunk_size: The size of the chunks to read.
    :return: yielded chunks.
    """
    remote_data = requests.get(url, stream=True)
    for chunk in remote_data.iter_content(chunk_size=chunk_size):
        yield chunk


def chunked_read(file_object, chunk_size=4096):
    """
    Read a file in chunks.
    :param file_object: The file object to read.
    :param chunk_size: The size of the chunks to read.
    :return:
    """
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data
