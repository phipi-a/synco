import os
import time


class Node:
    def __init__(self, name, parent, is_dir, mtime,last_sync):
        self.name = name
        self.parent = parent
        self.is_dir = is_dir
        self.children = []
        self.path = os.path.join(parent.path, name) if parent else name
        self.set_last_sync(last_sync)
        self.set_mtime(mtime)
    
    def __str__(self):
        return self.tree_string()
    
    def add_child(self, child):
        if self.is_dir:
            self.children.append(child)
            self.update_last_sync(child.last_sync)
            self.update_mtime(child.mtime)
        else:
            raise Exception("Cannot add child to a file node")

    def set_last_sync(self,last_sync):
        self.last_sync=last_sync
        if self.parent:
            self.parent.update_last_sync(self.last_sync)
    def set_mtime(self, mtime):
        self.mtime=mtime
        if self.parent:
            self.parent.update_mtime(mtime)
    def update_mtime(self, child_mtime):
        if self.is_dir:
            max_mtime=child_mtime
            for child in self.children:
                if child.mtime>max_mtime:
                    max_mtime=child.mtime
            self.set_mtime(max_mtime)
        else:
            self.parent.update_mtime(self.mtime)

    def update_last_sync(self, child_last_sync):
        if self.is_dir:
            min_sync_time=child_last_sync
            for child in self.children:
                if child.last_sync<min_sync_time:
                    min_sync_time=child.last_sync
            self.set_last_sync(min_sync_time)
        else:
            self.parent.update_last_sync(self.last_sync)
    def child_already_exists(self, name):
        for child in self.children:
            if child.name == name:
                return child
        return False
    def tree_string(self, level=0):
        s = "  " * level + self.name+f"(mtime: {time.ctime(self.mtime)}) (last_sync: {time.ctime(self.last_sync)})\n"
        for child in self.children:
            s += child.tree_string(level + 1)
        return s

    def get_node_by_path(self, path, include_parent=False):
        if path == self.path:
            return self
        dirs=path.split(os.path.sep)
        dirs=[ele for ele in dirs if ele!=""]
        dir=dirs[0]
        p=self
        for c in p.children:
            if c.name==dir:
                if len(dirs)==1:
                    return c
                return c.get_node_by_path(os.path.sep.join(dirs[1:]),include_parent)
        if include_parent:
            return self
        return None

class RootNode(Node):
    def __init__(self,last_sync):
        super().__init__("/", None, True, 0,last_sync=last_sync)

    def add_file_to_node(self, path, last_sync,mtime):
        dirs=path.split(os.path.sep)[1:]
        p=self
        for d in dirs[:-1]:
            check=p.child_already_exists(d)
            if check:
                p=check
            else:
                c=Node(d, p, True, 0,last_sync=last_sync)
                p.add_child(c)
                p=c
        check=p.child_already_exists(dirs[-1])
        if check:
            print("file already exists")
            return False
        else:
            c=Node(dirs[-1], p, False, mtime,last_sync=last_sync)
            p.add_child(c)

            return True
    
    def add_dir_to_node(self,path,last_sync):
        dirs=[el for el in path.split(os.path.sep)[1:] if el!=""]
        p=self
        for d in dirs:
            check=p.child_already_exists(d)
            if check:
                p=check
            else:
                c=Node(d, p, True, 0,last_sync=last_sync)
                p.add_child(c)
                p=c
        return True
            