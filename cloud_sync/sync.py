#! /usr/bin/env python3
import math
import pickle
import threading
import time
import json
import fnmatch
import os
from FileNode import RootNode
from notify import notification

from cloud_utils import delete_file, download_file, upload_file, mkdir_rec
from webdav3.client import Client
from tqdm import tqdm
from utils import conf_file_to_tree, create_if_not_exist, dict_to_tree, euro_to_utc, get_last_sysnc_by_path, read_file_lines, read_one_line, write_lines, write_one_line
import argparse
parser = argparse.ArgumentParser(description='Sync files from local to cloud')
parser.add_argument('--dry-run', action='store_true', help='Dry run')
parser.add_argument('--resolve', action='store_true', help='Resolve conflicts')
parser.add_argument('--edit', action='store_true', help='Edit config file')
parser.add_argument('--edit_ignore', action='store_true', help='Edit ignore file')
args = parser.parse_args()
file_root_path=os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
settings = json.load(open(os.path.join(file_root_path,"settings.json")))
cloud_prefix= "/remote.php/webdav"
config_file_path = os.path.join(file_root_path,"file.conf")
ignore_file_path= os.path.join(file_root_path,"ignore.conf")
cloud_root_path = settings["cloud_root_path"]
local_tree_path = os.path.join(file_root_path,"data/local_tree.pickle")
conflict_file_path = os.path.join(file_root_path,"conflict.conf")
time_shift_delta = 2
sync_num=8
if args.resolve:
    os.system(f'vim {conflict_file_path}')
    exit()
elif args.edit:
    os.system(f'vim {config_file_path}')
    exit()
elif args.edit_ignore:
    os.system(f'vim {ignore_file_path}')
    exit()
options = {
    'webdav_hostname': settings["hostname"],
    'webdav_login':    settings["username"],
    'webdav_password': settings["password"]
}

notification("Cloud Sync", "Starting sync", timeout=1000)
Client.default_http_header["list"]= ["Accept: */*","Depth: 100"]
client = Client(options)
# print(json.dumps(client.list(cloud_root_path, get_info=True), indent=4))
# check path to file
create_if_not_exist(config_file_path)
create_if_not_exist(ignore_file_path)
try:
    old_tree=pickle.load(open(local_tree_path,"rb"))
except:
    print("no local tree found")
    old_tree=None
local_tree = conf_file_to_tree(old_tree,config_file_path,ignore_file_path)
if not os.path.exists(os.path.dirname(local_tree_path)):
    os.makedirs(os.path.dirname(local_tree_path))

conflict_lines=read_file_lines(conflict_file_path)[1:] if os.path.exists(conflict_file_path) else []
conflict_keep_local=[]
conflict_keep_cloud=[]
conflict_do_nothing=[]
for line in conflict_lines:
    if line.startswith("l "):
        conflict_keep_local.append(line[2:])
    elif line.startswith("c "):
        conflict_keep_cloud.append(line[2:])
    elif line.startswith("- "):
        conflict_do_nothing.append(line[2:])




# d=client.list(cloud_root_path, get_info=True)
cloud_tree=dict_to_tree(client.list(cloud_root_path, get_info=True),cloud_root_path,cloud_prefix,ignore_file_path)
try:
    # check is path covert by config file
    def path_in_config_file(path):
        with open(config_file_path) as f:
            for line in f:
                p=line.strip().replace("~", os.path.expanduser("~"))
                if path.endswith("/")or p.endswith("/"):
                    if path.startswith(p) or p.startswith(path):
                        return True
                else:
                    if path == p:
                        return True

    # get actions based on local_tree 
    def update_state_of_local_tree(node):
        upload_paths=[]
        download_paths=[]
        delete_local_paths=[]
        conflict_paths=[]
        nothing_paths=[]
        state=None
        cloud_node=cloud_tree.get_node_by_path(node.path)
        
        # is file in cloud available
        if cloud_node:
            time_stemp=cloud_node.mtime
            # modified locally since last sync
            if node.last_sync < node.mtime:
                # modified on cloud since last sync
                if time_stemp > node.last_sync:
                    state="conflict"
                    if not node.is_dir:
                        if node.path in conflict_keep_local:
                            state="upload"
                            upload_paths.append(node.path)
                        elif node.path in conflict_keep_cloud:
                            state="download"
                            download_paths.append(node.path)
                        elif node.path in conflict_do_nothing:
                            state = "nothing"
                            nothing_paths.append(node.path)
                        else:
                            conflict_paths.append(node.path)
                else:
                    state = "upload"
                    if not node.is_dir:
                        upload_paths.append(node.path)
            # modified on cloud since last sync
            elif time_stemp > node.last_sync:
                state = "download"
                if not node.is_dir:
                    download_paths.append(node.path)
            else:
                state = "same"
        else:
            # file does not exist on cloud (modified locally since last sync)
            if node.last_sync < node.mtime:
                state = "upload"
                if not node.is_dir:
                    upload_paths.append(node.path)
            else:
                state = "delete_local"
                if not node.is_dir:
                    delete_local_paths.append(node.path)
        if state != "same" and state != "delete_local" and node.is_dir:
            for child in node.children:
                dir_dict=update_state_of_local_tree(child)
                upload_paths += dir_dict["upload"]
                download_paths += dir_dict["download"]
                delete_local_paths += dir_dict["delete_local"]
                conflict_paths += dir_dict["conflict"]
                nothing_paths += dir_dict["nothing"]
        return {"upload": upload_paths, "download": download_paths, "delete_local": delete_local_paths, "conflict": conflict_paths, "nothing": nothing_paths}

    # get actions based on cloud_tree
    def find_modified_cloud_files(path):
        root=cloud_tree.get_node_by_path(path)
        z=root.children
        download_paths=[]
        delete_cloud_paths=[]

        for c in z:
            cloud_timestamp=c.mtime
            if c.is_dir:
                dir_dict = find_modified_cloud_files(c.path)
                download_paths += dir_dict["download"]
                delete_cloud_paths += dir_dict["delete_cloud"]
            else:
                # file does not exist locally
                if not os.path.exists(c.path) and path_in_config_file(c.path):
                    # file was modified on cloud since last sync
                    if cloud_timestamp > get_last_sysnc_by_path(c.path,old_tree ,include_parent=False):
                        download_paths.append(c.path)
                    else:
                        delete_cloud_paths.append(c.path)
        return {"download": download_paths, "delete_cloud": delete_cloud_paths}
    l_actions=update_state_of_local_tree(local_tree)
    c_actions=find_modified_cloud_files("/")
    actions={"upload": l_actions["upload"], "download": l_actions["download"]+c_actions["download"], "delete_local": l_actions["delete_local"], "delete_cloud":c_actions["delete_cloud"], "conflict": l_actions["conflict"], "nothing": l_actions["nothing"]}
    pattern_list=read_file_lines(ignore_file_path)
    for pattern in pattern_list:
        if pattern == "":
            continue
        for action in actions:
            actions[action]=list(filter(lambda y: not fnmatch.fnmatch(y, pattern), actions[action]))
    if args.dry_run:
        print("dry run")
        print(json.dumps(actions, indent=4))
        exit()
    if len(actions["upload"]) > 0:
        print("creating directories (cloud)...")
        for path in tqdm(actions["upload"]):
            mkdir_rec(client,os.path.dirname(cloud_root_path+path),cloud_tree)
        print("uploading...")
        sync_num=4
        num_iterations=math.ceil(len(actions["upload"])/sync_num)
        for i in tqdm(range(num_iterations)):
            jobs=[]
            for file in actions["upload"][sync_num*i:i*sync_num+sync_num]:
                jobs.append(threading.Thread(target=upload_file, args=(client, file, cloud_root_path+file, time_shift_delta, local_tree)))
                jobs[-1].start()
            for job in jobs:
                job.join()
    if len(actions["delete_cloud"]) > 0:
        print("deleting cloud...")
        num_iterations=math.ceil(len(actions["delete_cloud"])/sync_num)
        for i in tqdm(range(num_iterations)):
            jobs=[]
            for file in actions["delete_cloud"][sync_num*i:i*sync_num+sync_num]:
                jobs.append(threading.Thread(target=delete_file, args=(client, cloud_root_path+file)))
                jobs[-1].start()
            for job in jobs:
                job.join()
    
    if len(actions["download"]) > 0:    
        print("creating directories (local)...")
        for path in tqdm(actions["download"]):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        print("downloading...")
        num_iterations=math.ceil(len(actions["download"])/sync_num)
        for i in tqdm(range(num_iterations)):
            jobs=[]
            for file in actions["download"][sync_num*i:i*sync_num+sync_num]:
                jobs.append(threading.Thread(target=download_file, args=(client, file, cloud_root_path+file,time_shift_delta, local_tree)))
                jobs[-1].start()
            for job in jobs:
                job.join()
    if len(actions["delete_local"]) > 0:
        print("deleting local...")
        for file in tqdm(actions["delete_local"]):
            os.remove(file)
            local_tree.get_node_by_path(file).set_last_sync(euro_to_utc(time.time()+time_shift_delta))
    if len(actions["nothing"]) > 0:
        print("nothing to do...")
        for file in tqdm(actions["nothing"]):
            local_tree.get_node_by_path(file).set_last_sync(euro_to_utc(time.time()+time_shift_delta))

    print("done")
    for file in actions["conflict"]:
        print("conflict: " + file)
    write_lines(conflict_file_path, ["--- [c] for keep cloud version [l] for keep local version [-] for do nothing ---"]+actions["conflict"])
    if len(actions["conflict"]) > 0:
        print("conflicts found, please resolve them in the conflict file: "+conflict_file_path)
        print("or run synco with the --resolve flag")
        notification("Cloud Sync [conflicts found]", "please resolve them in the conflict file: "+conflict_file_path+" or run synco --resolve", 10000)
    else:
        notification("Cloud Sync","Sync finished")
    pickle.dump(local_tree, open(local_tree_path, "wb"))
except Exception as e:
    pickle.dump(local_tree, open(local_tree_path, "wb"))
    raise e
    