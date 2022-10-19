import os
import time

from utils import euro_to_utc


def mkdir_rec(client, path, cloud_tree):
    if cloud_tree.get_node_by_path(path):
        return
    else:
        mkdir_rec(client, os.path.dirname(path),cloud_tree)
        client.mkdir(path)
        cloud_tree.add_dir_to_node(path, euro_to_utc(time.time()))


def upload_file(client, local_path, remote_path,time_shift_delta,tree):
    # mkdir_rec(client, os.path.dirname(remote_path))
    client.upload_sync(remote_path=remote_path, local_path=local_path)
    tree.get_node_by_path(local_path).set_last_sync(euro_to_utc(time.time()+time_shift_delta))

def download_file(client, local_path, remote_path ,time_shift_delta,tree):
        remote_path=remote_path.replace("//","/")
        client.download_sync(remote_path=remote_path, local_path=local_path)
        node=tree.get_node_by_path(local_path)
        if node:
            node.set_last_sync(euro_to_utc(time.time()+time_shift_delta))
        else:

            tree.add_file_to_node(local_path, euro_to_utc(time.time()+time_shift_delta), euro_to_utc(os.path.getmtime(local_path)))
            


def delete_file(client, path):
        client.clean(path)