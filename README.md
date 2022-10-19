# own_cloud
cloud_sync/sync.py is a python script that syncs a local directory with a remote WebDAV server.

## Before you start
1. copy settings_example.py to settings.py edit it to your needs
2. edit file.conf 
3. edit ignore.conf

## Usage
```
usage: sync.py [-h] [--dry-run] [--resolve] [--edit] [--edit_ignore]

Sync files from local to cloud

optional arguments:
  -h, --help     show this help message and exit
  --dry-run      Dry run
  --resolve      Resolve conflicts
  --edit         Edit config file
  --edit_ignore  Edit ignore file
```

## run global
```
sudo ln -s /path/to/cloud_sync/sync.py /usr/local/bin/synco

```