import fnmatch
from datetime import datetime 
from dateutil import tz
import json
import os
def euro_to_utc(euro_time):
    x=datetime.utcfromtimestamp(euro_time).astimezone(tz.gettz("Europe/Berlin"))
    return x.timestamp()
from FileNode import RootNode
def get_all_absolut_file_paths(directory):
    file_paths = []  # List which will store all of the full filepaths.
    # Read all directory, subdirectories and file lists
    for root, directories, files in os.walk(directory):
        for filename in files:
            # Create the full filepath by using os module.
            filepath = os.path.join(root, filename)
            file_paths.append(filepath)  # Add it to the list.
    return file_paths  # Self-explanatory.


def create_if_not_exist(path):
    if not os.path.exists(path):
        print(f"create new {path} file")
        with open(path, "w") as f:
            if path.endswith(".json"):
                json.dump({}, f)
            else:
                f.write("")

def dict_to_tree(entity_list,cloud_root_path,cloud_prefix,ignore_file_path="ignore.conf"):
    tree=RootNode(0)
    file_list=list(filter(lambda x: not x["isdir"], entity_list))
    for file in file_list:

        time_stemp=datetime.strptime(file['modified'], "%a, %d %b %Y %H:%M:%S %Z").timestamp()
        if is_not_ignored(file["path"],ignore_file_path):
            tree.add_file_to_node(file["path"].replace(cloud_prefix,"",1).replace(cloud_root_path,"/",1) ,last_sync=0,mtime=time_stemp)
    return tree

def conf_file_to_tree(last_tree, path="file.conf",ignore_file_path="ignore.conf"):
    if last_tree==None:
        last_tree_sync=0
    else:
        last_tree_sync = last_tree.last_sync
    tree=RootNode(last_sync=last_tree_sync)
    with open(path, "r") as f:
        for line in f:
            if line.startswith("#"):
                continue
            if line.strip() == "":
                continue
            p=os.path.abspath(line.strip().replace("~", os.path.expanduser("~")))
            if not is_not_ignored(p,ignore_file_path):
                continue
            if os.path.isdir(p):
                for file in get_all_absolut_file_paths(p) :
                    if is_not_ignored(file,ignore_file_path) and os.path.exists(file):
                        mtime = os.path.getmtime(file)
                        tree.add_file_to_node(file, last_sync=get_last_sysnc_by_path(file, last_tree), mtime=euro_to_utc(mtime))
            else:
                if os.path.exists(p):
                    mtime = os.path.getmtime(p)
                    tree.add_file_to_node(p, last_sync=get_last_sysnc_by_path(p, last_tree),mtime=euro_to_utc(mtime))
        return tree

    


def read_file_lines(path):
    with open(path, "r") as f:
        return f.read().splitlines()
def write_one_line(path, line):
    with open(path, "w") as f:
        f.write(line)
def read_one_line(path):
    with open(path, "r") as f:
        return f.read().strip()

def get_last_sysnc_by_path(path,tree, include_parent=False):
    if tree==None:
        return 0
    node=tree.get_node_by_path(path,include_parent=include_parent)
    if node:
        return node.last_sync
    else:
        return 0

def is_not_ignored(string, ignore_file_path="ignore.conf"):
    pattern_list=read_file_lines(ignore_file_path)
    for pattern in pattern_list:
        if fnmatch.fnmatch(string, pattern):
            return False
    return True

def write_lines(path, lines):
    with open(path, "w") as f:
        for line in lines:
            f.write(line+"\n")